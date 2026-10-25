# SpatialTwin — Gemini 4 Argon Hackathon Demonstrator

A physical and digital tabletop evacuation twin: a judge places a physical blockage token on a tabletop floor plan, **Gemini 4 Argon** perceives and proposes the blockage, a **Managed Antigravity Agent** autonomously investigates candidate interventions using client-executed local numerical tools, and an operator authorizes a miniature physical servo gate whose independent microswitch confirmation triggers a fresh re-solve and live NeoPixel route illumination.

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

1. **Direct Gemini 4 Argon Grounding**: Uses `google-genai` SDK (`from google import genai`) with `client.interactions.create(model="gemini-4-argon", ...)` to identify tokens on allowlisted pads (`portal:P1`, `portal:P2`, `boundary:B2`). A strict local validator prevents hallucinations.
2. **Managed Antigravity Agent Investigation**: Uses `client.interactions.create(agent="antigravity-preview-09-2026", agent_config={"type":"antigravity","model":"gemini-4-argon"}, ...)` to run multi-turn autonomous investigations comparing `KEEP_CURRENT` vs `OPEN_P3` using client-executed local tools (`get_reviewed_scenario`, `evaluate_allowed_alternative`, `get_checked_comparison`).
3. **Rigorous Population Conservation**: An all-population two-phase min-cost network flow solver tracks every single synthetic occupant ($N_{initial} = 120 = N_{completed} + N_{remaining}$) across a finite 40s horizon. If an egress is blocked, occupants remain accounted for in physical holding states.
4. **Honest No-Improvement Handling**: When downstream boundary `B2` is blocked, opening internal gate `P3` yields exactly +0 net gain. Both the solver and managed agent truthfully report zero benefit rather than manufacturing exit capacity.
5. **Physical Position Confirmation**: Microcontroller `ACK` only acknowledges command receipt. Route lights and digital state are updated only after debounced microswitches (D2 LOW, D3 HIGH) independently confirm the gate has arrived at the open endpoint.

---

## Quickstart

### 1. Backend Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run build
cd ..
```

### 3. Run Application
```bash
source .venv/bin/activate
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```
Open **`http://localhost:8000`** in your browser.

---

## Running the Automated Test Suite

Run all unit, integration, and devil's advocate adversarial tests:
```bash
source .venv/bin/activate
pytest tests/ -v
```
*(17 tests covering network flow conservation, checker constraints, protocol envelopes, hardware simulator, and adversarial attacks).*

---

## Detailed Documentation Links

- [Managed Agent Guide](docs/ai/managed.md) — Multi-turn Antigravity agent integration, tool interfaces, and token budgeting.
- [Vision Grounding Guide](docs/ai/grounding.md) — Direct Gemini 4 Argon structured vision, coordinate conventions, and semantic validation.
- [Setup & Stage Playbook](docs/ai/setup.md) — Hardware wiring, simulator options, and two-minute judge trial script.
- [Adversarial Review Report](docs/ai/devils-advocate.md) — Devil's Advocate boundary tests and falsification results.
- [Team Status & Milestones](docs/ai/team-status.md) — Project milestones, SDK versions, and deliverables.
- [Firmware Arduino Sketch](firmware/spatialtwin_board/README.md) — Pin map, Adafruit PCA9685 configuration, and upload instructions.
