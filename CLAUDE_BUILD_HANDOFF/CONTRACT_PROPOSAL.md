# Proposed Claude ↔ Codex interface boundary

Version `proposal-v0.1`, prepared 23 October 2026. **This is a proposal to freeze together, not an existing API or vendor schema.** Codex owns central application contracts. Claude implements adapters against the frozen version, with clearly labeled fakes while the real service is unavailable.

## Ownership

| Owner | Write paths, relative to project root |
|---|---|
| Codex | `backend/app/state/`, `backend/app/planner/`, `backend/app/hardware/`, `firmware/`, shared frontend shell/store/API client, central contracts |
| Claude grounding | `backend/app/ai/grounding/`, `tests/ai_contracts/grounding/`, `docs/ai/grounding.md` |
| Claude managed agent | `backend/app/ai/managed/`, `tests/ai_contracts/managed/`, `docs/ai/managed.md` |
| Claude UI | `frontend/src/features/proposal-evidence/` and co-located tests/stories |
| Claude integration | `tests/ai_contracts/integration/`, `tests/ai_contracts/fixtures/`, `scripts/ai_smoke/`, `docs/ai/setup.md`, `docs/ai/source-manifest.json` |
| Claude reviewer | `tests/adversarial_ai/`, `docs/ai/devils-advocate.md`; implementation read-only |
| Claude lead | `docs/ai/team-status.md`, `docs/ai/contract-requests.md`; integration after owners finish |

If the project already uses other roots, lead and Codex map these once. Record exact paths, baseline commit and the contract revision. Shared package/dependency locks and app entrypoints have one writer. A leaf agent cannot solve a missing dependency by implementing another team's service.

## 1. Context and capture

`RunContext`: `geometry_revision`, `scenario_revision`, `physical_revision`, `parameters_revision`, `solver_version`. Include a server-derived canonical context hash and currentness check. Revisions are not model-invented labels.

`Capture`: `capture_id`, capture timestamp, source kind (`tabletop_camera`, `annotated_plan`, `fixture`), image pixel dimensions/orientation, source geometry revision and expected scenario/physical revisions. Keep images separate from normal logs and serialize only bounded metadata to hardware. Camera input and hardware observations have different authority.

## 2. GroundingProposalV1

Required semantic fields:

- Version, capture ID and exact source context.
- `status`: `matched`, `ambiguous`, `no_match`.
- `candidate_ids`: canonical typed candidates from the source catalog.
- Nullable selected entity, represented by `entity_type` + `entity_id`.
- Operation `SET_UNAVAILABLE`, and a short visible-evidence description.
- Optional documented source-image box with explicit coordinate convention.

Supported stage target pairs are **`portal:P1`, `portal:P2`, `boundary:B2`**. A matched selection must be one of its candidates. Ambiguity has no applied entity; manual canonical choice resolves it in the local review flow. No-match cannot contain a silently applied target. A portal/boundary type mismatch, unknown ID, unsupported operation or stale source is rejected locally.

Use a vendor-supported simple JSON response schema, then a stricter local validator. Do not pass every application JSON Schema keyword to Gemini and assume support. Never add a model-generated percentage as calibrated confidence. A schema-valid response can still be factually wrong and must remain reviewable.

Grounding returns **a proposal**, not a state mutation. The shared command router validates a local Apply command, expected revision and idempotency key before accepting the hypothetical edit.

## 3. AI-facing ScenarioService port

Proposed transport-neutral async methods:

```text
get_reviewed_context(context) -> catalog + assumptions + permitted alternatives
evaluate_alternative(context, alternative_id, request_id) -> EvaluationEnvelope
get_checked_run(run_id) -> EvaluationEnvelope
```

`alternative_id` is a small enum: `KEEP_CURRENT`, `OPEN_P3`. Evaluation copies one immutable base snapshot, applies exactly the permitted hypothetical delta, solves and independently checks it. It does not move a servo or mutate observed application state. Idempotency includes base context, alternative and request ID; rejected context cannot silently evaluate a newer state.

`EvaluationEnvelope` contains base context/hash, candidate input hash, alternative/delta, run ID, computation status, initial population, completed modeled-boundary crossings, remaining population, time horizon, supported queue metric, assumptions, validator verdict/reasons, timings and provenance. A completed result is publishable only when its independent validation passes and its context is current for that use.

All initial occupants must remain accounted for. Invalid, failed, timed-out and partial outcomes remain distinct. The numerical meanings and units belong to Codex's service, not the agent's prose.

Candidates share the **same base context and initial conditions**; their candidate input hashes differ by the declared alternative. Requiring identical candidate hashes would incorrectly reject a real intervention. Comparison verifies that the only differences are allowlisted, with equal population/horizon/other assumptions. No boundary capacity increase is hidden inside OPEN_P3.

## 4. InvestigationResult

Built locally from tool records: investigation ID, base context, actual configured model/agent, status, candidate records/run IDs, checked comparison, concise agent explanation, errors, actual tool-call ledger, usage and deadline state. The agent does not have managed structured-output support. Do not parse numerical results out of prose to populate this envelope.

Tool records distinguish requested, arguments-complete, locally validated, executed, result-returned and provider-completed states. Duplicate calls return their known result. Incomplete/stale/failed investigations can expose valid individual records but cannot declare an overall best choice.

The default is at most two candidate alternatives and four accepted custom-function requests with a finite whole-investigation deadline. Provider token budget is best effort; continuations and cached usage need explicit cumulative accounting.

## 5. UI component seam

Injected props provide source capture/proposal, current context, provider status, selected candidate, baseline/predicted/observed checked results, actual tool evidence and hardware status. Injected callbacks request capture, choose a known entity, Apply a reviewed hypothetical edit, request comparison, request local physical-action approval, cancel pending input, and return presenter control.

The component never calls serial, changes global authoritative state directly, or synthesizes numerical progress. Codex owns API routing/state publication. The UI engineer supplies typed props/events and fixture stories; Codex mounts them once after agreement.

## 6. Physical action is a separate transaction

Only Codex's local action executor handles operator approval. The reviewed action identifies the predicted candidate, exact base context, device boot/session, gate epoch and calibration. A stale approval is rejected, not applied to the latest scenario.

`ACK` establishes command acceptance only. Debounced endpoint telemetry with current boot/session, increasing sequence and gate epoch establishes physical observation. Transit/unknown/fault/stale keeps P3 unavailable for observed-state calculation. After confirmation, a new physical revision is solved and checked before screen/LED publication.

The observed result has a new physical revision; it is not the old predicted result relabeled. A comparison may link the pinned baseline to this new observed run using the explicit intervention/confirmation receipt, while verifying equal initial scenario conditions. Before/after simulation restarts from the same initial synthetic population; this prototype does not model a real evacuation evolving during motor travel.

The serial pin map, NDJSON command names and power design are in `plans/PHYSICAL_DEMO_BUILD_PLAN.md` and `plans/PHYSICAL_DEMO_WIRING.md`. Claude's cloud agent gets none of those action functions.

## Integration handoff

Each owner supplies exact paths/commit, interface revision, setup, meaningful tests and results, fixture/live status, pending dependencies and known limitations. The devil's advocate reproduces critical failures independently. A human-provided handoff is sufficient if sessions have no authorized messaging channel; do not claim another session received a message that was never sent.

## New repository bootstrap — 24 October 2026

The target repository initially has no HEAD commit. Record “unborn main” instead of inventing a SHA. Before the first project commit, check remote refs and reconcile any existing remote history without force-pushing. Codex is the single bootstrap writer for shared manifests, configuration and central contracts. Other teammates can research, prepare fixtures and work only in disjoint owned paths in the existing checkout. Create separate worktrees only after an agreed committed baseline exists. A worktree does not copy uncommitted work or ignored credentials.

Root BUILD_PLAN.md is the current execution plan. Use geometry_revision and frontend/ as canonical naming; map_revision and app/ in older planning examples are historical aliases, not competing contracts. Google source snapshots remain dated23October and require the documented actual-account/SDK probes.
