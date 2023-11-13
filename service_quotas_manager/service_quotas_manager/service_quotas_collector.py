import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List
from unittest import TestCase

from service_quotas_manager.entities import ServiceQuota
from service_quotas_manager.util import convert_dict

logger = logging.getLogger()
logger.setLevel(logging.INFO)

LOCAL_METRIC_NAMESPACE = "ServiceQuotaManager"
LOCAL_METRIC_NAME = "ServiceQuotaUsage"


class ServiceQuotasCollector:
    def __init__(
        self,
        remote_service_quota_client,
        remote_cloudwatch_client,
        remote_config_client,
        local_cloudwatch_client,
        account_id: str,
    ):
        self.remote_service_quota_client = remote_service_quota_client
        self.remote_cloudwatch_client = remote_cloudwatch_client
        self.remote_config_client = remote_config_client
        self.local_cloudwatch_client = local_cloudwatch_client
        self.account_id = account_id

        self._service_quotas: List[ServiceQuota] = []
        self._custom_collection_queries = json.load(
            open("service_quotas_manager/custom_collection_queries.json")
        )

    def collect(self, selected_services: List[str]) -> Dict:
        filtered_services = self._find_service_codes(selected_services)
        service_quotas_with_metrics = []

        for service in filtered_services:
            service_quotas = self._find_service_quotas(service["ServiceCode"])

            for service_quota in service_quotas:
                if service_quota.usage_metric:
                    service_quotas_with_metrics.append(service_quota)
                elif service_quota.quota_code in self._custom_collection_queries.get(
                    service_quota.service_code, {}
                ):
                    service_quota.collection_query = self._custom_collection_queries[
                        service_quota.service_code
                    ][service_quota.quota_code]
                    service_quotas_with_metrics.append(service_quota)

        service_quota_groups = [
            service_quotas_with_metrics[i : i + 500]
            for i in range(0, len(service_quotas_with_metrics), 500)
        ]
        for service_quota_group in service_quota_groups:
            self._collect_cloudwatch_remote_metrics(
                [sq for sq in service_quota_group if sq.usage_metric]
            )
            self._collect_config_remote_metrics(
                [
                    sq
                    for sq in service_quota_group
                    if sq.collection_query.get("type", "") == "config"
                ]
            )
            self._put_local_metrics(service_quota_group)
            self._service_quotas += service_quota_group

    def manage_alarms(self, alerting_config: Dict) -> None:
        if not self._service_quotas:
            return

        if not alerting_config:
            return

        alarms_paginator = self.local_cloudwatch_client.get_paginator("describe_alarms")
        alarms_pages = alarms_paginator.paginate(
            AlarmNamePrefix="Service Quota:", AlarmTypes=["MetricAlarm"]
        )

        alarms_by_service_quota = {}
        for alarm_page in alarms_pages:
            for alarm in alarm_page["MetricAlarms"]:
                nd = {
                    dimension["Name"]: dimension["Value"]
                    for dimension in alarm["Dimensions"]
                }
                alarms_by_service_quota[
                    f"{nd['ServiceCode']}#{nd['QuotaCode']}#{nd['AccountId']}"
                ] = alarm

        self._upsert_alarms(alerting_config, alarms_by_service_quota)
        self._cleanup_alarms(alarms_by_service_quota)

    def _cleanup_alarms(self, alarms_by_service_quota: Dict):
        all_desired_alarm_codes = [
            f"{service_quota.service_code}#{service_quota.quota_code}#{self.account_id}"
            for service_quota in self._service_quotas
            if len(service_quota.metric_values) > 0
        ]
        alarms_to_delete = [
            alarm["AlarmName"]
            for key, alarm in alarms_by_service_quota.items()
            if key not in all_desired_alarm_codes
        ]
        alarm_removal_groups = [
            alarms_to_delete[i : i + 100] for i in range(0, len(alarms_to_delete), 100)
        ]
        for alarm_removal_group in alarm_removal_groups:
            logger.info(f"Deleting alarms {alarm_removal_group}")
            self.local_cloudwatch_client.delete_alarms(AlarmNames=alarm_removal_group)

    def _upsert_alarms(self, alerting_config: Dict, alarms_by_service_quota: Dict):
        for service_quota in self._service_quotas:
            if not service_quota.metric_values:
                logger.info(
                    f"Skipping alarm for {service_quota.service_name} / {service_quota.quota_name} due to missing metrics."
                )
                continue

            service_quota_key = f"{service_quota.service_code}#{service_quota.quota_code}#{self.account_id}"
            threshold_perc = (
                alerting_config.get("rules", {})
                .get(service_quota.service_name, {})
                .get(service_quota.quota_name, {})
                .get("threshold_perc")
            )
            if not threshold_perc:
                threshold_perc = alerting_config["default_threshold_perc"]

            threshold = round((service_quota.value * threshold_perc) / 100, 1)
            description = f"The service quota for {service_quota.quota_name} for service {service_quota.service_name} in account {self.account_id} is nearing its configured quota ({service_quota.value})."

            if service_quota.adjustable:
                description += " This quota is adjustable."

            desired_alarm_definition = {
                "AlarmName": f"Service Quota: {service_quota.quota_name} for service {service_quota.service_name} in account {self.account_id}",
                "AlarmDescription": description,
                "MetricName": LOCAL_METRIC_NAME,
                "Namespace": LOCAL_METRIC_NAMESPACE,
                "Statistic": service_quota.usage_metric.get(
                    "MetricStatisticRecommendation", "Maximum"
                ),
                "Dimensions": [
                    {"Name": "ServiceCode", "Value": service_quota.service_code},
                    {"Name": "QuotaCode", "Value": service_quota.quota_code},
                    {"Name": "QuotaName", "Value": service_quota.quota_name},
                    {"Name": "AccountId", "Value": self.account_id},
                ],
                "Period": 3600,
                "EvaluationPeriods": 3,
                "DatapointsToAlarm": 2,
                "Threshold": threshold,
                "ComparisonOperator": "GreaterThanThreshold",
            }

            if "notification_topic_arn" in alerting_config:
                desired_alarm_definition["AlarmActions"] = [
                    alerting_config["notification_topic_arn"]
                ]

            actual_alarm_definition = {}
            if service_quota_key in alarms_by_service_quota:
                actual_alarm_definition = {
                    key: alarms_by_service_quota[service_quota_key][key]
                    for key in desired_alarm_definition.keys()
                }
                if alerting_config["notification_topic_arn"]:
                    actual_alarm_definition["AlarmActions"] = [
                        alerting_config["notification_topic_arn"]
                    ]

            try:
                TestCase().assertDictEqual(
                    desired_alarm_definition, actual_alarm_definition
                )
                alarm_changed = False
            except AssertionError:
                alarm_changed = True

            if service_quota_key not in alarms_by_service_quota or alarm_changed:
                logger.info(f"Upserting alarm {desired_alarm_definition['AlarmName']}")
                self.local_cloudwatch_client.put_metric_alarm(
                    **desired_alarm_definition
                )
                time.sleep(0.35)  # PutMetricAlarm is rate limited at 3TPS.

    def _find_service_codes(self, selected_services: List[str]) -> List[Dict]:
        services_paginator = self.remote_service_quota_client.get_paginator(
            "list_services"
        )
        services_pages = services_paginator.paginate()

        filtered_services = []
        matched_services = []
        for service_page in services_pages:
            for service in service_page["Services"]:
                if service["ServiceName"] in selected_services:
                    filtered_services.append(service)
                    matched_services.append(service["ServiceName"])

        unmatched_services = [
            sn for sn in selected_services if sn not in matched_services
        ]
        if unmatched_services:
            logger.warning(
                f"The following services do not seem to exist: {', '.join(unmatched_services)}. Maybe you used the service code instead of the service name?"
            )

        return filtered_services

    def _find_service_quotas(self, service_code: str) -> List[ServiceQuota]:
        """
        Merge default quotas with applied quotas. Applied quotas
        overrule default quotas.
        """
        default_service_quota_paginator = (
            self.remote_service_quota_client.get_paginator(
                "list_aws_default_service_quotas"
            )
        )
        default_service_quota_pages = default_service_quota_paginator.paginate(
            ServiceCode=service_code
        )

        applied_service_quota_paginator = (
            self.remote_service_quota_client.get_paginator("list_service_quotas")
        )
        applied_service_quota_pages = applied_service_quota_paginator.paginate(
            ServiceCode=service_code
        )

        applied_service_quotas_by_id = {}
        for applied_service_quota_page in applied_service_quota_pages:
            for applied_service_quota in applied_service_quota_page["Quotas"]:
                applied_service_quotas_by_id[
                    applied_service_quota["QuotaCode"]
                ] = applied_service_quota

        service_quotas = []
        id_cntr = 0
        for service_quota_page in default_service_quota_pages:
            for service_quota in service_quota_page["Quotas"]:
                if service_quota["QuotaCode"] in applied_service_quotas_by_id:
                    service_quota = applied_service_quotas_by_id[
                        service_quota["QuotaCode"]
                    ]

                service_quota = ServiceQuota(**convert_dict(service_quota))

                service_quota.internal_id = f"{id_cntr:05}"
                id_cntr += 1
                service_quotas.append(service_quota)
        return service_quotas

    def _collect_config_remote_metrics(
        self, service_quota_group: List[ServiceQuota]
    ) -> None:
        for service_quota in service_quota_group:
            collection_params = service_quota.collection_query["parameters"]
            expression_result = self.remote_config_client.select_resource_config(
                Expression=collection_params["expression"], Limit=1
            )

            if len(expression_result.get("Results", [])) == 0:
                service_quota.metric_values = []
                continue

            columns = [
                field["Name"]
                for field in expression_result["QueryInfo"]["SelectFields"]
            ]
            selected_column = columns[collection_params["columnIndex"]]

            values = [
                round(
                    float(json.loads(expression_result["Results"][0])[selected_column]),
                    1,
                )
            ]
            logger.info(
                f"Collected metric values from AWS Config for quota {service_quota.service_name} / {service_quota.service_name}: {values}"
            )
            service_quota.metric_values = values

    def _collect_cloudwatch_remote_metrics(
        self, service_quota_group: List[ServiceQuota]
    ) -> None:
        current_time = datetime.now()
        metric_data = self.remote_cloudwatch_client.get_metric_data(
            MetricDataQueries=[
                {
                    "Id": service_quota.internal_id,
                    "MetricStat": {
                        "Metric": {
                            "Namespace": service_quota.usage_metric["MetricNamespace"],
                            "MetricName": service_quota.usage_metric["MetricName"],
                            "Dimensions": [
                                {"Name": key, "Value": value}
                                for key, value in service_quota.usage_metric[
                                    "MetricDimensions"
                                ].items()
                            ],
                        },
                        "Period": 300,
                        "Stat": service_quota.usage_metric[
                            "MetricStatisticRecommendation"
                        ],
                    },
                }
                for service_quota in service_quota_group
            ],
            StartTime=(
                current_time
                - timedelta(minutes=60)
                - (current_time - datetime.min) % timedelta(minutes=60)
            ),
            EndTime=(
                current_time - (current_time - datetime.min) % timedelta(minutes=60)
            ),
            ScanBy="TimestampDescending",
        )

        metric_data_by_id = {
            metric_data_result["Id"]: metric_data_result["Values"]
            for metric_data_result in metric_data["MetricDataResults"]
        }

        for service_quota in service_quota_group:
            values = metric_data_by_id[service_quota.internal_id]
            logger.info(
                f"Collected metric values from CloudWatch for quota {service_quota.service_name} / {service_quota.quota_name}: {values}"
            )
            service_quota.metric_values = values

    def _put_local_metrics(self, service_quota_group: List[ServiceQuota]) -> None:
        current_time = datetime.now()
        service_quotas_with_values = [
            sq for sq in service_quota_group if sq.metric_values
        ]

        self.local_cloudwatch_client.put_metric_data(
            Namespace=LOCAL_METRIC_NAMESPACE,
            MetricData=[
                {
                    "MetricName": LOCAL_METRIC_NAME,
                    "Dimensions": [
                        {"Name": "AccountId", "Value": self.account_id},
                        {"Name": "ServiceCode", "Value": service_quota.service_code},
                        {"Name": "QuotaName", "Value": service_quota.quota_name},
                        {"Name": "QuotaCode", "Value": service_quota.quota_code},
                    ],
                    "Timestamp": current_time,
                    "Value": service_quota.metric_values[0],
                }
                for service_quota in service_quotas_with_values
            ],
        )

        for service_quota in service_quotas_with_values:
            logger.info(
                f"Stored metric values for quota {service_quota.service_name} / {service_quota.quota_name}: {service_quota.metric_values[0]}"
            )
