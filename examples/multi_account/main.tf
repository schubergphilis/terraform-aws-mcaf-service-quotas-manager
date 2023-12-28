provider "aws" {
  region = "eu-west-1"
}

data "aws_iam_policy_document" "kms_key_policy_service_quotas_manager" {
  # The following statements are required for the Service Quotas Manager
  # Additional statements for managing the key are required as well.

  #checkov:skip=CKV_AWS_111:Ensure IAM policies does not allow write access without constraints (false positive due to key policy resources)
  #checkov:skip=CKV_AWS_356:Ensure no IAM policies documents allow "*" as a statement's resource for restrictable actions (false positive due to key policy resources)
  statement {
    sid = "ServiceQuotasManagerAlarms"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey*",
    ]
    effect    = "Allow"
    resources = ["*"]

    principals {
      type = "Service"
      identifiers = [
        "cloudwatch.amazonaws.com"
      ]
    }
  }

  statement {
    sid = "Allow access for CloudWatch Logs"
    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey"
    ]
    effect    = "Allow"
    resources = ["*"]

    principals {
      type = "Service"
      identifiers = [
        "logs.eu-west-1.amazonaws.com"
      ]
    }

    condition {
      test     = "ArnLike"
      variable = "kms:EncryptionContext:aws:logs:arn"
      values   = ["arn:aws:logs:eu-west-1:123456789000:*"]
    }
  }

  statement {
    sid = "Encrypt and Decrypt permissions for AWS services"
    actions = [
      "kms:CreateGrant",
      "kms:Decrypt",
      "kms:DescribeKey",
      "kms:Encrypt",
      "kms:GenerateDataKey*",
      "kms:ListGrants",
      "kms:ReEncrypt*",
      "kms:RevokeGrant"
    ]
    effect    = "Allow"
    resources = ["*"]

    condition {
      test     = "StringLike"
      variable = "kms:ViaService"

      values = [
        "lambda.eu-west-1.amazonaws.com",
        "s3.eu-west-1.amazonaws.com"
      ]
    }

    principals {
      type = "AWS"
      identifiers = [
        "arn:aws:iam::123456789000:root"
      ]
    }
  }
}

module "service_quotas_manager_kms_key" {
  source = "github.com/schubergphilis/terraform-aws-mcaf-kms?ref=v0.3.0"

  name                = "service-quotas-manager"
  description         = "KMS key used for encrypting resources used by the service quotas manager"
  enable_key_rotation = true
  policy              = data.aws_iam_policy_document.kms_key_policy_service_quotas_manager.json
}

resource "aws_sns_topic" "service_quotas_manager" {
  name              = "ServiceQuotasManagerNotifications"
  kms_master_key_id = module.service_quotas_manager_kms_key.arn
}

resource "aws_sns_topic_policy" "service_quotas_manager" {
  arn    = aws_sns_topic.service_quotas_manager.arn
  policy = data.aws_iam_policy_document.service_quotas_manager.json
}

data "aws_iam_policy_document" "service_quotas_manager" {
  policy_id = "__default_policy_ID"

  statement {
    actions = [
      "SNS:Subscribe",
      "SNS:SetTopicAttributes",
      "SNS:RemovePermission",
      "SNS:Receive",
      "SNS:Publish",
      "SNS:ListSubscriptionsByTopic",
      "SNS:GetTopicAttributes",
      "SNS:DeleteTopic",
      "SNS:AddPermission",
    ]

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceOwner"

      values = [
        "123456789000"
      ]
    }

    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    resources = [
      aws_sns_topic.service_quotas_manager.arn
    ]

    sid = "__default_statement_ID"
  }
}

module "service_quotas_manager" {
  source = "../.."

  kms_key_arn = module.service_quotas_manager_kms_key.arn
  quotas_manager_configuration = [
    {
      account_id = "123456789000"
      alerting_config = {
        default_threshold_perc = 75
        notification_topic_arn = aws_sns_topic.service_quotas_manager.arn
      }
    },
    {
      account_id = "123456789001"
      selected_services = [
        "Amazon Virtual Private Cloud (Amazon VPC)",
        "Amazon DynamoDB"
      ]
      alerting_config = {
        default_threshold_perc = 60
        notification_topic_arn = aws_sns_topic.service_quotas_manager.arn
      }
    }
  ]
}
