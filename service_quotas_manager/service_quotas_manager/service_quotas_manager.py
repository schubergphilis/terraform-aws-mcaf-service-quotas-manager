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

cloudwatch_client = boto3.client("cloudwatch")
s3_client = boto3.client("s3")
sts_client = boto3.client("sts")


def _load_config_from_s3(bucket: str, key: str) -> Dict:
    s3_obj = s3_client.get_object(Bucket=bucket, Key=key)
    return json.loads(s3_obj["Body"].read().decode("utf-8"))


def _assume_role(role_arn: str) -> Dict:
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


def handler(event, _context):
    account_id = event.get("account_id", _get_account_id_from_alarm(event.get("alarm")))
    if not account_id:
        logger.error("No account ID could be found in event. Exiting...")
        return

    config = _load_config_from_s3(event["config_bucket"], event["config_key"]).get(
        account_id, {}
    )
    if not config:
        logger.error(f"No configuration found for account {account_id}. Exiting...")
        return

    assume_role_arn = f"arn:aws:iam::{account_id}:role/{config['role_name']}"
    client_credentials = _assume_role(assume_role_arn)

    if "action" not in event:
        event["action"] = "CollectServiceQuotas"

    if event["action"] == "CollectServiceQuotas":
        remote_service_quota_client = boto3.client(
            "service-quotas", **client_credentials
        )
        remote_cloudwatch_client = boto3.client("cloudwatch", **client_credentials)
        remote_config_client = boto3.client("config", **client_credentials)

        sqc = ServiceQuotasCollector(
            remote_service_quota_client,
            remote_cloudwatch_client,
            remote_config_client,
            cloudwatch_client,
            account_id,
        )
        sqc.collect(list(set(config["selected_services"])))
        sqc.manage_alarms(config.get("alerting_config"))

    elif event["action"] == "IncreaseServiceQuota":
        remote_service_quota_client = boto3.client(
            "service-quotas", **client_credentials
        )
        remote_support_client = boto3.client("support", **client_credentials)

        service_quota: ServiceQuota = _get_service_quota_from_alarm(
            event["alarm"], remote_service_quota_client
        )

        increase_rule = None
        increase_rule_def = (
            config.get("quota_increase_config", {})
            .get(service_quota.service_name, {})
            .get(service_quota.quota_name)
        )
        if increase_rule_def:
            increase_rule = ServiceQuotaIncreaseRule(**increase_rule_def)

        sqi = ServiceQuotasIncreaser(remote_support_client, remote_service_quota_client)
        sqi.request_service_quota_increase(service_quota, increase_rule)
