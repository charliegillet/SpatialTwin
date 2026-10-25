# Judge experience and stage runbook

Prepared 24 October 2026 after a devil's-advocate review of the first draft. Numbers below come from the local solver (120 synthetic occupants, 40 s horizon) and from the live runs recorded in `runtime/`.

## What the judge does

1. Places the red token on a pad of the physical table, or drops **Fire** on P1, P2 or B2 in the 3D twin.
2. Watches the twin re-solve: the exit routes, exit arrows and the hero number change ("60 of 120 reach an exit in 40 s").
3. Watches a Gemini managed agent investigate in Google's cloud, pausing for checked numbers only this laptop can compute.
4. Presses **Approve** and watches the miniature gate move, the endpoint switch confirm it and the twin re-solve to 117.
5. Optionally drops **Smoke** on a passage with an arrival time to see a forecast (dashed, never approvable).

## Hazards (what they mean, honestly)

| Hazard | Meaning in the model | Approvable |
| --- | --- | --- |
| Fire / red token | Closed from 0 s; the scenario re-solves | Yes, after a checked comparison (live agent result on the physical board) |
| Smoke at T s | Closed from T s, known in advance (even seconds 0–38) | No, forecast only |
| Clear | Removes a hazard | — |

Hazards attach only to P1, P2 and B2: those are the only elements the planner can close. Free placement would need routing we do not compute, so we do not offer it. Neither fire nor smoke spreads: each just closes a passage or exit, now or at T s.

## Facts the presenter must know

- Only **P2** blocked makes the reserve gate useful: 60 → 117 (+57). With **P1** or **B2** blocked, opening P3 gives **+0** because P3 adds no exit capacity. Direct the scripted judge to the P2 pad; offer P1/B2 afterwards as "find a blockage where the gate does nothing".
- Smoke on P2 at T s: 60 + 3T reach an exit; T ≥ 20 s changes nothing (everyone has passed P2 by then). Smoke on P1 at 12 s gives 96; smoke on B2 at 12 s gives 75 (travel time to the exit).
- The managed agent run takes 40–57 s (hard cap 60 s). It currently makes one client-executed tool call (`get_checked_comparison`, about 14 ms locally). Say "the agent investigated, our checker decided" — never "the agent recommends".
- Direct Argon grounding has taken 3–22 s on the synthetic board (22 s in the 25 October live check; one 20 s timeout seen earlier). Narrate through it; do not promise a number.
- Keep exactly one app tab open on the presenter laptop. Every tab on the laptop counts as the operator: a second tab can send commands, stops or start its own live investigation (seen in the 25 October live check).

## Two-minute script (N = Nihal, C = Charlie, J = judge)

| Time | Who | Screen |
| --- | --- | --- |
| 0:00 | N hands J the token: "This table is a building: 120 modeled people, two exits, a reserve gate. Block the east passage — this pad." | Twin, hero 120 of 120, live camera |
| 0:10 | J places the token; N: "Hands up." J presses **Read the board**. | Frozen still that was sent, "Gemini 4 Argon" |
| 0:20 | Box and "P2 · Live Gemini" appear. J taps **Confirm**. | Hero 120 → 60, east route fades, plume on P2, agent starts by itself |
| 0:30 | N: "A Gemini managed agent in Google's cloud is investigating. It cannot touch this table. It can only ask this laptop for checked numbers." | Agent phases with elapsed time |
| 0:40 | N taps **Why**: "The gate helps only here: +57. With P1 or B2 blocked it does nothing — it adds no exit." | Four local cases |
| 1:20 | Agent finishes: "Open P3: 60 → 117 · checked". | Approve enabled |
| 1:25 | N: "The AI can't move anything. You can." J presses **Approve**. | Ladder: Approved → Acknowledged (not arrival) → Gate moving → Open switch → Re-solved |
| 1:40 | — | Hero 117 of 120 (+57), "Done · re-solved 117" |
| 1:50 | N: "Gemini read it, the agent investigated, our checker decided, you approved, a switch confirmed. A model, not a survival figure. Tap Why? to see where the gate does nothing, or try Smoke." | — |
| 2:00 | C presses **Next judge** during Q&A (the challenge "find a blockage where the gate does nothing" only after this, with P3 closed again). | Checklist turns green; measured 9 s in the simulator |

## After the climax: Simulation and Camera twin (building-v2)

The presenter menu has a **Twin** toggle: Tabletop (default, everything above) · Simulation · Camera twin. It is locked while an analysis runs, and **Next judge** always returns to Tabletop. building-v2 is a separate, illustrative eight-zone building (125 synthetic people, 40 s, four exits E1–E4, doors D1–D10). Every building-v2 door is simulated; the only physical gate is P3 on the tabletop. D4 is labelled "simulated servo".

**1:40 hand-off.** N: "That's the table. Now break a full building yourself." Switch to Simulation. The judge picks a hazard and drops it in any room; the local planner re-solves in about 50 ms and shows closed doors, opened doors, red X or green exits and routes. For the agent question, press **Ask the agent** in the door plan panel (it follows the presenter menu's Analysis mode): progress phases with elapsed time, then the agent's explanation attributed to it, the checker's decision and whether they agree. The hero reads "N of 125 reach an exit in 40 s · building-v2 model".

What each hazard does (declared model assumptions, not measured behaviour):

| Hazard | Room | Doors | Exits and signs |
| --- | --- | --- | --- |
| Fire | no entry; people inside leave until 6 s | fire doors around it close to entry (egress still allowed) | exits in the room red X |
| Smoke | half speed; untenable at T s (default 12) | smoke doors close to entry | exits in the room unsafe |
| Gas | no entry; people inside leave until 10 s | nothing near it is switched or moved; D4/D9 locked if they border it; responders vent to the outside | signs at the room set static red once |
| Chemical | no entry; people inside leave until 10 s | doors around it close to entry (confine) | exits in the room red X |
| Water | passable at half speed | no change | route shown as slowed |

Real numbers (generated by `tools/gen_twin_fixtures.py`; full table in `docs/demo/building-v2-matrix.md`):

- **Fire in the Lobby** → E1 red X, D1/D5/D6 closed to entry, the planner opens the dock door D9: **125** vs 96 with doors at default (**+29**). It does not open D4: the north stair exit is already full, so D4 adds no exit capacity — the same lesson as P3 on the tabletop.
- **Fire in the West corridor** → the planner opens D4: 125 vs 104 (+21).
- **Smoke in the Hall** (untenable at 12 s) → D4 opened for egress only: 99 vs 87 (+12).
- **Gas in the Hall** → D4 locked closed, nothing switched near the gas, routes avoid the hall: 125.
- **Water** never changes a count; it slows routes.
- **Fire in Room A** leaves 8 people in the room at 6 s; **fire, smoke, gas or chemical in the East corridor** leaves the 5 kitchen staff without a route (its only door opens into the corridor). The screen says why. These are modeled outcomes caused by the hazard, not by a door policy.

**Camera twin (only if its rehearsal passed).** Print `venue/print/building_v2_sheet.svg` at 100 % on matte A3 and `venue/print/hazard_cards.svg` on A4 (cut out the cards). Lay the sheet flat under the overhead camera. Presenter menu → Calibrate: click the four corner markers TL, TR, BR, BL in order. A judge places a red card in a room → **Read the board** → one chip per card ("FIRE · Lobby · Live Gemini") → **Confirm** → the door plan updates. Say: "Card positions are mapped onto the reviewed floor plan; the 3D model is authored, not reconstructed." A camera read is perception only: unconfirmed or edited camera hazards are refused by the planner, and nothing physical moves.

Sources the hazard rules are inspired by (say "inspired by", never "the same system"): dynamic exit signage with green arrows and red crosses and a human controller (SFPE article on the EU GETAWAY Intelligent Active Dynamic Signage System); hold-open fire doors releasing on alarm (GEZE); gas-leak guidance to eliminate ignition sources and ventilate (EMC Insurance); chemical-spill guidance to confine and deny entry (Weill Cornell EHS).

## Live checks (25 October, Gemini 4 Argon)

- **Simulation agent** (fire in the Lobby, Live Gemini): completed in 50 s with one `plan_doors` call; recommended D4 closed, D9 open; agreed with the checker (125 of 125 vs 96). The first attempt hit the 60 s cap because the agent was invited to check extra states one turn at a time; `plan_doors` now returns every checked state in one call. Narrate through ~50 s as on the tabletop.
- **Camera twin** on a synthetic tilted still of the printed sheet (not a real camera): FIRE → Lobby, GAS → Hall, WATER → West corridor, all high confidence, within 8 cm; 24 s with clicked corners, 13 s with Gemini finding the corner markers. Confirmed cards gave a checked plan (78 of 125 vs 36; D9 opened, D4 gas-locked).
- **Static video** (probe P3): passes; the still-video path is enabled by its receipt.
- Still to rehearse on site: the real overhead camera, venue light and the printed sheet; the flashed firmware.

## Questions judges will ask

1. **What does the agent decide?** It investigates through client-executed tools. Our checker decides. No model output moves hardware.
2. **Why an agent then?** It runs in Google's managed environment, pauses for tools only this laptop can run, and resumes — orchestration across a trust boundary.
3. **Why about 50 s?** First status around 15 s, tool pause around 32 s, done around 51 s; hard cap 60 s.
4. **Why not give the agent the servo?** The cloud cannot reach this laptop, a human approves movement, and an acknowledgement is not arrival.
5. **Is it hardcoded?** Move the token: P1 +0, B2 +0, P2 +57. Each solve takes milliseconds and has a run id.
6. **What does Gemini see?** One still. It returns a validated pad id and a box; a human confirms. It is not 3D reconstruction.
7. **Why only three targets?** A closed set keeps every proposal checkable; free placement would need invented routing.
8. **Do 117 people survive?** 117 of 120 synthetic occupants reach a modeled exit within 40 s. Not survival, not a real venue.
9. **Why no gain with B2 or P1 blocked?** P3 adds no exit; it only feeds B2, which is then full or closed.
10. **Did it really open?** An independent endpoint switch confirms it before we re-solve.
11. **What about people moving while the gate moves?** Not modeled. Closures are known in advance, not reactive replanning.
12. **Is the exit just a rate?** Yes — declared rates and capacities, not measured.
13. **Where is the agent in Simulation?** The plan itself is the local planner: it tries every state of the two controllable doors (D4, D9), solves and checks each, and picks the best checked one. **Ask the agent** (door plan panel) then runs the same pattern as the tabletop: in Live Gemini mode the managed agent investigates in Google's cloud (network-disabled environment where configured) and can only ask this laptop two read-only questions, `plan_doors` and `compare_door_states`; the local checker answers from its own numbers and decides. The panel always shows "Checker decided: <doors> · N of 125", and if the agent's recommendation differs it says "Agent suggested X; the checker's best is Y". In Local solver mode no Gemini call is made and the result is labelled "Local solver · no Gemini call". The run is capped at 6 tool calls and 60 s, can be cancelled, and is dropped by a new hazard, a mode switch or Next judge. Nothing physical moves and counts are modeled crossings. The live path is exercised offline against the pinned SDK with mocked HTTP; a real Gemini run needs a key and spend approval.
14. **Why does a fire in one corner close the whole room?** Hazards apply per room in this model; finer placement would need geometry we do not compute.
15. **Why doesn't gas open doors to vent?** Venting through internal doors pushes gas into escape routes and moving a motorised door is an ignition risk; the screen tells responders to vent to the outside.
16. **Does the camera build the 3D model?** No. It reads card type and position; positions are mapped onto the authored floor plan through the four corner markers.

## Failure plan (most likely and damaging first)

1. **Firmware or servo not ready** — go/no-go three hours before; otherwise run the simulator and say so (the chip reads "Simulator").
2. **Agent slow or times out** — narrate the four-case strip while it runs. In the simulator a local check ("Local solver · no Gemini call") can still be approved. On the physical board it cannot: moving the gate needs a live agent result, so press Retry agent; without a working Gemini connection the gate cannot be approved, by design.
3. **Token off-pad or on P1/B2** — the screen says "Move the token onto a pad"; direct the judge to the recessed P2 pad.
4. **Venue Wi-Fi** — run Gemini over a phone hotspot; everything else is local.
5. **Glare or angle** — fixed mount, lamp, matte print; after one failed read use the manual hazard on the twin.
6. **A new mode misbehaves on stage** — hide it (Twin → Tabletop) and carry on; if the whole app is unstable, open the frozen tabletop build: `git worktree` at `../SpatialTwin-demo-v1` (tag `demo-v1`) served with `env -u GEMINI_API_KEY ../SpatialTwin/.venv/bin/python -m uvicorn backend.app.main:app --port 8766` from that folder (its `frontend/dist` is already built) (add the key back for live Gemini).
7. **Operator token** (physical mode) — enter it once in the presenter menu; it survives Clear and reset, not a page reload.

## Reset for next judge (target ≤ 20 s)

Lift the token, press **Next judge**, wait for the checklist: scenario clear, P3 closed (switch observed), no run active, and a live camera (physical board) or a ready board view (simulator).

## Decisions taken

- Judges use the presenter's laptop, not their own phones (the network guard admits only this laptop; the live event stream cannot carry a token).
- Motion only when state changes (routes, hero number, gate); nothing loops.
- The hero number reads "N of 120 reach an exit in 40 s"; avoid "still inside", which reads as casualties.

## Go / no-go (24 October review)

- **Simulator stage:** go once the stale "Done" state, the top-bar Clear and the disabled-button styling are fixed (in progress).
- **Physical board:** no-go until all three hold — the approval path refuses local results in the UI as well as the backend; the overhead camera is selected in the presenter menu and the synthetic-board fallback is off in physical mode; and one full live run succeeds on the real board over the stage network (live agent → Approve → switch → 117).
