import logging
from typing import List

from service_quotas_manager.entities import ServiceQuota, ServiceQuotaIncreaseRule

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class ServiceQuotasIncreaser:
    def __init__(self, remote_support_client, remote_service_quota_client):
        self.remote_support_client = remote_support_client
        self.remote_service_quota_client = remote_service_quota_client

    def request_service_quota_increase(
        self, service_quota: ServiceQuota, increase_config: ServiceQuotaIncreaseRule
    ) -> None:
        if not self._check_preconditions(service_quota, increase_config):
            return

        desired_value = service_quota.value
        if increase_config.step:
            desired_value += float(increase_config.step)
        elif increase_config.factor:
            desired_value *= float(increase_config.factor)

        logger.info(
            f"Filing a quota increase request for {service_quota.service_name} / {service_quota.quota_name} to increase quota to {desired_value}"
        )

        requested_quota = (
            self.remote_service_quota_client.request_service_quota_increase(
                ServiceCode=service_quota.service_code,
                QuotaCode=service_quota.quota_code,
                DesiredValue=desired_value,
            )
        )
        logger.info(
            f"Quota increase for {service_quota.service_name} / {service_quota.quota_name} has been requested in case {requested_quota['RequestedQuota']['CaseId']}"
        )

        self._update_support_case(
            requested_quota["RequestedQuota"]["CaseId"],
            increase_config.motivation,
            increase_config.cc_mail_addresses,
        )

    def _update_support_case(
        self, case_id: str, motivation: str, cc_mail_addresses: List[str]
    ):
        self.remote_support_client.add_communication_to_case(
            caseId=case_id,
            communicationBody=motivation,
            ccEmailAddresses=cc_mail_addresses,
        )
        logger.info(f"Case {case_id} has been updated with a motivation.")

    def _check_preconditions(
        self, service_quota: ServiceQuota, increase_config: ServiceQuotaIncreaseRule
    ) -> bool:
        # Check whether the quota is adjustable and exit if it's not.
        # Makes no sense to try to increase a non-adjustable quota.
        if not service_quota.adjustable:
            logger.info(
                f"Quota {service_quota.quota_name} for service {service_quota.service_name} is not adjustable. Exiting..."
            )
            return False

        # Check whether there's configuration to know how to increase the quota.
        # Makes no sense to try to increase a quota if you don't know what to ask.
        if not increase_config:
            logger.info(
                f"Quota {service_quota.quota_name} for service {service_quota.service_name} has no increase configuration. Exiting..."
            )
            return False

        # Check whether there's no open increase cases.
        # Makes no sense to try to increase a quota if you already asked.
        historic_cases = self.remote_service_quota_client.list_requested_service_quota_change_history_by_quota(
            ServiceCode=service_quota.service_code, QuotaCode=service_quota.quota_code
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
                f"Quota {service_quota.quota_name} for service {service_quota.service_name} still has pending quota increase requests. Exiting..."
            )
            return False

        return True
