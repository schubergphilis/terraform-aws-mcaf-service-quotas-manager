output "lambda_service_quotas_manager_role_arn" {
  value       = aws_iam_role.service_quotas_manager_execution_role.arn
  description = "ARN of the service quotas manager lambda execution role"
}
