module "service_quotas_manager_bucket" {
  source  = "schubergphilis/mcaf-s3/aws"
  version = "~> 0.12.0"

  name          = var.bucket_name
  name_prefix   = var.bucket_name == null ? var.bucket_prefix : null
  force_destroy = true
  kms_key_arn   = var.kms_key_arn
  versioning    = true
  tags          = var.tags

  lifecycle_rule = [
    {
      id     = "default"
      status = "Enabled"

      abort_incomplete_multipart_upload = {
        days_after_initiation = 7
      }

      noncurrent_version_expiration = {
        noncurrent_days = 14
      }
    }
  ]
}

resource "aws_s3_object" "service_quotas_manager_config" {
  bucket  = module.service_quotas_manager_bucket.name
  key     = "quotas_manager_config.json"
  content = jsonencode(var.quotas_manager_configuration)
}
