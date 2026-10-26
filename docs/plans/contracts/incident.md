# Contract 5 detail: incident state and virtual doors (`/api/incident`)

Owner: incident teammate. Code: `backend/app/incident/`. Local only, no provider calls. Everything is a **simulated
device**: every payload carries `"simulated": true`; label it "Simulated device" on screen.

Mount (lead, `backend/app/main.py`):

```python
from backend.app.incident import build_incident_router
app.include_router(build_incident_router())
```

## Rules the UI must keep

- ACK is not arrival. A door is drawn **open** only when its gate reports `observed: "open"` (endpoint switch seen).
  Draw `OPENING`/`CLOSING` as the transit animation (1.5-2 s, `controller.transit_seconds`), `UNKNOWN`/`FAULT` as a
  warning, never as open. `applied` already encodes this per door.
- Approve quotes `plan_revision` + `candidate_hash` + `door_states`. Any change bumps `plan_revision` (hazards, fallback,
  reset), so a click on a stale card returns 409 `stale_plan`.
- Counts are "modeled crossings" (`plan.count_label`), never survival.
- Gates exist only for doors with actuation `motorized` or `simulated_servo` (building-v2: D4, D9). Other doors are
  signs: `applied: "sign"`, they follow the plan and cannot be jammed. A venue may have zero gates.

## GET `/api/incident` -> IncidentState

```jsonc
{
  "simulated": true,
  "venue_id": "building-v2", "geometry_revision": "geom-...",
  "plan_revision": 4,                       // 0-based counter shared by every change; never reused
  "hazards": [ /* HazardInput as posted */ ],
  "plan": null | {
    "plan_id": "dp-...", "plan_revision": 4, "candidate_hash": "...",
    "label": "primary" | "fallback",        // fallback while any door is stuck
    "note": null | "with D9 stuck closed",
    "reason": "hazards updated" | "fallback: D9 open never observed (stall); re-planned with D9 stuck closed",
    "valid": true,                          // checker-valid; false => approve is 422, show no numbers
    "status": "COMPLETE_WITHIN_MODEL",
    "initial_population": 125, "completed_crossings": 102, "baseline_completed": 80, "no_hazard_completed": 125,
    "count_label": "modeled crossings",
    "door_states": {"D1": "open", "D4": "closed", "D9": "open", ...},   // all doors; copy verbatim into approve
    "doors": [{"id": "D9", "state": "open", "lamp": "green", "actuation": "motorized", "controllable": true,
               "changed": true, "stuck": false, "decided_by": "door_planner", "reason": "...",
               "applied": "open" | "closed" | "moving" | "unknown" | "sign"}],
    "exits": [{"id": "X1", "zone": "...", "safe": true, "lamp": "green_flash", "modeled_crossings": 40, "reason": "..."}],
    "lights_px": "gggFF...",                // exit signs / strip, same px code as door-plan lights.px
    "stuck_doors": ["D9"], "held_doors": [],  // held: gates the unattended fail-safe keeps closed (see below)
    "advisories": [], "announcement": "...", "created_at": "ISO"
  },
  "plan_error": null | "outside_building",  // plan withdrawn because a re-plan failed
  "controller": {
    "simulated": true, "label": "Simulated device: no hardware is connected",
    "boot_id": "virtual-boot-...", "heartbeat": "ok" | "stale", "transit_seconds": 1.75,
    "gates": [{
      "gate_id": "D9", "state": "CLOSED|OPENING|OPEN|CLOSING|UNKNOWN|FAULT",
      "open_switch": false, "closed_switch": true,   // endpoint chips; both true or both false while not at rest = fault/transit
      "epoch": 1,                                    // +1 on every observed arrival
      "target": "OPEN" | "CLOSED" | null, "fault": null | "stall" | "switch_disagreement" | "dropped_ack",
      "last_command_id": "vcmd-3" | null, "last_ack": "ACCEPTED" | null,
      "observed": "open" | "closed" | null, "applied": "open|closed|moving|unknown", "detail": "...", "simulated": true }]
  },
  "stuck_doors": ["D9"],
  "approvals": [{ "approval_id": "apv-...", "plan_revision": 3, "candidate_hash": "...", "door_states": {...},
                  "status": "actuating" | "applied" | "failed", "commands": {"D9": "OPEN"},
                  "results": {"D9": "fault:stall"}, "reason": null | "...", "fallback_plan_revision": null | 4,
                  "started_at": "ISO", "finished_at": null | "ISO",
                  "actor": "operator" | "fail_safe", "simulated": true }],
  "approval_in_progress": false,
  "failsafe": { "armed": false, "window_seconds": 15,
                "status": "off" | "standing_by" | "counting_down" | "acted" | "approved",
                "plan_revision": null | 7, "deadline_at": null | "ISO", "seconds_left": null | 9.2,
                "held_doors": {"D4": ["HALL"]},   // gate -> hazard rooms it opens into, for gates held in the current plan
                "would_hold": ["D4"],             // while counting down: gates it would hold closed
                "note": "...", "last_action": null | {"at": "ISO", "plan_revision": 8, "approval_id": "apv-...", "summary": "..."} },
  "last_event_id": 17
}
```

## POST `/api/incident/hazards`

Body `{venue_id, expected_plan_revision, hazards: HazardInput[]}` (same `HazardInput` as door-plan; an empty list gives the
no-hazard baseline). Plans locally, bumps `plan_revision`, returns IncidentState. Switching `venue_id` to a different
venue starts a fresh incident and skips the revision check. Stuck doors persist across hazard changes.

- 409 `stale_plan` (revision), 409 `approval_in_progress`
- 404 `unknown_venue`
- 422 any door-planner code: `too_many_hazards`, `duplicate_hazard_id`, `invalid_horizon`, `outside_building`,
  `zone_mismatch`, `invalid_untenable_time`, plus `unconfirmed_camera_hazard`-style camera codes

Errors are `{"detail": {"code": "..."}}`.

## POST `/api/incident/approve`

Body `{plan_revision, candidate_hash, door_states}` copied from `plan`. Returns the ApprovalRecord immediately; the gates
then move in the background and progress arrives on SSE.

- 409 `stale_plan` (revision, hash or door_states differ), 409 `no_plan`, 409 `approval_in_progress`
- 422 `plan_not_valid`
- Only gates whose observed state differs from the plan are commanded; sign doors just follow the plan. If nothing needs
  to move the record is `applied` at once with `commands: {}`.
- If any gate ends `FAULT`/`UNKNOWN` (or never observed at its target): record `status: "failed"`, the gate becomes stuck,
  the plan is re-computed with it closed and published as `label: "fallback"` with a **new** `plan_revision`
  (`approval.fallback_plan_revision`). The fallback needs a fresh human approval. A stale controller marks every gate stuck.

## POST `/api/incident/faults` and `/faults/clear`

`{gate_id, fault}` with `fault` in `stall | switch_disagreement | dropped_ack | heartbeat_timeout` ("Jam the gate" =
`stall`). `heartbeat_timeout` is controller-wide (`gate_id` optional). Returns `{controller}`. 404 `unknown_gate`
(also for sign doors), 422 `gate_required`.

| fault | what the gate does on its next command (or the one in flight) |
|---|---|
| `stall` | ACK, OPENING, then no endpoint switch; after a timeout `FAULT` |
| `switch_disagreement` | transit ends with both switches on: `FAULT` |
| `dropped_ack` | no ACK within the timeout: `UNKNOWN` |
| `heartbeat_timeout` | after the watchdog (~3 s) every gate `UNKNOWN`, controller `heartbeat: "stale"`, commands refused, plan re-computed with all gates closed |

`faults/clear` body `{gate_id?}`: removes injected faults (all when omitted). A cleared gate stays `UNKNOWN`/`FAULT` and its
door stays stuck until it is observed again; `reset` is the full recovery.

## POST `/api/incident/reset`

Clears hazards, plan, approvals, stuck doors and faults; every gate returns to its default endpoint (CLOSED for D4/D9),
heartbeat ok, in-flight commands cancelled. `plan_revision` still increases. Returns IncidentState.

## POST `/api/incident/failsafe` (the unattended fail-safe)

Body `{armed: bool, window_seconds?: 5..120 (default 15), voice?: "gemini" | "browser" (default "browser")}`; returns
the `failsafe` view (`voice`, `voice_available` = GEMINI_API_KEY configured, `voice_model`). Local only, like every
`/api/incident` route: a phone's scoped cookie never reaches it. **Off by default; reset and a venue change turn it off.**

The one exception to "a human approves". Armed, every new checked plan (hazards, fallback, re-plan) starts a window. If
nobody approves, changes the hazards or disarms in that window, the fail-safe approves the plan itself
(`approval.actor: "fail_safe"`), after two rules a person would not need:

- it never opens a gate into a room with a hazard: every controllable gate with `entry_denied_into` is held closed
  (`plan.held_doors`, planned like a stuck door) and the plan is re-checked first, so a new `plan_revision` is approved;
- a gate in `FAULT`/`UNKNOWN` is treated as stuck closed.

It does nothing on a plan the checker did not accept, while doors are moving, or on a revision a person approved. If
the re-check with the held gates is not checker-valid, nothing moves and the person's plan stays approvable. Locked
gates (gas) are never switched. A held gate whose CLOSE is never observed is "position unknown, may still be open", not
"closed", and the next action's summary names it. Scope: motorized and simulated-servo gates; rooms with fire, smoke,
gas or a chemical (water does not deny entry).
Everything after the approval is the normal path: ACK is not arrival, a jam re-plans to a fallback, and the fallback
gets its own window. Disarming ("I'm here") hands held gates back to the planner (a new revision with the full plan, for
a person to approve). `last_action.summary` says what it did and, when holding a gate cost crossings, what a person could
approve instead ("a person could approve 105 by opening D4"). Counts stay modeled crossings.

### The fail-safe's voice: GET `/api/incident/failsafe/voice/{approval_id}`

Armed with `voice: "gemini"` (and a key), the server speaks for the fail-safe with Gemini TTS (`backend/app/ai/tts.py`,
`gemini-3.8-flash-tts`, one Interactions call, `store: false`, echoed model checked). The text is "Nobody approved in
time. The fail-safe approved the checked plan." plus the approved plan's announcement, with each door it is opening
worded "is opening" (never "is open"). It is synthesized when the window starts, for the plan the fail-safe would approve
(a dry run of the held re-check), and reused when it acts if the text is unchanged: one call per distinct text, at most
8 kept. A person who approves in time makes that clip unused (about $0.003).

The route returns `audio/wav` with `X-Voice-Model` and `X-Voice-Provenance: live`, waits up to 25 s for a clip still
being made, and answers 404 `no_voice` (a person's approval, or browser voice), 502 with the provider code
(`provider_timeout`, `provider_model_mismatch`, ...), or 504 `voice_pending`. `last_action.voice`,
`voice_status` (`pending | ready | failed`), `voice_model`, `voice_seconds`, `voice_error` say which voice spoke. The
browser plays the clip once per approval and falls back to its own voice on any failure, labelled on screen.

## GET `/api/incident/events` (SSE)

Headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`. `: ping` comment every 10 s. Reconnect with the `Last-Event-ID`
header (or `?last_event_id=N`): events after N are replayed from a bounded buffer (256); if N is older than the buffer a
`snapshot` is sent instead. A fresh connection starts with a `snapshot` (no `id:`).

Each frame: `id: <seq>\nevent: <type>\ndata: <json>\n\n`; every `data` has `seq`, `ts`, `type`, `simulated: true`,
`plan_revision`.

| event | extra fields |
|---|---|
| `snapshot` | `last_id`, `state` (IncidentState) |
| `plan` | `plan` (IncidentPlan or null), `hazards`, `stuck_doors`, `plan_error?` |
| `approval` | `approval` (ApprovalRecord; one event on start, one on finish) |
| `gate` | the gate fields above plus `phase`, `line`, `boot_id`, `seq_dev` |
| `fault` | `fault`, `gate_id`, `phase`, `line` (also `cleared`, `gates` on watchdog) |
| `reset` | `venue_id`, `line`, `state` |
| `failsafe` | `failsafe` (the view above), `line` (`FAILSAFE armed: ...`, `FAILSAFE r7: waiting 15 s ...`, `FAILSAFE r8: nobody approved within 15 s; ...`) |

`gate.phase`: `command` -> `ack` -> `transit` -> `observed` (success), or `ack_timeout`, `fault`, `rejected`.
`fault.phase`: `fault_injected`, `fault_cleared`, `controller_stale`. `line` is a ready-made serial-style string for the
event console, for example `CMD vcmd-1 SET_GATE_TARGET D9 OPEN`, `ACK vcmd-1 ACCEPTED (not arrival)`,
`OBSERVATION D9 OPEN open_switch=1 closed_switch=0 epoch=2`, `FAULT D9 stall: no endpoint switch after 3.25s`.

### Frontend recipe (door animation and chips)

1. On `gate` with `state: OPENING|CLOSING` start the leaf animation toward `target`, lasting `transit_seconds`.
2. On `gate.phase == "observed"` snap to the endpoint and light the matching chip (`open_switch` / `closed_switch`).
3. On `FAULT`/`UNKNOWN` freeze the leaf mid-way (or a `?` state) and show the fault badge; do not play an open animation.
4. On `plan` with `label: "fallback"` show `note` and `reason`; the previous approval card shows `status: "failed"`.
5. Phones / exit signs: render `plan.exits[].lamp` or `plan.lights_px` from the latest `plan` event, only when `plan.valid`.
