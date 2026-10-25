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

## Failure plan (most likely and damaging first)

1. **Firmware or servo not ready** — go/no-go three hours before; otherwise run the simulator and say so (the chip reads "Simulator").
2. **Agent slow or times out** — narrate the four-case strip while it runs. In the simulator a local check ("Local solver · no Gemini call") can still be approved. On the physical board it cannot: moving the gate needs a live agent result, so press Retry agent; without a working Gemini connection the gate cannot be approved, by design.
3. **Token off-pad or on P1/B2** — the screen says "Move the token onto a pad"; direct the judge to the recessed P2 pad.
4. **Venue Wi-Fi** — run Gemini over a phone hotspot; everything else is local.
5. **Glare or angle** — fixed mount, lamp, matte print; after one failed read use the manual hazard on the twin.
6. **Operator token** (physical mode) — enter it once in the presenter menu; it survives Clear and reset, not a page reload.

## Reset for next judge (target ≤ 20 s)

Lift the token, press **Next judge**, wait for the checklist: scenario clear, P3 closed (switch observed), no run active, and a live camera (physical board) or a ready board view (simulator).

## Decisions taken

- Judges use the presenter's laptop, not their own phones (the network guard admits only this laptop; the live event stream cannot carry a token).
- Motion only when state changes (routes, hero number, gate); nothing loops.
- The hero number reads "N of 120 reach an exit in 40 s"; avoid "still inside", which reads as casualties.

## Go / no-go (24 October review)

- **Simulator stage:** go once the stale "Done" state, the top-bar Clear and the disabled-button styling are fixed (in progress).
- **Physical board:** no-go until all three hold — the approval path refuses local results in the UI as well as the backend; the overhead camera is selected in the presenter menu and the synthetic-board fallback is off in physical mode; and one full live run succeeds on the real board over the stage network (live agent → Approve → switch → 117).
