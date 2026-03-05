# Upgrading Notes

This document captures the required refactoring on your part when upgrading to a module version that contains breaking changes.

## Upgrading to v2.0.0

### Key Changes v2.0.0

This module now requires a minimum AWS provider version of 6.0 to support the region parameter. If you are using multiple AWS provider blocks, please read [migrating from multiple provider configurations](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/guides/enhanced-region-support#migrating-from-multiple-provider-configurations).

## Upgrading to v1.0.0

### Key Changes v1.0.0

To ensure scalability of this solution for large organizations, the role name and path that the execution lambda assumes to manage service quotas in target accounts are no longer configurable per account. Instead, they must be the same across all accounts and are configured at the module level.

**Why this change?**

AWS IAM managed policies have a size limit of 6,144 characters. When managing hundreds of accounts with per-account role ARNs in the IAM policy, this limit is exceeded. The wildcard pattern approach is the standard solution for multi-account AWS architectures at scale.

#### Variables v1.0.0

The following variables have been modified:

- `var.quotas_manager_configuration.[*].role_name` and `var.quotas_manager_configuration.[*].role_path` have been moved to `var.assume_role.name` and `var.assume_role.path`.
