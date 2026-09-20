# Model Routing Architecture

## Why an abstraction layer

AURA must not depend permanently on one model vendor: pricing changes, capability
changes, outages, and policy changes at a single provider would otherwise become a
single point of failure for the entire business operating system. The Model Router is a
service that every agent invocation goes through — agents request a *capability class*,
not a specific model.

## Capability classes

| Class | Used for | Example routing (illustrative, versions pinned explicitly in config) |
|---|---|---|
| Local reasoning model | Restricted-class data, offline-degraded mode | Self-hosted open-weight model on owner hardware |
| Frontier reasoning model | Executive planning, complex analysis, high-stakes drafting | Hosted frontier model via zero-retention API tier |
| Coding model | Build Engine tasks | Frontier or coding-specialized model, sandboxed execution |
| Fast/inexpensive model | High-volume, low-complexity tasks (classification, routing, simple extraction) | Small/distilled model, local or hosted |
| Vision model | Document/image understanding, ad creative review | Multimodal frontier or specialized local model |
| Speech model | Voice interface, call transcription | Local speech-to-text preferred for privacy; hosted fallback |
| Embedding model | Semantic memory retrieval | Local embeddings preferred (keeps vector store private) |

## Routing decision factors

- **Sensitivity** (from the Model Privacy Gateway's classification) — restricted-class
  data never leaves local/private inference, full stop, regardless of what would be
  "better" for the task.
- **Task complexity** — don't spend frontier-model cost/latency on a trivial
  classification a fast model handles reliably.
- **Cost** — routing decisions are cost-aware against the goal's budget envelope.
- **Latency** — real-time contexts (e.g., live chat support) route to faster models even
  at some capability cost.
- **Provider availability** — health-checked; automatic failover to the next-ranked
  provider/model in the fallback chain on outage or elevated error rate.
- **Required capability** — some tasks genuinely need frontier reasoning (complex
  planning, ambiguous judgment calls) and the router does not downgrade those to save
  cost at the expense of correctness on consequential tasks.

## Fallback chain & degraded operation

Each capability class has an ordered fallback list. On primary-provider failure, the
Router retries against the next provider transparently to the calling workflow (the
durable workflow engine handles the retry, not an open model conversation). If **all**
hosted providers are unreachable, GREEN/AMBER tasks that can run on the local model
continue in degraded mode; RED-tier and anything requiring frontier-only capability
queues and waits, with the owner notified of degraded operation rather than the system
silently doing something lower-quality without saying so.

## Version pinning

Model versions are pinned explicitly in the Router's configuration, not "latest."
A version change is a reviewed change (same gate as a dependency upgrade — see
`docs/testing/README.md` and `docs/security/README.md#supply-chain-security`), because
model behavior changes are a real failure mode (failure scenario #6).
