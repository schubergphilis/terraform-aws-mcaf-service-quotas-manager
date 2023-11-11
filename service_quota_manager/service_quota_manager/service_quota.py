from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ServiceQuota:
    service_code: str
    quota_code: str
    service_name: str
    quota_name: str
    value: float
    adjustable: bool
    usage_metric: Dict = {}
    metric_values: List[float] = []
    collection_query: Dict = {}
    internal_id: str = ""
