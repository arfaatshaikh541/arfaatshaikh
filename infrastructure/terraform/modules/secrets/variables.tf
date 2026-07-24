variable "name_prefix" {
  type = string
}

variable "recovery_window_in_days" {
  description = "How long a deleted secret is recoverable before AWS permanently purges it. 0 allows immediate deletion (only appropriate for throwaway/test environments); production should keep the default."
  type        = number
  default     = 30
}

variable "database_url" {
  type      = string
  sensitive = true
}

variable "redis_url" {
  type      = string
  sensitive = true
}

variable "kafka_brokers" {
  description = "Comma-separated broker list for KAFKA_BROKERS (worker's config.go splits on \",\")."
  type        = string
}

variable "s3_endpoint" {
  type = string
}

variable "s3_region" {
  type = string
}

variable "s3_bucket" {
  type = string
}

variable "s3_access_key" {
  type      = string
  sensitive = true
}

variable "s3_secret_key" {
  type      = string
  sensitive = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
