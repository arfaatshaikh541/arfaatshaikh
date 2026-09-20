# AURA Threat Model

## Scope

AURA has exactly one legitimate root principal (the owner). Everything else — every
model, every agent, every connector, every piece of external content — is treated as
**untrusted or semi-trusted** until proven otherwise by policy, not by assumption.

## Threat actors

| Actor | Capability | Primary vector against AURA |
|---|---|---|
| Commodity attacker | Automated scanning, phishing kits, credential stuffing | Leaked API keys, exposed endpoints, reused passwords |
| Organized cybercrime | Targeted phishing, ransomware, BEC | Compromised connector OAuth tokens, financial social engineering via email/CRM |
| Malicious insider | N/A (single-owner system — but contractors/collaborators with limited access exist) | Over-scoped credentials, exfiltration via approved channels |
| Compromised SaaS provider | Supply-chain trust, token theft at provider | Connector compromise (email, CRM, ad platform breach), poisoned webhook data |
| Supply-chain attacker | Malicious/compromised package, model, or MCP server | Dependency injection, malicious tool definitions, model weight/API tampering |
| Sophisticated / state-sponsored actor | Zero-days, infrastructure-level access, long dwell time | Host compromise, cloud provider account takeover, targeted prompt-injection campaigns |

We explicitly do **not** claim resistance to a determined state-level actor with
infrastructure-level access. The design goal against that tier is **detection, containment,
and forensic accountability** — not prevention guarantees.

## Attack surfaces specific to an agentic system

1. **Prompt injection via external content** — email bodies, PDFs, web pages, GitHub
   issues, CRM notes, support tickets. Any of these can contain text designed to be
   interpreted as instructions. Mitigation: `docs/security/prompt-injection.md`.
2. **Tool/action abuse** — an agent tricked (via injection or hallucination) into calling
   a real-world tool (send email, spend money, push code) it should not. Mitigation:
   Action Broker + Policy Engine + Risk Engine (`docs/policies/README.md`).
3. **Credential exposure** — secrets leaking into prompts, logs, memory, or git history.
   Mitigation: Credential Broker, no long-lived secrets in agent context
   (`docs/security/README.md#credential-vault`).
4. **Memory poisoning** — false "facts" injected into semantic/episodic memory via a
   compromised or manipulated source, later trusted as ground truth. Mitigation:
   provenance + confidence + contradiction detection (`architecture/02-world-model-memory.md`).
5. **Privilege escalation by the Executive itself** — the EI reasoning its way into
   granting itself or a subordinate more capability "because it would help." Mitigated
   structurally: the EI has no code path that can write to the Policy Engine's permission
   store. This is enforced by service boundary, not by prompting.
6. **Supply chain** — malicious MCP servers, npm/pip packages, or a compromised model
   provider. Mitigation: `docs/security/supply-chain.md`.
7. **Lateral compromise** — one agent's sandbox escape or leaked credential used to reach
   another agent, the vault, or the host. Mitigated by sandbox isolation + per-agent
   short-lived scoped credentials + network segmentation (`docs/security/network.md`).
8. **Owner impersonation / social engineering of the owner** — an attacker posing as the
   owner to the system (e.g., spoofed "owner" instruction via a compromised channel).
   Mitigated by strong owner authentication (passkeys/hardware keys/mTLS) for anything
   that changes policy, and by RED-tier actions never trusting a channel that isn't the
   authenticated control plane.
9. **Denial of service against the owner's judgment** — flooding the owner with approval
   requests to induce rubber-stamping ("approval fatigue"). Mitigated by rate-limiting
   RED-approval requests per period and batching non-urgent approvals into digest form.

## Top 50 failure scenarios and mitigations

See `docs/threat-model/failure-scenarios.md` for the full enumerated list (grouped by
category: model failure, agent failure, infrastructure failure, security compromise,
business/financial failure, human/process failure).

## Residual risk statement

After all controls below are implemented, residual risk includes: zero-day exploitation
of a dependency before a patch exists; a sufficiently novel prompt-injection technique
evading current defenses on a single GREEN/AMBER action before detection catches it;
provider-side model behavior changes; and the fundamental limits of LLM judgment on
truly novel situations. The system is designed to make the **blast radius** of each of
these small and recoverable, not to claim they cannot happen.
