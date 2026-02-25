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

variable "kms_key_arn" {
  description = "The ARN of the KMS key to use with the configuration S3 bucket and scheduler"
  type        = string
}

variable "permissions_boundary" {
  type        = string
  default     = null
  description = "The ARN of the policy that is used to set the permissions boundary for the role."
}

variable "quotas_manager_configuration" {
  description = "The configuration for the service quotas manager"
  type = list(object({
    account_id        = string
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
}

variable "schedule_timezone" {
  description = "The timezone to schedule service quota metric collection in"
  type        = string
  default     = "Europe/Amsterdam"
}

variable "security_group_egress_rules" {
  type = list(object({
    cidr_ipv4                    = optional(string)
    cidr_ipv6                    = optional(string)
    description                  = string
    from_port                    = optional(number, 0)
    ip_protocol                  = optional(string, "-1")
    prefix_list_id               = optional(string)
    referenced_security_group_id = optional(string)
    to_port                      = optional(number, 0)
  }))
  default = [
    {
      description = "Default Security Group rule for Service Quota Manager Lambda"
      ip_protocol = "tcp"
      cidr_ipv4   = "0.0.0.0/0"
      to_port     = 443
    }
  ]
}

variable "subnet_ids" {
  description = "VPC subnets where Lambda is deployed"
  type        = list(string)
  default     = null
}

variable "tags" {
  description = "Tags to assign to resources created by this module"
  type        = map(string)
  default     = {}
}

variable "role_path" {
  description = "Namespaced IAM role path used when constructing the ServiceQuotasManagerRole ARN"
  type        = string
  default     = "/"

  validation {
    condition     = can(regex("^/.*?/$", var.role_path)) || var.role_path == "/"
    error_message = "The 'path' must start and end with '/' or be '/'."
  }
}

variable "role_name" {
  description = "Name of the IAM role used for the ServiceQuotasManager"
  type        = string
  default     = "ServiceQuotasManagerRole"
}
