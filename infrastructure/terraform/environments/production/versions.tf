terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # Remote state lives in S3 with DynamoDB-based locking, provisioned once,
  # by hand, outside this stack (a backend's own storage can never be
  # created by the same `terraform apply` that uses it as backend). See
  # docs/deployment/production-deployment.md for the one-time bootstrap
  # commands. Left commented so `terraform init`/`validate`/`plan` still
  # work with local state before that bucket exists -- e.g. in this
  # sandbox, which has no live AWS account at all.
  #
  # backend "s3" {
  #   bucket         = "gridkeep-terraform-state"
  #   key            = "production/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "gridkeep-terraform-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}
