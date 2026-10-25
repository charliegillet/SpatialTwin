# SpatialTwin: Direct Gemini 4 Argon Vision Grounding

## 1. Perception Architecture

SpatialTwin utilizes direct `gemini-4-argon` calls via `google-genai` to visually identify judge-placed incident tokens on a physical tabletop board.

```
Tabletop Camera (Overhead Still)
          │
          ▼
   [Capture Still] ─────────────► Direct gemini-4-argon (JSON Schema)
                                        │
                                        ▼
   [GroundingProposalV1] ◄────── Local Semantic Validator
          │                      (Restricts to portal:P1, portal:P2, boundary:B2)
          ▼
   Presenter Cockpit Review (Explicit Operator Apply)
```

### Cooperative Visual Grounding vs. Uncalibrated 3D
- Tokens are placed on designated target pads: `T_P1` (West Portal), `T_P2` (East Portal), and `T_B2` (East Exit).
- The model outputs cooperative perception proposals. It does not infer uncalibrated building dimensions, door widths, or room elevations from raw pixels alone.
- Physical units (meters and seconds) are provided by the reviewed venue schema, not inferred by AI vision.

---

## 2. API Contract & Direct Schema

```python
interaction = client.interactions.create(
    model="gemini-4-argon",
    input=[
        {"type": "text", "text": GROUNDING_PROMPT_WITH_CATALOG},
        {"type": "image", "data": frame_base64, "mime_type": "image/jpeg"},
    ],
    generation_config={"thinking_level": "low"},
    response_format={"type": "text", "mime_type": "application/json"},
)
```

### Proposed Output Schema:
```json
{
  "status": "matched | ambiguous | no_match",
  "candidate_ids": ["portal:P1", "portal:P2", "boundary:B2"],
  "selected_entity_type": "portal | boundary | null",
  "selected_entity_id": "P1 | P2 | B2 | null",
  "operation": "SET_UNAVAILABLE",
  "evidence": "Visible circular red blockage token on pad T_P2",
  "box_2d": [ymin, xmin, ymax, xmax]
}
```

---

## 3. Local Semantic Validation Rules

A schema-valid model output can still contain hallucinations or unauthorized actions. The local validator enforces:
1. **Allowlisted Target Invariant**: The pair `(selected_entity_type, selected_entity_id)` MUST match one of `(portal, P1)`, `(portal, P2)`, or `(boundary, B2)`. Unknown entities (e.g. `P3`, `B1`, `D99`) are rejected.
2. **Ambiguity Invariant**: If status is `ambiguous` or `no_match`, `selected_entity_id` MUST be `null`. No automatic application of an ambiguous target is permitted.
3. **Membership Invariant**: The selected target must be explicitly present in `candidate_ids`.
4. **Normalized Box Scale**: Bounding boxes use `[ymin, xmin, ymax, xmax]` on a `[0..1000]` normalized scale, clearly separated from millimeters or floor meters.

If semantic validation fails, the proposal is converted to `ambiguous` with explicit diagnostic error reasons, forcing human operator disambiguation.
