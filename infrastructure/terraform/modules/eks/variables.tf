variable "name_prefix" {
  type = string
}

variable "kubernetes_version" {
  description = "EKS control-plane Kubernetes version."
  type        = string
  default     = "1.31"
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  description = "Subnets the EKS control plane ENIs and worker nodes are placed in. The control plane's API endpoint is never exposed to the public subnets by this module (see cluster_endpoint_public_access)."
  type        = list(string)
}

variable "cluster_endpoint_public_access" {
  description = "Whether the EKS API server endpoint is reachable from the public internet at all (still access-list-restricted by cluster_endpoint_public_access_cidrs when true). Production default is false: the control plane is reached only through a bastion/VPN inside the VPC, consistent with this platform's \"never expose infrastructure credentials/access to anything the browser can reach\" rule extended to cluster administration itself."
  type        = bool
  default     = false
}

variable "cluster_endpoint_public_access_cidrs" {
  type    = list(string)
  default = []
}

variable "node_instance_types" {
  type    = list(string)
  default = ["m6i.xlarge"]
}

variable "node_desired_size" {
  type    = number
  default = 3
}

variable "node_min_size" {
  type    = number
  default = 3
}

variable "node_max_size" {
  type    = number
  default = 9
}

variable "node_disk_size_gb" {
  type    = number
  default = 100
}

variable "tags" {
  type    = map(string)
  default = {}
}
