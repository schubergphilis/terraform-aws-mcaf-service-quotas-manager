import json

import jmespath


class TestCustomCollectionQueries:
    def test_custom_collection_queries(self, aws_config_expression_results):
        all_queries = json.load(
            open("service_quotas_manager/custom_collection_queries.json")
        )
        for service_code in all_queries:
            for quota_code, defs in all_queries[service_code].items():
                try:
                    assert (
                        float(
                            jmespath.search(
                                defs["parameters"]["jmespath"],
                                aws_config_expression_results[service_code][quota_code],
                            )
                        )
                        == 2.0
                    )
                except AssertionError as ex:
                    print(
                        f"Failed JMESPath search of {defs['parameters']['jmespath']} for {service_code} / {quota_code}"
                    )
                    raise ex
