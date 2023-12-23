import json

import jmespath
import pytest


class TestCustomCollectionQueries:
    @pytest.fixture
    def expression_results(self):
        return {
            "L-0263D0A3": [{"resourceId": "eip-001"}, {"resourceId": "eip-002"}],
            "L-FB451C26": [{"resourceId": "lt-001"}, {"resourceId": "lt-002"}],
            "L-9FEE3D26": [{"resourceId": "eni-001"}, {"resourceId": "eni-002"}],
            "L-DC2B2D3D": [{"resourceId": "bucket-001"}, {"resourceId": "bucket-002"}],
            "L-407747CB": [
                {"vpcId": "vpc-001", "COUNT(*)": 1},
                {"vpcId": "vpc-002", "COUNT(*)": 2},
            ],
            "L-589F43AA": [
                {"vpcId": "vpc-001", "COUNT(*)": 1},
                {"vpcId": "vpc-002", "COUNT(*)": 2},
            ],
            "L-A4707A72": [{"resourceId": "igw-001"}, {"resourceId": "igw-002"}],
            "L-B4A6D682": [
                {"vpcId": "vpc-001", "COUNT(*)": 1},
                {"vpcId": "vpc-002", "COUNT(*)": 2},
            ],
            "L-DF5E4CA3": [{"resourceId": "eni-001"}, {"resourceId": "eni-002"}],
            "L-E79EC296": [{"resourceId": "sg-001"}, {"resourceId": "sg-002"}],
            "L-F678F1CE": [{"resourceId": "vpc-001"}, {"resourceId": "vpc-002"}],
            "L-F98FE922": [{"resourceId": "tbl-001"}, {"resourceId": "tbl-002"}],
            "L-F7858A77": [
                {"configuration": {"globalSecondaryIndexes": ["a", "b"]}},
                {"configuration": {"globalSecondaryIndexes": ["a"]}},
            ],
            "L-AA0FF27B": [
                {"configuration": {"endpointConfiguration": {"types": ["REGIONAL"]}}},
                {"configuration": {"endpointConfiguration": {"types": ["REGIONAL"]}}},
            ],
            "L-A966AB5C": [
                {"configuration": {"endpointConfiguration": {"types": ["PRIVATE"]}}},
                {"configuration": {"endpointConfiguration": {"types": ["PRIVATE"]}}},
            ],
            "L-B97207D0": [
                {"configuration": {"endpointConfiguration": {"types": ["EDGE"]}}},
                {"configuration": {"endpointConfiguration": {"types": ["EDGE"]}}},
            ],
            "L-379E48B0": [
                {"relationships": [{"resourceType": "AWS::ApiGateway::Stage"}]},
                {
                    "relationships": [
                        {"resourceType": "AWS::ApiGateway::Stage"},
                        {"resourceType": "AWS::ApiGateway::Stage"},
                    ]
                },
            ],
        }

    def test_custom_collection_queries(self, expression_results):
        all_queries = json.load(
            open("service_quotas_manager/custom_collection_queries.json")
        )
        for service in all_queries:
            for quota_code, defs in all_queries[service].items():
                assert (
                    float(
                        jmespath.search(
                            defs["parameters"]["jmespath"],
                            expression_results[quota_code],
                        )
                    )
                    == 2.0
                )
