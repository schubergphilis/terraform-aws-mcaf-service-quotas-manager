import json
import time
from datetime import datetime, timedelta
from difflib import SequenceMatcher as SM
from typing import Dict, Final, List, Optional
from unittest import TestCase

import jmespath
from botocore.exceptions import ClientError
from jmespath.exceptions import ParseError
from service_quotas_manager.entities import ServiceQuota
from service_quotas_manager.util import convert_dict, get_logger

CE_ITEM_BLACKLIST: Final[List["str"]] = ["Tax", "EC2 - Other"]
"""Filter out these too generic Cost Explorer items"""

LOCAL_METRIC_NAMESPACE: Final[str] = "ServiceQuotaManager"
"""The namespace under which to store metrics in CloudWatch"""

LOCAL_METRIC_NAME: Final[str] = "ServiceQuotaUsage"
"""The metric name under which to store metrics in CloudWatch"""

METRIC_FILTER_THRESHOLD_PERC: Final[int] = 10
"""Quota usage below this % of applied quota is ignored."""

logger = get_logger()


class ServiceQuotasCollector:
    def __init__(
            self,
            remote_service_quota_client,
            remote_cloudwatch_client,
            remote_config_client,
            remote_ce_client,
            local_cloudwatch_client,
            account_id: str,
    ):
        self.remote_service_quota_client = remote_service_quota_client
        self.remote_cloudwatch_client = remote_cloudwatch_client
        self.remote_config_client = remote_config_client
        self.remote_ce_client = remote_ce_client
        self.local_cloudwatch_client = local_cloudwatch_client
        self.account_id = account_id

        self._service_quotas: List[ServiceQuota] = []
        self._custom_collection_queries = json.load(
            open("service_quotas_manager/custom_collection_queries.json")
        )

        self.__sqid_cntr = 0

    def collect(self, selected_services: List[str]) -> None:
        """
        Collect metrics from a remote account via CloudWatch Metrics
        or AWS Config. Store them as a custom metric in CloudWatch in the
        local account.
        """

        filtered_services = self._find_service_codes(selected_services)
        if not filtered_services:
            return

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
            service_quotas_with_metrics[i: i + 500]
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
            self._filter_metrics(service_quota_group)
            self._put_local_metrics(service_quota_group)
            self._service_quotas += service_quota_group

    def manage_alarms(self, alerting_config: Dict) -> None:
        """
        Create, update or delete alarms. Skip if there's no
        alerting config or no service quotas to monitor.
        """

        if not self._service_quotas:
            return

        if not alerting_config:
            return

        # Retrieve all currently setup alarms for service quotas.
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

                if nd["AccountId"] != self.account_id:
                    continue

                alarms_by_service_quota[
                    f"{nd['ServiceCode']}#{nd['QuotaCode']}#{nd['AccountId']}"
                ] = alarm

        self._upsert_alarms(alerting_config, alarms_by_service_quota)
        self._cleanup_alarms(alerting_config, alarms_by_service_quota)

    def _cleanup_alarms(self, alerting_config: Dict, alarms_by_service_quota: Dict):
        """
        Remove alarms that are no longer required. Reasons could be that the service
        is no longer used or configured to be monitored.
        """

        all_desired_alarm_codes = [
            f"{service_quota.service_code}#{service_quota.quota_code}#{self.account_id}"
            for service_quota in self._service_quotas
            if self.__should_alarm(alerting_config, service_quota)
        ]
        alarms_to_delete = [
            alarm["AlarmName"]
            for key, alarm in alarms_by_service_quota.items()
            if key not in all_desired_alarm_codes
        ]
        alarm_removal_groups = [
            alarms_to_delete[i: i + 100] for i in range(0, len(alarms_to_delete), 100)
        ]
        for alarm_removal_group in alarm_removal_groups:
            logger.info(f"Deleting alarms {alarm_removal_group}")
            self.local_cloudwatch_client.delete_alarms(AlarmNames=alarm_removal_group)

    def _upsert_alarms(self, alerting_config: Dict, alarms_by_service_quota: Dict):
        """
        Manages alarms that need to be created or alarms that require an update based
        on how they are configured.
        """

        for service_quota in self._service_quotas:
            if not self.__should_alarm(alerting_config, service_quota):
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

    def __should_alarm(
            self, alerting_config: Dict, service_quota: ServiceQuota
    ) -> bool:
        """
        Determine if an alarm should be created for a service quota by checking
        alert rules and metric values.

        - A service quota without metrics is generally a service that is not used
        and requires no alarm.
        - A service quota that is set to be explicitly ignored requires no alarm.
        """

        if not service_quota.metric_values:
            logger.debug(
                f"Skipping alarm for {service_quota.service_name} / {service_quota.quota_name} due to missing/filtered metrics."
            )
            return False

        if (
                alerting_config.get("rules", {})
                        .get(service_quota.service_name, {})
                        .get(service_quota.quota_name, {})
                        .get("ignore", False)
        ):
            logger.info(
                f"Skipping alarm for {service_quota.service_name} / {service_quota.quota_name} due to explicit ignore."
            )
            return False

        return True

    def __auto_detect_service_codes_from_billing(self) -> Optional[List[str]]:
        """
        Auto-detect services to monitor by retrieving a list
        of services from Cost Explorer. This allows for automated ways of
        adding services to monitor.
        """

        try:
            ce_report = self.remote_ce_client.get_cost_and_usage(
                TimePeriod={
                    "Start": (datetime.today() - timedelta(days=30)).strftime(
                        "%Y-%m-%d"
                    ),
                    "End": datetime.today().strftime("%Y-%m-%d"),
                },
                Granularity="MONTHLY",
                Metrics=["BlendedCost"],
                GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            )
        except ClientError as ex:
            logger.error(
                f"No services to monitor specified and unable to determine based on billing. Error: {ex.response['Error']['Code']}. Exiting..."
            )
            return

        ce_service_names = [
            ce_item["Keys"][0]
            for ce_item in ce_report["ResultsByTime"][0]["Groups"]
            if ce_item["Keys"][0] not in CE_ITEM_BLACKLIST
        ]

        return ce_service_names

    def _find_service_codes(self, selected_services: Optional[List[str]]) -> List[Dict]:
        """
        Find the services to monitor quotas for. Services to monitor can be defined in two ways:

        1. Manual through configuration passed in. That way a user can define and maintain a
        list of services to monitor.

        2. Automated by giving access to billing. That way the tool will derive services to monitor
        from your billing statement. Not as accurate as manual, but more dynamic.
        """

        auto_detected_services = []
        if not selected_services:
            auto_detected_services = self.__auto_detect_service_codes_from_billing()

        services_paginator = self.remote_service_quota_client.get_paginator(
            "list_services"
        )
        services_pages = services_paginator.paginate()

        filtered_services = []
        matched_services = []
        for service_page in services_pages:
            for service in service_page["Services"]:
                if auto_detected_services:
                    for detected_service in auto_detected_services:
                        diff_ratio = SM(
                            None, detected_service, service["ServiceName"]
                        ).ratio()
                        if diff_ratio > 0.75:
                            filtered_services.append(service)
                            logger.info(
                                f"Selected service {service['ServiceName']} based on cost and usage reports ({detected_service})."
                            )
                            auto_detected_services.remove(detected_service)
                            break
                else:
                    if service["ServiceName"] in selected_services:
                        filtered_services.append(service)
                        matched_services.append(service["ServiceName"])

        if not auto_detected_services:
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
        Find the service quotas to manage based on the service they are part of.
        Service quotas can be set to an AWS default or to an applied quota.
        Merge default quotas with applied quotas. Applied quotas overrule default
        quotas.
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
                if "ErrorReason" in applied_service_quota:
                    continue

                applied_service_quotas_by_id[
                    applied_service_quota["QuotaCode"]
                ] = applied_service_quota
            time.sleep(1)

        service_quotas = []
        for service_quota_page in default_service_quota_pages:
            for service_quota in service_quota_page["Quotas"]:
                if "ErrorReason" in service_quota:
                    logger.warning(
                        f"Can not manage quota {service_quota['ServiceName']} / {service_quota['QuotaName']}. Reason code: {service_quota['ErrorReason']['ErrorCode']}. Reason message: {service_quota['ErrorReason']['ErrorMessage']}"
                    )
                    continue

                if service_quota["QuotaCode"] in applied_service_quotas_by_id:
                    service_quota = applied_service_quotas_by_id[
                        service_quota["QuotaCode"]
                    ]

                service_quota = ServiceQuota(**convert_dict(service_quota))
                service_quota.internal_id = f"sq{self.__sqid_cntr:05}"
                self.__sqid_cntr += 1
                service_quotas.append(service_quota)
            time.sleep(1)

        return service_quotas

    def _collect_config_remote_metrics(
            self, service_quota_group: List[ServiceQuota]
    ) -> None:
        """
        Collect the usage for various service quotas from the targeted account by using
        AWS Config. A JMESPath expression is then applied to the collected query result
        to retrieve the value looked for.

        See https://jmespath.org/ for how to use.
        """

        for service_quota in service_quota_group:
            c_params = service_quota.collection_query["parameters"]
            expression_result_paginator = self.remote_config_client.get_paginator(
                "select_resource_config"
            )
            expression_result_pages = expression_result_paginator.paginate(
                Expression=c_params["expression"]
            )

            expression_result = []
            for expression_result_page in expression_result_pages:
                expression_result += [
                    json.loads(row) for row in expression_result_page.get("Results", [])
                ]

            if len(expression_result) == 0:
                logger.info(
                    f"The AWS config query ({c_params['expression']}) yielded no results "
                    f"({service_quota.service_code} / {service_quota.quota_code})"
                )
                continue

            try:
                collected_values = jmespath.search(
                    c_params["jmespath"], expression_result
                )
                service_quota.metric_values = [round(float(collected_values), 1)]
                logger.debug(
                    f"Collected metric values from AWS Config for quota "
                    f"{service_quota.service_name} / {service_quota.quota_name}: {collected_values}"
                )
            except ParseError as p_ex:
                logger.warning(
                    f"A JMESPath parse error occurred ({service_quota.service_code} / "
                    f"{service_quota.quota_code}): {p_ex.msg}."
                )
            except ValueError:
                logger.warning(
                    f"The value retrieved from the JMESPath expression could not be converted "
                    f"to float ({service_quota.service_code} / {service_quota.quota_code})."
                )

    def _collect_cloudwatch_remote_metrics(
            self, service_quota_group: List[ServiceQuota]
    ) -> None:
        """
        Collect the usage for various service quotas from the targeted account by using CloudWatch Metrics.
        Combine the metrics to collect in groups of 500 metrics to make the process more time- and
        cost efficient.
        """

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
                        "Period": (
                            service_quota.period["PeriodValue"]
                            if service_quota.period
                               and service_quota.period["PeriodUnit"] == "SECOND"
                            else 300
                        ),
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
            logger.debug(
                f"Collected metric values from CloudWatch for quota {service_quota.service_name} / {service_quota.quota_name}: {values}"
            )
            service_quota.metric_values = values

    def _filter_metrics(self, service_quota_group: List[ServiceQuota]) -> None:
        """
        Filter out metrics for service quotas that have values, an applied quota,
        and a current usage of less than 10% of the applied quota. This is to prevent
        monitoring and cost for quotas that don't matter (yet). As soon as a quota increases
        above the 10% threshold it will be included in monitors and alarms.
        """
        for service_quota in service_quota_group:
            if (
                    service_quota.value
                    and service_quota.metric_values
                    and service_quota.metric_values[0]
                    < (service_quota.value * METRIC_FILTER_THRESHOLD_PERC) / 100
            ):
                logger.info(
                    f"Filtering out service quota {service_quota.service_name} / {service_quota.quota_name} because of low usage ({service_quota.metric_values[0]} < {METRIC_FILTER_THRESHOLD_PERC}% of {service_quota.value})"
                )
                service_quota.metric_values = []

    def _put_local_metrics(self, service_quota_group: List[ServiceQuota]) -> None:
        """
        Store the values collected for various service quotas as custom metrics in
        CloudWatch. Combine the metrics of various service quotas in a single call
        to make this process more time and cost efficient.
        """
        current_time = datetime.now()
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
                for service_quota in service_quota_group
                if service_quota.metric_values
            ],
        )

        for service_quota in service_quota_group:
            if service_quota.metric_values:
                logger.info(
                    f"Stored metric values for quota {service_quota.service_name} / {service_quota.quota_name}: {service_quota.metric_values[0]}"
                )
