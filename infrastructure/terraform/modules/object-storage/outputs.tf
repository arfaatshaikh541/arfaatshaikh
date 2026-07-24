output "bucket_name" {
  value = aws_s3_bucket.artefacts.bucket
}

output "bucket_arn" {
  value = aws_s3_bucket.artefacts.arn
}

output "bucket_regional_domain_name" {
  value = aws_s3_bucket.artefacts.bucket_regional_domain_name
}

output "access_key_id" {
  value     = aws_iam_access_key.artefacts_service.id
  sensitive = true
}

output "secret_access_key" {
  value     = aws_iam_access_key.artefacts_service.secret
  sensitive = true
}
