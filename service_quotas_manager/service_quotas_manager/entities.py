from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ServiceQuota:
    adjustable: bool
    global_quota: bool
    quota_arn: str
    quota_code: str
    quota_name: str
    service_code: str
    service_name: str
    unit: str
    value: float

    collection_query: Dict = field(default_factory=lambda: {})
    error_reason: Dict = field(default_factory=lambda: {})
    internal_id: str = ""
    metric_values: List[float] = field(default_factory=lambda: [])
    period: Dict = field(default_factory=lambda: {})
    quota_applied_at_level: str = ""
    quota_context: Dict = field(default_factory=lambda: {})
    usage_metric: Dict = field(default_factory=lambda: {})


@dataclass
class ServiceQuotaIncreaseRule:
    service_quota: ServiceQuota
    cc_mail_addresses: List[str]
    motivation: str
    factor: Optional[float] = None
    step: Optional[float] = None
