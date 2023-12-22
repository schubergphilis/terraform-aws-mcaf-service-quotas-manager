provider "aws" {
  region = "eu-west-1"
}

module "service_quotas_manager" {
  source = "../.."

  quotas_manager_configuration = [{
    account_id = 123456789000
    role_name  = "ServiceQuotaManagerRole"
    alerting_config = {
      default_threshold_perc = 75
      notification_topic_arn = "arn:aws:sns:eu-west-1:123456789000:service-quotas-manager-notifications"
    }
  }]
}
