# Service Quotas Manager

![tests](https://github.com/schubergphilis/terraform-aws-mcaf-service-quotas-manager/actions/workflows/test.yml/badge.svg)

![Solution Architecture](./docs/architecture.png)

This Service Quotas Manager can be installed as part as an AWS Organization or individual account to manage service quotas and become (more) demonstrably in control of them. It currently supports the following:

1. Collection of service quotas and metrics per configured account, storing usage metrics centrally. Usage metrics can be derived from CloudWatch or AWS Config. The latter obviously requires AWS Config to be enabled in your target account.

1. Automated discovery of used services by querying AWS Cost Explorer.

1. Management of alarms on your service quotas with configurable thresholds per quota. Alarms can be disabled by omitting the alerting config.

1. Optionally an SNS topic can be provided as alarm action.

1. Automated requesting of service quota increases by configurable steps and motivations for support case updates (requires at least AWS Business Support and alarms to be enabled).

## Prerequisites & considerations

* To support collection of usage metrics from AWS Config, AWS Config needs to be enabled in every target account in your organization. This is usually the case in enterprise organizations.

* To support automated quota increase requests at least AWS Business Support is required.

* This service quota manager relies on custom CloudWatch metrics ($0.30/metric/month) and CloudWatch alarms ($0.10/alarm/month). Services to monitor are configurable; more services monitored means increased cost.

* Most quotas are applied per region. This Service Quota Manager also operates in a single region. Install the Service Quota Manager in more regions in order to support more regions.

## Setup

### Target Accounts

#### Roles
This manager works by assuming roles in your target accounts from a single central management account to collect applied service quotas and usage metrics. Every account you want to be managed requires a role that can be assumed by the service quota manager. Setting up these roles is not part of this solution but could be part of - for example - your account baseline.

Each role requires the following trust policy:

```json
{
	"Version": "2012-10-17",
	"Statement": [
	  {
			"Sid": "AllowServiceQuotaManager",
			"Effect": "Allow",
			"Principal": {
				"AWS": "arn:aws:iam::<manager_account_id>:role/ServiceQuotaManagerExecutionRole-<region_name>"
			},
			"Action": "sts:AssumeRole"
		}
	]
}
```

Each role requires the following policies attached:

1. AWS Managed policy `ServiceQuotasReadOnlyAccess`.
2. A custom policy with the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowConfigReadAccess",
      "Effect": "Allow",
      "Action": "config:SelectResourceConfig",
      "Resource": "*"
    },
    {
      "Sid": "AllowSupportAccess",
      "Effect": "Allow",
      "Action": [
        "support:DescribeSeverityLevels",
        "support:AddCommunicationToCase"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AllowOptionalCeAccessForServiceAutoDiscovery",
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
      ],
      "Resource": "*"
    },
    {
      "Sid": "AllowServiceQuotaAccess",
      "Effect": "Allow",
      "Action": [
          "servicequotas:RequestServiceQuotaIncrease"
      ],
      "Resource": "*"
    }
  ]
}
```

### Central Account

> [!TIP]
> Consider using a services account or audit account to deploy the service quotas manager in.

A minimal setup can be done like this:

```hcl
module "service_quotas_manager" {
  source = github.com/schubergphilis/terraform-aws-mcaf-service-quotas-manager?ref=v1.0.0

  quotas_manager_configuration = {
    "123456789000" = {
      role_name = "ServiceQuotaManagerRole"
      alerting_config = {
        default_threshold_perc = 75
        notification_topic_arn = "arn:aws:sns:eu-west-1:123456789000:service-quotas-manager-notifications"
      }
    }
  }
}
```

See the [infrastructure tests](https://github.com/schubergphilis/terraform-aws-mcaf-service-quotas-manager/blob/main/tests/service-quotas-manager.tftest.hcl) for more examples on how to configure thresholds and auto-increase rules.

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.6.0 |
| <a name="requirement_archive"></a> [archive](#requirement\_archive) | 2.4.0 |
| <a name="requirement_aws"></a> [aws](#requirement\_aws) | 5.25.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_archive"></a> [archive](#provider\_archive) | 2.4.0 |
| <a name="provider_aws"></a> [aws](#provider\_aws) | 5.25.0 |

## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_service_quotas_manager_bucket"></a> [service\_quotas\_manager\_bucket](#module\_service\_quotas\_manager\_bucket) | github.com/schubergphilis/terraform-aws-mcaf-s3 | v0.11.0 |
| <a name="module_service_quotas_manager_lambda"></a> [service\_quotas\_manager\_lambda](#module\_service\_quotas\_manager\_lambda) | github.com/schubergphilis/terraform-aws-mcaf-lambda | v1.1.2 |

## Resources

| Name | Type |
|------|------|
| [aws_cloudwatch_event_rule.trigger_service_quotas_manager_on_alarm](https://registry.terraform.io/providers/hashicorp/aws/5.25.0/docs/resources/cloudwatch_event_rule) | resource |
| [aws_cloudwatch_event_target.trigger_service_quotas_manager_on_alarm](https://registry.terraform.io/providers/hashicorp/aws/5.25.0/docs/resources/cloudwatch_event_target) | resource |
| [aws_iam_policy.service_quotas_manager_schedules](https://registry.terraform.io/providers/hashicorp/aws/5.25.0/docs/resources/iam_policy) | resource |
| [aws_iam_role.service_quotas_manager_execution_role](https://registry.terraform.io/providers/hashicorp/aws/5.25.0/docs/resources/iam_role) | resource |
| [aws_iam_role.service_quotas_manager_schedules](https://registry.terraform.io/providers/hashicorp/aws/5.25.0/docs/resources/iam_role) | resource |
| [aws_iam_role_policy.service_quotas_manager_execution_policy](https://registry.terraform.io/providers/hashicorp/aws/5.25.0/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy_attachment.service_quotas_manager_schedules](https://registry.terraform.io/providers/hashicorp/aws/5.25.0/docs/resources/iam_role_policy_attachment) | resource |
| [aws_lambda_permission.trigger_service_quotas_manager_on_alarm](https://registry.terraform.io/providers/hashicorp/aws/5.25.0/docs/resources/lambda_permission) | resource |
| [aws_s3_object.service_quotas_manager_config](https://registry.terraform.io/providers/hashicorp/aws/5.25.0/docs/resources/s3_object) | resource |
| [aws_scheduler_schedule.sqm_collect_service_quotas](https://registry.terraform.io/providers/hashicorp/aws/5.25.0/docs/resources/scheduler_schedule) | resource |
| [aws_scheduler_schedule_group.service_quotas_manager](https://registry.terraform.io/providers/hashicorp/aws/5.25.0/docs/resources/scheduler_schedule_group) | resource |
| [archive_file.service_quotas_manager_source](https://registry.terraform.io/providers/hashicorp/archive/2.4.0/docs/data-sources/file) | data source |
| [aws_caller_identity.current](https://registry.terraform.io/providers/hashicorp/aws/5.25.0/docs/data-sources/caller_identity) | data source |
| [aws_region.current](https://registry.terraform.io/providers/hashicorp/aws/5.25.0/docs/data-sources/region) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_bucket_kms_key_arn"></a> [bucket\_kms\_key\_arn](#input\_bucket\_kms\_key\_arn) | The ARN of the KMS key to use with the configuration S3 bucket | `string` | `null` | no |
| <a name="input_bucket_prefix"></a> [bucket\_prefix](#input\_bucket\_prefix) | The optional prefix for the service quota manager configuration bucket | `string` | `""` | no |
| <a name="input_quotas_manager_configuration"></a> [quotas\_manager\_configuration](#input\_quotas\_manager\_configuration) | The configuration for the service quota manager | <pre>map(object({<br>    role_name         = string<br>    selected_services = optional(list(string), [])<br>    alerting_config = optional(object({<br>      default_threshold_perc = number<br>      notification_topic_arn = optional(string, "")<br>      rules = optional(<br>        map(<br>          map(<br>            object({<br>              threshold_perc = number<br>            })<br>          )<br>        ), {}<br>      )<br>      }), {<br>      default_threshold_perc = 75<br>      notification_topic_arn = ""<br>      rules                  = {}<br>    })<br>    quota_increase_config = optional(map(map(object({<br>      step              = optional(number)<br>      factor            = optional(number)<br>      motivation        = string<br>      cc_mail_addresses = list(string)<br>    }))), {})<br>  }))</pre> | n/a | yes |
| <a name="input_schedule_kms_key_arn"></a> [schedule\_kms\_key\_arn](#input\_schedule\_kms\_key\_arn) | The ARN of the KMS key to use with the configuration S3 bucket | `string` | `null` | no |
| <a name="input_schedule_timezone"></a> [schedule\_timezone](#input\_schedule\_timezone) | The timezone to schedule service quota metric collection in | `string` | `"Europe/Amsterdam"` | no |
| <a name="input_tags"></a> [tags](#input\_tags) | Tags to assign to resources created by this module | `map(string)` | `{}` | no |

## Outputs

No outputs.
<!-- END_TF_DOCS -->

## Licensing

100% Open Source and licensed under the Apache License Version 2.0. See [LICENSE](https://github.com/schubergphilis/terraform-aws-mcaf-service-quotas-manager/blob/main/LICENSE) for full details.
