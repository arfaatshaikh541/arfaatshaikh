# Object-storage module: the S3 bucket backing internal/platform/storage
# (workload/model artefacts, presigned-URL-only access -- see that
# package's own doc comment). Versioning is enabled here for the same
# reason storage.Connect enables it on the MinIO bucket locally: an
# artefact upload must never silently clobber an earlier one at the same
# key (see ObjectVersionID in internal/platform/storage).

resource "aws_s3_bucket" "artefacts" {
  bucket = var.bucket_name

  tags = merge(var.tags, {
    Name = var.bucket_name
  })
}

resource "aws_s3_bucket_versioning" "artefacts" {
  bucket = aws_s3_bucket.artefacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artefacts" {
  bucket = aws_s3_bucket.artefacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "artefacts" {
  bucket = aws_s3_bucket.artefacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "artefacts" {
  bucket = aws_s3_bucket.artefacts.id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

# control-api's storage.Client authenticates with a static access-key/secret
# pair (minio-go's credentials.NewStaticV4), the same shape whether the
# endpoint is MinIO locally or real S3 in production -- see
# apps/control-api/internal/platform/storage/storage.go. This IAM user is
# scoped to exactly this bucket and nothing else in the account.
resource "aws_iam_user" "artefacts_service" {
  name = "${var.name_prefix}-artefacts-service"
  tags = var.tags
}

resource "aws_iam_user_policy" "artefacts_service" {
  name = "${var.name_prefix}-artefacts-access"
  user = aws_iam_user.artefacts_service.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BucketLevel"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:GetBucketVersioning",
        ]
        Resource = aws_s3_bucket.artefacts.arn
      },
      {
        Sid    = "ObjectLevel"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:DeleteObjectVersion",
        ]
        Resource = "${aws_s3_bucket.artefacts.arn}/*"
      },
    ]
  })
}

resource "aws_iam_access_key" "artefacts_service" {
  user = aws_iam_user.artefacts_service.name
}
