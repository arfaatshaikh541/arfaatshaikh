import os
import secrets
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import get_settings
from app.core.rate_limit import get_redis

settings = get_settings()

# How long a generated download URL/token remains valid.
DOWNLOAD_URL_TTL_SECONDS = 10 * 60


class StorageAdapter(ABC):
    @abstractmethod
    def save(self, key: str, content: bytes, content_type: str) -> None: ...

    @abstractmethod
    def get_download_url(self, key: str) -> str: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...


def build_storage_key(*, tenant_id: uuid.UUID, module: str, entity_id: uuid.UUID, filename: str) -> str:
    """Tenant-namespaced, non-sequential path — never guessable from
    adjacent object keys."""
    safe_name = "".join(ch for ch in filename if ch.isalnum() or ch in "._-") or "file"
    return f"tenants/{tenant_id}/{module}/{entity_id}/{uuid.uuid4().hex}-{safe_name}"


class LocalDiskAdapter(StorageAdapter):
    """Development adapter. Files live under STORAGE_LOCAL_ROOT; "signed"
    download URLs are a short-lived, single-purpose random token stored
    in Redis (token -> key), redeemed by `GET /api/files/{token}` — the
    browser never learns the real storage key or gets a permanent URL.
    """

    def __init__(self) -> None:
        self.root = Path(settings.storage_local_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        return self.root / key

    def save(self, key: str, content: bytes, content_type: str) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def get_download_url(self, key: str) -> str:
        token = secrets.token_urlsafe(32)
        get_redis().set(f"filetoken:{token}", key, ex=DOWNLOAD_URL_TTL_SECONDS)
        return f"{settings.api_base_url}/api/files/{token}"

    def delete(self, key: str) -> None:
        path = self._path_for(key)
        if path.exists():
            os.remove(path)

    def read(self, key: str) -> bytes:
        return self._path_for(key).read_bytes()

    def resolve_token(self, token: str) -> str | None:
        value = get_redis().get(f"filetoken:{token}")
        return value if value else None


class S3Adapter(StorageAdapter):
    """Production adapter — any S3-compatible provider (AWS S3, MinIO,
    DigitalOcean Spaces, Backblaze B2, ...). REQUIRES EXTERNAL CREDENTIAL:
    S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY."""

    def __init__(self) -> None:
        import boto3

        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
        )
        self._bucket = settings.s3_bucket

    def save(self, key: str, content: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=content, ContentType=content_type)

    def get_download_url(self, key: str) -> str:
        return self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=DOWNLOAD_URL_TTL_SECONDS
        )

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)


_adapter: StorageAdapter | None = None


def get_storage_adapter() -> StorageAdapter:
    global _adapter
    if _adapter is None:
        _adapter = S3Adapter() if settings.storage_backend == "s3" else LocalDiskAdapter()
    return _adapter
