from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ServiceQuotaIncreaseRule:
    cc_mail_addresses: List[str]
    motivation: str
    quota_name: str
    service_name: str
    factor: Optional[float] = None
    step: Optional[float] = None
