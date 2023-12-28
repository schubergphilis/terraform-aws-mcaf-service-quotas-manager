from typing import List

from botocore.exceptions import ClientError
from service_quotas_manager.entities import ServiceQuotaIncreaseRule
from service_quotas_manager.util import get_logger

logger = get_logger()


class ServiceQuotasIncreaser:
    """
    ServiceQuotasIncreaser
    """

    def __init__(self, remote_support_client, remote_service_quota_client):
        self.remote_support_client = remote_support_client
        self.remote_service_quota_client = remote_service_quota_client

    def request_service_quota_increase(
            self, increase_rule: ServiceQuotaIncreaseRule
    ) -> None:
        """
        File a service quota increase if all pre-conditions are met. Steps are
        to file the case and then update it to include information on the motivation
        and to CC the case to configured recipients. From here on any future case
        communication must happen outside of this service quotas manager.
        """

        if not self._check_preconditions(increase_rule):
            return

        desired_value = increase_rule.service_quota.value
        if increase_rule.step:
            desired_value += float(increase_rule.step)
        elif increase_rule.factor:
            desired_value *= float(increase_rule.factor)

        logger.info(
            f"Filing a quota increase request for {increase_rule.service_quota.service_name} / {increase_rule.service_quota.quota_name} to increase quota to {desired_value}"
        )

        requested_quota = (
            self.remote_service_quota_client.request_service_quota_increase(
                ServiceCode=increase_rule.service_quota.service_code,
                QuotaCode=increase_rule.service_quota.quota_code,
                DesiredValue=desired_value,
            )
        )
        logger.info(
            f"Quota increase for {increase_rule.service_quota.service_name} / {increase_rule.service_quota.quota_name} has been requested in case {requested_quota['RequestedQuota']['CaseId']}"
        )

        self._update_support_case(
            requested_quota["RequestedQuota"]["CaseId"],
            increase_rule.motivation,
            increase_rule.cc_mail_addresses,
        )

    def _update_support_case(
            self, case_id: str, motivation: str, cc_mail_addresses: List[str]
    ):
        """
        Update the just created support case by adding the configured motivation
        to it and including the configured carbon copy mail addresses.
        """

        self.remote_support_client.add_communication_to_case(
            caseId=case_id,
            communicationBody=motivation,
            ccEmailAddresses=cc_mail_addresses,
        )
        logger.info(f"Case {case_id} has been updated with a motivation.")

    def _check_preconditions(self, increase_rule: ServiceQuotaIncreaseRule) -> bool:
        """
        There's certain preconditions to be met before a case can be created.

        1. There needs to be increase rule configured for the quotas manager to
        know if- and how to increase.

        2. The quota needs to be adjustable. It makes no sense to request an increase
        on a quota that is not adjustable in the first place.

        3. The account on which the quota is applicable needs to have business support
        enabled. The usage of the support API is tied to having business support enabled.

        4. There should not be an already open case for this service quota.
        """

        if not increase_rule:
            logger.info(
                f"Quota {increase_rule.service_quota.quota_name} for service {increase_rule.service_quota.service_name} has no increase configuration. Exiting..."
            )
            return False

        if not increase_rule.service_quota.adjustable:
            logger.info(
                f"Quota {increase_rule.service_quota.quota_name} for service {increase_rule.service_quota.service_name} is not adjustable. Exiting..."
            )
            return False

        try:
            self.remote_support_client.describe_severity_levels()
        except ClientError as ex:
            if ex.response["Error"]["Code"] == "SubscriptionRequiredException":
                logger.error(
                    "This account has no valid support plan to use the Support API. A quota increase request could not be placed."
                )
                return False
            else:
                raise ex

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
                f"Quota {increase_rule.service_quota.quota_name} for service {increase_rule.service_quota.service_name} still has pending quota increase requests. Exiting..."
            )
            return False

        return True
