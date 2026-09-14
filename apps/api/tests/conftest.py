import os

os.environ.setdefault("WOI_ENVIRONMENT", "test")
os.environ.setdefault("WOI_DATABASE_URL", "postgresql+asyncpg://x:x@localhost:5432/x")
os.environ.setdefault("WOI_REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("WOI_CELERY_BROKER_URL", "redis://localhost:6379/1")
os.environ.setdefault("WOI_CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
os.environ.setdefault("WOI_S3_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("WOI_S3_ACCESS_KEY", "test")
os.environ.setdefault("WOI_S3_SECRET_KEY", "test-secret")
os.environ.setdefault("WOI_S3_BUCKET", "test")
os.environ.setdefault("WOI_ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault("WOI_SECRET_KEY", "test-secret-key-with-more-than-32-characters")
