"""Deliberately simple, explainable scoring — not a sophisticated
actuarial risk model. Two distinct numbers, kept separate so they don't
get conflated:

- `compute_finding_risk_score`: how bad is *this one* finding, 0-100,
  used to sort/display individual findings (severity, adjusted by the
  affected asset's criticality).
- `compute_tenant_security_score`: how healthy is the tenant *overall*,
  100 minus a fixed penalty per open/assigned/accepted-risk finding
  severity, floored at 0. More open findings means a lower score even
  if any single one isn't severe — a tenant with ten "medium" findings
  is not actually fine.

Both formulas are intentionally linear and easy to explain to a
customer; refining them (weighting by asset exposure, time-open, etc.)
is reasonable future work, not required for this milestone.
"""

from __future__ import annotations

FINDING_SEVERITY_BASE = {"critical": 90, "high": 65, "medium": 40, "low": 15}
ASSET_CRITICALITY_MULTIPLIER = {"critical": 1.1, "high": 1.0, "medium": 0.9, "low": 0.75}
TENANT_SCORE_SEVERITY_PENALTY = {"critical": 20, "high": 12, "medium": 6, "low": 2}


def compute_finding_risk_score(severity: str, asset_criticality: str) -> int:
    base = FINDING_SEVERITY_BASE[severity]
    multiplier = ASSET_CRITICALITY_MULTIPLIER.get(asset_criticality, 1.0)
    return min(100, round(base * multiplier))


def compute_tenant_security_score(open_finding_severities: list[str]) -> int:
    penalty = sum(TENANT_SCORE_SEVERITY_PENALTY[s] for s in open_finding_severities)
    return max(0, 100 - penalty)


__all__ = [
    "compute_finding_risk_score",
    "compute_tenant_security_score",
]
