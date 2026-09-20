# ADR 0003: Security Guardian is architecturally separate from the Executive/agent hierarchy

## Status
Proposed

## Context
An oversight system that the entity it oversees can influence, reconfigure, or disable
is not real oversight. The brief explicitly requires the Executive AI must NOT be able
to disable Security Guardian.

## Decision
Security Guardian is a distinct service with its own credential root (issued once by
the Credential Broker's owner-controlled bootstrap process, not derivable through any
EI/agent-accessible API), its own write path to the audit log, and the sole write path
to the Action Broker's freeze mechanism. No API exists from the EI or any agent to
Security Guardian's configuration, policy, or lifecycle. This is enforced by the absence
of a code path, not by an instruction to the model.

## Consequences
- **Positive**: a compromised or misaligned EI cannot suppress detection of its own
  compromise; freeze capability survives EI compromise.
- **Negative**: Security Guardian itself becomes a high-value target and a
  single-point-of-trust for detection; mitigated by keeping its own logic simple,
  rule-heavy (deterministic thresholds) rather than another complex LLM-judgment
  system, and by scheduled fire-drill testing (failure scenario #50) to catch silent
  Guardian failure.

## Alternatives considered
- Security monitoring as a module within the EI's own service (rejected — directly
  contradicts the non-negotiable requirement and collapses the trust boundary).
