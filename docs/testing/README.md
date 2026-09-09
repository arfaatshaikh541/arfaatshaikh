# Testing Strategy

## Principle

Never report a test as passed unless it was actually executed, with real output
captured. This document defines the required test categories; `docs/project-status.md`
records actual execution results per milestone — a category listed here with no
corresponding logged run is, by definition, not yet done.

## Required categories

1. **Unit tests** — per-service logic (Policy Engine rule evaluation, Risk Engine
   classification, memory schema validation, etc.).
2. **Integration tests** — cross-service flows (Action Broker → Policy Engine →
   Credential Broker → mock connector).
3. **End-to-end tests** — full workflow from owner command to completed, reported
   action, against a staging environment with sandboxed/synthetic external systems.
4. **Property tests** — invariants that must hold across arbitrary inputs (e.g., "no
   issued credential ever outlives its declared TTL," "budget envelope spend never
   exceeds cap regardless of request ordering/concurrency").
5. **Permission tests** — verify an agent role cannot invoke actions outside its
   declared tool scope, for every role.
6. **Policy tests** — OPA policy unit tests covering every autonomy-level × risk-tier
   combination and edge cases (missing fields, conflicting constraints).
7. **Action-risk tests** — verify the Risk Engine classifies a comprehensive set of
   known action types correctly, including adversarial attempts to mislabel a RED
   action as GREEN via crafted request shape.
8. **Agent-isolation tests** — verify a compromised/malicious agent process cannot
   reach another agent's sandbox, credentials, or task context.
9. **Credential tests** — issuance, scoping, TTL expiry, revocation-on-freeze,
   revocation-on-kill-switch, and that no long-lived secret is ever observable in agent
   context/logs/memory.
10. **Prompt-injection tests** — a maintained corpus of known injection patterns run
    against every role that processes external content, verifying the provenance/
    action-gate discipline in `docs/security/prompt-injection.md` holds.
11. **Malicious-document tests** — PDFs/documents crafted with embedded instructions,
    verifying document-ingestion agents treat content as data.
12. **Malicious-email tests** — same, for the Email Assistant and Support Agent roles
    specifically, including spoofed-owner-instruction attempts.
13. **Data-exfiltration tests** — attempt to get an agent to send sensitive data to an
    unauthorized destination via injection or misdirection; verify network egress
    allowlisting and the Model Privacy Gateway both independently block it.
14. **Privilege-escalation tests** — attempt to get the EI or any agent to grant
    itself/another agent broader scope; verify the structural absence of that write
    path holds under adversarial prompting.
15. **Financial-limit tests** — verify budget/amount/velocity limits hold under
    concurrent requests, retries, and adversarial amount-splitting attempts.
16. **Rollback tests** — verify the rollback/undo semantics for every action type that
    claims reversibility actually work end-to-end.
17. **Memory-integrity tests** — verify provenance/versioning/supersession behave
    correctly, contradiction detection actually fires on conflicting writes, and
    deletion-with-audit-trail works as specified.
18. **Model-failure tests** — verify graceful behavior when a model call errors,
    times out, or returns malformed output.
19. **Provider-outage tests** — verify Model Router fallback chain and connector
    health-check/degraded-mode behavior under simulated provider outage.
20. **Network-partition tests** — verify agent runtime fails closed (not open) when it
    loses connectivity to the control plane / Policy Engine.
21. **Disaster-recovery tests** — scheduled restore drills (see
    `docs/disaster-recovery/README.md`), pass/fail logged.
22. **Backup-restore tests** — a subset of DR tests specifically verifying data
    integrity post-restore against pre-backup checksums.
23. **Load tests** — verify the system's concurrency caps and rate limits hold, and
    latency stays acceptable, under realistic multi-workflow load.
24. **Long-running-agent tests** — a workflow spanning many checkpoints/days in
    simulated time, verifying no state loss, no drift beyond the re-grounding design's
    tolerance, and correct lease/timeout behavior.
25. **Adversarial red-team exercises** — periodic, scenario-based exercises (not
    automated unit tests) where a human red-team attempts to achieve a RED-tier outcome
    through any combination of injection, social engineering of the owner interface, or
    chained lower-tier actions; findings feed Failure Memory and this test suite.

## Gating

CI blocks merge on categories 1–17 (fast, deterministic, run every change). Categories
18–24 run on a scheduled/staging cadence (not every commit, due to cost/time). Category
25 (red-team) runs at defined milestone gates, per `docs/roadmap.md`, with results
required before any autonomy-level increase for the capabilities exercised.

## Evidence requirement

Every milestone's acceptance report (`docs/project-status.md`) links the actual CI run /
test report for the categories claimed complete for that milestone — a claim without a
linked, real run is treated as not done.
