from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ServiceQuotaIncreaseRule:
    service_name: str
    quota_name: str
    step: Optional[float]
    factor: Optional[float]
    motivation: str
    cc_mail_addresses: List[str]
