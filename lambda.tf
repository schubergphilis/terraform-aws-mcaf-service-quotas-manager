data "archive_file" "service_quotas_manager_source" {
  type        = "zip"
  source_dir  = "${path.module}/service_quotas_manager/service_quotas_manager"
  output_path = "service_quotas_manager.zip"
}

module "service_quotas_manager_lambda" {
  source   = "github.com/schubergphilis/terraform-aws-mcaf-lambda?ref=v1.1.1"
  filename = data.archive_file.service_quotas_manager_source.output_path

  name          = "ServiceQuotasManager"
  create_policy = false
  description   = "Service Quotas Manager Lambda Function"
  handler       = "service_quotas_manager.service_quotas_manager.handler"
  memory_size   = 256
  retries       = 0
  role_arn      = aws_iam_role.service_quotas_manager_execution_role.arn
  runtime       = "python3.11"
  timeout       = 180
}

resource "aws_iam_role" "service_quotas_manager_execution_role" {
  name               = "ServiceQuotaManagerExecutionRole-${data.aws_region.current.name}"
  assume_role_policy = file("${path.module}/templates/lambda_assume_role_policy.json")
}

resource "aws_iam_role_policy" "service_quotas_manager_execution_policy" {
  name = "ServiceQuotaManagerExecutionPolicy-${data.aws_region.current.name}"
  role = aws_iam_role.service_quotas_manager_execution_role.id

  policy = templatefile("${path.module}/templates/lambda_execution_policy.json.tpl", {
    account_id                       = data.aws_caller_identity.current.id
    assumable_role_arns              = jsonencode(local.assumable_role_arns)
    region_name                      = data.aws_region.current.name
    service_quotas_manager_bucket_arn = module.service_quotas_manager_bucket.arn
  })
}
