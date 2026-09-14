from __future__ import annotations

import hashlib
from dataclasses import dataclass

import boto3
from botocore.config import Config

from app.core.config import get_settings


@dataclass(frozen=True, slots=True)
class ObjectDigest:
    digest: str
    byte_size: int


def calculate_object_digest(object_key: str, algorithm: str) -> ObjectDigest:
    if algorithm not in {"sha256", "sha512"}:
        raise ValueError("Unsupported digest algorithm")
    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=str(settings.s3_endpoint),
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
        config=Config(connect_timeout=5, read_timeout=20, retries={"max_attempts": 2}),
    )
    response = client.get_object(Bucket=settings.s3_bucket, Key=object_key)
    hasher = hashlib.new(algorithm)
    byte_size = 0
    body = response["Body"]
    try:
        for chunk in iter(lambda: body.read(1024 * 1024), b""):
            hasher.update(chunk)
            byte_size += len(chunk)
    finally:
        body.close()
    return ObjectDigest(digest=hasher.hexdigest(), byte_size=byte_size)
