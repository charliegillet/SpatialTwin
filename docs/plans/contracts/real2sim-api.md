# Real2Sim draft API (Contract 3, detailed)

Code: `backend/app/ai/real2sim/{routes,drafts,extract,critique,fixtures}.py`. Router factory
`build_real2sim_router(adapter, fixtures_enabled)`, prefix `/api/real2sim`. Tests: `tests/real2sim/test_{extract,
critique,drafts,routes_real2sim}.py`. Everything below is offline-tested; what still needs a live probe is listed at
the end.

The rule the UI must keep visible: **Argon proposes, the local compiler and graph checks decide, the operator
accepts.** A draft never changes the active venue until `POST .../accept` succeeds. Every draft carries a
`provenance` and a `provenance_label` that must be shown wherever the draft is shown.

## Lifecycle

```
POST /drafts ──> extracting ──> checking ──> [critiquing]* ──> ready ──POST /accept──> accepted
                     │              │              │
                     └──────────────┴──────────────┴──> failed
```

- `extracting`: live Argon call streaming (or a saved run being loaded).
- `checking`: local compile (preview, no controllable doors) + graph checks.
- `critiquing`: at most `settings.critique_rounds` (default 1, max 2) chained rounds, only when the checks report
  errors (or nothing compiled). A round's correction is kept only if errors strictly drop (or stay equal while
  warnings drop).
- `ready`: finished; Accept may be attempted (it re-compiles and re-checks; see `accept_blockers`).
- `failed`: see `errors[-1]` for the code. A failed live reading is never replaced by a fixture.
- `accepted`: closed; the venue is stored (and active when `make_active`).

`revision` increases at every persisted step (and at accept). Accept needs the current revision (compare-and-set).

## POST /api/real2sim/drafts

Request (JSON, unknown keys rejected):

```json
{
  "mode": "live",                       // "live" | "fixture"   (default "live")
  "image_base64": "<base64>",           // live only; decoded max 8 MiB
  "mime_type": "image/jpeg",            // live only: "image/jpeg" | "image/png" | "application/pdf"
  "source_kind": "photo",               // "photo" | "sketch" | "pdf"  (pdf <=> application/pdf)
  "fixture_id": null,                   // fixture only: a saved run id from GET /saved
  "name": "Meridian level 1",           // optional, 1-60 chars; used for the venue name and id slug
  "thinking_level": null                // optional "low" | "medium" | "high"; default from server (medium)
}
```

Response 200: `{"draft_id": "r2s-<24 hex>", "revision": 1, "status": "extracting"}`. Open the SSE stream next.

Errors (`{"detail": {"code": ...}}`):

| HTTP | code | when |
|---|---|---|
| 403 | `fixtures_disabled` | fixture mode while `SPATIALTWIN_MODE=production` |
| 404 | `unknown_fixture` | no such saved run |
| 409 | `draft_id_conflict` | id collision (practically never) |
| 413 | `source_too_large` | decoded source over 8 MiB |
| 415 | `unsupported_mime_type` | not jpeg/png/pdf |
| 422 | `source_required`, `invalid_source_encoding`, `source_mime_mismatch`, `source_kind_mismatch`, `invalid_source_image`, `invalid_source_dimensions` | bad upload (max 8192 px per side, 16 MP) |
| 422 | `invalid_fixture_id`, `invalid_fixture`, `fixture_with_image`, `fixture_id_required`, `live_request_with_fixture_id` | bad fixture request |
| 429 | `real2sim_busy` | another live reading is running (one at a time) |
| 503 | `configuration_missing` | no Gemini key configured: offer the saved runs instead |
| 503 | `runtime_storage_unavailable` | the runtime directory cannot be written |
| 422 | `{"detail": "Invalid request", "fields": [...]}` | schema-level validation (main.py handler; never echoes the image) |

Source handling: a JPEG/PNG with an EXIF rotation is turned upright before Argon reads it (`source.notes` says so),
so the overlay, the model and the operator see the same picture. A PDF is sent as a document (page 1); its overlay is
drawn on a blank page of the same proportions (page size from the MediaBox, else a declared A4-landscape default).

## GET /api/real2sim/drafts/{draft_id}

The draft view. Fields (all always present; `null`/empty until the step has run):

```json
{
  "draft_id": "r2s-b3a96db303b7a09e08bd3357",
  "revision": 3,
  "status": "ready",                      // see lifecycle
  "created_at": "2026-10-26T…+00:00", "updated_at": "…",
  "schema": "real2sim-draft-1",
  "mode": "live",                         // "live" | "fixture"
  "name": "Meridian level 1",             // request name, else the saved run title, else null
  "provenance": "live",                   // "live" | "synthetic" | "saved_run"
  "provenance_label": "Live Gemini 4 Argon reading (proposal; checked locally, accepted by an operator)",
  "fixture": null,                        // fixture mode: {fixture_id, title, provenance, recorded_at, interaction_id_hash, note}
  "source": {"kind": "photo", "mime_type": "image/jpeg", "sha256": "…", "bytes": 812345,
             "width_px": 3024, "height_px": 4032, "page_size_basis": null,      // PDFs: "mediabox" | "assumed_a4_landscape"
             "notes": ["rotated upright from EXIF orientation 6"], "stored_as": "source.jpg"},
  "draft": { /* VenueDraftV1 (schema.py), 0-1000 [y, x] image coordinates */ },
  "extracted_draft": null,                // the first reading, when a critique round replaced it
  "unreadable": ["smudged label top left"],       // Argon's own list: show next to Accept
  "dropped": ["door KD9: joins unknown or identical room ATTIC"],   // salvage_draft: elements Argon got wrong
  "repaired": ["room LIVING: name shortened to 40 characters"],     // salvage_draft: harmless repairs applied
  "extracted_salvage": null,              // {dropped, repaired} of the first reading when a round replaced it
  "compile": {
    "venue": { /* preview VenueV2 (no controllable doors, no headcount) */ },
    "report": {"element_ids": {"LIVING": "LIVING", "KD1": "D1", "X1": "E1"},   // draft key -> venue id
               "evidence_points": {"D1": [550, 300]},                         // venue id -> draft [y, x]
               "metres_per_px": 0.0158, "scale_basis": "dimension_label",     // or operator_input / default_width
               "defaults": ["door KD1 (D1) width 0.9 m (default; the drawing gave none)"],
               "edits": ["rounded every coordinate to 0.1 m"],
               "dropped": ["door KD7: no shared wall of at least 0.6 m"]},
    "error": null                         // e.g. "no_exit_survived", "empty_drawing": nothing could be compiled
  },
  "checks": {"issues": [{"code": "room_unreachable", "severity": "error", "message": "…", "element_ids": ["BATH"]}],
             "errors": 1, "warnings": 0, "compile_error": null, "geometry_revision": "geom-…"},
  "rounds": [{"round": 1, "issues_before": {"errors": 3, "warnings": 1, "compile_failed": false},
              "issues_after": {"errors": 0, "warnings": 1, "compile_failed": false}, "accepted": true,
              "note": "round 1: 3 errors, 1 warnings -> 0 errors, 1 warnings; correction kept",
              "errors": [], "interaction_id_hash": "5f2c…", "provider_model": "gemini-4-argon",
              "token_usage": {"total_tokens": 9000}, "latency_ms": 14210.3, "overlay_sent": true,
              "dropped": [], "repaired": []}],
  "critique_note": null,                  // e.g. "no critique needed: …", "critique skipped: a saved run makes no provider call"
  "thoughts": [{"phase": "extract", "text": "**Reading the walls** …", "recorded": false}],  // max 120, 1500 chars each
  "receipts": [{"phase": "extract", "status": "completed", "provenance": "live", "provider_model": "gemini-4-argon",
                "interaction_id_hash": "a1b2c3d4e5f60718", "token_usage": {"total_tokens": 23000},
                "latency_ms": 28740.1, "first_thought_ms": 6120.4, "first_output_ms": 21002.9,
                "sdk_version": "2.33.0", "thinking_level": "medium", "streamed": true, "errors": []}],
  "errors": [],                           // codes, newest last (non-fatal ones too: overlay_unavailable, topdown_unavailable)
  "timings_ms": {"extract": 28740.1, "compile_checks": [4.8, 5.1], "render": 49.5, "total": 43210.0},
  "settings": {"thinking_level": "medium", "critique_rounds": 1, "stream": true},
  "overlay_available": true, "topdown_available": true,
  "accepted": null,                       // after accept: {venue_id, geometry_revision, accepted_at, controllable_doors,
                                          //   headcount, building_width_m, make_active, report, issues}
  "controllable_door_candidates": [{"key": "KD1", "between": ["LIVING", "HALL"], "room_names": ["Living", "Hall"],
                                    "symbol": "swing", "confidence": 0.9, "venue_door_id": "D1"}],
  "max_controllable_doors": 3,
  "accept_blockers": [],                  // preview: "status:extracting", "compile:no_exit_survived", graph error codes
  "last_event_id": 14                     // null after a restart (the stream is then re-synthesized)
}
```

Raw provider interaction ids are never returned or stored; `interaction_id_hash` is
`sha256(id)[:16]`, the same digest `tools/probe_capabilities.py` writes.

Errors: 404 `unknown_draft` (also for any id not matching `^r2s-[0-9a-f]{24}$`).

## GET /api/real2sim/drafts/{draft_id}/events (SSE)

`text/event-stream`. Every event has an integer `id` (per draft, from 1), an `event` name and one JSON `data` line.
Replay: send `Last-Event-ID: <n>` (EventSource does this on reconnect) or `?last_event_id=<n>`; the server replays
every retained event with id > n, then follows live. Idle keepalive is the comment line `: ping` (every 15 s). The
server **closes the stream after `done` or `error`**: close the `EventSource` on those two events, otherwise the
browser reconnects (and receives nothing new). The log keeps at most 400 events per draft; thoughts are capped.

| event | data |
|---|---|
| `status` | `{"draft_id", "status", "phase", "revision", "provenance"}`; phase: `read`, `check`, `critique-1`, `critique-2`, `done`, `replay` |
| `thought` | `{"phase": "extract" \| "critique-1" \| "critique-2" \| "saved_run", "index", "text", "recorded"}`; `recorded: true` = replayed from a saved run |
| `draft` | `{"phase", "draft": VenueDraftV1, "unreadable": [...], "dropped": [...], "repaired": [...], "counts": {"rooms", "doors", "exits"}}` |
| `checks` | `{"phase", "issues": [GraphIssue], "errors", "warnings", "compile_error", "geometry_revision"}` |
| `round` | one critique round record (same shape as `rounds[]` in the view) |
| `done` | `{"draft_id", "status": "ready", "revision", "errors", "warnings", "provenance"}` (terminal) |
| `error` | `{"draft_id", "status": "failed", "revision", "code", "provenance"}` (terminal) |

Typical live order: `status(extracting)`, `thought`×n, `draft`, `status(checking)`, `checks`,
[`status(critiquing)`, `thought`×n, `round`, `draft`, `checks`], `status(ready)`, `done`.
After a server restart the stream is re-synthesized from the stored status: `status(phase "replay")` then `done` or
`error`. A draft left in progress by a restart is reported failed with `pipeline_interrupted`.

Render `thought.text` as plain text (it is model text and may quote what is written in the image).

## GET /api/real2sim/drafts/{draft_id}/overlay.png and /topdown.png

`image/png`, `Cache-Control: no-store`. The overlay is the source image with the compiled geometry drawn back on it
(room outlines and names, door ticks labelled with venue ids, exits, Argon's evidence points, dropped elements in
red); the top-down is the preview VenueV2 alone. Re-fetch after `done` (a kept critique round redraws both).
404 `overlay_unavailable` / `topdown_unavailable` (nothing compiled, or rendering failed; `errors` says which).

## POST /api/real2sim/drafts/{draft_id}/accept

```json
{
  "expected_revision": 3,                 // the view's revision (or the last status/done event's)
  "controllable_doors": ["KD1", "KD5"],  // draft door keys, at most 3, unique; default []
  "headcount": 40,                        // optional 0-5000: spread by the compiler over non-circulation rooms
  "building_width_m": 24.0,               // optional 0-500: the operator's scale override (east-west width)
  "venue_id": null,                       // optional ^[a-z0-9-]{3,40}$, never "building-v2"; default slug(name|title)+"-"+6 hex
  "make_active": true
}
```

The server recompiles with these choices, runs the graph checks, then stores the venue and closes the draft in one
compare-and-set transaction (`VenueRegistry.accept_draft`).

Response 200:

```json
{"venue_id": "meridian-level-1-24a745", "venue_revision": 1, "draft_revision": 4, "active_revision": 7,
 "geometry_revision": "geom-e6e3b8deabc33d02", "provenance": "live",
 "warnings": [/* GraphIssue with severity "warning" */], "defaults": ["…declared defaults…"]}
```

`active_revision` is `null` when `make_active` is false. After a 200, refetch the active venue
(`GET /api/venues/active`, `GET /api/venues/{venue_id}`): the 3D scene keys on `geometry_revision`.

Errors:

| HTTP | detail |
|---|---|
| 404 | `{"code": "unknown_draft"}` |
| 409 | `{"code": "draft_not_ready", "status": "<status>"}` (still running, failed, or already accepted) |
| 409 | `{"code": "stale_draft_revision", "revision": <current>}`; also a bare `{"code": "<registry code>"}` (`stale_draft_revision`, `draft_closed`, `draft_not_ready`, ...) if the registry's compare-and-set loses a race |
| 422 | `{"code": "too_many_controllable_doors", "max": 3}`, `{"code": "duplicate_controllable_door"}`, `{"code": "unknown_controllable_door", "keys": [...]}`, `{"code": "invalid_venue_id"}` |
| 422 | `{"code": "compile_failed", "error": "no_exit_survived"}` (nothing could be compiled) / `{"code": "compiler_failure"}` |
| 422 | `{"code": "graph_check_errors", "issues": [GraphIssue, ...]}` (all issues, errors and warnings) |

A 422 leaves the draft `ready`: the operator can change the controllable doors or the width and try again.

## GET /api/real2sim/saved

```json
{"fixtures_enabled": true,
 "saved": [{"fixture_id": "sketch-home", "title": "Hand-drawn home sketch: six rooms, window exit",
            "source_kind": "sketch", "provenance": "synthetic",
            "provenance_label": "Synthetic saved run: an image drawn by our own generator, not a photograph and not a Gemini reading",
            "recorded_at": null, "interaction_id_hash": null, "note": "…", "source_mime": "image/png",
            "source_sha256": "…", "counts": {"rooms": 6, "doors": 6, "exits": 3},
            "draft_title": "Home sketch", "image_kind": "sketch"}],
 "invalid": []}
```

With fixtures disabled: `{"fixtures_enabled": false, "saved": [], "invalid": []}`. A recorded live run
(`provenance: "saved_run"`) is labelled "Saved run: a recorded Gemini 4 Argon reading from <time>, interaction
#<hash>; not a live call". Saved runs make no provider call and run no critique round.

## Configuration (environment)

| variable | default | meaning |
|---|---|---|
| `SPATIALTWIN_REAL2SIM_THINKING` | `medium` | default thinking level (`low`/`medium`/`high`) |
| `SPATIALTWIN_REAL2SIM_STREAM` | `1` | `0` = one non-streaming call (no live thought summaries) |
| `SPATIALTWIN_REAL2SIM_CRITIQUE_ROUNDS` | `1` | 0-2 |
| `SPATIALTWIN_REAL2SIM_DIR` | `<repo>/runtime/real2sim` | per-draft source, canvas, overlay, top-down files |
| `SPATIALTWIN_REAL2SIM_FIXTURES_DIR` | `<repo>/venue/real2sim` | saved runs (Contract 2 layout) |

Fixed limits: extraction deadline 120 s, critique deadline 90 s, `max_output_tokens` 32768, image parts at
`resolution: "high"`, one live reading at a time.

## Provider call (for reviewers)

`client.aio.interactions.create(model="gemini-4-argon", system_instruction=…, input=[text, image|document],
generation_config={"thinking_level", "thinking_summaries": "auto", "max_output_tokens": 32768},
response_format={"type": "text", "mime_type": "application/json", "schema": provider_response_schema()},
store=True, stream=True, timeout=…)`; the critique adds `previous_interaction_id` and sends the overlay PNG plus the
typed issues (draft keys, not venue ids). The output is parsed as strict JSON and rebuilt with `salvage_draft`;
model mismatch, missing receipt, a non-completed status, an unexpected step (tool call), an incomplete stream or a
malformed output are typed failures (`provider_model_mismatch`, `provider_receipt_missing`,
`provider_status_not_completed`, `unexpected_provider_step`, `provider_stream_incomplete`, `invalid_provider_output`,
`draft_not_an_object`, `no_room_survived`); transport errors map to `provider_timeout`, `provider_rate_limited`,
`provider_access_denied`, `provider_unavailable`, `provider_request_rejected`, `provider_stream_error`,
`provider_failure`; local faults are `local_processing_failure`.

**Verified offline** against google-genai 2.33.0 with mocked HTTP (request field names, SSE parsing of
`thought_summary`/`text` deltas, unknown events skipped).

**Verified live (26 Oct 2026, through the running server, receipts in `runtime/live/*-live-view.json`):**

- The first schema (with every bound and array limit) was refused: HTTP 400 "the specified schema produces a
  constraint that has too many states for serving". `provider_response_schema()` is now structural only; every bound
  is enforced by `salvage_draft`. With it, `stream=True`, `store=True`, `thinking_summaries: "auto"` and image
  `resolution: "high"` are all accepted.
- `sketch-home` (sketch, medium): ready in 20.1 s wall, first output 6.5 s, 4,993 tokens; 6/6 rooms, 6/6 doors, 3/3
  exits, scale from the "12 m" dimension label; 0 graph-check issues. No thought tokens: Argon did not think.
- `evac-office` (photo, medium): ready in 36.2 s, first thought 10.9 s, 6,641 tokens; 9/9 rooms, 10/10 doors, 4/4
  exits, scale from the 10 m scale bar; 0 issues; 2 thought summaries.
- `evac-office` (photo, high): ready in 50.2 s, first thought 7.9 s, 8,445 tokens; the same perfect reading; 7 thought
  summaries.
- Thought summaries stream only when the model thinks; at `medium` a simple sketch may show none.

**Still needs a live probe:** PDF document parts, and a critique round chained on `previous_interaction_id` with a new
image (both readings above passed the checks, so no critique round ran).
