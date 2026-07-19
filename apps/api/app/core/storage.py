"""S3-compatible object storage client (boto3, sync).

`boto3` has no async client, but neither call this module makes is a
blocking network operation in practice where it matters: `object_key_for`
is pure string formatting, and `presigned_download_url` signs a URL
locally without any request to the object store. The genuinely blocking
operations - `upload_bytes` and `download_bytes` - are only ever called
from Celery tasks (`worker.export_tasks`, `worker.csv_import_tasks`) or,
for `upload_bytes`, the CSV-import preview step (a small, one-shot
upload inline in the request - see `csv_import.services.preview_csv`),
never from a hot API request path, so neither risks blocking the event
loop in practice.

Bucket provisioning is deliberately not this module's job: a real S3
deployment's bucket is created by infrastructure/ops, not application
code, and having the app silently auto-create buckets on first use would
mask a real configuration error (wrong bucket name, wrong credentials)
behind a "helpful" side effect. If the configured bucket doesn't exist,
`upload_bytes` raises and the export is recorded as failed with a clear
error message - see `worker.export_tasks`.
"""

import boto3
from botocore.client import Config as BotoConfig

from app.core.config import get_settings


def get_s3_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
        use_ssl=settings.s3_use_ssl,
        config=BotoConfig(signature_version="s3v4"),
    )


def object_key_for_export(*, tenant_id: str, export_id: str, extension: str) -> str:
    """Tenant-prefixed so a bucket listing or a misconfigured policy can
    never leak one tenant's export path into another's - the same
    tenant-scoping discipline the rest of the schema enforces via RLS,
    applied to the one storage layer RLS can't reach."""
    return f"tenants/{tenant_id}/exports/{export_id}/export.{extension}"


def upload_bytes(*, key: str, data: bytes, content_type: str) -> int:
    settings = get_settings()
    client = get_s3_client()
    client.put_object(
        Bucket=settings.s3_bucket_name,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return len(data)


def download_bytes(*, key: str) -> bytes:
    settings = get_settings()
    client = get_s3_client()
    response = client.get_object(Bucket=settings.s3_bucket_name, Key=key)
    return response["Body"].read()


def presigned_download_url(*, key: str, filename: str, expires_in_seconds: int = 900) -> str:
    """Generated fresh on every call rather than stored - a stored
    presigned URL would eventually expire and become dead data. Signing
    is a local computation (an HMAC over the request parameters); it does
    not contact the object store, so this is safe to call from an async
    API request handler."""
    settings = get_settings()
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.s3_bucket_name,
            "Key": key,
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
        },
        ExpiresIn=expires_in_seconds,
    )
