variable "name_prefix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "allowed_security_group_ids" {
  type = list(string)
}

variable "engine_version" {
  type    = string
  default = "7.1"
}

variable "node_type" {
  type    = string
  default = "cache.r7g.large"
}

variable "num_replicas" {
  description = "Number of replica nodes in addition to the primary. The entitlements-cache fallback behaviour proven in apps/control-api/internal/app/chaos_test.go's TestEntitlementsSurviveRedisOutage means a total Redis outage is already a tested, survivable condition for reads -- replicas here are for read scaling and faster failover, not a hard availability dependency."
  type        = number
  default     = 1
}

variable "automatic_failover_enabled" {
  type    = bool
  default = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
