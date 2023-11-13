import json
import os
from pathlib import Path

import botocore.session
import pytest

FIXTURES_PATH = f"{os.path.dirname(__file__)}/fixtures"

### Boto3 Client Fixtures


@pytest.fixture
def s3():
    return botocore.session.get_session().create_client("s3")


@pytest.fixture
def cloudwatch():
    return botocore.session.get_session().create_client("cloudwatch")


@pytest.fixture
def sts():
    return botocore.session.get_session().create_client("sts")


@pytest.fixture
def service_quotas():
    return botocore.session.get_session().create_client("service-quotas")


@pytest.fixture
def aws_config():
    return botocore.session.get_session().create_client("config")


@pytest.fixture
def support():
    return botocore.session.get_session().create_client("support")


### AWS Service Responses


@pytest.fixture
def service_quotas_list_all_services():
    return json.load(open(Path(FIXTURES_PATH) / "service_quotas.json"))[
        "list_services"
    ]["all"]


@pytest.fixture
def service_quotas_list_default_quotas_ec2():
    return json.load(open(Path(FIXTURES_PATH) / "service_quotas.json"))[
        "list_aws_default_service_quotas"
    ]["ec2"]


@pytest.fixture
def service_quotas_list_applied_quotas_ec2():
    return json.load(open(Path(FIXTURES_PATH) / "service_quotas.json"))[
        "list_service_quotas"
    ]["ec2"]


@pytest.fixture
def service_quotas_list_default_quotas_lambda():
    return json.load(open(Path(FIXTURES_PATH) / "service_quotas.json"))[
        "list_aws_default_service_quotas"
    ]["lambda"]


@pytest.fixture
def service_quotas_list_applied_quotas_lambda():
    return json.load(open(Path(FIXTURES_PATH) / "service_quotas.json"))[
        "list_service_quotas"
    ]["lambda"]
