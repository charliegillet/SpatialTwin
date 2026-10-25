# Judge experience and stage runbook (demo v2, no hardware)

Rewritten 26 October 2026 for the software-only demo. The tabletop runbook (servo gate, endpoint switches, overhead
camera) lives with the frozen `demo-v1` tag. Numbers below come from the local solver and from live Gemini 4 Argon runs
recorded under `runtime/` on 25–26 October; every count is modeled crossings, never survival.

## The promise in one line

"Show us any building's evacuation map. Gemini 4 Argon turns it into a live twin, our checker plans the doors, a team of
managed agents stress-tests the plan, and you approve. AI proposes, the checker decides, a human approves."

## Before the judges arrive (venue preparation)

- The posted evacuation maps of the venue are read and accepted ahead of time on the presenter laptop
  (Build → photo → Accept). They stay in the gitignored `runtime/`: the venue's maps are under the owner's terms and are
  never committed or shared. Accepted venues so far: `ferry-building-level-3` (8 areas, 7 doors, 2 stair exits) and
  `ferry-building-level-2` (12 areas, 11 doors, D9 marked motorized).
- The same readings are exported as labelled **saved runs** of the venue's own maps ("a recorded Gemini 4 Argon
  reading from …; not a live call") by `runtime/live/export_saved_runs.py` into the gitignored `runtime/saved-runs/`,
  next to our synthetic sketch and office map. Start the server with them so Act 1 always has a fallback, and on the
  LAN so phones can reach it:
  `SPATIALTWIN_REAL2SIM_FIXTURES_DIR=runtime/saved-runs SPATIALTWIN_SIGN_SECRET=<32+ chars> .venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`
- Presenter menu → choose the venue to start on. **Next judge** returns to the built-in building; the venue picker in
  the presenter menu switches back.
- Phones: Simulation → **Phone exit signs** → **Show QR codes** (one per exit, one to propose hazards). Turn on
  **Judge mode** so judges' hazards join the twin at once; doors still need your Approve. If phones cannot reach the
  laptop (the panel warns), open **Signs on this laptop** on a second screen instead.
- Preflight: the capabilities chip shows a fresh live receipt; one live team run has completed in the last hour.
- One app tab only on the presenter laptop: every tab is the operator.

## Act 1 · "Your building in a minute" (Build mode)

1. The judge picks **Photo of a posted map**, **Sketch** or **PDF** and takes or uploads it.
2. Argon reads it live. Thought summaries stream (first one after about 11 s); the overlay draws every room, door and
   exit Argon found back onto the photo, so each element has visible evidence. Anything it could not read is listed.
3. The local compiler builds the venue, graph checks run in under a second, and if they find errors one critique round
   sends Argon the photo plus the overlay to fix them. The 3D stage shows the draft as **Draft preview · not accepted**.
4. The judge marks up to three doors as motorized and presses **Accept**. The twin switches to it.

Measured (live, `gemini-4-argon`, thinking medium):

| Input | Read | Critique round | Result |
| --- | --- | --- | --- |
| Ferry Building Level 3 map (photo) | 23–25 s | 35 s, 12 → 0 errors (an earlier attempt: 16 → 2) | accepted |
| Ferry Building Level 2 map (photo) | 37 s | 74 s, 16 → 0 errors | accepted |
| Ferry Building Floor 2, whole sheet (photo) | 41 s | 73 s, 20 → 4 errors | blocked by the checks, not accepted |
| Synthetic office map | 36–50 s | not needed | ready |
| Synthetic home sketch | 19 s | not needed | accepted |

Say while it reads: "Argon proposes the geometry. Nothing becomes the venue until the checks pass and you accept."
If the reading is slow or fails, say so and open a **saved run** (labelled as such, never passed off as live).

## Act 2 · "Break it" (Simulation)

1. The judge arms **Fire** (or Smoke, Gas, Chemical, Water) and drops it in a room of the new venue.
2. The local planner tries every state of the motorized doors, solves and checks each, and picks the best checked one
   in well under a second. The hero number changes ("78 of 80 reach an exit in 116 s · +10 by opening D9"), routes and
   exit signs redraw, fire doors close to entry.
3. The announcement says a door "is to be opened": it only says "is open" once that door's endpoint switch reports it.

## Act 3 · "Agents investigate, the checker decides, you approve"

1. **Ask the agent team · Live Gemini**. Two managed agents (Antigravity agent on `gemini-4-argon`) run in parallel in
   Google's cloud; their steps stream into two lanes:
   - **Strategist** submits a recommendation through a typed `submit_recommendation` function.
   - **Robustness** runs code in a network-disabled sandbox holding a copy of our solver kit, sweeping single-door and
     single-exit failures, then submits a recommendation with numeric claims.
2. Every claim is re-run by the local checker: the panel shows "agent claimed | checker verified" per claim and
   "N of N claims reproduced by the local checker". A mismatch is shown, never hidden.
3. The judge presses **Approve plan**. The simulated door controller acknowledges ("ACK · heard, not arrived"), the
   door travels about 1.75 s, and only the endpoint switch makes it read "Endpoint confirmed · open".
4. **Jam the gate**, then approve again: the door is never observed open, it is marked stuck, the server re-plans with
   it closed and the whole twin switches to that **fallback** (hero "fallback · D9 stuck · −10 vs the plan", routes,
   lamps and door list). The fallback needs a fresh human approval.

Live team runs on 26 October (building-v2, fire in the lobby, four runs):

- Strategist: 27–38 s every time, 2/2 claims reproduced, about $0.02.
- Robustness: 86 s, about 150 s and 172 s when it completed (12/12 claims reproduced, about $0.10; in the last run all
  12 numbers appeared in the sandbox's own code output). Once it missed its then 150 s deadline and the panel showed
  the labelled local fallback instead. The deadline is now 210 s, and nothing in Act 3 waits on this lane: approve and
  jam the doors while it streams.
- After the sandbox sweep was narrowed to single failures (the scenarios the claims are about), a run started by
  itself from a judge's phone hazard on Ferry Building Level 2 finished in 24 s (strategist, 2/2) and 57 s
  (robustness, 12/12, all computed in the sandbox), about $0.07 together: "D9 open holds 18 of 18 single failures".
- The team now starts by itself 2.5 s after a hazard is placed (live by default); "Ask the agent team" re-runs it.
- The strategist chose D4 closed + D9 open (125 of 125). The robustness lane chose D4 open + D9 open, also 125, which
  held under 18 of 18 single failures against 8 of 16 for the strategist's choice. The checker's own best is D4 closed
  + D9 open; the panel states both, and they tie.

## Close (15 s)

"Gemini read the map, the agents stress-tested the plan, our checker decided, you approved, and the door only counted
as open when its switch said so. A model of declared rates, not a survival figure."

## Questions judges will ask

1. **Did Argon really build this?** Yes: the overlay is drawn from the same numbers as the 3D venue. Every element has
   a point on the photo. Unreadable parts are listed, and Accept is blocked while graph checks report errors.
2. **Is it hardcoded?** Upload any map or sketch. Move the fire: each solve is a fresh run with its own id.
3. **What do the agents decide?** Nothing. They propose and make claims; the local checker re-runs every claim and
   decides; a human approves anything that changes state.
4. **Why two agents?** Different jobs: the fastest good plan, and the plan that survives failures. Their disagreement
   is shown, with the checker's numbers for both.
5. **What runs in the sandbox?** Our solver kit with the network disabled. networkx is not installed there, so the kit
   uses a pure-Python estimator and its claims are labelled "sandbox estimate"; the exact local checker then reproduces
   them. Do not claim the sandbox ran the exact solver.
6. **Are there guardrails on the agent?** Code runs in a network-disabled environment and only client functions reach
   the laptop. A hook that denies writes is configured but our probe did not observe a denial, so **do not claim the
   hook guardrail works**.
7. **Did the door really open?** The controller is simulated (no hardware at this event), but it keeps the hardware
   protocol: an ACK is not arrival, only the endpoint switch counts, and a stall, dropped ACK, disagreeing switches or a
   lost heartbeat all become faults that trigger a re-plan.
8. **Do 78 people survive?** 78 of 80 synthetic occupants reach a modeled exit within the horizon. Declared rates and
   capacities, not measured behaviour, not survival.
9. **What does it cost?** Reading a map is a few thousand tokens. A two-lane team run is about $0.12 at list prices,
   and the panel shows its estimate.

## Failure plan

1. **Argon slow or fails on a judge's photo**: show the failure honestly, then open a saved run (labelled).
2. **Agent lane slow or fails**: the lane shows the failure next to a labelled local fallback; the checker's plan is
   approvable without the agents.
3. **Venue Wi-Fi**: Gemini over a phone hotspot; everything else is local.
4. **A second tab or phone changes the hazards**: Approve waits ("Syncing this screen's hazards…") until this screen
   and the server agree.

## Reset for the next judge

Presenter menu → **Reset devices** (clears hazards, faults and stuck doors), or **Next judge** for a full reset to the
built-in building.
