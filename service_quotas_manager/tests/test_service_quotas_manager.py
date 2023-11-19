import json
from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import patch

from botocore.stub import Stubber

from service_quotas_manager.entities import ServiceQuota, ServiceQuotaIncreaseRule
from service_quotas_manager.service_quotas_manager import (
    _get_account_id_from_alarm,
    _get_increase_rule_from_config,
    _get_service_quota_from_alarm,
    _load_config_from_s3,
)
from service_quotas_manager.service_quotas_manager import handler as sqm_handler
from service_quotas_manager.util import convert_dict


class TestServiceQuotasIncreaser:
    def test_can_get_account_id_from_alarm(self):
        account_id = "123456789000"
        alarm_details = {
            "configuration": {
                "metrics": [
                    {
                        "metricStat": {
                            "metric": {
                                "dimensions": {
                                    "AccountId": account_id,
                                    "QuotaCode": "L-123456",
                                    "ServiceCode": "lambda",
                                }
                            }
                        }
                    }
                ]
            }
        }
        assert _get_account_id_from_alarm(alarm_details) == account_id

    def test_can_load_config_from_s3(self, s3):
        stubbed_s3 = Stubber(s3)
        stubbed_s3.add_response(
            "get_object",
            {
                "Body": BytesIO(
                    json.dumps(
                        {"123456789000": {"foo": "bar"}, "123456789001": {"bar": "foo"}}
                    ).encode()
                )
            },
            {"Bucket": "bucket_name", "Key": "bucket_key"},
        )
        stubbed_s3.activate()

        config = _load_config_from_s3(s3, "bucket_name", "bucket_key", "123456789000")
        assert config == {"foo": "bar"}

    def test_can_get_increase_rule_from_config(
        self, service_quotas_list_applied_quotas_lambda
    ):
        service_quota = ServiceQuota(
            **convert_dict(service_quotas_list_applied_quotas_lambda["Quotas"][0])
        )
        config = {
            "quota_increase_config": {
                "AWS Lambda": {
                    "Concurrent executions": {
                        "step": 500,
                        "motivation": "Test motivation",
                        "cc_mail_addresses": ["devops_engineer@acme.com"],
                    }
                }
            }
        }
        rule = _get_increase_rule_from_config(config, service_quota)

        assert isinstance(rule, ServiceQuotaIncreaseRule)
        assert rule.step == 500
        assert rule.motivation == "Test motivation"

    def test_get_increase_rule_from_config_returns_none_on_no_match(
        self, service_quotas_list_applied_quotas_lambda
    ):
        service_quota = ServiceQuota(
            **convert_dict(service_quotas_list_applied_quotas_lambda["Quotas"][0])
        )
        config = {
            "quota_increase_config": {
                "Amazon Elastic Compute Cloud (Amazon EC2)": {
                    "Running Dedicated r6idn Hosts": {
                        "step": 10,
                        "motivation": "Test motivation",
                        "cc_mail_addresses": ["devops_engineer@acme.com"],
                    }
                }
            }
        }
        rule = _get_increase_rule_from_config(config, service_quota)

        assert not rule

    def test_can_get_applied_service_quota_from_alarm(
        self, service_quotas, service_quotas_list_applied_quotas_lambda
    ):
        alarm_details = {
            "configuration": {
                "metrics": [
                    {
                        "metricStat": {
                            "metric": {
                                "dimensions": {
                                    "AccountId": "123456789000",
                                    "QuotaCode": "L-123456",
                                    "ServiceCode": "lambda",
                                }
                            }
                        }
                    }
                ]
            }
        }

        stubbed_service_quotas = Stubber(service_quotas)
        stubbed_service_quotas.add_response(
            "get_service_quota",
            {"Quota": service_quotas_list_applied_quotas_lambda["Quotas"][0]},
            {"QuotaCode": "L-123456", "ServiceCode": "lambda"},
        )
        stubbed_service_quotas.activate()

        quota = _get_service_quota_from_alarm(alarm_details, service_quotas)

        assert isinstance(quota, ServiceQuota)
        stubbed_service_quotas.assert_no_pending_responses()

    def test_can_get_default_service_quota_from_alarm(
        self, service_quotas, service_quotas_list_applied_quotas_lambda
    ):
        alarm_details = {
            "configuration": {
                "metrics": [
                    {
                        "metricStat": {
                            "metric": {
                                "dimensions": {
                                    "AccountId": "123456789000",
                                    "QuotaCode": "L-123456",
                                    "ServiceCode": "lambda",
                                }
                            }
                        }
                    }
                ]
            }
        }

        stubbed_service_quotas = Stubber(service_quotas)
        stubbed_service_quotas.add_client_error("get_service_quota")
        stubbed_service_quotas.add_response(
            "get_aws_default_service_quota",
            {"Quota": service_quotas_list_applied_quotas_lambda["Quotas"][0]},
            {"QuotaCode": "L-123456", "ServiceCode": "lambda"},
        )
        stubbed_service_quotas.activate()

        quota = _get_service_quota_from_alarm(alarm_details, service_quotas)

        assert isinstance(quota, ServiceQuota)
        stubbed_service_quotas.assert_no_pending_responses()

    def test_handler_exits_if_no_account_id_provided(self, caplog):
        sqm_handler({}, None)
        assert "No account ID could be found in event. Exiting..." in [
            r.message for r in caplog.records
        ]

    def test_handler_exits_if_no_action_provided(self, caplog):
        sqm_handler({"account_id": "123456789001"}, None)
        assert "No action specified in event. Exiting..." in [
            r.message for r in caplog.records
        ]

    @patch("service_quotas_manager.service_quotas_manager._get_local_client")
    def test_handler_exits_if_no_valid_action_provided(
        self, mocked_client, s3, sts, caplog
    ):
        stubbed_s3 = Stubber(s3)
        stubbed_s3.add_response(
            "get_object",
            {
                "Body": BytesIO(
                    json.dumps(
                        {"123456789000": {"role_name": "ServiceQuotaManager"}}
                    ).encode()
                )
            },
            {"Bucket": "bucket_name", "Key": "bucket_key"},
        )
        stubbed_s3.activate()

        stubbed_sts = Stubber(sts)
        stubbed_sts.add_response(
            "assume_role",
            {
                "Credentials": {
                    "AccessKeyId": "fake-access-key-id",
                    "SecretAccessKey": "fake-secret-access-key",
                    "SessionToken": "fake-session-token",
                    "Expiration": datetime.now() + timedelta(seconds=900),
                }
            },
            {
                "DurationSeconds": 900,
                "RoleArn": "arn:aws:iam::123456789000:role/ServiceQuotaManager",
                "RoleSessionName": "ServiceQuotaManagerRole",
            },
        )
        stubbed_sts.activate()

        mocked_client.side_effect = [s3, sts]

        sqm_handler(
            {
                "account_id": "123456789000",
                "config_bucket": "bucket_name",
                "config_key": "bucket_key",
                "action": "FooBar",
            },
            None,
        )

        assert "Action FooBar not recognized as valid action. Exiting..." in [
            r.message for r in caplog.records
        ]

    @patch("service_quotas_manager.service_quotas_manager._get_local_client")
    def test_handler_exits_if_no_config_for_account_could_be_found(
        self, mocked_client, s3, caplog
    ):
        stubbed_s3 = Stubber(s3)
        stubbed_s3.add_response(
            "get_object",
            {"Body": BytesIO(json.dumps({"123456789000": {"foo": "bar"}}).encode())},
            {"Bucket": "bucket_name", "Key": "bucket_key"},
        )
        stubbed_s3.activate()

        mocked_client.return_value = s3

        sqm_handler(
            {
                "account_id": "123456789001",
                "config_bucket": "bucket_name",
                "config_key": "bucket_key",
                "action": "CollectServiceQuotas",
            },
            None,
        )
        assert "No configuration found for account 123456789001. Exiting..." in [
            r.message for r in caplog.records
        ]
