"""Answers an owner's free-text question from real retrieved memory --
the model is only ever asked to summarize records MemoryStore.search()
and decision_chain() actually found, with those records included
verbatim in the prompt. An answer that cites "the pricing decision from
March" is citing a real row, never a hallucination, because the model
was never given the freedom to answer from anything else. If nothing
relevant was found, that's reported honestly rather than asking the
model to improvise.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..providers import ModelRouter, NoProviderAvailable
from .store import MemoryStore
from .world_model import WorldModelStore


@dataclass
class MemoryAnswer:
    question: str
    context_used: list[dict] = field(default_factory=list)
    answer: str | None = None
    error: str | None = None


def _format_context_line(result, memory: MemoryStore) -> str:
    line = f"[{result.kind} {result.created_at.date().isoformat()}] {result.text}"
    if result.kind == "decision":
        chain = memory.decision_chain(result.id)
        if len(chain) > 1:
            history = " -> ".join(f"'{d.statement}' ({d.created_at.date().isoformat()})" for d in chain)
            line += f" [decision history: {history}]"
    if result.entity_ids:
        line += f" [entities: {', '.join(result.entity_ids)}]"
    return line


async def answer_question(
    question: str, memory: MemoryStore, model_router: ModelRouter, limit: int = 5,
    world_model: WorldModelStore | None = None,
) -> MemoryAnswer:
    results = memory.search(question, limit=limit, world_model=world_model)
    if not results:
        return MemoryAnswer(question=question, error="no relevant memory found for this question")

    context_lines = [_format_context_line(r, memory) for r in results]
    context_used = [
        {
            "kind": r.kind, "id": r.id, "text": r.text, "score": r.score,
            "created_at": r.created_at.isoformat(), "entity_ids": r.entity_ids,
        }
        for r in results
    ]

    prompt = (
        "Answer the owner's question using ONLY the memory records below -- "
        "never information from outside them. If a decision's history shows "
        "it changed over time, explain what changed and when. If the records "
        "don't actually answer the question, say so honestly instead of guessing.\n\n"
        f"Question: {question}\n\nRelevant memory:\n" + "\n".join(context_lines)
    )
    try:
        chunks = [chunk async for chunk in model_router.generate_stream(prompt, history=[])]
    except NoProviderAvailable as exc:
        return MemoryAnswer(question=question, context_used=context_used, error=str(exc))

    return MemoryAnswer(question=question, context_used=context_used, answer="".join(chunks).strip())
