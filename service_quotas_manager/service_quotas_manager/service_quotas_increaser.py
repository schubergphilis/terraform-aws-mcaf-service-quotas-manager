from typing import List

from botocore.exceptions import ClientError

from service_quotas_manager.entities import ServiceQuotaIncreaseRule
from service_quotas_manager.util import logger


class ServiceQuotasIncreaser:
    def __init__(self, remote_support_client, remote_service_quota_client, account_id):
        self.remote_support_client = remote_support_client
        self.remote_service_quota_client = remote_service_quota_client
        self.account_id = account_id

    def request_service_quota_increase(
        self, increase_rule: ServiceQuotaIncreaseRule
    ) -> None:
        if not self._check_preconditions(increase_rule):
            return

        desired_value = increase_rule.service_quota.value
        if increase_rule.step:
            desired_value += float(increase_rule.step)
        elif increase_rule.factor:
            desired_value *= float(increase_rule.factor)

        logger.info(
            f"[{self.account_id}] Filing a quota increase request for {increase_rule.service_quota.service_name} / {increase_rule.service_quota.quota_name} to increase quota to {desired_value}"
        )

        requested_quota = (
            self.remote_service_quota_client.request_service_quota_increase(
                ServiceCode=increase_rule.service_quota.service_code,
                QuotaCode=increase_rule.service_quota.quota_code,
                DesiredValue=desired_value,
            )
        )
        logger.info(
            f"[{self.account_id}] Quota increase for {increase_rule.service_quota.service_name} / {increase_rule.service_quota.quota_name} has been requested in case {requested_quota['RequestedQuota']['CaseId']}"
        )

        self._update_support_case(
            requested_quota["RequestedQuota"]["CaseId"],
            increase_rule.motivation,
            increase_rule.cc_mail_addresses,
        )

    def _update_support_case(
        self, case_id: str, motivation: str, cc_mail_addresses: List[str]
    ):
        self.remote_support_client.add_communication_to_case(
            caseId=case_id,
            communicationBody=motivation,
            ccEmailAddresses=cc_mail_addresses,
        )
        logger.info(
            f"[{self.account_id}] Case {case_id} has been updated with a motivation."
        )

    def _check_preconditions(self, increase_rule: ServiceQuotaIncreaseRule) -> bool:
        # Check whether there's configuration to know how to increase the quota.
        # Makes no sense to try to increase a quota if you don't know what to ask.
        if not increase_rule:
            logger.info(
                f"[{self.account_id}] Quota {increase_rule.service_quota.quota_name} for service {increase_rule.service_quota.service_name} has no increase configuration. Exiting..."
            )
            return False

        # Check whether the quota is adjustable and exit if it's not.
        # Makes no sense to try to increase a non-adjustable quota.
        if not increase_rule.service_quota.adjustable:
            logger.info(
                f"[{self.account_id}] Quota {increase_rule.service_quota.quota_name} for service {increase_rule.service_quota.service_name} is not adjustable. Exiting..."
            )
            return False

        # Check whether this account has business support enabled. Without business support
        # the support API can not be used and case motivation can not be given. In these cases
        # it's better to not perform increase requests at all and let that be manual activity.
        try:
            self.remote_support_client.describe_severity_levels()
        except ClientError as ex:
            if ex.response["Error"]["Code"] == "SubscriptionRequiredException":
                logger.error(
                    f"[{self.account_id}] This account has no valid support plan to use the Support API. A quota increase request could not be placed."
                )
                return False
            else:
                raise ex

        # Check whether there's no open increase cases.
        # Makes no sense to try to increase a quota if you already asked.
        historic_cases = self.remote_service_quota_client.list_requested_service_quota_change_history_by_quota(
            ServiceCode=increase_rule.service_quota.service_code,
            QuotaCode=increase_rule.service_quota.quota_code,
        )["RequestedQuotas"]
        cases_by_status = {}
        for case in historic_cases:
            if case["Status"] not in cases_by_status:
                cases_by_status[case["Status"]] = []
            cases_by_status[case["Status"]].append(case)

        if (
            len(cases_by_status.get("PENDING", [])) > 0
            or len(cases_by_status.get("CASE_OPENED", [])) > 0
        ):
            logger.info(
                f"[{self.account_id}] Quota {increase_rule.service_quota.quota_name} for service {increase_rule.service_quota.service_name} still has pending quota increase requests. Exiting..."
            )
            return False

        return True
