# Service Quota Manager

This Service Quota Manager can be installed as part as an AWS Organization or individual account to manage service quotas and become (more) demonstrably in control of your service quotas. It currently supports the following:

1. Collection of service quotas and metrics per configured account, storing usage metrics centrally. Usage metrics can be derived from CloudWatch or AWS Config. The latter obviously requires AWS Config to be enabled in your target account.

1. Management of alarms on your service quotas with configurable thresholds per quota.

1. Automated requesting of service quota increases by configurable steps and motivations for support case updates (requires at least AWS Business Support).

## Prerequisites & considerations

* To support collection of usage metrics from AWS Config, AWS Config needs to be enabled in every target account in your organization. This is usually the case in enterprise organizations.

* To support automated motivation updates on service quota increase support tickets, at least AWS Business Support is required.

* This service quota manager relies on custom CloudWatch metrics (~$0.30/metric/month) and CloudWatch alarms (~$0.10/alarm/month). Services to monitor are configurable; more services monitored means increased cost.

* Most quotas are applied per region. This Service Quota Manager also operates in a single region. Install the Service Quota Manager in more regions in order to support more regions.

## Setup

### Target Accounts

#### Roles
This manager works by assuming roles in your target accounts from a single central management account to collect applied service quotas and usage metrics. Every account you want to be managed requires a role that can be assumed by the service quota manager. Setting up these roles is not part of this solution and could be part of your account baseline.

Each role requires the following trust policy:

```
{
	"Version": "2012-10-17",
	"Statement": [
		{
			"Sid": "AllowServiceQuotaManager",
			"Effect": "Allow",
			"Principal": {
				"AWS": "arn:aws:iam::<manager_account_id>:role/<service_quota_manager_lambda_role_arn>"
			},
			"Action": "sts:AssumeRole"
		}
	]
}
```

Each role requires the following permission policy:

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowCloudwatchMetricData",
            "Effect": "Allow",
            "Action": "cloudwatch:GetMetricData",
            "Resource": "*"
        },
        {
            "Sid": "AllowConfigReadAccess",
            "Effect": "Allow",
            "Action": "config:SelectResourceConfig",
            "Resource": "*"
        },
        {
            "Sid": "AllowServiceQuotaAccess",
            "Effect": "Allow",
            "Action": [
                "servicequotas:ListServices",
                "servicequotas:GetServiceQuota",
                "servicequotas:ListAWSDefaultServiceQuotas",
                "servicequotas:RequestServiceQuotaIncrease",
                "servicequotas:ListRequestedServiceQuotaChangeHistoryByQuota",
                "servicequotas:ListServiceQuotas",
                "servicequotas:GetAWSDefaultServiceQuota"
            ],
            "Resource": "*"
        }
    ]
}
```

### Management Account

#### Installation

TBD

#### Configuration

TBD
