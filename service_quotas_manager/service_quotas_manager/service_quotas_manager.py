import json
import logging
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError

from service_quotas_manager.entities import ServiceQuota, ServiceQuotaIncreaseRule
from service_quotas_manager.service_quotas_collector import ServiceQuotasCollector
from service_quotas_manager.service_quotas_increaser import ServiceQuotasIncreaser
from service_quotas_manager.util import convert_dict

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _load_config_from_s3(s3_client, bucket: str, key: str, account_id: str) -> Dict:
    s3_obj = s3_client.get_object(Bucket=bucket, Key=key)
    config = json.loads(s3_obj["Body"].read().decode("utf-8"))
    return config.get(account_id, {})


def _assume_role(role_arn: str) -> Dict:
    sts_client = _get_local_client("sts")
    assumed_role = sts_client.assume_role(
        RoleArn=role_arn, RoleSessionName="ServiceQuotaManagerRole", DurationSeconds=900
    )

    return {
        "aws_access_key_id": assumed_role["Credentials"]["AccessKeyId"],
        "aws_secret_access_key": assumed_role["Credentials"]["SecretAccessKey"],
        "aws_session_token": assumed_role["Credentials"]["SessionToken"],
    }


def _get_account_id_from_alarm(alarm_details: Dict) -> Optional[str]:
    if not alarm_details:
        return
    dimensions = alarm_details["configuration"]["metrics"][0]["metricStat"]["metric"][
        "dimensions"
    ]
    return dimensions.get("AccountId")


def _get_increase_rule_from_config(
    config: Dict, service_quota: ServiceQuota
) -> Optional[ServiceQuotaIncreaseRule]:
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


def _get_remote_client(client_name: str, credentials: Dict):
    return boto3.client(client_name, **credentials)


def _get_local_client(client_name: str):
    return boto3.client(client_name)


def handler(event, _context):
    account_id = event.get("account_id", _get_account_id_from_alarm(event.get("alarm")))
    if not account_id:
        logger.error("No account ID could be found in event. Exiting...")
        return

    if "action" not in event:
        logger.error("No action specified in event. Exiting...")
        return

    config = _load_config_from_s3(
        _get_local_client("s3"), event["config_bucket"], event["config_key"], account_id
    )
    if not config:
        logger.error(f"No configuration found for account {account_id}. Exiting...")
        return

    assume_role_arn = f"arn:aws:iam::{account_id}:role/{config['role_name']}"
    remote_creds = _assume_role(assume_role_arn)

    if event["action"] == "CollectServiceQuotas":
        sqc = ServiceQuotasCollector(
            _get_remote_client("service-quotas", remote_creds),
            _get_remote_client("cloudwatch", remote_creds),
            _get_remote_client("config", remote_creds),
            _get_local_client("cloudwatch"),
            account_id,
        )
        sqc.collect(list(set(config["selected_services"])))
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
