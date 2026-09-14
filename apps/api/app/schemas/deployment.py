from pydantic import BaseModel, Field, HttpUrl

class DeploymentConfigRequest(BaseModel):
    environment: str = Field(pattern="^(development|test|staging|production)$")
    public_base_url: HttpUrl
    allowed_origins: list[HttpUrl] = Field(default_factory=list, max_length=50)
    cookie_secure: bool
    secret_key_length: int = Field(ge=0, le=4096)
    image_digest: str = Field(min_length=1, max_length=160)
    migration_revision: str = Field(min_length=1, max_length=80)
    secrets_provider: str = Field(min_length=1, max_length=80)

class ReleaseReadinessRequest(BaseModel):
    environment: str = Field(pattern="^(development|test|staging|production)$")
    verification_statuses: dict[str, str] = Field(default_factory=dict)
    backup_rehearsal_passed: bool
    ai_release_gate_passed: bool
