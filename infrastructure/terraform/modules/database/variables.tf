variable "name_prefix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  description = "Private subnets the DB subnet group spans. Must cover at least 2 AZs for Multi-AZ."
  type        = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security groups allowed to reach Postgres on port 5432 -- in practice, the EKS cluster security group plus the backup-role's bastion/CI runner if one exists outside the cluster."
  type        = list(string)
}

variable "engine_version" {
  description = "Postgres major/minor version. Kept in lockstep with the version this platform's migrations (apps/control-api/internal/platform/db/migrations) are written and tested against: Postgres 16."
  type        = string
  default     = "16.4"
}

variable "instance_class" {
  type    = string
  default = "db.r6g.xlarge"
}

variable "allocated_storage_gb" {
  type    = number
  default = 200
}

variable "max_allocated_storage_gb" {
  description = "Ceiling for RDS storage autoscaling."
  type        = number
  default     = 1000
}

variable "multi_az" {
  type    = bool
  default = true
}

variable "db_name" {
  type    = string
  default = "gridkeep"
}

variable "master_username" {
  type    = string
  default = "gridkeep_admin"
}

variable "backup_retention_days" {
  description = "Automated RDS snapshot retention. Independent of, and in addition to, the logical pg_dump-based drill in docs/disaster-recovery/backup-and-restore-runbook.md -- that runbook's gridkeep_backup role and restore procedure apply equally to a manual pg_dump against this instance; RDS automated backups are the fast-recovery path, pg_dump is the portable/cross-environment path."
  type        = number
  default     = 14
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "performance_insights_enabled" {
  type    = bool
  default = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
