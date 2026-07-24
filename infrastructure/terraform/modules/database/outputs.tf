output "endpoint" {
  value = aws_db_instance.this.address
}

output "port" {
  value = aws_db_instance.this.port
}

output "db_name" {
  value = aws_db_instance.this.db_name
}

output "master_username" {
  value = aws_db_instance.this.username
}

output "master_password" {
  value     = random_password.master.result
  sensitive = true
}

output "security_group_id" {
  value = aws_security_group.db.id
}

# Standard-format connection string control-api's config.go expects for
# DATABASE_URL (pgx v5 DSN via lib/pq-style URL). Callers needing the
# gridkeep/gridkeep_backup application roles instead of this master
# connection must build their own DSN from the individual outputs above --
# this one is for bootstrapping migrations only.
output "database_url" {
  value     = "postgres://${aws_db_instance.this.username}:${random_password.master.result}@${aws_db_instance.this.address}:${aws_db_instance.this.port}/${aws_db_instance.this.db_name}?sslmode=require"
  sensitive = true
}
