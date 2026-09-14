# Claim grounding and answer assembly

Milestone 6 Unit 2 introduces a deterministic, fail-closed boundary between retrieved evidence and any future language model.

## Pipeline

1. Classify the question and assign a risk level.
2. Restrict retrieval to the required approved corpora.
3. Validate every evidence checksum and attribution contract.
4. Split a proposed answer into explicit claims.
5. Require one or more evidence references for every religious claim.
6. Apply claim-type rules before assembly.
7. Assemble numbered citations only after every claim passes.
8. Return `insufficient` instead of an answer when any claim fails.

## Claim types

- `direct_quote`: wording must occur verbatim in cited evidence.
- `source_summary`: must cite valid evidence.
- `scholarly_interpretation`: must cite Tafsir evidence.
- `difference_of_opinion`: must cite at least two distinct attributions.
- `general_explanation`: must remain linked to valid evidence.

## High-risk boundary

Divorce, marriage validity, inheritance, takfir, custody, vows, medical fasting exemptions, and sensitive financial contracts are classified as high risk. Even a fully grounded response receives a visible non-fatwa escalation statement.

## Explicit non-claims

This unit does not contain an LLM, generate religious content, decide fatwas, or establish theological truth. It validates and assembles externally proposed claims only.
