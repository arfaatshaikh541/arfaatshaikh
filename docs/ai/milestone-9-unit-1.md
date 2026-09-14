# Milestone 9 Unit 1: Evidence-grounded AI orchestration

## Purpose

This unit introduces a deterministic gate between model-generated draft claims and user-visible Islamic answers. A language model is never treated as a source of Islamic authority.

## Invariants

- Every answer claim requires one or more governed `source_passages`.
- Citation evidence is fingerprinted and verified before use.
- Direct quotations must occur verbatim in the cited evidence.
- Scholarly interpretation requires Tafsir evidence.
- Differences of opinion require separately attributed evidence.
- Personal rulings and all high-risk cases are escalated to a qualified scholar.
- Unsupported or malformed claims fail closed.
- Claim verification decisions and scholar escalations are persistable and auditable.

## API

`POST /ai-orchestration/evaluate` evaluates draft claims and returns `completed`, `blocked`, or `escalated`. It does not call an external model and does not itself issue a fatwa.

## Deferred

Persistent orchestration execution, provider adapters, streaming, multilingual alignment, evaluation datasets, queue workers, and operational dashboards are later Milestone 9 units.
