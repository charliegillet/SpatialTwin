---
name: responder-brief
description: Draft a short responder brief from checked numbers only, with fact placeholders the server fills.
---
# Responder brief (draft, never sent)

- Write at most 6 short lines for an incident responder. Mark it "DRAFT — not sent".
- Never type a number. Write a placeholder instead and let the server fill it from the local checker:
  `{{fact:completed_crossings}}`, `{{fact:initial_population}}`, `{{fact:baseline_completed}}`,
  `{{fact:recommended_doors}}`, `{{fact:fallback_doors}}`, `{{fact:unsafe_exits}}`.
- Say which exits are unsafe and which doors the checked plan opens; say that counts are modeled crossings of a
  synthetic population, not a survival prediction, and that doors in the twin are simulated.
- Save it to `/workspace/out/brief.md`. Do not send it anywhere; the sandbox has no network.
