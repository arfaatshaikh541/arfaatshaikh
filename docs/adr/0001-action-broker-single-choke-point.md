# ADR 0001: All agent actions route through a single Action Broker

## Status
Proposed (Milestone 0 architecture decision — not yet implemented)

## Context
AURA agents need to take real-world effectful actions (send email, spend money, deploy
code, write to CRM). Without a single enforcement point, safety controls (policy, risk
classification, approval, kill switch, audit) would need to be re-implemented per
connector/agent, and any one omission becomes a bypass.

## Decision
Every effectful action, regardless of which agent or capability family originates it,
must pass through one Action Broker service, which sequences: kill-switch check → policy
check → risk classification → approval (if required) → credential issuance → execution
→ audit write. No agent, including the Executive Intelligence, has a direct execution
path to any connector or credential.

## Consequences
- **Positive**: kill switch, audit, and policy enforcement are comprehensive by
  construction, not by convention; adding a new capability automatically inherits all
  safety controls.
- **Negative**: the Action Broker is a critical-path single point of failure/latency for
  every action; must be built for high availability and low latency, and its own
  compromise is the highest-value target in the system — mitigated by keeping it
  minimal, heavily tested, and monitored independently by the Security Guardian.

## Alternatives considered
- Per-connector policy enforcement (rejected — inconsistent, easy to bypass by adding a
  new connector without wiring in every control).
- Trusting agent self-restraint via prompting alone (rejected — explicitly contradicts
  the "models make mistakes / instructions may be malicious" design assumption).
