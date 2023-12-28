import json
from typing import Dict, Optional

import boto3
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from service_quotas_manager.entities import ServiceQuota, ServiceQuotaIncreaseRule
from service_quotas_manager.service_quotas_collector import ServiceQuotasCollector
from service_quotas_manager.service_quotas_increaser import ServiceQuotasIncreaser
from service_quotas_manager.util import convert_dict, get_logger

logger = get_logger()


def _load_config_from_s3(s3_client, bucket: str, key: str, account_id: str) -> Dict:
    """Read account specific configuration from S3 object."""
    s3_obj = s3_client.get_object(Bucket=bucket, Key=key)
    config = json.loads(s3_obj["Body"].read().decode("utf-8"))

    configuration_by_account = {conf["account_id"]: conf for conf in config}

    return configuration_by_account.get(account_id, {})


def _assume_role(role_arn: str) -> Dict:
    """Assume a role in a different account and return temporary credentials."""
    sts_client = _get_local_client("sts")

    try:
        assumed_role = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName="ServiceQuotaManagerRole",
            DurationSeconds=900,
        )
    except ClientError as ex:
        logger.error(
            f"Could not assume role {role_arn}. Error: {ex.response['Error']['Code']}. Exiting..."
        )
        return {}

    return {
        "aws_access_key_id": assumed_role["Credentials"]["AccessKeyId"],
        "aws_secret_access_key": assumed_role["Credentials"]["SecretAccessKey"],
        "aws_session_token": assumed_role["Credentials"]["SessionToken"],
    }


def _get_account_id_from_alarm(alarm_details: Dict) -> Optional[str]:
    """Retrieve the account id from payload if the Lambda is triggered by an alarm."""

    if not alarm_details:
        return
    dimensions = alarm_details["configuration"]["metrics"][0]["metricStat"]["metric"][
        "dimensions"
    ]
    return dimensions.get("AccountId")


def _get_increase_rule_from_config(
    config: Dict, service_quota: ServiceQuota
) -> Optional[ServiceQuotaIncreaseRule]:
    """Retrieve an increase rule from config if the Lambda is triggered by an alarm."""

    increase_rule_def = (
        config.get("quota_increase_config", {})
        .get(service_quota.service_name, {})
        .get(service_quota.quota_name)
    )
    if increase_rule_def:
        increase_rule_def["service_quota"] = service_quota
        return ServiceQuotaIncreaseRule(**increase_rule_def)
    else:
        return None


def _get_service_quota_from_alarm(
    alarm_details: Dict, remote_service_quota_client
) -> ServiceQuota:
    """Find a service quota based on payload if the Lambda is triggered by an alarm."""

    dimensions = alarm_details["configuration"]["metrics"][0]["metricStat"]["metric"][
        "dimensions"
    ]
    try:
        return ServiceQuota(
            **convert_dict(
                remote_service_quota_client.get_service_quota(
                    ServiceCode=dimensions["ServiceCode"],
                    QuotaCode=dimensions["QuotaCode"],
                )["Quota"]
            )
        )
    except ClientError:
        return ServiceQuota(
            **convert_dict(
                remote_service_quota_client.get_aws_default_service_quota(
                    ServiceCode=dimensions["ServiceCode"],
                    QuotaCode=dimensions["QuotaCode"],
                )["Quota"]
            )
        )


def _get_remote_client(
    client_name: str, credentials: Dict, region: Optional[str] = None
):
    """Create a boto3 client based on credentials from an assumed role."""

    if region:
        credentials["region_name"] = region
    return boto3.client(client_name, **credentials)


def _get_local_client(client_name: str):
    """Create a boto3 client based on Lambda invocation credentials."""

    return boto3.client(client_name)


@logger.inject_lambda_context
def handler(event: Dict, _context: LambdaContext):
    """
    Lambda Entrypoint

    This lambda can be triggered in two ways:

    1. Schedule based. The action is to collect metrics from remote accounts, store
    them in local CloudWatch Metrics and to manage alarms on these metrics.

    2. By an alarm if one of the alarms from method 1 exceeds set thresholds.
    The action in that case is to see if there's a rule to apply for a service
    quote increase request.
    """

    account_id = event.get("account_id", _get_account_id_from_alarm(event.get("alarm")))
    if not account_id:
        logger.error("No account ID could be found in event. Exiting...")
        return

    logger.append_keys(account_id=account_id)

    if "action" not in event:
        logger.error("No action specified in event. Exiting...")
        return

    config = _load_config_from_s3(
        _get_local_client("s3"), event["config_bucket"], event["config_key"], account_id
    )
    if not config:
        logger.error("No configuration found for account. Exiting...")
        return

    assume_role_arn = f"arn:aws:iam::{account_id}:role/{config['role_name']}"
    remote_creds = _assume_role(assume_role_arn)

    if not remote_creds:
        return

    if event["action"] == "CollectServiceQuotas":
        sqc = ServiceQuotasCollector(
            _get_remote_client("service-quotas", remote_creds),
            _get_remote_client("cloudwatch", remote_creds),
            _get_remote_client("config", remote_creds),
            _get_remote_client("ce", remote_creds, "us-east-1"),
            _get_local_client("cloudwatch"),
            account_id,
        )
        sqc.collect(list(set(config.get("selected_services", []))))
        sqc.manage_alarms(config.get("alerting_config"))

    elif event["action"] == "IncreaseServiceQuota":
        remote_service_quota_client = _get_remote_client("service-quotas", remote_creds)

        service_quota: ServiceQuota = _get_service_quota_from_alarm(
            event["alarm"], remote_service_quota_client
        )

        sqi = ServiceQuotasIncreaser(
            _get_remote_client("support", remote_creds), remote_service_quota_client
        )
        sqi.request_service_quota_increase(
            _get_increase_rule_from_config(config, service_quota)
        )
    else:
        logger.error(
            f"Action {event['action']} not recognized as valid action. Exiting..."
        )
        return
