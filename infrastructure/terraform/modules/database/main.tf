# Database module: the single Postgres instance backing every RLS-protected
# table in apps/control-api/internal/platform/db/migrations. FORCE ROW LEVEL
# SECURITY is set on every one of those tables (see
# docs/security/tenant-isolation-audit.md), so the master username created
# here must never be the role control-api itself connects as in production --
# it exists only to run migrations and create the two lower-privilege roles
# the application actually uses:
#   - the `gridkeep` app role (control-api's own connection, subject to RLS)
#   - the `gridkeep_backup` role (BYPASSRLS, used only for pg_dump/pg_restore
#     per docs/disaster-recovery/backup-and-restore-runbook.md)
# Creating those two roles and running migrations is a deploy-time application
# step (make migrate / cmd/server's own migration runner), not something this
# module does -- Terraform provisions the instance, not its logical schema.

resource "random_password" "master" {
  length  = 32
  special = true
  # RDS rejects '/', '@', '"', and space in the master password.
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-db"
  subnet_ids = var.subnet_ids

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-db-subnet-group"
  })
}

resource "aws_security_group" "db" {
  name_prefix = "${var.name_prefix}-db-"
  description = "Allows Postgres (5432) only from the security groups explicitly passed in (the EKS cluster, never 0.0.0.0/0)."
  vpc_id      = var.vpc_id

  ingress {
    description     = "Postgres from EKS / authorised callers"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = var.allowed_security_group_ids
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-db-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# Forces every client connection to use TLS and disables the plaintext
# fallback -- this is the RDS-side half of the "no explicit TLS
# configuration in application code, deliberately left to the layer that
# terminates it" gap flagged as informational in
# docs/security/cryptographic-review.md. rds.force_ssl=1 is what actually
# closes that gap for the database connection specifically.
resource "aws_db_parameter_group" "this" {
  name_prefix = "${var.name_prefix}-pg16-"
  family      = "postgres16"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  parameter {
    name         = "log_connections"
    value        = "1"
    apply_method = "pending-reboot"
  }

  parameter {
    name         = "log_disconnections"
    value        = "1"
    apply_method = "pending-reboot"
  }

  tags = var.tags

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_db_instance" "this" {
  identifier     = "${var.name_prefix}-db"
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage_gb
  max_allocated_storage = var.max_allocated_storage_gb
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.master_username
  password = random_password.master.result
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.this.name
  parameter_group_name   = aws_db_parameter_group.this.name
  vpc_security_group_ids = [aws_security_group.db.id]

  multi_az            = var.multi_az
  publicly_accessible = false

  backup_retention_period = var.backup_retention_days
  backup_window           = "03:00-04:00"
  maintenance_window      = "mon:04:30-mon:05:30"
  copy_tags_to_snapshot   = true

  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.name_prefix}-db-final"

  performance_insights_enabled = var.performance_insights_enabled

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  auto_minor_version_upgrade = true

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-db"
  })
}
