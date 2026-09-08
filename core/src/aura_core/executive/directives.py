"""Explicit, narrow parsing for "Run X" / "Operate X" executive
directives -- the exact shape section 10 of the product brief asks for
("Run Gridkeep" must not be met with a generic goal-form). Matches this
codebase's established rule that anything driving a real decision either
matches a known pattern or reports itself as unrecognized, never a
best-effort guess (the same discipline `classify_message_intent()` and
`executive.parse_plan()` already apply to model output).

STANDARD_DEPARTMENTS is a generic organizational scaffold, not a
fabricated fact about any specific business -- it says nothing about what
Gridkeep (or any company) actually does, only names the kind of
workstream categories most operating businesses have. Real objectives,
KPIs, and constraints for the actual business still have to come from the
owner before MandateEngine.activate() will allow the mandate to run: this
directive only removes the friction of a generic intake form for the
*first* command, it does not, and must not, invent the business content
that form would have collected.
"""
from __future__ import annotations

import re

STANDARD_DEPARTMENTS = [
    "Executive", "Sales", "Marketing", "Social Media", "Customer Service",
    "Customer Success", "Operations", "Production", "Software Engineering",
    "Finance", "Security", "Research", "Growth",
]

_RUN_PATTERN = re.compile(r"^\s*(?:run|operate)\s+(.+?)\s*$", re.IGNORECASE)


def parse_run_directive(text: str) -> str | None:
    """Returns the company name from a "Run X" / "Operate X" directive,
    or None if `text` doesn't match that exact shape. Never a guess at
    what the caller "probably" meant -- an unrecognized directive is
    reported as unrecognized, exactly like an unclassified email or an
    unparseable model plan elsewhere in this codebase."""
    match = _RUN_PATTERN.match(text)
    return match.group(1) if match else None
