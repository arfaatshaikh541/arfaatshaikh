from pydantic import BaseModel, Field


class AIStatusResponse(BaseModel):
    mode: str
    provider: str
    available: bool
    external_ai_enabled: bool


class AIGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


class AIGenerateResponse(BaseModel):
    available: bool
    provider: str
    text: str | None = None
    error: str | None = None
