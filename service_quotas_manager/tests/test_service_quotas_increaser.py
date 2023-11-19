import pytest
from botocore.stub import Stubber

from service_quotas_manager.entities import ServiceQuota, ServiceQuotaIncreaseRule
from service_quotas_manager.service_quotas_increaser import ServiceQuotasIncreaser
from service_quotas_manager.util import convert_dict


class TestServiceQuotasIncreaser:
    @pytest.mark.parametrize("rule_type", ["step", "factor"])
    def test_can_request_service_quota_increase(
        self,
        rule_type,
        support,
        service_quotas,
        service_quotas_list_applied_quotas_lambda,
    ):
        increaser = ServiceQuotasIncreaser(support, service_quotas)
        service_quota = ServiceQuota(
            **convert_dict(service_quotas_list_applied_quotas_lambda["Quotas"][0])
        )

        rule_params = {
            "service_quota": service_quota,
            "motivation": "I just want an increase!",
            "cc_mail_addresses": ["test@test.com"],
        }

        if rule_type == "step":
            rule_params["step"] = 10
        else:
            rule_params["factor"] = 1.2

        service_quota_increase_rule = ServiceQuotaIncreaseRule(**rule_params)

        stubbed_service_quotas = Stubber(service_quotas)
        stubbed_service_quotas.add_response(
            "list_requested_service_quota_change_history_by_quota",
            {"RequestedQuotas": []},
            {"QuotaCode": "L-B99A9384", "ServiceCode": "lambda"},
        )
        stubbed_service_quotas.add_response(
            "request_service_quota_increase",
            {"RequestedQuota": {"CaseId": "CASE000099"}},
            {
                "DesiredValue": (1010.0 if rule_type == "step" else 1200),
                "QuotaCode": "L-B99A9384",
                "ServiceCode": "lambda",
            },
        )
        stubbed_service_quotas.activate()

        stubbed_support = Stubber(support)
        stubbed_support.add_response(
            "describe_severity_levels",
            {"severityLevels": [{"code": "foo", "name": "bar"}]},
            {},
        )
        stubbed_support.add_response(
            "add_communication_to_case",
            {},
            {
                "caseId": "CASE000099",
                "ccEmailAddresses": ["test@test.com"],
                "communicationBody": "I just want an increase!",
            },
        )
        stubbed_support.activate()

        increaser.request_service_quota_increase(service_quota_increase_rule)
