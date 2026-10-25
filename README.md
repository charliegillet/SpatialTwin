# SpatialTwin — Gemini 4 Argon Hackathon Demonstrator

Show it any building's evacuation map. **Gemini 4 Argon** reads the photo, sketch or PDF into a live 3D twin, a local planner and checker decide which doors to open, a team of **Gemini managed agents** stress-tests that plan in Google's cloud, and a person approves before any door moves. Judges join in from their own phones: each phone becomes a live exit sign, and they can drop hazards into the building.

AI proposes; the local checker decides; a human approves anything that changes state. Every count is a modeled crossing of synthetic occupants, never a survival figure. There is no hardware at this event: the doors are a simulated controller that keeps the hardware protocol (an acknowledgement is not arrival; only an endpoint switch counts).

**Repository:** <https://github.com/charliegillet/SpatialTwin> · **Contributors:** Nihal, Charlie, Codex, Claude · SpatialTwin began before the event (the tabletop version is tagged `demo-v1`); this demo adds Real2Sim, the agent team, the virtual door controller and phone signs.

---

## The demo in three acts

| Act | What the judge does | What decides |
| --- | --- | --- |
| **1 · Build** | Photographs the posted evacuation map (or a sketch or PDF). Argon's reading streams with thought summaries; the overlay draws every room, door and exit back onto the photo; graph checks run and one critique round fixes errors; the judge marks up to three motorized doors and presses **Accept**. | A deterministic compiler and graph checks; Accept is blocked while any check fails. |
| **2 · Break it** | Drops Fire, Smoke, Gas, Chemical or Water anywhere, on the laptop or from a phone (Judge mode). Doors close to entry, exits turn red or green, routes re-plan, phone signs flip. | The local door planner tries every state of the motorized doors, solves and checks each, and picks the best checked plan. |
| **3 · Agents, checker, approval** | **Ask the agent team**: a strategist and a robustness lane run in parallel on `gemini-4-argon`, the robustness lane running our solver kit in a network-disabled sandbox. Every claimed number is re-run by the local checker. The judge approves; the virtual door travels and its endpoint confirms it; **Jam the gate** forces a re-plan to the checked fallback. | The checker decides; the human approves; only an endpoint observation counts as open. |

Stage runbook with measured live timings: [docs/demo/judge-experience.md](docs/demo/judge-experience.md) · backup video script: [docs/demo/backup-video.md](docs/demo/backup-video.md).

---

## Architecture

```
 Phones (judges)                           Browser (React 19 + Vite; React Three Fiber for the 3D twin)
 sign.html: live exit sign or              ├─ Build: Real2Sim panel, overlay, checks, Accept, 3D draft preview
 hazard proposer (scoped cookie)           ├─ Simulation: hazards, door plan, agent-team lanes, approval and doors
        │ HTTP + SSE (allowlist only)      └─ Presenter: venue picker, phone QR codes, Judge mode
        ▼                                              │ HTTP + server-sent events
 ┌─────────────────────────── Local authoritative backend (FastAPI + SQLite) ───────────────────────────────┐
 │ NetworkGuard (loopback, or a scoped phone cookie for the sign allowlist) · venue registry (revisions)     │
 │ Real2Sim: extract → salvage → compiler → graph checks → critique → Accept                                 │
 │ flow_solver_v2 + checker_v2 + hazard effects + door planner + announcer                                  │
 │ incident mirror + virtual door controller (ACK ≠ arrival, faults, fallback re-plan) · phone signs         │
 └──────────────▲───────────────────────────────────────────────────────────────▲──────────────────────────┘
                │ structured readings (proposals only)                          │ client functions + verified claims
        gemini-4-argon (Interactions API,                      antigravity-preview-09-2026 managed agents on
        streamed thought summaries)                            gemini-4-argon: strategist + robustness (sandbox kit,
                                                               network disabled)
```

The tabletop (servo gate, endpoint switches, NeoPixels, overhead camera) is still in the code and in the presenter menu, but it is not part of this demo.

## Invariants

1. **AI proposes, the checker decides.** Gemini returns schema-validated proposals (a pad id and box, or typed cards); nothing changes until an operator confirms. The managed agent can only call local tools that return checked numbers.
2. **No cloud tool reaches the doors.** Agents call only client functions that return checked numbers; only the operator's Approve commands a door, keyed to the exact plan revision and candidate hash.
3. **ACK is not arrival.** The gate counts as open only after the independent endpoint switch reports it.
4. **Honest provenance.** Live Gemini, Fixture, Local solver, Uploaded image and Simulated are always labelled; live errors never become fixtures. Every door at this event is simulated by the virtual door controller.
5. **Every occupant accounted for.** N_initial = N_completed + N_remaining in every frame of every plan; the checker rebuilds the allowed network on its own and rejects any witness that breaks it.

---

## Quickstart

```bash
python3 -m venv .venv
uv pip sync --python .venv/bin/python requirements.lock
cd frontend && npm ci && npm run build && cd ..
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. `GEMINI_API_KEY` in `.env` (never committed) enables live Argon readings and the agent team; without it everything local works (planner, Simulation, saved runs, local agent lanes, virtual doors) and Gemini paths report "not configured".

**Phones as exit signs.** Phones must reach the laptop, so serve the built frontend on the LAN: `.venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000` (optionally `SPATIALTWIN_SIGN_SECRET` of 32+ characters so phone links survive a restart). The network guard still admits only loopback and scoped phone cookies. Never point phones at `vite --host`. Details: [docs/plans/contracts/signs.md](docs/plans/contracts/signs.md).

**Stage runbook:** [docs/demo/judge-experience.md](docs/demo/judge-experience.md) — the three acts, measured timings, judge questions, failure plan and reset. The tabletop demo is tagged `demo-v1`.

**Printables for the Camera twin:** `.venv/bin/python -m tools.print_assets` writes `venue/print/building_v2_sheet.svg` (A3, four corner markers) and `venue/print/hazard_cards.svg` (A4).

## Tests

```bash
.venv/bin/python -m pytest -q                      # backend: planner, checkers, goldens, hazards, camera, hardware, AI contracts
cd frontend && npm test && npx tsc --noEmit && npm run build
.venv/bin/python -m tools.smoke_connections --base http://127.0.0.1:8000   # 40 end-to-end checks against a running server
```

The offline harness blocks provider, network and device access and isolates SQLite. Ten recorded tabletop envelopes guard the original planner byte for byte.

## Verification status (26 October 2026, demo v2)

- Verified live on 25–26 October (Gemini 4 Argon; receipts in `runtime/`):
  - Real2Sim on synthetic maps and sketches, and on photos of the venue's own posted evacuation maps (critique rounds 12 → 0 and 16 → 0 errors before Accept; one larger sheet stayed blocked at 4 errors);
  - the two-lane agent team on building-v2 (four runs): the strategist completed every time in 27–38 s with 2/2 claims reproduced; the robustness lane completed in 86–172 s with 12/12 claims reproduced (all 12 computed in the sandbox in the last run) and once missed its deadline, when the labelled local fallback took over;
  - capability probes: sandbox code execution with the network disabled (networkx absent, so the kit's estimator runs; an uploaded zip makes the exact solver importable), stream shape, environment reuse. The hook guardrail probe did **not** observe a denial, so no hook guardrail is claimed.
- Verified in the browser: Build → Accept → Simulation, fire → re-plan, approve → transit → endpoint open, jam → fault → the whole twin follows the fallback, phone sign pages.
- Not verified here: phones on the venue Wi-Fi (client isolation can block them; the runbook has the fallback).

Earlier tabletop verification (24–25 October):
  - direct grounding of the synthetic tabletop board and a full tabletop managed-agent run (P2 → 117);
  - the building-v2 managed agent: fire in the Lobby, 50 s, one `plan_doors` call, recommended D4 closed / D9 open, agreeing with the checker (125 of 125 vs 96 at defaults);
  - Camera twin card reads on a **synthetic** tilted still of the printed sheet: FIRE, GAS and WATER read with the right type and room, positions within 8 cm, both with clicked corners (24 s) and with Gemini locating the corner markers (13 s); confirmed cards produced a checked plan;
  - the static-video probe (P3), after the provider schema stopped asking the model for the application-owned `operation` field.
- Verified offline and in the browser: Simulation end to end, the Camera twin UI, the compact LED protocol (host, simulator and a native C test of the firmware parser).
- Not yet verified: a real overhead camera and printed sheet, and the firmware sketch compiled and flashed on the board (every LED claim depends on it).

## Documentation

- [Stage runbook](docs/demo/judge-experience.md) · [building-v2 matrix](docs/demo/building-v2-matrix.md)
- [Interface system](DESIGN.md) · [UI quality toolkit](docs/ui-toolkit.md)
- [Production operation & release gates](docs/ai/production-readiness.md) · [Integration assurance](docs/ai/integration-assurance-2026-10-24.md)
- [Managed agent guide](docs/ai/managed.md) · [Vision grounding guide](docs/ai/grounding.md) · [Setup & stage playbook](docs/ai/setup.md)
- [Firmware](firmware/README.md) (SET_DISPLAY codes, bench steps) · [Sketch notes](firmware/spatialtwin_board/README.md)
- [Winning-feature research](docs/research/winner-feature-analysis-2026-10-24.md) · [Feature research](docs/research/feature-additions-2026-10-24.md)
- [Adversarial review](docs/ai/devils-advocate.md) (historical) · [Team status](docs/ai/team-status.md)
