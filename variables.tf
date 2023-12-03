variable "bucket_kms_key_arn" {
  description = "The ARN of the KMS key to use with the configuration S3 bucket"
  type        = string
  default     = null
}

variable "bucket_prefix" {
  description = "The optional prefix for the service quota manager configuration bucket"
  type        = string
  default     = ""
}

variable "quotas_manager_configuration" {
  description = "The configuration for the service quota manager"
  type = map(object({
    role_name         = string
    selected_services = optional(list(string), [])
    alerting_config = optional(object({
      default_threshold_perc = number
      notification_topic_arn = optional(string, "")
      rules = optional(
        map(
          map(
            object({
              threshold_perc = optional(number, null)
              ignore         = optional(bool, false)
            })
          )
        ), {}
      )
      }), {
      default_threshold_perc = 75
      notification_topic_arn = ""
      rules                  = {}
    })
    quota_increase_config = optional(map(map(object({
      step              = optional(number)
      factor            = optional(number)
      motivation        = string
      cc_mail_addresses = list(string)
    }))), {})
  }))
}

variable "schedule_kms_key_arn" {
  description = "The ARN of the KMS key to use with the configuration S3 bucket"
  type        = string
  default     = null
}

variable "schedule_timezone" {
  description = "The timezone to schedule service quota metric collection in"
  type        = string
  default     = "Europe/Amsterdam"
}

variable "tags" {
  description = "Tags to assign to resources created by this module"
  type        = map(string)
  default     = {}
}
