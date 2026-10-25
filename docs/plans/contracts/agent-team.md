# Contract: the managed-agent team (agents teammate, 26 Oct 2026)

Implementation: `backend/app/ai/managed/{door_agent,robustness,scenarios,trace,sandbox,costs}.py`,
`backend/app/hazard/door_planner.py` (`evaluate_with_faults`), routes in `backend/app/venues/agent.py`.
Every number shown is a **modeled crossing** checked by the local checker; an agent's number is a *claim* until
`verification` says it was reproduced. Thoughts are never streamed (AntigravityAgentConfig has no
`thinking_summaries`); the trace carries code cells, their results, visible output text and function calls.

## Backwards compatibility (the existing panel keeps working)

- `POST /investigate` with `{hazards, mode}` (no `lanes`) runs the **Strategist lane only**.
- `GET /investigations/{id}`: `status`, `provider_progress` and `investigation` keep their meaning and follow the
  **first lane**; `investigation` is `null` until that lane is published. Existing `DoorAgentResult` fields are
  unchanged; new fields are only added. `investigation.investigation_id` is the team id returned by POST.
- `deadline_seconds` is now the Strategist's deadline: default 45 s, max 90 (was 60 / 60).
- The old 75 s client give-up still works for the Strategist; for a team, use `deadline_at_ms` (below).

## Routes (prefix `/api/venues/{venue_id}`; an id from another venue answers 404 `unknown_investigation`)

### `POST /investigate`

```json
{"hazards": [...], "horizon_seconds": null, "mode": "live" | "local",
 "lanes": ["strategist", "robustness"],          // optional; default ["strategist"]; order ignored
 "deadline_seconds": 45,                         // strategist, 0 < s <= 90
 "robustness_deadline_seconds": 150,             // robustness, 0 < s <= 240
 "supersede": true}                              // a new live team cancels the running one (else 429)
```

Response 200:

```json
{"investigation_id": "dinv-ce5ab532-...",
 "deadline_at": "2026-10-26T21:24:01.672000Z", "deadline_at_ms": 1792963441672,   // latest lane deadline
 "lanes": {"strategist": {"investigation_id": "dinv-ce5ab532-....strategist", "deadline_seconds": 45.0,
                          "deadline_at": "...Z", "deadline_at_ms": 1792963336672},
           "robustness": {"investigation_id": "dinv-ce5ab532-....robustness", "deadline_seconds": 150.0,
                          "deadline_at": "...Z", "deadline_at_ms": 1792963441672}},
 "trace_url": "/api/venues/building-v2/investigations/dinv-ce5ab532-.../trace"}
```

Errors: 404 `unknown_venue`; 403 local mode in production; 422 `{code}` (`outside_building`, `invalid_horizon`,
`unconfirmed_camera_hazard`, `duplicate_lane`, pydantic validation); 429 when the shared provider slots or the team
slot are taken (a live team holds 1 shared slot + the team slot; at most one live team at a time).

The client should give up at `deadline_at_ms + 15 000` (cancel reserve + fallback), not at a fixed 75 s.

### `GET /investigations/{id}`

```json
{"investigation_id": "dinv-...", "status": "running" | "completed" | "failed" | "incomplete" | "cancelled" | "timed_out",
 "team_status": "running" | "finished" | "cancelled",
 "deadline_at": "...Z", "deadline_at_ms": 1792963441672,
 "lanes": {"strategist": LaneView | {"lane", "status": "running", "investigation_id", "deadline_*"}, ...},
 "parent_investigation_id": null, "trace_url": "...",
 "provider_progress": [ ...first lane's receipts, as before ... ],
 "investigation": DoorAgentResult | null}
```

Poll until `team_status != "running"` for the team; the legacy panel stops at `status != "running"`.

### `POST /investigations/{id}/cancel` — unchanged (`cancellation_requested` | `already_finished`). Cancels every lane;
a cancelled lane never falls back.

### `GET /investigations/{id}/trace` — SSE (see below). `Last-Event-ID` header or `?after=<seq>` replays.

### `POST /investigations/{id}/followup` — "What if D3 jams?"

```json
{"scenario": "stuck_closed:D3", "mode": "live" | "local", "deadline_seconds": 90}   // <= 180
```

Response: the POST /investigate shape plus `"parent_investigation_id"` and `"scenario"` (canonical label). It is a new
team with one lane, `followup`. Live: continues the parent's robustness (or follow-up) interaction in the **same
sandbox** (`environment=<environment_id>`, `previous_interaction_id=<acknowledgement interaction>`). Local: the
checker evaluates the scenario. Errors: 404; 409 `parent_running` (parent team still running); 409
`{"code": "parent_finishing", "retry_after_seconds": 2}` (the parent's acknowledgement is still in flight after a
15 s wait: retry); 409 `{"code": "parent_geometry_changed"}` (the venue's `geometry_revision` is no longer the one
the parent ran against, which the team record stores: re-investigate instead; applies to live and local);
409 `{"code": "followup_in_progress", "retry_after_seconds": 5}` (a live follow-up already holds this parent's
sandbox; follow-ups are serialised per sandbox environment and a second one is refused, never queued, because chained
interactions in one environment would interleave); 422 `{code}` for a bad scenario (`scenario_unrecognized`, ...). A live follow-up whose parent
was not live fails with `followup_parent_unavailable` and falls back to the labelled local lane.

## Scenario grammar (one string; also what agents write)

`baseline` | `stuck_closed:<DOOR>` | `exit_blocked:<EXIT>` | `jam:<DOOR|EXIT>@0.50` (0 < f < 1, two decimals) |
`untenable:<HAZARD_ID>=<SECONDS>` | `second_hazard:<TYPE>@<ZONE>`; up to 3 terms joined with `+`. Labels come back
canonical (terms sorted, factors `0.50`). A gas `second_hazard` can lock a controllable door: it stays closed.

## `DoorAgentResult` additions (all optional; existing fields unchanged)

| field | type | meaning |
|---|---|---|
| `lane` | `"strategist" \| "robustness" \| "followup" \| null` | which lane produced the top-level fields |
| `label` | string | honesty chip: `"Live Gemini · gemini-4-argon"`, `"Local solver · no Gemini call"`, `"Local fallback · live robustness lane failed (investigation_deadline)"`, `"Unavailable"` |
| `deadline_at`, `deadline_at_ms` | ISO-Z string, epoch ms | this lane's deadline |
| `token_budget` | int | lane `max_total_tokens` (strategist 40 000, robustness 150 000, follow-up 80 000) |
| `cost_estimate` | `{usd, input_tokens, cached_tokens, output_tokens, rates_per_million, basis}` \| null | estimate at Argon list price ($2 / $0.10 cached / $10 per 1M through 30 Nov 2026); null when local |
| `provider_retries` | int | 429/5xx retries inside the deadline |
| `stream` | `{requested, used, events, steps, drops, resumed, idle, fell_back_to_polling, rejected}` \| null | streaming receipt (live only) |
| `submission` | `{door_states, fallback_if_jammed, claims[{scenario, completed_crossings, candidate_hash?, applies_to}], rationale, source, warnings}` \| null | what the agent submitted (`source`: `submit_recommendation` \| `text_fallback` \| `local`) |
| `verification` | `{verified, total, checks[...], mismatches[...], source: "agent" \| "sandbox" \| "local", note}` \| null | local re-run of every claim; each check has `scenario, applies_to, claimed_completed_crossings, claimed_candidate_hash, local_completed_crossings, local_candidate_hash, local_is_valid, reproduced, reason` (`crossings_mismatch`, `candidate_hash_mismatch`, `scenario_unrecognized`, `unknown_fault_door`, ...) |
| `recommendation_source` | `"submit_recommendation" \| "text_fallback" \| "local" \| null` | `text_fallback` = the old RECOMMENDATION line (one release) |
| `fallback_if_jammed` | DoorStateMap \| null | state to use if an opened door jams shut |
| `recommended_ties_checked_best` | bool \| null | same checked crossings as the checker's best |
| `robustness` | Sweep \| null | local checker sweep (below); on the team result: the robustness/follow-up lane's |
| `robustness_headline` | string | e.g. `"D9 open holds 8 of 16 single failures; breaks under stuck_closed:D10, stuck_closed:D2; D4 open + D9 open ties at baseline and holds 18 of 18; if D9 jams: D4 open (modeled crossings, local checker)."` |
| `sandbox` | `{available, kit_version, files, bytes, network: "disabled" \| "inherited", mount: "inline_sources" \| "environment_reuse"}` \| null | robustness/follow-up only |
| `fallback_for` | `{investigation_id, status, errors}` \| null | set on a local fallback: the live attempt it replaces |
| `parent_investigation_id`, `scenario` | string \| null | follow-ups |
| `team_status` | `"running" \| "finished" \| "cancelled" \| null` | team result only |
| `lanes` | `{[lane]: LaneView}` | team result only |

`LaneView` = `{investigation_id, lane, status, provenance, label, recommended_door_states, fallback_if_jammed,
recommended_outcome, recommended_ties_checked_best, agrees_with_checker, agreement_note, explanation,
recommendation_source, robustness_headline, token_usage, token_budget, cost_estimate, deadline_at, deadline_at_ms,
latency_ms, provider_model, provider_retries, errors, scenario, verification: {verified, total, source,
mismatches} | null, stream, sandbox, fallback_for, fallback: LaneView | null, effective}` where `effective` is
`"live"`, `"local"`, `"local_fallback"` (use `fallback`) or `"none"`. A failed live lane is shown with its errors;
its local fallback is nested, never substituted silently. On screen: "N/N sandbox claims reproduced by local
checker" only when `verification.source == "sandbox"`; local verifications are not agent evidence.

**Provenance semantics.** `verification.source` is `"sandbox"` only when this lane's run produced a non-error
`code_execution_result` step (seen on the stream or in a polled interaction); a robustness/follow-up lane that
submitted without running code is `"agent"` (its numbers may be copied from `verify_candidates` or the input plan).
Each check carries `provenance`: `"sandbox"` when the claimed crossing count appears as a number in a
`code_execution_result` of the run (best-effort text match), else `"agent"`; `verification.sandbox_matched` counts
reproduced `sandbox` claims. A claim about a checker-rejected (invalid) door state is never reproduced
(`reason: "local_plan_invalid"`).

**Tokens.** The acknowledging continuation runs after the lane result is published, so its usage is added when the
result is read: `token_usage` and `cost_estimate` (lane view, team result top level and saved lane result) include
it and `ack_token_usage` shows it separately (the usage the provider reported when the acknowledgement was created).
It does not count against `token_budget`.

**Cancellation.** The local robustness sweep runs in a worker thread and is stopped (between scenarios) when its lane
ends for any reason: cancel, supersede, deadline or failure; `robustness.cancelled` is true for a sweep that was
stopped (it is also `truncated`).

`Sweep` (`robustness`): `{provenance: "local_checker", candidate, candidate_is_checked_best, baseline,
single_failures[{scenario, door_states, completed_crossings, initial_population, modeled_exposure_people_seconds,
is_valid, candidate_hash, best_door_states, best_completed_crossings, best_is_valid, holds, delta_vs_baseline}],
single_failures_total, single_failures_held, breaks[{scenario, completed_crossings, best_door_states,
best_completed_crossings}], fallback_if_jammed{if_jammed, door_states, completed_crossings, is_valid,
candidate_completed_crossings} | null, tied_best_states[{door_states, completed_crossings, single_failures_total,
single_failures_held, is_candidate}], most_robust_tied_state, untenable_sensitivity[{hazard_id, type, zone_id,
declared_untenable_s, curve[{untenable_s, completed_crossings, best_completed_crossings, holds}]}],
worst_second_hazard[{zone_id, type, completed_crossings, best_completed_crossings, best_door_states, holds,
is_valid}], solves, truncated, cancelled, elapsed_ms, note}`. "Holds" = no other door state does better under that failure.

## Trace SSE (`text/event-stream`)

Frame: `id: <seq>\nevent: <name>\ndata: <json>\n\n`; idle `: ping\n\n` every 10 s. Every `data` has
`{seq, event, lane, elapsed_ms}` plus:

| event | durable | extra fields |
|---|---|---|
| `deadline` | yes | `deadline_at, deadline_at_ms, lanes{[lane]: {investigation_id, deadline_seconds, deadline_at, deadline_at_ms}}` (first frame) |
| `lane` | yes | `status: "started" \| "plan_ready"`, `mode`, `deadline_*`, `token_budget`, `states_checked`, `fallback_for?` |
| `status` | no | `status` (provider lifecycle), `source?: "stream"`, `interaction_ref` (last 8 chars) |
| `delta` | no | `kind: "step_start" \| "delta"`, `index`, `step_type` (`code_execution_call`, `code_execution_result`, `model_output`, `function_call`, `thought`), `delta_type?`, `text?` (≤ 4000 chars, untrusted) |
| `step` | yes | `kind: "step"`, `index`, `step_type`, `chars`, `text?` (≤ 2000), `name?` (function), `language?`, `is_error?`, `usage?`, `source?: "poll"` |
| `tool` | yes | `function_name`, `status: executed \| failed \| duplicate`, `error`, `execution_time_ms`, `verified?`, `total?` |
| `verification` | yes | `verified, total, mismatches[], source` |
| `usage` | yes | `token_usage, token_budget, cost_estimate` |
| `retry` | yes | `method, code, attempt, delay_ms` |
| `stream` | yes | `action: "resumed" \| "polling"`, `last_event_id?`, `reason?: "idle"` |
| `fallback` | yes | `reason{investigation_id, status, errors}` |
| `result` | yes | a `LaneView` (without `fallback`/`effective`) |
| `done` | yes | `team_status, elapsed_ms` (last frame; the stream then closes) |

Non-durable frames are lost on reconnect; durable ones replay from the ledger (also after a server restart).
`thought` steps carry no text, ever.

## TypeScript additions requested (frontend/src/twin/types.ts is the lead's)

```ts
export type DoorAgentLane = 'strategist' | 'robustness' | 'followup';
export interface DoorAgentClaimCheck { index: number; scenario: string; applies_to: 'recommended' | 'fallback';
  claimed_completed_crossings: number | null; claimed_candidate_hash: string | null;
  local_completed_crossings: number | null; local_candidate_hash: string | null; local_is_valid: boolean | null;
  reproduced: boolean; reason: string | null }
export interface DoorAgentVerification { verified: number; total: number; source: 'agent' | 'sandbox' | 'local';
  mismatches: DoorAgentClaimCheck[]; checks?: DoorAgentClaimCheck[] }
export interface DoorAgentCost { usd: number; input_tokens: number; cached_tokens: number; output_tokens: number; basis: string }
export interface DoorAgentLaneView { investigation_id: string; lane: DoorAgentLane; status: DoorAgentStatus | 'running';
  provenance?: DoorAgentProvenance; label?: string; recommended_door_states?: DoorStateMap | null;
  fallback_if_jammed?: DoorStateMap | null; recommended_ties_checked_best?: boolean | null; agrees_with_checker?: boolean;
  agreement_note?: string; explanation?: string; robustness_headline?: string; verification?: DoorAgentVerification | null;
  token_usage?: Record<string, number>; token_budget?: number; cost_estimate?: DoorAgentCost | null;
  deadline_at?: string; deadline_at_ms?: number; latency_ms?: number; errors?: string[]; scenario?: string | null;
  fallback?: DoorAgentLaneView | null; effective?: 'live' | 'local' | 'local_fallback' | 'none' }
// DoorAgentResult gains (optional): lane, label, deadline_at, deadline_at_ms, token_budget, cost_estimate,
//   provider_retries, verification, recommendation_source, fallback_if_jammed, recommended_ties_checked_best,
//   robustness (unknown/record), robustness_headline, parent_investigation_id, scenario,
//   team_status: 'running' | 'finished' | 'cancelled', lanes: Partial<Record<DoorAgentLane, DoorAgentLaneView>>
// DoorAgentProgress gains (optional): team_status, deadline_at, deadline_at_ms, lanes, trace_url, parent_investigation_id
// DoorAgentStatus already covers the lane statuses; add 'running' only to DoorAgentLaneView.status.
```

`frontend/src/api/twin.ts`: send `lanes` (and `supersede`) in `startDoorInvestigation`, read `deadline_at_ms`;
add `followUpDoorInvestigation(venueId, id, scenario, mode)`; map the new error codes
(`followup_parent_unavailable`, `parent_finishing`, `submission_missing`, `investigation_deadline` now "did not
finish within its deadline").
