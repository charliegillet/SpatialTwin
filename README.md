# SpatialTwin — Gemini 4 Argon Hackathon Demonstrator

A physical and digital tabletop evacuation twin: a judge places a physical blockage token on a tabletop floor plan, **Gemini 4 Argon** perceives and proposes the blockage, a **Managed Antigravity Agent** autonomously investigates candidate interventions using client-executed local numerical tools, and an operator authorizes a miniature physical servo gate whose independent microswitch confirmation triggers a fresh re-solve and live NeoPixel route illumination.

**AI verification:** the hardened direct and managed paths passed real-provider smoke checks on 24 October 2026. The image was synthetic; real-board accuracy and physical bench gates remain separate. See [integration assurance](docs/ai/integration-assurance-2026-10-24.md) and [operation/release gates](docs/ai/production-readiness.md). Live errors never silently become fixtures; fixtures and local comparisons are explicit demo actions.

**Repository:** <https://github.com/charliegillet/SpatialTwin>  
**Project Root:** `/Users/nihalnihalani/Desktop/Github/SpatialTwin`  
**Contributors:** Nihal, Charlie, Codex, Claude  

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                      Physical Tabletop & Hardware                        │
│  Overhead Camera  ──►  Arduino UNO R4 Minima  ──►  Adafruit PCA9685 PWM  │
│  BLOCKED Tokens   ──►  Dual Microswitches (D2/D3) ──► 24 WS2812B NeoPixels│
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │ USB Serial / NDJSON Protocol (v: 1)
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        Local Authoritative Backend                       │
│  FastAPI + SQLite (WAL Mode) • StateManager • HardwareBridge & Simulator │
│                                                                          │
│  ┌───────────────────────┐             ┌──────────────────────────────┐  │
│  │ Two-Phase Network Flow│             │ Independent Checker          │  │
│  │ Planner (NetworkX)    │             │ Total Population Conservation│  │
│  └───────────────────────┘             └──────────────────────────────┘  │
└───────────────────▲──────────────────────────────────────▲───────────────┘
                    │                                      │
     Direct Vision  │                  Client-Executed     │
     Grounding      │                  Local Tools         │
                    ▼                                      ▼
┌───────────────────────────────┐     ┌───────────────────────────────────┐
│       gemini-4-argon          │     │    antigravity-preview-09-2026    │
│  Direct Model (Structured)    │     │  Managed Agent (gemini-4-argon)   │
└───────────────────────────────┘     └───────────────────────────────────┘
```

---

## Key Invariants & Features

1. **Direct Gemini 4 Argon Grounding**: Uses `google-genai` SDK (`from google import genai`) with `await client.aio.interactions.create(model="gemini-4-argon", ...)` to identify tokens on allowlisted pads (`portal:P1`, `portal:P2`, `boundary:B2`). Strict schema and local validation reject malformed/out-of-catalog proposals; an operator still reviews visual accuracy.
2. **Managed Antigravity Agent Investigation**: Uses `await client.aio.interactions.create(agent="antigravity-preview-09-2026", agent_config={"type":"antigravity","model":"gemini-4-argon"}, ...)` to run multi-turn autonomous investigations comparing `KEEP_CURRENT` vs `OPEN_P3` using client-executed local tools (`get_reviewed_scenario`, `evaluate_allowed_alternative`, `get_checked_comparison`).
3. **Rigorous Population Conservation**: An all-population two-phase min-cost network flow solver tracks every single synthetic occupant ($N_{initial} = 120 = N_{completed} + N_{remaining}$) across a finite 40s horizon. If an egress is blocked, occupants remain accounted for in physical holding states.
4. **Honest No-Improvement Handling**: When downstream boundary `B2` is blocked, opening internal gate `P3` yields exactly +0 net gain. Both the solver and managed agent truthfully report zero benefit rather than manufacturing exit capacity.
5. **Physical Position Confirmation**: Microcontroller `ACK` only acknowledges command receipt. Route lights and digital state are updated only after debounced microswitches (D2 LOW, D3 HIGH) independently confirm the gate has arrived at the open endpoint.

---

## Quickstart

### 1. Backend Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
uv pip sync --python .venv/bin/python requirements.lock
```

### 2. Frontend Setup
```bash
cd frontend
npm ci
npm run build
cd ..
```

### 3. Run Application
```bash
source .venv/bin/activate
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
Open **`http://localhost:8000`** in your browser.

### Demo without the physical board

Keep `SERIAL_PORT` empty when starting the backend to use the hardware simulator. With server-side Gemini credentials configured, select **Demo board**, place the token at **P2**, and choose **Analyze board**. This sends the displayed synthetic board image to the real provider; **Fixture** remains a separate option that uses no Gemini tokens.

Review the proposed `portal:P2`, then **Apply closure**. The checked illustrative model changes from 120 crossings to 60 out of 120 synthetic occupants. In Intervention analysis, select **Live Gemini** and run the analysis. A successful managed response compares the checked current layout with opening P3: 60 versus 117 crossings over the same 40-second horizon.

After reviewing the comparison, open **Device** and approve P3 while the workspace explicitly says **Simulator**. A simulated open endpoint creates a new physical revision and checked result. Provider receipts, original image/hash and tool evidence are available through **Inspect evidence**. Old proposals and predictions become stale after their context changes. **Reset scenario** clears blockages but preserves the reported gate position; restart the simulator backend to rehearse from a closed gate again.

This demonstrates live Gemini on a synthetic image and simulated hardware. It does not verify real-camera accuracy, a surveyed venue plan or physical gate behavior.

### Explore and share a scenario

- **Inspect plan** opens the computed schedule: scrub or play stored frames, inspect B1/B2 crossings, and account for every synthetic occupant in holding or transfer. This is aggregate numerical playback.
- **Scenarios** opens a read-only lab. Optionally predict which closure benefits most, choose reported P3 or an explicitly closed-reserve benchmark, then **Run four cases**. Baseline/P1/P2/B2 each receive two independently checked local solves. The accepted scenario and hardware stay unchanged.
- **Evidence → Prepare printable brief → Download HTML** prepares a self-contained HTML snapshot with an inline preview and an explicit download link with current/historical labels, sources, assumptions, checker findings and any recorded equal-condition comparison. Open it locally and use your browser's Print command. The existing JSON export remains available.

See [feature research and verification](docs/research/feature-additions-2026-10-24.md) for comparable tools, verified winning-project references and implementation limits.

---

## Running the Automated Test Suite

Run all unit, integration, and devil's advocate adversarial tests:
```bash
source .venv/bin/activate
pytest tests/ -v
```
The offline harness blocks provider/network/device access and isolates SQLite. It covers SDK response types, error/retry behavior, deadlines, cancellation, durable duplicate/restart handling, capture/admission/provenance and the existing numerical/simulator cases. Also run `npm test` and `npm run build` in `frontend/`. See the dated verification record for counts and actual live receipts.

---

## Detailed Documentation Links

- [Interface System](DESIGN.md) — Design tokens, responsive behavior, keyboard flow and UI research sources.
- [UI Quality Toolkit](docs/ui-toolkit.md) — Installed design/testing skills and the isolated responsive + axe accessibility review (`cd frontend && npm run review:ui`).

- [Production Operation & Release Gates](docs/ai/production-readiness.md) — Modes, retention, bounded execution and remaining real-camera/physical validation.
- [Integration Assurance](docs/ai/integration-assurance-2026-10-24.md) — Offline, browser and actual provider evidence.
- [Managed Agent Guide](docs/ai/managed.md) — Multi-turn Antigravity agent integration, tool interfaces, and token budgeting.
- [Vision Grounding Guide](docs/ai/grounding.md) — Direct Gemini 4 Argon structured vision, coordinate conventions, and semantic validation.
- [Setup & Stage Playbook](docs/ai/setup.md) — Hardware wiring, simulator options, and two-minute judge trial script.
- [Adversarial Review Report](docs/ai/devils-advocate.md) — Historical review; the dated audit and verification supersede its old completion claims.
- [Team Status & Milestones](docs/ai/team-status.md) — Project milestones, SDK versions, and deliverables.
- [Firmware Arduino Sketch](firmware/spatialtwin_board/README.md) — Pin map, Adafruit PCA9685 configuration, and upload instructions.
