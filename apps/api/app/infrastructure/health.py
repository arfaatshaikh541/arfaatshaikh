import asyncio
from dataclasses import asdict, dataclass

import boto3
from botocore.config import Config
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import database


@dataclass(frozen=True, slots=True)
class DependencyHealth:
    postgres: bool
    redis: bool
    object_storage: bool

    @property
    def ready(self) -> bool:
        return self.postgres and self.redis and self.object_storage

    def as_dict(self) -> dict[str, bool]:
        return {**asdict(self), "ready": self.ready}


async def check_dependencies() -> DependencyHealth:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)

    async def postgres_check() -> bool:
        try:
            async with database.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def redis_check() -> bool:
        try:
            return bool(await redis.ping())
        except Exception:
            return False

    def s3_check() -> bool:
        try:
            client = boto3.client(
                "s3",
                endpoint_url=str(settings.s3_endpoint),
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
                config=Config(connect_timeout=2, read_timeout=2, retries={"max_attempts": 1}),
            )
            client.head_bucket(Bucket=settings.s3_bucket)
            return True
        except Exception:
            return False

    try:
        async with asyncio.timeout(4):
            postgres, redis_ok, object_storage = await asyncio.gather(
                postgres_check(), redis_check(), asyncio.to_thread(s3_check)
            )
    except TimeoutError:
        postgres = redis_ok = object_storage = False
    finally:
        await redis.aclose()

    return DependencyHealth(
        postgres=postgres,
        redis=redis_ok,
        object_storage=object_storage,
    )
