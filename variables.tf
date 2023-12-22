variable "bucket_prefix" {
  description = "The optional prefix for the service quota manager configuration bucket"
  type        = string
  default     = ""
}

variable "bucket_name" {
  description = "The optional name for the service quota manager configuration bucket, overrides bucket_prefix"
  type        = string
  default     = null
}

variable "kms_key_arn" {
  description = "The ARN of the KMS key to use with the configuration S3 bucket and scheduler"
  type        = string
  default     = null
}

variable "quotas_manager_configuration" {
  description = "The configuration for the service quota manager"
  type = list(object({
    accountid         = number
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

  validation {
    condition     = length(var.quotas_manager_configuration) == length(distinct(var.quotas_manager_configuration[*].accountid))
    error_message = "quotas manager configuration items needs to have a unique accountid defined"
  }
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
