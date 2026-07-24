variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "production"
}

variable "azs" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "artefacts_bucket_name" {
  description = "Must be globally unique across all of S3. Override in terraform.tfvars before applying."
  type        = string
  default     = "gridkeep-production-artefacts"
}

variable "eks_kubernetes_version" {
  type    = string
  default = "1.31"
}

variable "eks_node_instance_types" {
  type    = list(string)
  default = ["m6i.xlarge"]
}

variable "eks_node_desired_size" {
  type    = number
  default = 3
}

variable "eks_node_min_size" {
  type    = number
  default = 3
}

variable "eks_node_max_size" {
  type    = number
  default = 9
}

variable "db_instance_class" {
  type    = string
  default = "db.r6g.xlarge"
}

variable "db_multi_az" {
  type    = bool
  default = true
}

variable "cache_node_type" {
  type    = string
  default = "cache.r7g.large"
}

variable "cache_num_replicas" {
  type    = number
  default = 1
}

variable "msk_broker_instance_type" {
  type    = string
  default = "kafka.m7g.large"
}

variable "msk_number_of_broker_nodes" {
  description = "Must be a multiple of length(var.azs)."
  type        = number
  default     = 3
}
