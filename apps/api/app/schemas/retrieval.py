from pydantic import BaseModel, Field


class RetrievalQueryRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    language: str = Field(default="en", min_length=2, max_length=16)
    corpora: list[str] = Field(default_factory=lambda: ["quran", "hadith", "tafsir"], min_length=1, max_length=5)
    limit: int = Field(default=12, ge=1, le=50)


class RetrievalEvidenceView(BaseModel):
    chunk_id: str
    corpus_type: str
    canonical_reference: str
    exact_text: str
    text_sha256: str
    source_edition_id: str
    source_passage_id: str
    attribution: str
    licence: str
