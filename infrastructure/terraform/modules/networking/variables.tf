variable "name_prefix" {
  description = "Prefix applied to every resource name/tag created by this module (e.g. \"gridkeep-production\")."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "azs" {
  description = "Availability zones to spread subnets and NAT gateways across. Three is the minimum for a production-grade, multi-AZ control plane (matches the EKS/RDS Multi-AZ requirements downstream)."
  type        = list(string)

  validation {
    condition     = length(var.azs) >= 3
    error_message = "At least 3 availability zones are required for production-grade multi-AZ placement."
  }
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for the public subnets, one per AZ, in the same order as var.azs."
  type        = list(string)
  default     = ["10.20.0.0/20", "10.20.16.0/20", "10.20.32.0/20"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for the private subnets, one per AZ, in the same order as var.azs. Every service in this platform (EKS nodes, RDS, ElastiCache, MSK) is placed here -- nothing but the load balancer/NAT layer touches the public subnets."
  type        = list(string)
  default     = ["10.20.128.0/20", "10.20.144.0/20", "10.20.160.0/20"]
}

variable "single_nat_gateway" {
  description = "If true, route all private subnets through one NAT gateway (cheaper, single point of failure). If false (the production default), provision one NAT gateway per AZ for high availability."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Additional tags merged onto every resource this module creates."
  type        = map(string)
  default     = {}
}
