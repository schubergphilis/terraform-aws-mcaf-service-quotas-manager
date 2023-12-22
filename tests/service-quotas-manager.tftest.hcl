run "setup_tests" {
  module {
    source = "./tests/setup"
  }
}

run "basic" {
  command = apply

  variables {
    bucket_prefix = "sqmtest-basic-"

    quotas_manager_configuration = [
      {
        account_id = "123456789000"
        role_name = "ServiceQuotaManagerRole"
        selected_services = [
          "AWS Lambda",
        ]
        alerting_config = {
          default_threshold_perc = 75
          notification_topic_arn = "arn:aws:sns:eu-west-1:123456789000:service-quotas-manager-notifications"
        }
      }
    ]
  }

  assert {
    condition     = length(aws_scheduler_schedule.sqm_collect_service_quotas) == 1
    error_message = "Expected 1 schedule per monitored account to be created."
  }

  assert {
    condition     = length(aws_cloudwatch_event_rule.trigger_service_quotas_manager_on_alarm) == 0
    error_message = "Expected no event rules for alarms if no increase config was defined."
  }

  assert {
    condition     = length(jsondecode(aws_iam_role_policy.service_quotas_manager_execution_policy.policy)["Statement"][2]["Resource"]) == 1
    error_message = "Expected the service quota manager to only assume a role in configured target accounts."
  }
}

run "increase_config" {
  command = apply

  variables {
    bucket_prefix = "sqmtest-increase-config-"
    quotas_manager_configuration = [
      {
        account_id = "123456789000"
        role_name = "ServiceQuotaManagerRole"
        selected_services = [
          "Amazon Virtual Private Cloud (Amazon VPC)",
          "Amazon Elastic Compute Cloud (Amazon EC2)",
          "AWS Lambda",
          "Amazon Elastic File System (EFS)",
          "Amazon DynamoDB",
          "Amazon Simple Storage Service (Amazon S3)"
        ]
        alerting_config = {
          default_threshold_perc = 75
          rules = {
            "AWS Lambda" = {
              "Elastic network interfaces per VPC" = {
                threshold_perc = 85
              }
            }
          }
        }
        quota_increase_config = {
          "AWS Lambda" = {
            "Elastic network interfaces per VPC" = {
              step              = 50
              motivation        = "We run a serverless integration platform that heavily relies on AWS Lambda. This account is a development account and we allow our developers to run feature environments to test the integrations they build in an isolated setting. In order to be able to grow the number of feature environments in this account we would like to request this quote increase. 50 Additional ENI's allow for running 1 additional feature environment, while limiting it to run on only a single AZ."
              cc_mail_addresses = ["devops_engineer@acme.com"]
            }
          }
        }
      }
    ]
  }

  assert {
    condition     = length(aws_scheduler_schedule.sqm_collect_service_quotas) == 1
    error_message = "Expected 1 schedule per monitored account to be created."
  }

  assert {
    condition     = length(aws_cloudwatch_event_rule.trigger_service_quotas_manager_on_alarm) == 1
    error_message = "Expected one event rule for alarms if no increase config was defined."
  }

  assert {
    condition     = length(jsondecode(aws_iam_role_policy.service_quotas_manager_execution_policy.policy)["Statement"][2]["Resource"]) == 1
    error_message = "Expected the service quota manager to only assume a role in configured target accounts."
  }
}

run "multi_account" {
  command = apply

  variables {
    bucket_prefix = "sqmtest-multi-account-"

    quotas_manager_configuration = [
      {
        account_id = "123456789000"
        role_name = "ServiceQuotaManagerRole"
        alerting_config = {
          default_threshold_perc = 75
          notification_topic_arn = "arn:aws:sns:eu-west-1:123456789000:service-quotas-manager-notifications"
        }
      },
      {
        account_id = "123456789001"
        role_name = "ServiceQuotaManagerRole"
        selected_services = [
          "Amazon Virtual Private Cloud (Amazon VPC)",
          "Amazon DynamoDB"
        ]
        alerting_config = {
          default_threshold_perc = 60
          notification_topic_arn = "arn:aws:sns:eu-west-1:123456789001:service-quotas-manager-notifications"
        }
      }
    ]
  }

  assert {
    condition     = length(aws_scheduler_schedule.sqm_collect_service_quotas) == 2
    error_message = "Expected 1 schedule per monitored account to be created."
  }

  assert {
    condition     = length(aws_cloudwatch_event_rule.trigger_service_quotas_manager_on_alarm) == 0
    error_message = "Expected one event rule for alarms if no increase config was defined."
  }

  assert {
    condition     = length(jsondecode(aws_iam_role_policy.service_quotas_manager_execution_policy.policy)["Statement"][2]["Resource"]) == 2
    error_message = "Expected the service quota manager to only assume a role in configured target accounts."
  }
}
