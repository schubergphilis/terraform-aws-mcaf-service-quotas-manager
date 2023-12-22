from botocore.stub import ANY, Stubber

from service_quotas_manager.entities import ServiceQuota
from service_quotas_manager.service_quotas_collector import ServiceQuotasCollector
from service_quotas_manager.util import convert_dict


class TestServiceQuotasCollector:
    def test_can_manage_alarms(
        self,
        service_quotas,
        cloudwatch,
        aws_config,
        cost_explorer,
        service_quotas_list_applied_quotas_lambda,
    ):
        collector = ServiceQuotasCollector(
            service_quotas,
            cloudwatch,
            aws_config,
            cost_explorer,
            cloudwatch,
            "123456789000",
        )

        service_quota = ServiceQuota(
            **convert_dict(service_quotas_list_applied_quotas_lambda["Quotas"][0])
        )

        service_quota.metric_values = [1.0, 1.5]
        collector._service_quotas = [service_quota]

        stubbed_cloudwatch = Stubber(cloudwatch)
        stubbed_cloudwatch.add_response(
            "describe_alarms",
            {
                "MetricAlarms": [
                    {
                        "AlarmDescription": "The service quota for Running Dedicated r6idn Hosts for service Amazon Elastic Compute Cloud (Amazon EC2) in account 123456789000 is nearing its configured quota (1000.0). This quota is adjustable.",
                        "AlarmName": "Service Quota: Running Dedicated r6idn Hosts for service Amazon Elastic Compute Cloud (Amazon EC2) in account 123456789000",
                        "ComparisonOperator": "GreaterThanThreshold",
                        "DatapointsToAlarm": 2,
                        "Dimensions": [
                            {"Name": "ServiceCode", "Value": "ec2"},
                            {"Name": "QuotaCode", "Value": "L-C4EABC2C"},
                            {
                                "Name": "QuotaName",
                                "Value": "Running Dedicated r6idn Hosts",
                            },
                            {"Name": "account_id", "Value": "123456789000"},
                        ],
                        "EvaluationPeriods": 3,
                        "MetricName": "ServiceQuotaUsage",
                        "Namespace": "ServiceQuotaManager",
                        "Period": 3600,
                        "Statistic": "Maximum",
                        "Threshold": 1.3,
                    }
                ]
            },
            {"AlarmNamePrefix": "Service Quota:", "AlarmTypes": ["MetricAlarm"]},
        )
        stubbed_cloudwatch.add_response(
            "put_metric_alarm",
            {},
            {
                "AlarmDescription": "The service quota for Concurrent executions for service AWS Lambda in account 123456789000 is nearing its configured quota (1000.0). This quota is adjustable.",
                "AlarmName": "Service Quota: Concurrent executions for service AWS Lambda in account 123456789000",
                "ComparisonOperator": "GreaterThanThreshold",
                "DatapointsToAlarm": 2,
                "Dimensions": [
                    {"Name": "ServiceCode", "Value": "lambda"},
                    {"Name": "QuotaCode", "Value": "L-B99A9384"},
                    {"Name": "QuotaName", "Value": "Concurrent executions"},
                    {"Name": "account_id", "Value": "123456789000"},
                ],
                "EvaluationPeriods": 3,
                "MetricName": "ServiceQuotaUsage",
                "Namespace": "ServiceQuotaManager",
                "Period": 3600,
                "Statistic": "Maximum",
                "Threshold": 750.0,
            },
        )
        stubbed_cloudwatch.add_response(
            "delete_alarms",
            {},
            {
                "AlarmNames": [
                    "Service Quota: Running Dedicated r6idn Hosts for service Amazon Elastic Compute Cloud (Amazon EC2) in account 123456789000"
                ]
            },
        )
        stubbed_cloudwatch.activate()

        collector.manage_alarms({"default_threshold_perc": 75})

        stubbed_cloudwatch.assert_no_pending_responses()

    def test_can_collect_service_quotas(
        self,
        service_quotas,
        cloudwatch,
        aws_config,
        cost_explorer,
        service_quotas_list_all_services,
        service_quotas_list_default_quotas_lambda,
        service_quotas_list_applied_quotas_lambda,
    ):
        collector = ServiceQuotasCollector(
            service_quotas,
            cloudwatch,
            aws_config,
            cost_explorer,
            cloudwatch,
            "123456789000",
        )

        stubbed_service_quotas = Stubber(service_quotas)
        stubbed_service_quotas.add_response(
            "list_services", service_quotas_list_all_services, {}
        )
        stubbed_service_quotas.add_response(
            "list_service_quotas",
            service_quotas_list_applied_quotas_lambda,
            {"ServiceCode": "lambda"},
        )
        stubbed_service_quotas.add_response(
            "list_aws_default_service_quotas",
            service_quotas_list_default_quotas_lambda,
            {"ServiceCode": "lambda"},
        )
        stubbed_service_quotas.activate()

        stubbed_cloudwatch = Stubber(cloudwatch)
        stubbed_cloudwatch.add_response(
            "get_metric_data",
            {"MetricDataResults": [{"Id": "sq00000", "Values": [1.0, 2.0]}]},
            {
                "EndTime": ANY,
                "MetricDataQueries": ANY,
                "ScanBy": "TimestampDescending",
                "StartTime": ANY,
            },
        )
        stubbed_cloudwatch.add_response(
            "put_metric_data",
            {},
            {
                "MetricData": [
                    {
                        "Dimensions": [
                            {"Name": "account_id", "Value": "123456789000"},
                            {"Name": "ServiceCode", "Value": "lambda"},
                            {
                                "Name": "QuotaName",
                                "Value": "Function and layer storage",
                            },
                            {"Name": "QuotaCode", "Value": "L-9FEE3D26"},
                        ],
                        "MetricName": "ServiceQuotaUsage",
                        "Timestamp": ANY,
                        "Value": 120.0,
                    },
                ],
                "Namespace": "ServiceQuotaManager",
            },
        )
        stubbed_cloudwatch.activate()

        stubbed_aws_config = Stubber(aws_config)
        stubbed_aws_config.add_response(
            "select_resource_config",
            {
                "Results": ['{"COUNT(*)":120}'],
                "QueryInfo": {"SelectFields": [{"Name": "COUNT(*)"}]},
            },
            {
                "Expression": "SELECT COUNT(*) WHERE resourceType = 'AWS::EC2::NetworkInterface' and configuration.interfaceType = 'lambda'",
                "Limit": 1,
            },
        )
        stubbed_aws_config.activate()

        collector.collect(["AWS Lambda"])

        stubbed_cloudwatch.assert_no_pending_responses()
        stubbed_service_quotas.assert_no_pending_responses()

    def test_can_auto_discover_services(
        self,
        service_quotas,
        cloudwatch,
        aws_config,
        cost_explorer,
        service_quotas_list_all_services,
        service_quotas_list_default_quotas_lambda,
        service_quotas_list_applied_quotas_lambda,
        cost_explorer_get_cost_and_usage_single_service,
    ):
        collector = ServiceQuotasCollector(
            service_quotas,
            cloudwatch,
            aws_config,
            cost_explorer,
            cloudwatch,
            "123456789000",
        )

        stubbed_cost_explorer = Stubber(cost_explorer)
        stubbed_cost_explorer.add_response(
            "get_cost_and_usage",
            cost_explorer_get_cost_and_usage_single_service,
            {
                "Granularity": "MONTHLY",
                "GroupBy": [{"Key": "SERVICE", "Type": "DIMENSION"}],
                "Metrics": ["BlendedCost"],
                "TimePeriod": {"End": ANY, "Start": ANY},
            },
        )
        stubbed_cost_explorer.activate()

        stubbed_service_quotas = Stubber(service_quotas)
        stubbed_service_quotas.add_response(
            "list_services", service_quotas_list_all_services, {}
        )
        stubbed_service_quotas.add_response(
            "list_service_quotas",
            service_quotas_list_applied_quotas_lambda,
            {"ServiceCode": "lambda"},
        )
        stubbed_service_quotas.add_response(
            "list_aws_default_service_quotas",
            service_quotas_list_default_quotas_lambda,
            {"ServiceCode": "lambda"},
        )
        stubbed_service_quotas.activate()

        stubbed_cloudwatch = Stubber(cloudwatch)
        stubbed_cloudwatch.add_response(
            "get_metric_data",
            {"MetricDataResults": [{"Id": "sq00000", "Values": [1.0, 2.0]}]},
            {
                "EndTime": ANY,
                "MetricDataQueries": ANY,
                "ScanBy": "TimestampDescending",
                "StartTime": ANY,
            },
        )
        stubbed_cloudwatch.add_response(
            "put_metric_data",
            {},
            {
                "MetricData": [
                    {
                        "Dimensions": [
                            {"Name": "account_id", "Value": "123456789000"},
                            {"Name": "ServiceCode", "Value": "lambda"},
                            {
                                "Name": "QuotaName",
                                "Value": "Function and layer storage",
                            },
                            {"Name": "QuotaCode", "Value": "L-9FEE3D26"},
                        ],
                        "MetricName": "ServiceQuotaUsage",
                        "Timestamp": ANY,
                        "Value": 120.0,
                    },
                ],
                "Namespace": "ServiceQuotaManager",
            },
        )
        stubbed_cloudwatch.activate()

        stubbed_aws_config = Stubber(aws_config)
        stubbed_aws_config.add_response(
            "select_resource_config",
            {
                "Results": ['{"COUNT(*)":120}'],
                "QueryInfo": {"SelectFields": [{"Name": "COUNT(*)"}]},
            },
            {
                "Expression": "SELECT COUNT(*) WHERE resourceType = 'AWS::EC2::NetworkInterface' and configuration.interfaceType = 'lambda'",
                "Limit": 1,
            },
        )
        stubbed_aws_config.activate()

        collector.collect([])

        stubbed_cloudwatch.assert_no_pending_responses()
        stubbed_service_quotas.assert_no_pending_responses()
