output "vpc_id" {
  value = module.networking.vpc_id
}

output "eks_cluster_name" {
  value = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "eks_oidc_provider_arn" {
  value = module.eks.oidc_provider_arn
}

output "database_endpoint" {
  value = module.database.endpoint
}

output "cache_primary_endpoint" {
  value = module.cache.primary_endpoint_address
}

output "kafka_bootstrap_brokers" {
  value = module.message_queue.bootstrap_brokers_plaintext
}

output "artefacts_bucket_name" {
  value = module.object_storage.bucket_name
}

output "control_api_secret_arn" {
  value = module.secrets.control_api_secret_arn
}

output "worker_secret_arn" {
  value = module.secrets.worker_secret_arn
}

output "web_secret_arn" {
  value = module.secrets.web_secret_arn
}

output "configure_kubectl" {
  description = "Command to update local kubeconfig against this cluster once it exists."
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}
