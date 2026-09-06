"""AURA headless core runtime.

This package intentionally implements only what has been genuinely built and
tested in this environment: persistent memory, a model-provider abstraction
with a real Ollama client, a deterministic instant-action lane, and a
streaming chat API. It does not implement voice, telephony, social
connectors, financial execution, or computer control — see
docs/agents/README.md and core/RUNBOOK.md for what those require and why
they aren't here yet.
"""

__version__ = "0.1.0"
