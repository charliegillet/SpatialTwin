# WalkTwin demo runbook

No slides. Three beats, each ends on one state change the judge sees. Every number said aloud comes from a CLI output (`runtime/bench/<venue>.json`, the session report); none is typed in advance.

Wording rules: say "reach a modeled exit in 120 s", "Argon proposed", "geometry measured", "checker verified", "you approved". Held-out frames are "held out from the critique's frame pairs". Banned words (never in our copy; if the agent writes one, it is shown as the agent's unedited words, flagged): "safe", "compliant", "survive", "evacuated".

## Script

| Beat | Time | The judge sees | Say |
|---|---|---|---|
| 1. Your walk becomes the twin | 0:00-0:55 | The judge films about 40 s of one room (a single room keeps Argon's output small and fast). Their SfM path appears while Argon works. The saved full-floor run opens, and clicking a door's evidence seeks the video. | "Every event moves the tables. Nobody re-checks the exits. Film the room." |
| 2. Argon proposes, geometry disposes | 0:55-1:50 | The ghost walker passes through a wall and flashes red. Argon's patch adds the door, citing its timestamp. Illegal crossings drop (`<before>` to `<after>`, from the session) and held-out edge alignment improves. One patch is rejected, with its reason. | "Argon compared its twin with the whole video. Your footsteps checked Argon." Add benchmark numbers from `runtime/bench` only. |
| 3. Fire, fix, approve | 1:50-2:50 | The judge drops Fire on the main exit; the hero number falls, marked checked. The sandbox sweep and the checker's verified figure appear side by side. The proposal is to open D3; the judge clicks its evidence, approves, the number recovers, and the note appears headed "DRAFT — not sent". | "The agent investigated, our checker measured, you approved. Nothing leaves this laptop." |

### Closing 10 seconds

Show the judge's own clip result, or its measured stage time stated honestly: "this takes about `<N>` minutes; here is the run from `<HH:MM>`" (N from the rehearsal table below, HH:MM from the saved run's timestamp; the UI shows "saved run · started HH:MM"). The ADA rows, the report and the benchmark table stay in the drawer for Q&A.

## Q&A, one sentence per lens

- **Invented doors:** every element has a timestamp, a human accepts the graph, footsteps catch missed doors, and precision and recall are reported against tape-measured keys.
- **Who pays:** the venue operator, at every layout change; today the walk is visual with no record. Do not quote market sizes.
- **Does it work in a home:** the home benchmark row (read it from `runtime/bench/home.json`; say "pending" if it has not been run).
- If asked about held-out frames: they are held out from the critique's frame pairs.
- Do not repeat launch-blog claims (for example benchmark scores) unless re-checked on the day; do not present Flash-model efficiency figures as Argon's.

## Pre-demo checklist

Needs a human with a Gemini key. Nothing here is pre-filled.

- [ ] `GEMINI_API_KEY` set in `.env` (see `.env.example`).
- [ ] `PYTHONPATH=backend /Users/charlie/hackathons/walktwin/.venv/bin/python tools/probe.py all --clip runtime/probe_clip.mp4`, then open `runtime/probes/*.json` and record:
  - [ ] every receipt exists and has `ok: true` (note any `refused: true`)
  - [ ] agentic video observed: ___ (yes / no, and time to first token ___ s)
  - [ ] repeated video URI accepted: ___ (yes / no). If no, use inline base64 for clips under 20 MB and skip zoom parts.
  - [ ] gates that failed and the fallback chosen: ________
- [ ] `cd frontend && npm ci && npm run build` (the server mounts `frontend/dist`; headless renders need it).
- [ ] Start the server from the repo root: `PYTHONPATH=backend uvicorn walktwin.api:app --host 0.0.0.0 --port 8000` (project virtualenv)
- [ ] Laptop IP: ___ . Phone opens `http://<laptop-ip>:8000`. If venue Wi-Fi blocks it (client isolation), use a personal hotspot, or AirDrop/USB the clip and upload it.
- [ ] Run the server on a personal hotspot, not shared Wi-Fi. The server has no auth, so anyone on the same Wi-Fi can use the Gemini key through it.
- [ ] One app tab only, window sized for the projector, notifications off.
- [ ] Saved live SHACK15 session prepared (see below) and its timestamp is visible on screen.

### Saved live run (prepare in advance)

SHACK15 staff permission obtained: ___ . Empty areas only; no identifiable people in frame.

- [ ] Extracted from the full-floor clip, refined with SfM, graph accepted.
- [ ] Three investigations precomputed on accept (cap at 3) and receipts saved.
- [ ] Shown as a **saved live run** with its timestamp: ___ (HH:MM).
- [ ] Session id: ___

## Rehearsals (three, measured)

Record each stage's measured time. Narration hints are set from these, never from a fixed timer.

| Stage | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| upload: ___ s | ___ | ___ | ___ |
| extraction: ___ s | ___ | ___ | ___ |
| SfM: ___ s | ___ | ___ | ___ |
| critique and patch: ___ s | ___ | ___ | ___ |
| investigation: ___ s | ___ | ___ | ___ |
| end to end for the judge's clip: ___ s | ___ | ___ | ___ |

Median end to end: ___ s (used for the closing 10 seconds).

## Fallbacks on stage

A failure is shown honestly. Never replace a failed live step with a fixture or a canned result.

- **Slow extraction (or agentic time to first token):** the judge's clip is one room, about 40 s. While it runs, show the SfM path and the saved live run with its timestamp. If it has not finished by the closing, say the measured stage time and show the saved run.
- **SfM fails (blank walls, glass):** the geometry panel shows "unavailable". The loop runs on model-reported counts only, and we say so. Try the MapAnything-apache fallback if time allows.
- **No Wi-Fi or phone cannot reach the laptop:** personal hotspot, or AirDrop/USB the clip and upload it from the laptop browser.
- **Provider failure (rate limit, credits, refusal):** the app shows the provider failure and its stop reason. Say what failed, show the cached receipt and the saved run, and continue with the parts that do not need the provider (checker, geometry, approval). Do not substitute pre-written output.
- **Headless WebGL fails:** use the SwiftShader flags; otherwise render in a visible Chromium window.
- **Benchmark is flat:** report it flat. The geometry loop's improvement is a separate measured claim.

## Submission checklist

- [ ] One-minute video showing only features built at the event.
- [ ] Repo is public.
- [ ] Demo link works from a second device.
- [ ] All team members are on the submission.
