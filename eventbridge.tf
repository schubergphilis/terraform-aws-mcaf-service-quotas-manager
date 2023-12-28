resource "aws_cloudwatch_event_rule" "trigger_service_quotas_manager_on_alarm" {
  count = local.has_increase_config ? 1 : 0

  name        = "ServiceQuotaManagerIncreaserOnAlarm"
  description = "Event rule to trigger the Service Quota Manager if a quota reaches its configured threshold."
  tags        = var.tags

  event_pattern = jsonencode({
    "source" : ["aws.cloudwatch"],
    "detail-type" : ["CloudWatch Alarm State Change"],
    "detail" : {
      "alarmName" : [{
        "prefix" : "Service Quota"
      }],
      "state" : {
        "value" : ["ALARM"]
      }
    }
  })
}

resource "aws_cloudwatch_event_target" "trigger_service_quotas_manager_on_alarm" {
  count = local.has_increase_config ? 1 : 0

  arn  = module.service_quotas_manager_lambda.arn
  rule = aws_cloudwatch_event_rule.trigger_service_quotas_manager_on_alarm[0].name

  input_transformer {
    input_paths = {
      alarm = "$.detail"
    }

    input_template = "{\"action\": \"IncreaseServiceQuota\",\"alarm\": <alarm>,\"config_bucket\": \"${module.service_quotas_manager_bucket.name}\",\"config_key\": \"${aws_s3_object.service_quotas_manager_config.key}\"}"
  }

  retry_policy {
    maximum_event_age_in_seconds = 60
    maximum_retry_attempts       = 0
  }
}

resource "aws_lambda_permission" "trigger_service_quotas_manager_on_alarm" {
  count          = local.has_increase_config ? 1 : 0
  action         = "lambda:InvokeFunction"
  function_name  = module.service_quotas_manager_lambda.name
  principal      = "events.amazonaws.com"
  source_account = data.aws_caller_identity.current.account_id
  source_arn     = aws_cloudwatch_event_rule.trigger_service_quotas_manager_on_alarm[0].arn
}

resource "aws_scheduler_schedule_group" "service_quotas_manager" {
  name = "ServiceQuotaManager"
  tags = var.tags
}

resource "aws_scheduler_schedule" "sqm_collect_service_quotas" {
  for_each = { for cfg in var.quotas_manager_configuration : cfg.account_id => cfg }

  #checkov:skip=CKV_AWS_297:Ensure EventBridge Scheduler Schedule uses Customer Managed Key (CMK)
  name                         = "sqm-collect-service-quotas-${each.key}"
  group_name                   = aws_scheduler_schedule_group.service_quotas_manager.name
  schedule_expression          = "cron(0 * ? * * *)"
  schedule_expression_timezone = var.schedule_timezone

  flexible_time_window {
    mode                      = "FLEXIBLE"
    maximum_window_in_minutes = 5
  }

  target {
    arn      = module.service_quotas_manager_lambda.arn
    role_arn = aws_iam_role.service_quotas_manager_schedules.arn

    input = jsonencode({
      account_id    = each.key
      config_bucket = aws_s3_object.service_quotas_manager_config.bucket
      config_key    = aws_s3_object.service_quotas_manager_config.key
      action        = "CollectServiceQuotas"
    })
  }
}

resource "aws_iam_role" "service_quotas_manager_schedules" {
  name = "ServiceQuotaManagerSchedulerRole-${data.aws_region.current.name}"
  tags = var.tags

  assume_role_policy = templatefile("${path.module}/templates/service_quotas_manager_scheduler_assume_role_policy.json.tpl", {
    account_id = data.aws_caller_identity.current.account_id
  })
}

resource "aws_iam_policy" "service_quotas_manager_schedules" {
  name = "ServiceQuotaManagerSchedulerPolicy-${data.aws_region.current.name}"
  path = "/"
  tags = var.tags

  policy = templatefile("${path.module}/templates/service_quotas_manager_scheduler_policy.json.tpl", {
    service_quotas_manager_lambda_arn = module.service_quotas_manager_lambda.arn
  })
}

resource "aws_iam_role_policy_attachment" "service_quotas_manager_schedules" {
  role       = aws_iam_role.service_quotas_manager_schedules.name
  policy_arn = aws_iam_policy.service_quotas_manager_schedules.arn
}
