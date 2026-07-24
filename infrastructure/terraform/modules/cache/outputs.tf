output "primary_endpoint_address" {
  value = aws_elasticache_replication_group.this.primary_endpoint_address
}

output "port" {
  value = 6379
}

output "security_group_id" {
  value = aws_security_group.cache.id
}

output "auth_token" {
  value     = random_password.auth_token.result
  sensitive = true
}

output "redis_url" {
  description = "TLS + auth-token connection string in the exact form go-redis's ParseURL (internal/platform/cache/redis.go) expects for REDIS_URL."
  value       = "rediss://:${random_password.auth_token.result}@${aws_elasticache_replication_group.this.primary_endpoint_address}:6379/0"
  sensitive   = true
}
