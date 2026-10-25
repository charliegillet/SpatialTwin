# Demo v2 (no hardware): team contracts and file ownership

Lead: Claude (Opus 5.5). Approved plan: `/Users/nihalnihalani/.claude/plans/gleaming-imagining-puffin.md`.
Worktree (the only implementation root): `/Users/nihalnihalani/Desktop/Github/SpatialTwin/.claude/worktrees/demo-v2-software`
(branch `worktree-demo-v2-software`, based on `origin/main` 2142e41 plus uncommitted Phase 0 and Phase A work).

## Ground rules for every teammate

- **Write only the files you own** (table below). Shared entrypoints have one writer: the lead. If you need a change
  in a file you do not own (a route mounted in `main.py`, a type in `frontend/src/twin/types.ts`, a new dependency),
  put the exact request in your final report instead of editing.
- **No live provider calls.** No Gemini key is configured and the offline test harness blocks the network
  (`tests/conftest.py`). Code paths that call Gemini must be testable with a fake client. Live probes are run by the
  lead later, with the user's approval.
- **No commits, no branch switches, no `git stash`.** Other teammates are editing the same working tree right now.
  Never run `git checkout`, `git restore`, `git reset` or `git clean` on any path.
- **Match the house style.** Read neighbouring modules first: dense, precise docstrings that say *why*; typed
  pydantic models with `extra="forbid"`; error codes as short snake_case strings; no raw provider text or image bytes
  in logs or errors; honest provenance labels (`live`, `fixture`, `saved_run`, `local`, `simulated`).
- **Product invariants (README):** AI proposes, the local checker decides, a human approves anything that changes
  state. Counts are "modeled crossings", never survival. Live failures stay failures; a fixture is always labelled.
- **Tests:** backend `.../SpatialTwin/.venv/bin/python -m pytest -q -p no:cacheprovider <your tests>` from the worktree
  root (the venv lives in the main checkout: `/Users/nihalnihalani/Desktop/Github/SpatialTwin/.venv`). Run the full
  suite before you report. Frontend: `cd frontend && npm test && npx tsc --noEmit`. New test folders need an
  `__init__.py` (see `tests/venues/`).
- Phase A already landed: venue registry (`backend/app/venues/registry.py`), generic `venue_id`
  (`backend/app/venues/model.py`), graph checks (`backend/app/venues/graph_checks.py`), venue-aware frontend API
  (`frontend/src/api/twin.ts`). A hand-written second venue is `tests/venues/fixtures/home_flat.json`.

## File ownership

| Owner | Files (create or edit) |
|---|---|
| lead | `backend/app/main.py`, `tests/conftest.py`, `requirements*`, `frontend/package*.json`, `backend/app/venues/{model,registry,graph_checks,routes,schemas}.py`, `backend/app/ai/real2sim/schema.py`, `frontend/src/App.tsx`, `frontend/src/api/**`, `frontend/src/twin/types.ts`, `frontend/src/components/{TwinWorkspace,PresenterMenu}.tsx`, this file |
| real2sim (Opus) | `backend/app/ai/real2sim/{extract,critique,drafts,routes,fixtures}.py`, `tests/real2sim/test_{extract,critique,drafts,routes}*.py`, `docs/plans/contracts/real2sim-api.md` |
| compiler (Sonnet) | `backend/app/venues/compiler.py`, `backend/app/ai/real2sim/overlay.py`, `venue/real2sim/**`, `tools/gen_real2sim_fixtures.py`, `tests/real2sim/test_{compiler,overlay,fixtures}*.py`, `tests/real2sim/__init__.py`, `docs/plans/contracts/compiler.md` |
| agents (Opus) | `backend/app/ai/managed/**`, `backend/app/hazard/door_planner.py`, `backend/app/venues/agent.py`, `tools/build_sandbox_kit.py`, `tools/probe_capabilities.py`, `tests/ai_contracts/**`, `tests/venues/test_door_planner*.py`, `tests/agents/**`, `docs/plans/contracts/agent-team.md`, `docs/ai/managed.md` |
| incident (Sonnet) | `backend/app/incident/**`, `tests/incident/**`, `docs/plans/contracts/incident.md` |
| devil's advocate (Opus) | read-only everywhere; reports findings in its final message |

## Contract 1: VenueDraftV1 and the compiler (frozen)

`backend/app/ai/real2sim/schema.py` defines `VenueDraftV1` (what Argon returns, 0–1000 `[y, x]` image coordinates),
`SourceImage`, `CompileReport` and `CompileResult`. Do not redefine them.

```python
# backend/app/venues/compiler.py (compiler teammate)
def compile_draft(draft: VenueDraftV1, image: SourceImage, *, venue_id: str,
                  controllable_doors: Iterable[str] = (), headcount: Optional[int] = None,
                  building_width_m: Optional[float] = None,
                  name: Optional[str] = None, provenance: Optional[str] = None) -> CompileResult: ...
```

- `building_width_m` is the operator's scale override (overall east–west width of the drawn building). It wins over
  the draft's `scale`; with neither, the compiler assumes a declared default width and says so in `defaults`.

- Deterministic: same inputs, same `VenueV2` (including `geometry_revision = "geom-" + sha256(...)[:16]`).
- Output is a strict, unchanged `VenueV2` that renders in the 3D scene and plans with the existing solver:
  rectilinear rooms, doors exactly on shared axis-aligned walls, exits exactly on outside walls (see
  `frontend/src/twin/sceneModel.ts:28-100` and `graph_checks.py`), at most one door per room pair (merge parallel
  doors: sum widths), occupants ≤ capacity, horizon a multiple of the step and ≤ 120 s, `led_map` covering every
  exit and controllable door.
- `controllable_doors` are draft door keys the operator marked (at most 3): `default_state="closed"`,
  `planner_can_open=True`, `actuation="motorized"`. Every other door is open by default.
- Declared defaults are listed in `CompileReport.defaults` and end up in the venue `provenance` text.

```python
# backend/app/ai/real2sim/overlay.py (compiler teammate)
def render_overlay(image_bytes: bytes, draft: VenueDraftV1, result: CompileResult) -> bytes: ...  # PNG
def render_topdown(venue: VenueV2, width_px: int = 1200) -> bytes: ...                            # PNG
```

## Contract 2: saved runs (fixtures) on disk

`venue/real2sim/<fixture_id>/` holds `source.png` (or `.jpg`), `draft.json` (a `VenueDraftV1`), and `meta.json`:
`{"fixture_id", "title", "source_kind": "photo"|"sketch"|"pdf", "provenance": "saved_run"|"synthetic",
"recorded_at": ISO or null, "interaction_id_hash": str or null, "note"}`. A synthetic image drawn by our own tool is
`"provenance": "synthetic"` and must be labelled so on screen; a recorded live reading is `"saved_run"`.
The compiler teammate creates at least `evac-office` (a posted-evacuation-map style image) and `sketch-home`
(a hand-drawn style home plan) with `tools/gen_real2sim_fixtures.py`.

## Contract 3: Real2Sim draft API (real2sim teammate defines details in `docs/plans/contracts/real2sim-api.md`)

Router factory: `build_real2sim_router(adapter: GroundingAdapter, fixtures_enabled: Callable[[], bool]) -> APIRouter`,
prefix `/api/real2sim`. The lead mounts it in `main.py`. Minimum surface:

- `POST /api/real2sim/drafts` `{image_base64, mime_type, source_kind, mode: "live"|"fixture", fixture_id?, name?}`
  → `{draft_id, revision, status}`; extraction continues in the background.
- `GET /api/real2sim/drafts/{id}` → the draft view (status, provenance, draft, compiled venue, checks, critique
  rounds, thought summaries, unreadable list, receipts, errors).
- `GET /api/real2sim/drafts/{id}/events` → SSE (`status`, `thought`, `draft`, `checks`, `round`, `done`, `error`,
  `: ping`), replayable with `Last-Event-ID`.
- `GET /api/real2sim/drafts/{id}/overlay.png`, `/topdown.png`.
- `POST /api/real2sim/drafts/{id}/accept` `{expected_revision, controllable_doors, headcount?, venue_id?, make_active}`
  → `{venue_id, venue_revision, active_revision}`; 409 on a stale revision, 422 when graph checks have errors.
  Uses `venue_registry().accept_draft(...)` from Phase A.
- `GET /api/real2sim/saved` → the saved runs from Contract 2.

## Contract 4: managed-agent team (agents teammate details it in `docs/plans/contracts/agent-team.md`)

Keeps the existing routes in `backend/app/venues/agent.py` working (the frontend uses them today) and adds a trace
stream `GET /api/venues/{venue_id}/investigations/{id}/trace` (SSE). The result gains lanes (strategist,
robustness), a `submit_recommendation`-based recommendation with locally re-verified claims, and a robustness summary.

## Contract 5: incident state and virtual doors (incident teammate details it in `docs/plans/contracts/incident.md`)

Router factory `build_incident_router(...) -> APIRouter`, prefix `/api/incident`: incident state per venue
(hazards, checked plan with `plan_revision` + `candidate_hash`), approvals keyed on both, a `VirtualDoorController`
(ACK ≠ arrival, 1.5–2 s transit, endpoint switches, injectable faults), and `GET /api/incident/events` SSE.
