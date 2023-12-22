from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ServiceQuota:
    """
    Represents a service quota from AWS.

    Attributes
    ----------
    adjustable: bool
        Whether a quota can be adjusted.
    global_quota: bool
        Whether a quota is global (e.g. not only applies to a single region).
    quota_arn: str
        The ARN of the quota.
    quota_code: str
        The identifier of the quota.
    quota_name: str
        The descriptive name of the quota.
    service_code: str
        The identifier of the service the quota belongs to.
    service_name: str
        The descriptive name of the service the quota belongs to.
    unit: str
        The unit in which the quota is applied and measures.
    collection_query: Dict = field(default_factory=lambda: {})
        Specifies the query to use if a quota has a non-default way of
        collecting usage (i.e. by using AWS config).
    error_reason: Dict = field(default_factory=lambda: {})
        The reason a quota or its usage could not be read by AWS.
        Can be related to unavailability of services or authorization errors.
    internal_id: str = ""
        The internal id of the quota as is used by this tool reference
        back to quota when making optimized calls to other AWS services.
    metric_values: List[float] = field(default_factory=lambda: [])
        The metric values collected for this quota that indicate quota usage.
    period: Dict = field(default_factory=lambda: {})
        The period for which AWS advises to collect usage for (value and unit).
    quota_applied_at_level: str = ""
        Specifies at which level of granularity that the quota value is applied.
    quota_context: Dict = field(default_factory=lambda: {})
        The context for this service quota.
    usage_metric: Dict = field(default_factory=lambda: {})
        Specifies how to collect quota usage from CloudWatch Metrics
        (namespace, metricname, dimensions and statistic)
    value: Optional[float] = None
        The actual quota value currently applied.
    """

    adjustable: bool
    global_quota: bool
    quota_arn: str
    quota_code: str
    quota_name: str
    service_code: str
    service_name: str
    unit: str

    collection_query: Dict = field(default_factory=lambda: {})
    error_reason: Dict = field(default_factory=lambda: {})
    internal_id: str = ""
    metric_values: List[float] = field(default_factory=lambda: [])
    period: Dict = field(default_factory=lambda: {})
    quota_applied_at_level: str = ""
    quota_context: Dict = field(default_factory=lambda: {})
    usage_metric: Dict = field(default_factory=lambda: {})
    value: Optional[float] = None


@dataclass
class ServiceQuotaIncreaseRule:
    """
    Represents a local service quota increase rule.

    service_quota: ServiceQuota
        An instance of a ServiceQuota
    cc_mail_addresses: List[str]
        A list of mail address that need to be included in
        communication with AWS support about the increase request.
    motivation: str
        The motivation for the quota increase request. This will
        be included in the ticket.
    factor: Optional[float] = None
        The factor to request an increase with (applied quota * factor).
        Cannot be used in combination with a step.
    step: Optional[float] = None
        The step to request an increase with (applied quota + step).
        Cannot be used in combination with a factor.
    """

    service_quota: ServiceQuota
    cc_mail_addresses: List[str]
    motivation: str
    factor: Optional[float] = None
    step: Optional[float] = None
