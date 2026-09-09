# Top 50 Failure Scenarios and Mitigations

Format: **Scenario → Mitigation(s)**. Grouped by category. This list is a living document —
update it as new failure modes are discovered in practice (that discovery itself becomes a
Failure Memory entry, see `architecture/02-world-model-memory.md`).

## Model / reasoning failures (1–10)

1. **LLM hallucinates a fact used in a report** → All executive reports require
   evidence links; unverifiable claims are flagged "unverified" and excluded from
   metrics, never silently included.
2. **LLM hallucinates a tool/API that doesn't exist** → Action Broker validates every
   tool call against a registered schema before execution; unknown tools are rejected,
   not attempted.
3. **LLM misinterprets an ambiguous owner goal** → Goal Engine requires explicit
   success metrics, constraints, and stop conditions before a goal is activated; ambiguous
   goals trigger a clarifying question, not a guess.
4. **LLM drifts from the original goal over a long task** → Long-running tasks are
   checkpointed workflows, re-grounded against the stored goal/policy at each step, not
   one continuous freeform conversation.
5. **LLM produces confident but wrong financial/legal reasoning** → Finance/legal outputs
   are always labeled as assistive drafts requiring human or licensed-professional
   review; RED-tier by default.
6. **Model provider changes model behavior silently (version update)** → Model Router
   pins model versions explicitly; version changes go through the same testing gate as
   any other dependency upgrade.
7. **LLM is manipulated by a leading/loaded question from the owner interface** →
   Executive is instructed to distinguish requests from directives, and any request that
   would change policy/permissions still routes through the Policy Engine's explicit
   change flow, not implicit compliance.
8. **Different agents reach contradictory conclusions from the same data** →
   Contradiction detection in Semantic Memory surfaces conflicts to the owner or Chief of
   Staff agent rather than silently picking one.
9. **LLM refuses or stalls on a legitimate task due to over-cautious alignment
   behavior** → Escalation path to owner with the specific blocker stated, rather than
   silent failure.
10. **Embedding/retrieval failure returns irrelevant context, causing bad output** →
    Retrieval results include confidence/relevance scores; low-confidence retrieval
    triggers a "insufficient context" response instead of confabulation.

## Agent / orchestration failures (11–20)

11. **Agent loops indefinitely on a failing subtask** → Durable workflow engine enforces
    max retries, timeouts, and circuit breakers per task.
12. **Two agents take conflicting actions on the same resource (race condition)** →
    Resource-level leases/locks in the World Model; Action Broker serializes writes to
    the same entity.
13. **Agent crashes mid-task, leaving inconsistent state** → Idempotent actions +
    checkpointed workflow state; resumable from last checkpoint, not restarted blindly.
14. **Ephemeral agent spawns unboundedly (resource exhaustion)** → Hard cap on concurrent
    agents per family, enforced by the orchestrator, independent of what the Executive
    "wants."
15. **Agent misreports its own success (false positive completion)** → Verification step
    is a separate policy-defined check (e.g., "did the PR actually merge," "did the email
    actually send"), not self-attestation by the same agent.
16. **Sub-agent given an overly broad delegated goal reinterprets scope** → Delegation
    always carries explicit allowed/prohibited actions and budget, inherited and
    narrowed, never widened, from the parent goal.
17. **Agent output degrades quietly over time as it "learns" bad patterns** →
    Procedural Memory changes require passing a held-out evaluation before being adopted
    as the new default procedure.
18. **Executive delegates a RED action indirectly through an AMBER-permissioned agent**
    → Risk classification is attached to the action, not the agent; the Policy Engine
    reclassifies regardless of which agent requested it.
19. **Dead-lettered tasks pile up unnoticed** → Dead-letter queue has an owner-visible
    dashboard and alerting threshold; Chief of Staff agent reviews it on a schedule.
20. **Agent health monitoring itself fails silently** → Security Guardian and
    infrastructure monitoring are separate systems from the agent fleet they watch,
    with independent heartbeat alerting.

## Security / credential failures (21–30)

21. **API key leaks into logs or LLM context** → Secret detection/redaction at every
    context-assembly boundary (Model Privacy Gateway); vault issues short-lived tokens,
    never long-lived keys, into agent context.
22. **Prompt injection from a received email instructs the agent to exfiltrate data** →
    External content is labeled DATA at ingestion; no action derived purely from DATA
    content can reach AMBER/RED without independent policy confirmation.
23. **Malicious MCP server / tool returns a poisoned tool schema** → Only pre-approved,
    pinned, signed tool/connector manifests are loaded; new tools require owner
    approval to register.
24. **Compromised connector OAuth token used for lateral access** → Tokens scoped to
    minimum required permission per connector; revocation is immediate and global on
    Security Guardian trigger.
25. **Agent sandbox escape** → Defense in depth: container isolation, no host filesystem
    access beyond declared mounts, egress allowlists, syscall restriction where
    supported.
26. **Vector store / memory tampering (data poisoning attack)** → Memory writes are
    attributed and versioned; anomalous write patterns trigger Security Guardian review;
    corrections are append-only (supersede, not overwrite).
27. **Audit log tampering to hide an incident** → Tamper-evident append-only log
    (hash-chained); Security Guardian holds an independent copy the Executive cannot
    write to.
28. **Insider (contractor) with limited access over-uses granted scope** →
    Least-privilege, time-bound credentials per contractor integration; all actions
    audited identically to AI agents.
29. **Dependency/package supply-chain compromise** → Lockfiles, SBOM, vulnerability
    scanning, and a review gate before any new dependency reaches production.
30. **Model provider itself is compromised or subpoenaed** → Sensitive data routing
    prefers local/private inference (Model Privacy Gateway); minimum-necessary-context
    principle limits blast radius of any single provider compromise.

## Infrastructure / reliability failures (31–38)

31. **Model provider outage mid-task** → Model Router fallback chain (secondary
    provider/local model); task retried, not lost, on resume.
32. **Network partition between control plane and agent runtime** → Agents fail closed
    (stop, don't guess); durable workflow resumes once connectivity restores.
33. **Database/vector store outage** → Read replicas / backups; degraded mode serves
    cached/last-known state with explicit "stale" labeling, never silent staleness.
34. **Backup restore untested and fails when actually needed** → Scheduled automated
    restore drills with pass/fail logged in `docs/disaster-recovery/`.
35. **Host machine failure (owner's private infra)** → Documented recovery runbook +
    offline recovery key; RTO/RPO defined per data class.
36. **Certificate/credential expiry breaks a connector silently** → Expiry monitoring
    with advance alerts, not discovered via failure.
37. **Cost runaway from a misbehaving agent loop (API bill spike)** → Hard spend caps at
    the Model Router and Financial Control layer, independent of agent-reported budget
    tracking.
38. **Clock skew / timezone bug causes scheduled tasks to misfire** → Centralized
    scheduler with UTC-normalized storage and explicit timezone handling at the
    presentation layer only.

## Business / financial / process failures (39–46)

39. **Agent commits to a customer promise AURA cannot fulfill** → Commitment Memory
    requires explicit capacity/feasibility check before a commitment is confirmed
    externally; uncertain commitments route to owner.
40. **Marketing spend exceeds budget due to platform auto-optimization** → Budget
    envelopes enforced at the payment/credential layer (hard cap), not just at the
    agent's internal accounting.
41. **AURA sends a discount/refund outside policy under social-engineering pressure
    from a "customer"** → Discount/refund thresholds are policy-engine-enforced limits,
    not agent judgment calls; above-threshold requires owner approval.
42. **Duplicate or conflicting outreach to the same lead by two engines** → CRM is the
    single source of truth for contact state; outreach actions are gated by a
    per-contact rate limit and dedupe check.
43. **AURA violates a platform's anti-spam/ToS rules during outreach** → Policy Engine
    encodes platform-specific rules as explicit constraints checked before send, not
    left to agent judgment.
44. **Reported revenue/metrics don't reconcile with actual accounting records** →
    Reconciliation Assistant cross-checks reported figures against source-of-truth
    financial system before they appear in executive reports.
45. **AURA takes an action a court/regulator later finds requires human authorship
    disclosure it didn't give** → AI-disclosure policy is enforced by default at the
    Communication Engine, opt-out requires explicit owner + legal basis recorded.
46. **Owner is unavailable and a time-sensitive RED decision expires** → Stop conditions
    and default-safe fallback (do nothing / hold) defined per goal; escalation via
    multiple channels before expiry.

## Governance / oversight failures (47–50)

47. **Owner grants a broad permission once and forgets it's still active** → Permissions
    have default expirations and periodic re-affirmation prompts, not silent permanence.
48. **Owner approval fatigue leads to rubber-stamping RED requests** → Rate-limited,
    batched, and each RED request includes a concise risk summary, not just "approve?".
49. **Kill switch exists but isn't actually wired to every execution path** → Kill
    switch is enforced at the Action Broker (the single choke point all actions must
    pass through), not per-agent, so no path can bypass it by construction.
50. **Security Guardian itself is never tested and silently stops working** →
    Scheduled synthetic incident injection ("fire drills") verify Guardian detection and
    freeze capability on a recurring cadence, with results logged.
