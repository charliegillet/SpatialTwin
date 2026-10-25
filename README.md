# SpatialTwin — Gemini 4 Argon Hackathon Demonstrator

An evacuation digital twin you can touch. A judge blocks a passage on a physical tabletop, **Gemini 4 Argon** reads the board, a **Gemini managed agent** investigates in Google's cloud using numbers only this laptop can compute, a local checker decides, and the judge approves a miniature servo gate whose endpoint switch confirms it moved. Then the judge breaks a larger building on screen, dropping fire, smoke, gas, chemical or water anywhere, and watches doors close to entry, exits turn red or green and routes re-plan.

AI proposes; the local checker decides; a human approves anything physical. Every count is a modeled crossing of synthetic occupants, never a survival figure.

**Repository:** <https://github.com/charliegillet/SpatialTwin> · **Contributors:** Nihal, Charlie, Codex, Claude

---

## Three modes (presenter menu → Twin)

| Mode | What the judge does | What decides |
| --- | --- | --- |
| **Tabletop** (default) | Places a red token on the 4-zone board (or drops Fire/Smoke on the model). Gemini reads the still, the managed agent investigates, the judge approves the servo gate P3. | Two-phase min-cost flow planner + independent checker: 120 → 60 with P2 blocked → 117 with P3 open. |
| **Simulation** | Drops typed hazards anywhere in a 3D eight-room building (`building-v2`, 125 people, 40 s). | Local door planner: tries every state of the controllable doors, solves and checks each, picks the best checked plan. |
| **Camera twin** | Places red cards (FIRE, SMOKE, GAS, CHEMICAL, WATER) on a printed floor sheet; Gemini reads them; the operator confirms. | Card positions are mapped onto the authored plan through four corner markers; the same local door planner decides. |

Hazard rules in building-v2 (declared model assumptions, inspired by dynamic exit signage and fire/gas/chemical guidance):

- **Fire / Chemical** — no entry; doors around the room close to entry (egress still allowed); people inside leave until it becomes untenable; exits in the room show a red X.
- **Smoke** — half speed, then untenable at T s; smoke doors close to entry.
- **Gas** — no entry; nothing near it is switched or moved (motorised doors next to it lock, signs set static red once); responders are told to vent to the outside.
- **Water** — passable at half speed; no door changes.

Real outcomes are generated from the planner, never typed in: see [building-v2 matrix](docs/demo/building-v2-matrix.md). Example: fire in the Lobby closes D1/D5/D6 to entry, marks E1 unsafe and opens the dock door D9 → 125 of 125 vs 96 with doors at default.

---

## Architecture

```
 Physical tabletop                      Browser (React 19 + Vite; three.js loaded only for Simulation/Camera twin)
 overhead camera, red token,            ├─ Tabletop stage: isometric SVG twin, hazard palette, approval ladder
 UNO R4 + PCA9685 servo gate,           ├─ Simulation: React Three Fiber scene, door plan, exit signs, playback
 2 endpoint switches, 24 NeoPixels      └─ Camera twin: calibration, card chips, confirm
        │ USB serial, NDJSON v1                 │ HTTP + server-sent events
        ▼                                       ▼
 ┌────────────────────────────── Local authoritative backend (FastAPI + SQLite) ─────────────────────────────┐
 │ HardwareBridge / simulator (ACK ≠ arrival) · StateManager · network guard · operator tokens · STOP       │
 │ tabletop-v1: flow_solver + checker + schedule checker        building-v2: flow_solver_v2 + checker_v2     │
 │ hazard forecasts + exposure                                  hazard effects + door planner + announcer   │
 │ grounding (still / video)                                    camera calibration + card reader + confirm  │
 └───────────────▲─────────────────────────────────────────────────────────────────▲─────────────────────────┘
                 │ structured perception (proposals only)                          │ client-executed local tools
        gemini-4-argon (Interactions API)                    antigravity-preview-09-2026 managed agent (gemini-4-argon,
                                                             network-disabled environment)
```

## Invariants

1. **AI proposes, the checker decides.** Gemini returns schema-validated proposals (a pad id and box, or typed cards); nothing changes until an operator confirms. The managed agent can only call local tools that return checked numbers.
2. **No cloud tool reaches hardware.** Only the operator-approve route moves the servo, with an operator token on physical hardware and a live result as evidence.
3. **ACK is not arrival.** The gate counts as open only after the independent endpoint switch reports it.
4. **Honest provenance.** Live Gemini, Fixture, Local solver, Uploaded image and Simulated are always labelled; live errors never become fixtures. building-v2 doors are simulated; the physical gate is on the tabletop.
5. **Every occupant accounted for.** N_initial = N_completed + N_remaining in every frame of every plan; the checker rebuilds the allowed network on its own and rejects any witness that breaks it.

---

## Quickstart

```bash
python3 -m venv .venv
uv pip sync --python .venv/bin/python requirements.lock
cd frontend && npm ci && npm run build && cd ..
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. Without `GEMINI_API_KEY` everything local works (planner, Simulation, simulator hardware, fixtures); Gemini paths report "not configured". Keep `SERIAL_PORT` empty to use the hardware simulator.

**Stage runbook:** [docs/demo/judge-experience.md](docs/demo/judge-experience.md) — the two-minute script, judge questions, failure plan and reset. A frozen copy of the tabletop demo is tagged `demo-v1`.

**Printables for the Camera twin:** `.venv/bin/python -m tools.print_assets` writes `venue/print/building_v2_sheet.svg` (A3, four corner markers) and `venue/print/hazard_cards.svg` (A4).

## Tests

```bash
.venv/bin/python -m pytest -q                      # backend: planner, checkers, goldens, hazards, camera, hardware, AI contracts
cd frontend && npm test && npx tsc --noEmit && npm run build
.venv/bin/python -m tools.smoke_connections --base http://127.0.0.1:8000   # 40 end-to-end checks against a running server
```

The offline harness blocks provider, network and device access and isolates SQLite. Ten recorded tabletop envelopes guard the original planner byte for byte.

## Verification status (25 October 2026)

- Verified live (24–25 October, Gemini 4 Argon, receipts in `runtime/probes` and `runtime/live-checks-2026-10-25`):
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
