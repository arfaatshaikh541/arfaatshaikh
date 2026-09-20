"""Email intent classification: closes the "classify/intent" half of
section 12's email gap (IMAP receive/threading were closed earlier this
session) using the Model Router's REASONING role, which was already
available -- this was always a wiring gap, not a missing capability.

Never fabricates a category outside the fixed list: an unparseable or
unexpected model response is reported as "unclassified", not silently
mapped to whichever category happens to look closest -- the same
"never fabricate success" discipline `executive.parse_plan()` already
applies to model output that drives a real decision.
"""
from __future__ import annotations

from .providers import ModelRouter

INTENT_CATEGORIES = ("inquiry", "complaint", "action_required", "informational", "spam")


async def classify_message_intent(subject: str, body: str, model_router: ModelRouter) -> str:
    prompt = (
        "Classify the intent of this email into exactly one of these categories: "
        f"{', '.join(INTENT_CATEGORIES)}.\n"
        "Respond with ONLY the single category word, nothing else.\n\n"
        f"Subject: {subject}\nBody: {body}"
    )
    chunks = [chunk async for chunk in model_router.generate_stream(prompt, history=[])]
    raw = "".join(chunks).strip().lower()
    if not raw:
        return "unclassified"
    candidate = raw.split()[0].strip(".,!?\"'")
    return candidate if candidate in INTENT_CATEGORIES else "unclassified"
