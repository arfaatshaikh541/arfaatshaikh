variable "name_prefix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  description = "Private subnets the broker ENIs are placed in. MSK requires at least 2; 3 (one per AZ) is the production default used by the root environment."
  type        = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security groups allowed to reach the brokers -- in practice, the worker's EKS node/pod security group (apps/worker consumes via internal/consumer/kafka_adapter.go) and control-api if it ever produces directly."
  type        = list(string)
}

variable "kafka_version" {
  type    = string
  default = "3.6.0"
}

variable "broker_instance_type" {
  type    = string
  default = "kafka.m7g.large"
}

variable "number_of_broker_nodes" {
  description = "Total broker count across all AZs -- must be a multiple of length(var.subnet_ids)."
  type        = number
  default     = 3
}

variable "broker_ebs_volume_size_gb" {
  type    = number
  default = 200
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "tags" {
  type    = map(string)
  default = {}
}
