data "archive_file" "service_quota_manager_source" {
  type        = "zip"
  source_dir  = "service_quota_manager/service_quota_manager"
  output_path = "service_quota_manager.zip"
}

module "service_quota_manager_lambda" {
  source   = "github.com/schubergphilis/terraform-aws-mcaf-lambda?ref=v1.1.1"
  filename = data.archive_file.service_quota_manager_source.output_path

  name          = "ServiceQuotaManager"
  create_policy = false
  description   = "Service Quota Manager Lambda Function"
  handler       = "service_quota_manager.service_quota_manager.handler"
  memory_size   = 256
  retries       = 0
  role_arn      = aws_iam_role.service_quota_manager_execution_role.arn
  runtime       = "python3.11"
  timeout       = 180
  tags          = local.tags
}

resource "aws_iam_role" "service_quota_manager_execution_role" {
  name               = "ServiceQuotaManagerExecutionRole"
  assume_role_policy = file("${path.module}/templates/lambda_assume_role_policy.json")
}

resource "aws_iam_role_policy" "service_quota_manager_execution_policy" {
  name = "ServiceQuotaManagerExecutionPolicy"
  role = aws_iam_role.service_quota_manager_execution_role.id

  policy = templatefile("${path.module}/templates/lambda_execution_policy.json.tpl", {
    account_id                       = data.aws_caller_identity.current.id
    assumable_role_arns              = jsonencode(local.assumable_role_arns)
    region_name                      = data.aws_region.current.name
    service_quota_manager_bucket_arn = module.service_quota_manager_bucket.arn
  })
}
