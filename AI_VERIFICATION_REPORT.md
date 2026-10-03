# AI verification report

Date: 2026-10-03. Overall: **PARTIAL**. The platform correctly reports "unavailable" and abstains; generation with a real local model is **BLOCKED** (the model registry is refused by the egress policy).

## Provider

Ollama only (`WOI_AI_MODE=local`, `WOI_EXTERNAL_AI_ENABLED=false`); no paid API is configured or required. The `ollama/ollama:latest` container from `docker-compose.prod.yml` is healthy. `ollama pull` fails because `registry.ollama.ai` is refused by the environment's egress policy (403 on CONNECT; recorded in `data/source-probes.json`). `docker compose exec ollama ollama list` is therefore empty. Model choice for the real host (not tested): with 4 CPUs and 15 GB of RAM and no GPU, an 8B-parameter quantised model is the practical ceiling; a 3B-class model is safer. That is a sizing estimate, not a measurement.

## Pipeline, step by step

| Step | Result | Evidence |
|---|---|---|
| User question | PASS | `POST /api/v1/assistant/query` requires a signed-in user and a CSRF token |
| Classification and safety | PASS_AUTOMATED_ONLY | Questions outside the supported corpora, and unsafe ones, never reach retrieval (tests) |
| Retrieval | PASS | Published, approved passages only (Qur'an text and two translations today); hidden datasets are never searched |
| Source filtering and ranking | PASS | Authority classes kept apart (primary / scholarly / secondary); confidence computed; weak evidence abstains |
| **Ollama** | **BLOCKED** | No model installed. The API returns `ai_synthesis.status = "unavailable"`; the UI says "no local model is running" |
| Citation validation | PASS_AUTOMATED_ONLY | `validate_synthesis` rejects a summary that cites a source not retrieved, or has uncited sentences (tests, with model output supplied by the tests) |
| Answer | PASS | The core answer is verbatim quotation with source, edition, licence and rights status; nothing is paraphrased by a model |
| Uncertainty / abstention | PASS | "Insufficient verified sources" for questions with no support; verified in a real browser on the production stack |

## What the AI is not allowed to do

It never supplies Qur'an quotations, hadith, hadith grades, fiqh rulings, scholar quotations or citations: every quoted item is copied from the database record it cites, and the optional model summary is shown only if every sentence validates against those records; otherwise it is discarded and reported as rejected. Hadith, gradings, tafsir, fiqh and scholars have **no published data**, so the assistant cannot answer from them at all.

## What the UI now shows

- **SOURCE EVIDENCE**: a heading above the quoted passages.
- **LOCAL AI** and **MODEL: `<name>`** (from configuration) in the AI section, whether or not the model answered. If external AI were ever enabled the label would read EXTERNAL AI.
- The unavailable, rejected and validated states, and the line "It is not itself a source."

Checked in real Chromium on the production stack and in an API test.

## Not tested

Generation, latency and memory of any real model; quality of any summary; behaviour when the model returns malformed or adversarial text beyond what the unit tests cover.
