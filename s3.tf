module "service_quotas_manager_bucket" {
  source = "github.com/schubergphilis/terraform-aws-mcaf-s3?ref=v0.11.0"

  #checkov:skip=CKV_AWS_21:Ensure all data stored in the S3 bucket have versioning enabled
  #checkov:skip=CKV_TF_1:Ensure Terraform module sources use a commit hash
  #checkov:skip=CKV_AWS_300:Ensure S3 lifecycle configuration sets period for aborting failed uploads
  name          = "${var.bucket_prefix}service-quotas-manager-${data.aws_region.current.name}"
  force_destroy = true
  kms_key_arn   = var.bucket_kms_key_arn

  lifecycle_rule = [
    {
      id     = "default"
      status = "Enabled"

      abort_incomplete_multipart_upload = {
        days_after_initiation = 7
      }
    }
  ]

  tags = var.tags
}

resource "aws_s3_object" "service_quotas_manager_config" {
  bucket  = module.service_quotas_manager_bucket.name
  key     = "quotas_manager_config.json"
  content = jsonencode(var.quotas_manager_configuration)
}
