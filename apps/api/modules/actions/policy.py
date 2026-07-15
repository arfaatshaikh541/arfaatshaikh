"""Automation-mode policy — deliberately simple and documented, same
spirit as Milestone 3's scoring formulas: a fixed, explainable table
rather than a configurable rules engine, so a tenant can reason about
exactly what each mode does before turning it on.

Modes run least to most autonomous:

- ``observe``  — automation never acts. A playbook match is not even
  recorded as a pending action; the finding is simply visible for a
  human to remediate manually. The safest possible default.
- ``guided``   — a playbook match always creates an ActionRun, but every
  one starts ``pending_approval`` regardless of safety class — a human
  approves every automated action once, then it runs.
- ``balanced`` — safety class 0-1 (safe, reversible) actions auto-run;
  safety class 2+ (disruptive) waits for approval. The recommended
  default for a tenant ready to turn automation on.
- ``autopilot``— safety class 0-3 auto-run; only class 4 (the most
  severe/irreversible) waits for approval.
- ``lockdown`` — every safety class auto-runs immediately, including
  class 4. Intended for active-incident containment where speed matters
  more than review, not a day-to-day default.
"""

from __future__ import annotations

# None means "don't even create an ActionRun for a playbook match" —
# see `creates_action_run_for_playbook_match`. -1 means "create one, but
# never auto-approve" since no real safety_class is <= -1.
AUTO_EXECUTE_MAX_SAFETY_CLASS: dict[str, int | None] = {
    "observe": None,
    "guided": -1,
    "balanced": 1,
    "autopilot": 3,
    "lockdown": 4,
}


def creates_action_run_for_playbook_match(mode: str) -> bool:
    return AUTO_EXECUTE_MAX_SAFETY_CLASS.get(mode) is not None


def is_playbook_action_auto_approved(mode: str, safety_class: int) -> bool:
    threshold = AUTO_EXECUTE_MAX_SAFETY_CLASS.get(mode)
    if threshold is None:
        return False
    return safety_class <= threshold
