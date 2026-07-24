locals {
  name_prefix = "gridkeep-${var.environment}"

  common_tags = {
    Project     = "gridkeep"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

module "networking" {
  source = "../../modules/networking"

  name_prefix = local.name_prefix
  azs         = var.azs
  tags        = local.common_tags
}

module "eks" {
  source = "../../modules/eks"

  name_prefix         = local.name_prefix
  kubernetes_version  = var.eks_kubernetes_version
  vpc_id              = module.networking.vpc_id
  private_subnet_ids  = module.networking.private_subnet_ids
  node_instance_types = var.eks_node_instance_types
  node_desired_size   = var.eks_node_desired_size
  node_min_size       = var.eks_node_min_size
  node_max_size       = var.eks_node_max_size
  tags                = local.common_tags
}

module "database" {
  source = "../../modules/database"

  name_prefix                = local.name_prefix
  vpc_id                     = module.networking.vpc_id
  subnet_ids                 = module.networking.private_subnet_ids
  allowed_security_group_ids = [module.eks.cluster_security_group_id]
  instance_class             = var.db_instance_class
  multi_az                   = var.db_multi_az
  tags                       = local.common_tags
}

module "cache" {
  source = "../../modules/cache"

  name_prefix                = local.name_prefix
  vpc_id                     = module.networking.vpc_id
  subnet_ids                 = module.networking.private_subnet_ids
  allowed_security_group_ids = [module.eks.cluster_security_group_id]
  node_type                  = var.cache_node_type
  num_replicas               = var.cache_num_replicas
  tags                       = local.common_tags
}

module "message_queue" {
  source = "../../modules/message-queue"

  name_prefix                = local.name_prefix
  vpc_id                     = module.networking.vpc_id
  subnet_ids                 = module.networking.private_subnet_ids
  allowed_security_group_ids = [module.eks.cluster_security_group_id]
  broker_instance_type       = var.msk_broker_instance_type
  number_of_broker_nodes     = var.msk_number_of_broker_nodes
  tags                       = local.common_tags
}

module "object_storage" {
  source = "../../modules/object-storage"

  name_prefix = local.name_prefix
  bucket_name = var.artefacts_bucket_name
  tags        = local.common_tags
}

module "secrets" {
  source = "../../modules/secrets"

  name_prefix   = local.name_prefix
  database_url  = module.database.database_url
  redis_url     = module.cache.redis_url
  kafka_brokers = module.message_queue.bootstrap_brokers_plaintext
  s3_endpoint   = "s3.${var.aws_region}.amazonaws.com"
  s3_region     = var.aws_region
  s3_bucket     = module.object_storage.bucket_name
  s3_access_key = module.object_storage.access_key_id
  s3_secret_key = module.object_storage.secret_access_key
  tags          = local.common_tags
}
