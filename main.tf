locals {
  assumable_role_arns = [
    for account_id, config in var.quota_manager_configuration : "arn:aws:iam::${account_id}:role/${config.role_name}"
  ]
  has_increase_config = sum([for _, config in var.quota_manager_configuration : length(config.quota_increase_config)]) > 0
}

data "aws_region" "current" {}

data "aws_caller_identity" "current" {}
