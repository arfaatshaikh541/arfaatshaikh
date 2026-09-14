# Assistant Experience and Evidence Inspection

The bilingual assistant is a presentation layer over governed retrieval, claim validation, and safety decisions. It never treats rendered citations as sufficient by themselves: each source panel exposes the canonical reference, attribution, and exact evidence text. Arabic uses native RTL direction. Conversation records are private to the authenticated account; feedback references a specific answer run and cannot rewrite canonical content or evidence.

## Accessibility contract

- labelled question field and native submit control
- 44px minimum primary target
- live answer status without forced focus movement
- keyboard-operable native `details` source inspection
- visible focus indicators
- reduced-motion support
- language and direction boundaries
- insufficiency communicated as text, not colour alone

## Privacy contract

High-risk and privacy-sensitive questions use reduced raw-question retention. Audit integrity relies on checksums and append-only entries rather than indefinite storage of personal question text.
