from botocore.stub import Stubber

from service_quota_manager.service_quota import ServiceQuota
from service_quota_manager.service_quota_increase_rule import ServiceQuotaIncreaseRule
from service_quota_manager.service_quota_increaser import ServiceQuotaIncreaser
from service_quota_manager.util import convert_dict


class TestServiceQuotaIncreaser:
    def test_can_request_service_quota_increase(self, support, service_quotas, service_quotas_list_applied_quotas_lambda):
        increaser = ServiceQuotaIncreaser(support, service_quotas)
        service_quota = ServiceQuota(
            **convert_dict(service_quotas_list_applied_quotas_lambda["Quotas"][0])
        )
        service_quota_increase_rule = ServiceQuotaIncreaseRule(
            service_name=service_quota.service_name,
            quota_name=service_quota.quota_name,
            step=10,
            motivation="I just want an increase!",
            cc_mail_addresses=["test@test.com"]
        )

        stubbed_service_quotas = Stubber(service_quotas)
        stubbed_service_quotas.add_response(
            "list_requested_service_quota_change_history_by_quota",
            {
                "RequestedQuotas": []
            },
            {"QuotaCode": "L-B99A9384", "ServiceCode": "lambda"}
        )
        stubbed_service_quotas.add_response(
            "request_service_quota_increase",
            {
                "RequestedQuota": {
                    "CaseId": "CASE000099"
                }
            },
            {
                "DesiredValue": 1010.0, "QuotaCode": "L-B99A9384", "ServiceCode": "lambda"
            }
        )
        stubbed_service_quotas.activate()

        stubbed_support = Stubber(support)
        stubbed_support.add_response(
            "add_communication_to_case",
            {},
            {
                "caseId": "CASE000099",
                "ccEmailAddresses": ["test@test.com"],
                "communicationBody": "I just want an increase!"
            }
        )
        stubbed_support.activate()

        increaser.request_service_quota_increase(service_quota, service_quota_increase_rule)
