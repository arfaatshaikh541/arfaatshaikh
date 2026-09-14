from __future__ import annotations
import re
import unicodedata
from collections import deque
from dataclasses import dataclass
from uuid import UUID

from app.schemas.knowledge_network import RelationshipInput, SearchRequest, TraversalRequest

ARABIC_DIACRITICS = re.compile(r'[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]')

@dataclass(frozen=True)
class GraphEdge:
    source: UUID
    target: UUID
    relationship_type: str
    evidence_passage_id: UUID
    approved: bool = True

class KnowledgeNetworkPolicy:
    @staticmethod
    def normalize_search_text(value: str) -> str:
        value = unicodedata.normalize('NFKC', value).strip().casefold()
        value = ARABIC_DIACRITICS.sub('', value)
        value = value.replace('أ','ا').replace('إ','ا').replace('آ','ا').replace('ى','ي')
        return ' '.join(value.split())

    @staticmethod
    def validate_relationship(payload: RelationshipInput, *, source_published: bool, target_published: bool, evidence_current_and_approved: bool) -> dict:
        reasons: list[str] = []
        if not source_published or not target_published:
            reasons.append('both entities must be published')
        if not evidence_current_and_approved:
            reasons.append('relationship evidence must be current and approved')
        if payload.relationship_type == 'authenticates' and payload.confidence < 90:
            reasons.append('authentication links require confidence of at least 90')
        return {'allowed': not reasons, 'reasons': reasons, 'publish': not reasons}

    @staticmethod
    def traverse(request: TraversalRequest, edges: list[GraphEdge]) -> dict:
        adjacency: dict[UUID, list[GraphEdge]] = {}
        allowed_types = set(request.relationship_types)
        for edge in edges:
            if not edge.approved or (allowed_types and edge.relationship_type not in allowed_types):
                continue
            adjacency.setdefault(edge.source, []).append(edge)
            adjacency.setdefault(edge.target, []).append(edge)
        visited = {request.root_entity_id}
        queue = deque([(request.root_entity_id, 0)])
        results: list[dict] = []
        truncated = False
        while queue:
            current, depth = queue.popleft()
            if depth >= request.max_depth:
                continue
            for edge in adjacency.get(current, []):
                nxt = edge.target if edge.source == current else edge.source
                if nxt in visited:
                    continue
                if len(visited) >= request.max_nodes:
                    truncated = True
                    queue.clear()
                    break
                visited.add(nxt)
                results.append({'entity_id': str(nxt), 'depth': depth + 1, 'relationship_type': edge.relationship_type, 'evidence_passage_id': str(edge.evidence_passage_id)})
                queue.append((nxt, depth + 1))
        return {'root_entity_id': str(request.root_entity_id), 'nodes': results, 'result_count': len(results), 'truncated': truncated}

    @staticmethod
    def build_search_plan(request: SearchRequest) -> dict:
        normalized = KnowledgeNetworkPolicy.normalize_search_text(request.query)
        terms = [normalized] if request.exact_phrase else [term for term in normalized.split(' ') if term]
        return {
            'normalized_query': normalized,
            'terms': terms,
            'languages': request.languages,
            'entity_types': request.entity_types,
            'evidence_only': request.evidence_only,
            'limit': request.limit,
            'ranking': ['exact_alias','canonical_label','transliteration','keyword','relationship_proximity'],
            'user_generated_content_excluded': True,
        }
