module "service_quota_manager_bucket" {
  source = "github.com/schubergphilis/terraform-aws-mcaf-s3?ref=v0.11.0"
  name   = "${var.bucket_prefix}service-quota-manager"
}

resource "aws_s3_object" "service_quota_manager_config" {
  bucket  = module.service_quota_manager_bucket.name
  key     = "quota_manager_config.json"
  content = jsonencode(var.quota_manager_configuration)
}
