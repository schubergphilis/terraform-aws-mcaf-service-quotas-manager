variable "bucket_prefix" {
  description = "The prefix for the service quotas manager configuration bucket."
  type        = string
  default     = "service-quotas-manager"
}

variable "bucket_name" {
  description = "The optional name for the service quotas manager configuration bucket, overrides `bucket_prefix`."
  type        = string
  default     = null
}

variable "execution_role" {
  description = "Configuration of the IAM role to assume to execute the service quotas manager lambda"
  type = object({
    name_prefix          = optional(string, "ServiceQuotasManagerExecutionRole")
    path                 = optional(string, "/")
    permissions_boundary = optional(string, null)
  })
  default = {}

  validation {
    condition     = can(regex("^/.*?/$", var.execution_role.path)) || var.execution_role.path == "/"
    error_message = "The 'path' must start and end with '/' or be '/'."
  }
}

variable "kms_key_arn" {
  description = "The ARN of the KMS key to use with the configuration S3 bucket and scheduler"
  type        = string
}

variable "quotas_manager_configuration" {
  description = "The configuration for the service quotas manager"
  type = list(object({
    account_id        = string
    role_name         = optional(string, "ServiceQuotasManagerRole")
    role_path         = optional(string, "/")
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
    condition     = length(var.quotas_manager_configuration) == length(distinct(var.quotas_manager_configuration[*].account_id))
    error_message = "quotas manager configuration items needs to have a unique account_id defined"
  }

  validation {
    condition     = alltrue([for config in var.quotas_manager_configuration : (can(regex("^/.*?/$", config.role_path)) || config.role_path == "/")])
    error_message = "Each 'role_path' must start and end with '/' or be '/'."
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
