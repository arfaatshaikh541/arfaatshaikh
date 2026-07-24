output "control_api_secret_arn" {
  value = aws_secretsmanager_secret.control_api.arn
}

output "worker_secret_arn" {
  value = aws_secretsmanager_secret.worker.arn
}

output "web_secret_arn" {
  value = aws_secretsmanager_secret.web.arn
}
