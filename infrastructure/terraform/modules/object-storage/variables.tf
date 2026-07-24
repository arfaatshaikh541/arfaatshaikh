variable "name_prefix" {
  type = string
}

variable "bucket_name" {
  description = "Globally-unique S3 bucket name. Maps directly to control-api's S3_BUCKET_ARTEFACTS (default \"gridkeep-artefacts\" locally against MinIO)."
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
