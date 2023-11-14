module "service_quotas_manager_bucket" {
  source = "github.com/schubergphilis/terraform-aws-mcaf-s3?ref=v0.11.0"
  name   = "${var.bucket_prefix}service-quota-manager-${data.aws_region.current.name}"
  tags   = var.tags
}

resource "aws_s3_object" "service_quotas_manager_config" {
  bucket  = module.service_quotas_manager_bucket.name
  key     = "quotas_manager_config.json"
  content = jsonencode(var.quotas_manager_configuration)
}
