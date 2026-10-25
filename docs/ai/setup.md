# SpatialTwin Setup & Quickstart Guide

**Current AI operation and release gates:** read [production-readiness.md](production-readiness.md). The legacy demo script below describes intended behavior, not proof of live or physical validation. Missing provider credentials return unavailable; fixture/local modes require an explicit choice. On startup the backend loads the repository `.env` (`backend/app/env_file.py`): only `GEMINI_API_KEY`, `SERIAL_PORT`, `SERIAL_BAUD`, `HOST`, `PORT` and `SPATIALTWIN_*` keys are read, a variable already set in the process environment always wins, and `SPATIALTWIN_ENV_FILE=` (empty) disables it.

## 1. Prerequisites

- Python 3.11+ (CPython 3.13 tested)
- Node.js 18+ (Node v25 tested)
- (Optional) Arduino IDE 2.x or `arduino-cli` if uploading firmware to physical hardware
- (Optional) `GEMINI_API_KEY` for live Argon and Antigravity Managed Agent calls

---

## 2. Fast Installation

### Backend Setup
```bash
# From repository root:
python3 -m venv .venv
source .venv/bin/activate
uv pip sync --python .venv/bin/python requirements.lock
```

### Frontend Setup
```bash
cd frontend
npm ci
npm run build
cd ..
```

---

## 3. Running SpatialTwin

### Single-Command Presentation Mode (Serves API + Built UI)
```bash
source .venv/bin/activate
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
Open your browser to: **`http://localhost:8000`**

### Live Development Mode (Concurrent Vite + FastAPI)
In Terminal 1 (Backend):
```bash
source .venv/bin/activate
uvicorn backend.app.main:app --reload --port 8000
```

In Terminal 2 (Frontend):
```bash
cd frontend
npm run dev
```
Open browser to: **`http://localhost:5173`** (proxies `/api` and `/health` to backend).

---

## 4. Hardware Configuration

- **Automatic Simulator Mode**: If `SERIAL_PORT` is not defined in `.env`, the backend automatically starts the in-memory `HardwareSimulator`. It models 500ms servo transit, debounced microswitches, and NDJSON telemetry.
- **Physical Arduino Mode**: Plug in the Arduino UNO R4 Minima via USB-C. Find the port (e.g. `/dev/cu.usbmodem1101` on macOS) and set:
  ```bash
  export SERIAL_PORT="/dev/cu.usbmodem1101"
  ```
  The bridge connects immediately at 115200 baud, executes the `HELLO` handshake, and begins 250ms heartbeats.

---

## 5. Intended Two-Minute Judge Demo Script

> Superseded for the stage by [docs/demo/judge-experience.md](../demo/judge-experience.md), which has the current script, the Simulation and Camera twin hand-off, judge questions and the reset procedure. The text below is kept for history.

Run only after the corresponding live capture and physical bench gates pass. Numbers below are illustrative model outputs, not observed real-building results. Current UI supports separate live/fixture and live/local actions; use the displayed receipts to identify the source.

1. **Baseline View (0:00 - 0:30)**:
   - Point out 120 synthetic occupants in Main Event Hall with both portals P1 and P2 open.
   - Show 120 completed modeled crossings (60 via Exit B1, 60 via Exit B2) and 0 residual.
2. **Judge Incident Token (0:30 - 1:00)**:
   - Ask judge to place BLOCKED token on East Portal (Pad `T_P2`).
   - Click "Capture Overhead Still" -> Direct Gemini 4 Argon matches `portal:P2`.
   - Click "Apply Closure" -> Recomputes immediately: Completed drops to 60 (Exit B1 saturated), 60 trapped in hall.
3. **Managed Agent Autonomous Tool Investigation (1:00 - 1:30)**:
   - Click "Run Antigravity Investigation".
   - Watch Antigravity Managed Agent autonomously call `get_reviewed_scenario`, `evaluate_allowed_alternative("OPEN_P3")`, and `get_checked_comparison`.
   - Show side-by-side comparison: `OPEN_P3` yields +57 additional crossings (117 total) by routing through the reserve channel to B2!
4. **Physical Gate Movement & Independent Position Confirmation (1:30 - 2:00)**:
   - Operator clicks "Authorize Gate Movement (OPEN_P3)".
   - Highlight that Firmware ACK does NOT claim arrival; state remains `TRANSIT` and LEDs glow amber.
   - The physical gate swings open; independent microswitch D2 triggers LOW.
   - The confirmation increments `physical_revision`, triggers a fresh solve, and the physical NeoPixel LEDs turn bright green to illuminate the newly verified egress route!
