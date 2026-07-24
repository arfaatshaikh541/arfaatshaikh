# Cache module: ElastiCache Redis backing internal/platform/cache, used for
# the entitlements cache (subscriptions.Service) and session/rate-limit
# state. Encrypted at rest and in transit with an auth token -- go-redis's
# ParseURL (internal/platform/cache/redis.go) accepts the resulting
# rediss://:<token>@host:port/0 URL natively, no code change required.

resource "random_password" "auth_token" {
  # ElastiCache auth tokens must be 16-128 printable ASCII characters,
  # excluding '@', '"', and '/'.
  length           = 40
  special          = true
  override_special = "!#$%^&*()-_=+[]{}<>:?"
}

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name_prefix}-cache"
  subnet_ids = var.subnet_ids

  tags = var.tags
}

resource "aws_security_group" "cache" {
  name_prefix = "${var.name_prefix}-cache-"
  description = "Allows Redis (6379) only from the security groups explicitly passed in."
  vpc_id      = var.vpc_id

  ingress {
    description     = "Redis from EKS / authorised callers"
    from_port       = 6379
    to_port         = 6379
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
    Name = "${var.name_prefix}-cache-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id = "${var.name_prefix}-cache"
  description          = "${var.name_prefix} entitlements/session cache"

  engine         = "redis"
  engine_version = var.engine_version
  node_type      = var.node_type
  port           = 6379

  num_cache_clusters = var.num_replicas + 1

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = [aws_security_group.cache.id]

  automatic_failover_enabled = var.automatic_failover_enabled
  multi_az_enabled           = var.automatic_failover_enabled

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = random_password.auth_token.result

  auto_minor_version_upgrade = true

  snapshot_retention_limit = 7
  snapshot_window          = "05:00-06:00"
  maintenance_window       = "mon:06:30-mon:07:30"

  apply_immediately = false

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-cache"
  })
}
