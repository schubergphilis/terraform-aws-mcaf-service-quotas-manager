provider "aws" {
  region = "eu-west-1"
}

module "service_quotas_manager" {
  source = "../.."

  quotas_manager_configuration = [{
    account_id = "123456789000"
    role_name  = "ServiceQuotaManagerRole"
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
  }]
}
