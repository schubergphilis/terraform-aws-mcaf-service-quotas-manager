import logging
from typing import Dict, List

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class ServiceQuota:
    def __init__(self, source: Dict) -> None:
        self.service_code: str = source["ServiceCode"]
        self.quota_code: str = source["QuotaCode"]
        self.service_name: str = source["ServiceName"]
        self.quota_name: str = source["QuotaName"]
        self.value: float = source["Value"]
        self.adjustable: bool = source["Adjustable"]
        self.usage_metric: Dict = source.get("UsageMetric", {})

        self.metric_values: List[float] = []
        self.collection_query: Dict = {}
        self.internal_id: str = ""

    @property
    def service_code(self):
        return self._service_code

    @property
    def quota_code(self):
        return self._quota_code

    @property
    def service_name(self):
        return self._service_name

    @property
    def quota_name(self):
        return self._quota_name

    @property
    def value(self):
        return self._value

    @property
    def adjustable(self):
        return self._adjustable

    @property
    def metric_values(self):
        return self._metric_values

    @metric_values.setter
    def metric_values(self, value: List[float]):
        self._metric_values = value

    @property
    def collection_query(self):
        return self._collection_query

    @collection_query.setter
    def collection_query(self, value: Dict):
        self._collection_query = value

    @property
    def internal_id(self):
        return self._internal_id

    @internal_id.setter
    def internal_id(self, value: str):
        self._internal_id = value

    @property
    def usage_metric(self):
        return self._usage_metric
