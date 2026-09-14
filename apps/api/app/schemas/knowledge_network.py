from __future__ import annotations
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

RelationshipType = Literal['explains','supports','authenticates','references','narrated_by','revealed_in','mentions','contradicts_claim','related_topic','prerequisite','continuation_of','derived_from','contextualises','topic_membership']
EntityType = Literal['quran_ayah','hadith_narration','tafsir_entry','topic','lesson','course','scholar','research','dua','prophet','companion','place','historical_event']

class CanonicalEntityInput(BaseModel):
    canonical_key: str = Field(min_length=3, max_length=220, pattern=r'^[a-z0-9][a-z0-9:._-]+$')
    entity_type: EntityType
    source_entity_id: UUID
    english_label: str = Field(min_length=1, max_length=320)
    arabic_label: str = Field(default='', max_length=320)
    transliteration: str = Field(default='', max_length=320)
    canonical_url: HttpUrl
    source_passage_id: UUID | None = None
    publication_status: Literal['draft','reviewed','published','archived'] = 'draft'

    @model_validator(mode='after')
    def evidence_required_for_publication(self):
        if self.publication_status == 'published' and self.source_passage_id is None:
            raise ValueError('published knowledge entities require governed source evidence')
        return self

class RelationshipInput(BaseModel):
    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: RelationshipType
    evidence_passage_id: UUID
    rationale: str = Field(min_length=10, max_length=4000)
    confidence: int = Field(ge=0, le=100)

    @field_validator('target_entity_id')
    @classmethod
    def no_self_link(cls, value, info):
        if value == info.data.get('source_entity_id'):
            raise ValueError('self relationships are forbidden')
        return value

class TraversalRequest(BaseModel):
    root_entity_id: UUID
    max_depth: int = Field(default=2, ge=1, le=5)
    max_nodes: int = Field(default=100, ge=1, le=500)
    relationship_types: list[RelationshipType] = Field(default_factory=list, max_length=16)

class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=200)
    languages: list[Literal['ar','en','transliteration']] = Field(default_factory=lambda:['ar','en','transliteration'])
    entity_types: list[EntityType] = Field(default_factory=list, max_length=14)
    exact_phrase: bool = False
    evidence_only: bool = True
    limit: int = Field(default=20, ge=1, le=100)

class CrossReferenceRequest(BaseModel):
    entity_id: UUID
    relationship_types: list[RelationshipType] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=100)
