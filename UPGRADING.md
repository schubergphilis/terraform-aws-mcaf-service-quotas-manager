# Upgrading Notes

This document captures the required refactoring on your part when upgrading to a module version that contains breaking changes.

## Upgrading to v0.6.0

### Key Changes

- **`role_name` and `role_path` are now root-level variables**  
  Previously, these were configured inside the `execution_role` object. They must now be set at the module root if you need custom values.

- **`permissions_boundary` moved to a root variable**  
  Previously part of the `execution_role` object, it is now a top-level variable (`var.permissions_boundary`) that IAM roles reference directly.
