data "archive_file" "service_quotas_manager_source" {
  type        = "zip"
  source_dir  = "${path.module}/service_quotas_manager"
  output_path = "service_quotas_manager.zip"
}

module "service_quotas_manager_lambda" {
  source  = "schubergphilis/mcaf-lambda/aws"
  version = "~> 1.1.2"

  #checkov:skip=CKV_AWS_338:Ensure CloudWatch log groups retains logs for at least 1 year
  filename = data.archive_file.service_quotas_manager_source.output_path

  name                        = "ServiceQuotasManager"
  create_policy               = false
  description                 = "Service Quotas Manager Lambda Function"
  handler                     = "service_quotas_manager.service_quotas_manager.handler"
  kms_key_arn                 = var.kms_key_arn
  log_retention               = 90
  memory_size                 = 256
  retries                     = 0
  role_arn                    = aws_iam_role.service_quotas_manager_execution_role.arn
  runtime                     = "python3.11"
  security_group_egress_rules = var.security_group_egress_rules
  subnet_ids                  = var.subnet_ids
  timeout                     = 300

  environment = {
    POWERTOOLS_LOG_LEVEL    = "INFO"
    POWERTOOLS_SERVICE_NAME = "ServiceQuotasManager"
  }

  # Use a AWS provided layer to include Powertools to simplify the redistribution process.
  # Also see https://docs.powertools.aws.dev/lambda/python/latest/#lambda-layer.
  layers = [
    "arn:aws:lambda:${data.aws_region.current.name}:017000801446:layer:AWSLambdaPowertoolsPythonV2:58"
  ]

  tags = var.tags
}

resource "aws_iam_role" "service_quotas_manager_execution_role" {
  name                 = "${var.execution_role.name_prefix}-${data.aws_region.current.name}"
  assume_role_policy   = file("${path.module}/templates/lambda_assume_role_policy.json")
  path                 = var.execution_role.path
  permissions_boundary = var.execution_role.permissions_boundary
  tags                 = var.tags
}

resource "aws_iam_policy" "service_quotas_manager_execution_policy" {
  name = "ServiceQuotasManagerExecutionPolicy-${data.aws_region.current.name}"

  policy = templatefile("${path.module}/templates/lambda_execution_policy.json.tpl", {
    account_id                        = data.aws_caller_identity.current.id
    assumable_role_arns               = jsonencode(local.assumable_role_arns)
    kms_key_arn                       = var.kms_key_arn
    region_name                       = data.aws_region.current.name
    service_quotas_manager_bucket_arn = module.service_quotas_manager_bucket.arn
  })
}

resource "aws_iam_role_policy_attachment" "service_quotas_manager_vpc_access" {
  role       = aws_iam_role.service_quotas_manager_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy_attachment" "service_quotas_manager_execution_policy_attach" {
  role       = aws_iam_role.service_quotas_manager_execution_role.name
  policy_arn = aws_iam_policy.service_quotas_manager_execution_policy.arn
}
