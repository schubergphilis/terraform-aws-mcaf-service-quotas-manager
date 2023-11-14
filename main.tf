locals {
  assumable_role_arns = [
    for account_id, config in var.quotas_manager_configuration : "arn:aws:iam::${account_id}:role/${config.role_name}"
  ]
  has_increase_config = sum([for _, config in var.quotas_manager_configuration : (config.quota_increase_config == null ? 0 : length(config.quota_increase_config))]) > 0
}

data "aws_region" "current" {}

data "aws_caller_identity" "current" {}
