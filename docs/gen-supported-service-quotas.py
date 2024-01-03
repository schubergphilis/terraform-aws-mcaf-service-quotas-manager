"""Generate a Markdown table for supported service quotas

This script generates a table for supported service quotas in Markdown format
to be used as documentation input for the project. The output can be redirected
towards an md file and should render to a proper table.

This script uses the boto3 library as a means to consume the AWS API. Credentials
can be set through any boto3 supported method. See
https://boto3.amazonaws.com/v1/documentation/api/latest/guide/quickstart.html#configuration
for the various ways of how to do that.

Run example: python3 docs/gen-supported-service-quotas.py > SUPPORTED_QUOTAS.md
"""

import json
import time

from dataclasses import dataclass
from typing import Dict, List

import boto3


@dataclass
class ServiceQuotaService:
    """Keeps statistics about all service quotas for a service."""

    name: str
    total_quotas: int = 0
    native_collection_support: int = 0
    added_collection_support: int = 0

    def total_supported(self) -> int:
        return self.native_collection_support + self.added_collection_support

    def coverage_pct(self) -> int:
        if self.total_quotas == 0:
            return 100
        return int((self.total_supported() * 100) / self.total_quotas)


sq_client = boto3.client("service-quotas")

supported_service_quotas: List[ServiceQuotaService] = []

# Read the file with custom collection queries
ccqs: Dict = json.load(
    open("service_quotas_manager/service_quotas_manager/custom_collection_queries.json")
)

# Retrieve all services in Service Quotas.
services_paginator = sq_client.get_paginator("list_services")
services_pages = services_paginator.paginate()

service_quotas_services = []
for services_page in services_pages:
    service_quotas_services += services_page["Services"]

# For each service, find default and applied service quotas. Build
# a dict with information about the coverage per service.
for service_quotas_service in service_quotas_services:
    sqs = ServiceQuotaService(name=service_quotas_service["ServiceName"])

    # Retrieve all default service quotas
    default_quotas_paginator = sq_client.get_paginator(
        "list_aws_default_service_quotas"
    )
    default_quotas_pages = default_quotas_paginator.paginate(
        ServiceCode=service_quotas_service["ServiceCode"]
    )

    default_quotas = [
        quota for page in default_quotas_pages for quota in page["Quotas"]
    ]
    sqs.total_quotas = len(default_quotas)

    # Retrieve all applied service quotas and index
    # by quota code.
    applied_quotas_paginator = sq_client.get_paginator("list_service_quotas")
    applied_quotas_pages = applied_quotas_paginator.paginate(
        ServiceCode=service_quotas_service["ServiceCode"]
    )

    applied_quotas_by_quota_code = {
        applied_quota["QuotaCode"]: applied_quota
        for applied_quotas_page in applied_quotas_pages
        for applied_quota in applied_quotas_page["Quotas"]
    }

    # For each default quota, see if there's an applied quota.
    # See if there's native- or added support for collecting
    # quota usage and count as such.
    for default_quota in default_quotas:
        quota = applied_quotas_by_quota_code.get(
            default_quota["QuotaCode"], default_quota
        )

        if quota.get("UsageMetric"):
            sqs.native_collection_support += 1
        elif quota["QuotaCode"] in ccqs.get(quota["ServiceCode"], {}):
            sqs.added_collection_support += 1

    supported_service_quotas.append(sqs)
    time.sleep(0.1)  # The service quotas API is rate limited.

# Generate the markdown required to display the information as table.
table_rows = [
    "| Service | Total Quotas | Supported by AWS | Supported by SQM | Coverage |",
    "| :--- | :---: | :---: | :---: | :---: |",
]

preamble = """# Supported Service Quotas

The Service Quotas Manager (SQM) works by collecting quota usage and comparing them against applicable quotas.
The table below shows an overview of all services in AWS Service Quotas and to what extend usage for their related
service quotas can be collected.

Please note that extending support is one of the goals of this project and an ongoing effort. Also, not all quotas
are eligable for support as their usage might only be available to AWS internally.
"""

for sqs in supported_service_quotas:
    table_rows.append(
        f"| {sqs.name} | {sqs.total_quotas} | {sqs.native_collection_support} | {sqs.added_collection_support} | {sqs.coverage_pct()}% |"
    )

# Create a row for totals
total_quotas = sum([sqs.total_quotas for sqs in supported_service_quotas])
total_supported = sum([sqs.total_supported() for sqs in supported_service_quotas])
total_coverage_pct = int((total_supported * 100) / total_quotas)

table_rows.append(
    f"| **Total** | "
    f"{total_quotas} | "
    f"{sum([sqs.native_collection_support for sqs in supported_service_quotas])} | "
    f"{sum([sqs.added_collection_support for sqs in supported_service_quotas])} | "
    f"{total_coverage_pct}% |"
)

print(preamble)
print("\n".join(table_rows))
