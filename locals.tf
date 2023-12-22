locals {
  assumable_role_arns = [
    for item in var.quotas_manager_configuration : "arn:aws:iam::${item.accountid}:role/${item.role_name}"
  ]
  has_increase_config = sum([for item in var.quotas_manager_configuration : (item.quota_increase_config == null ? 0 : length(item.quota_increase_config))]) > 0
}

data "aws_region" "current" {}

data "aws_caller_identity" "current" {}
