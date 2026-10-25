# WalkTwin (walkthrough-video SpatialTwin) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A crowd manager, or a judge, films a walk through a real space on a phone. Gemini 4 Argon turns the video into a reviewed venue graph and a 3D twin, renders the twin, compares it with the video and corrects it in a loop. Each round is scored by geometry Argon doesn't control: the walker's own camera path, recovered locally by structure-from-motion. A deterministic solver and an independent checker then measure egress under a hazard the judge places. A managed agent sweeps allowed interventions in its own sandbox, the local checker verifies its shortlist, and a human approves one. The output is a drafted (never sent) note to security.

**Architecture:**
- **Direct Argon** handles every video task: extraction, then render-vs-video critique chained onto the same interaction, so the whole video stays in context.
- **Local structure-from-motion** (pycolmap) recovers the camera path and a point cloud. A frozen alignment and a geometry score make each round's improvement measured, not self-reported, and a patch that makes the score worse is rejected.
- **The managed Antigravity agent** gets text and images. It runs what-if sweeps with code execution in its own sandbox, then calls client-executed tools.
- **Authority stays local:** every number on screen comes from a local solver run that an independent checker has passed. Model output proposes; local code validates; a human accepts. Every artifact carries the graph revision it was computed from, so stale results are refused.

**Tech Stack:** Python 3.12, FastAPI, pydantic 2, networkx, numpy, pycolmap (BSD), opencv-python-headless, `google-genai` (pinned after the Task 2 probe), ffmpeg/ffprobe, Playwright (Python) with headless Chromium. Frontend: Vite, React 19, TypeScript, three.js. Tests: pytest, pytest-asyncio, vitest.

**Spec:** §0 below. It comes from the 25 October 2026 design conversation and the hackathon participant guide (Problem Statement Two, "More Dimensions"). It is amended by [`reports/WalkTwin hackathon idea improvements.md`](<../../../reports/WalkTwin hackathon idea improvements.md>): corrections C1–C11 and additions A1–A9 are folded in below, and the notes behind them are in `research_notes/WalkTwin hackathon idea improvements/`.

**Working name:** WalkTwin, repo `walktwin`. Rename freely, but don't present it as "SpatialTwin": judges could take it for the pre-event project.

---

## 0. Spec (what we are building and why)

**User:** the venue ops lead or designated crowd manager doing the walk before doors open, at a venue whose layout changes for every event.
- Model codes require trained crowd managers (one per 250 occupants above 250), and their duties include keeping exits clear.
- San Francisco's temporary-event permit (SFFD Administrative Bulletin 2.14) checks a dimensioned floor plan at least five business days ahead. It has no step for re-checking a layout that changes on the day.
- Today the walk is a visual check, with no measurement and no record. Inspectors' most common night-time finding is something placed in front of an exit.
- **Their decision tonight is binary:** open doors, or first unlock, clear or staff exit X.

**Pitch framing:** a space audit with a measured verdict, whose input is phone video. Don't pitch it as a 3D-twin project. In the 355-winner analysis, space and compliance audits took first place 3 of 6 times and 3D twins 1 of 15. Recent render-compare-retry entries without a measured answer (Recurse.run, Farallon) did not place. One line: *the twin is how Argon checks its own reading, your footsteps are how we check Argon, and the solver is how we measure.*

**Problem statement fit:** PS2 asks for a system that "renders what it made, watches the result, critiques it against the goal, and fixes it in a loop."
- WalkTwin's loop: video → graph → rendered twin → Argon compares renders with the video → graph patches → re-render.
- Every round is scored by geometry from the walker's own path, so a patch that makes things worse is rejected.
- Google's AI Studio 3D guide recommends the same shape: a separate critic, several rendered views, and a 2D plan first for interiors.
- The 1M-context claim is honest only when one stateful interaction holds the video, every round's renders and the graph. That's why critique turns chain onto the extraction interaction. A single clip alone is only about 15K–45K tokens.

**Judging map:**

| Criterion (round one weight) | How WalkTwin earns it |
|---|---|
| Working live demo, real inputs, real verification loop (50%) | The judge films the room. A geometry score from their own footsteps: illegal wall crossings, wall support, held-out edge alignment. Checker-verified solver runs. A benchmark against tape-measured answer keys. |
| Problem and usefulness (25%) | A named user, a binary decision they make tonight, and a drafted note to security. Could grow into a pre-opening walk tool. |
| Originality, Argon-only (15%) | Argon reads a handheld walkthrough, then critiques its twin against the whole video in one chained multimodal interaction. |
| Pitch clarity (10%) | Three beats on the twin, no slides. |
| Best use of Managed Agents ($5K) | The agent runs what-if sweeps in its own network-disabled sandbox, the local checker verifies the shortlist, and the sandbox and checker figures are shown side by side. |

**Patterns borrowed from past winners** (from `docs/research/winner-feature-analysis-2026-10-24.md` in the old repo; ideas only, no code):
- Measured result, unknowns stated (Etch, HomeReady): pass, fail or cannot measure, with ADA citations.
- Improvement over a baseline (Ripple, AGI Factory): four extraction modes benchmarked, plus the geometry score falling round by round.
- Separate critic (AI Studio 3D guide): the geometry score, which no model controls.
- Human authority (AWW, HomeReady): accept the graph, approve the change; the note is drafted, never sent.
- Clear stakes: getting people out of the room you are standing in. Lead with the Station nightclub finding: about two-thirds of occupants tried the main entrance while other exits went unused. Never claim WalkTwin would have saved lives.

**Out of scope, shown on screen as "cannot measure" and turned into a hand-check to-do list:**
- survival, and approved or code-official egress capacity
- IBC/NFPA occupant load
- doorway depth, which decides whether a door needs 32 in or 36 in
- turning space reduced by furniture
- door hardware and opening force, thresholds, ramp slopes, signage, fire separation
- crowd density effects, and people moving during the event
- any area not filmed

---

## Global Constraints

- **New work only:** the fresh repo's first commit is made after the 10:30 AM kickoff on 25 October 2026. Nothing is copied from the SpatialTwin repo: no source, tests, venue JSON, UI components or prompts.
- **Reuse allowed:** open-source dependencies under their licences, Google documentation code samples (Apache-2.0, credited in `NOTICE`), the 2010 ADA Standards (cite sections), and knowledge from the earlier work. Re-express that knowledge in new code.
- **Not allowed:** the SHACK15 vendor map, Ferry Building maps (Hudson Pacific terms restrict reuse), Matterport tours, or video of identifiable people without consent. Ask SHACK15 staff before filming; film empty areas.
- **Model weights, use:** pycolmap/COLMAP/GLOMAP (BSD), OpenCV, MoGe-2 (MIT), Depth Anything V2 Small and DA3-BASE/SMALL/METRIC-LARGE (Apache-2.0), MapAnything-apache weights.
- **Model weights, never add:** DUSt3R, MASt3R(-SLAM), CUT3R, the original VGGT-1B, Pi3/Pi3X weights, UniDepth, Apple Depth Pro, SpatialLM encoders, SceneScript, larger Depth Anything models, or OpenSplat (AGPL).
- **Model IDs:**
  - direct: `gemini-4-argon`
  - managed agent: `antigravity-preview-09-2026` with `agent_config={"type":"antigravity","model":"gemini-4-argon","max_total_tokens":300000}`
  - Never omit the model; the agent's default is a Flash model.
  - Google estimates 100K–500K input tokens per agent task. A budget that runs out returns `incomplete`; resuming gets a fresh budget.
- **Direct calls:**
  - `store=True` on every call.
  - `background=True`, polled with `client.interactions.get`, for extraction and critique.
  - `max_output_tokens: 65536` with high thinking. The cap covers thinking as well as output, so a lower cap can return `incomplete` with empty text.
  - Join text across all `model_output` steps.
- **Video input:** upload through the Files API (≤ 2 GB, kept 48 hours). Video modes:
  - `agentic`: `{"type":"video","uri":...,"mime_type":"video/mp4","processing":"agentic"}`
  - `static`: `{"type":"static","fps":1}`
  - `static_hifps`: `{"type":"static","fps":3}` with `"resolution":"high"`
  - Google recommends static for clips under 5 minutes, and the docs conflict on agentic support for Argon. Confirm agentic actually ran by counting `processing_call` steps; zero means it didn't.
- **Managed agent input:** text and inline base64 images only; no video, audio or documents. There is no structured `response_format`, so use a `submit_recommendation` function instead.
- **Agent tools:** passing `tools` replaces the agent's defaults. List `code_execution` explicitly and leave out `google_search` and `url_context`. Sandbox filesystem tools also appear as `function_call` steps but run on their own, so the client executes only allowlisted function names.
- **Declared parameters** are labelled "declared" in the UI and report. They are model assumptions, not measurements:
  - `dt_s=2`, `horizon_s=120`
  - `specific_flow_p_per_m_s=1.3`, applied to effective width: clear width minus `boundary_layer_m=0.15` on each side
  - `walk_speed_m_s=1.2`
  - `non_anchor_uncertainty=0.20`
  - `eye_height_m=1.5±0.1`
  - geometry thresholds 0.5 m, 0.15 m and 5 px
- **Copy rules:** never "survive", "safe", "compliant" or "evacuated". Say "reach a modeled exit in 120 s", "meets ADA §404.2.3 within measured range" or "cannot measure". Write "Argon proposed", "geometry measured", "checker verified", "you approved". Label scores "model-reported" or "measured".
- **Authority:** no model output changes the accepted graph or scenario without a human accept or approve request that carries `expected_revision`. A stale revision returns HTTP 409.
- **Live failures stay failures.** Fixtures are an explicit "Replay saved run" action labelled as a replay. Every benchmark number on screen must come from the CLI.
- **Nothing is sent externally.** The note to security is a local draft headed `DRAFT — not sent`.

## Review Focus

1. **The walkthrough misses an exit or part of the floor.** Zones that can't reach an exit show as "unreachable / not filmed", never as reaching an exit. Tests: Task 4 `test_unreachable_zone_warning`, Task 5 `test_unreachable_zone_counts_as_remaining`.
2. **iPhone HEVC `.mov`, portrait, variable frame rate.** Prep transcodes to H.264 720p mp4 and keeps orientation. Test: Task 8 `test_prepare_hevc_portrait_mov`.
3. **The critique loop oscillates, or a patch makes the geometry worse.** It stops on a repeated graph revision or a measured regression. Tests: Task 11 `test_loop_stops_on_repeated_revision`, `test_loop_rejects_measured_regression`.
4. **The judge changes the graph or hazard while the agent or loop runs, or picks a hazard that has a precomputed investigation.** Late results are refused for the new revision and shown as stale; a precomputed investigation is used only when its scenario hash matches. Tests: Task 14 `test_stale_investigation_rejected`, `test_precomputed_investigation_matches_hazard`.
5. **SfM fails on blank walls or glass.** The geometry score shows "unavailable", never a made-up number, and the loop falls back to model-reported counts. Tests: Task 8b `test_run_sfm_failed_on_blank_video`, Task 11 `test_loop_without_sfm_labels_unavailable`.

---

## Team lanes (run in parallel from kickoff)

| Lane | Owner | Tasks |
|---|---|---|
| Data capture and answer keys (humans) | Nihal + Charlie | Task 12 capture steps, permission, filming, tape-measuring |
| Core numerics | Codex | Tasks 3–7 |
| Geometry critic | Claude or Codex, one writer | Tasks 8b, 10b |
| AI adapters | Claude | Tasks 2, 9, 11, 13 |
| Twin and UI | Claude or Codex, one writer | Tasks 10, 16 |
| Integration | Codex | Tasks 14, 15 |

One writer per file. `contracts.py` and lockfiles have a single owner (Codex). Everyone else requests changes.

## File structure

```
walktwin/
  README.md            # what it is, "Built at the event" + "Prior work, not presented" sections
  NOTICE               # Google sample attribution (Apache-2.0), ADA citation note
  LICENSE              # MIT
  requirements.txt / requirements.lock
  backend/walktwin/
    contracts.py       # pydantic models + revision hashing (single owner)
    graph_checks.py    # deterministic validation of a VenueGraph
    flow.py            # time-expanded max-flow egress solver
    checker.py         # independent run checker (imports nothing from flow.py)
    egress_rules.py    # ADA 2010 width/turning checks with pass/fail/cannot_measure
    media.py           # ffmpeg/ffprobe prep and frame extraction
    sfm.py             # pycolmap camera path, point cloud, frozen alignment
    genai_client.py    # client factory, Files upload, background polling, receipts
    extract.py         # Argon video -> VenueGraph
    render.py          # Playwright headless render of twin views (perspective + top-down)
    geometry_score.py  # measured loop score from the walker's own path
    critique.py        # chained Argon frame-vs-render critique -> PatchOps
    patch.py           # deterministic patch application
    loop.py            # refine loop orchestration + stop rules
    benchmark.py       # answer-key scoring + CLI
    agent.py           # managed Antigravity sandbox sweep + call ledger
    sessions.py        # session state, revisions, JSON persistence
    report.py          # verification report, HTML export, note to security
    api.py             # FastAPI app
  agent_env/
    AGENTS.md          # copy rules; numbers only from evaluate_interventions
    skills/sweep/SKILL.md, skills/ada/SKILL.md
    hooks/pre_tool_execution.py   # denies writes to accepted_graph.json
  frontend/
    src/twin/buildScene.ts, cameraFor.ts, ghostWalker.ts, crowdDots.ts
    src/render.tsx     # headless render entry (render.html)
    src/app/...        # workflow screens
  tools/probe.py       # live API + SfM probes (Task 2)
  bench/<venue>/answer_key.json, video.mp4 (video git-ignored if > 50 MB; store hash)
  tests/...            # mirrors backend modules; tests/fakes.py; tests/fixtures/
  runtime/             # git-ignored: sessions, receipts, renders, sfm, bench results
```

---

### Task 1: Fresh public repo with provenance

**Files:**
- Create: `README.md`, `NOTICE`, `LICENSE`, `.gitignore`, `requirements.txt`, `pytest.ini`, `frontend/` (Vite React-TS scaffold), `backend/walktwin/__init__.py`, `tests/test_smoke.py`

- [ ] **Step 1:** Done at 11:15 PT. The work lives on the orphan branch `charlie` of `charliegillet/SpatialTwin`, which has no pre-event history, checked out as a worktree at `/Users/charlie/hackathons/walktwin`. Commit and push to `origin charlie` after every task. The repo is currently **private**; the rules require it to be public before submission, and making it public is the user's call.
- [ ] **Step 2:** Write `README.md` with three headed sections:
  - **Built at the Gemini 4 Argon SF Hackathon (25 Oct 2026):** everything in this repo.
  - **Prior work, not presented:** "Before the event the team built a hardware tabletop prototype (SpatialTwin). No code, data or assets from it are in this repo."
  - **Limits:** the cannot-measure list from §0.
- [ ] **Step 3:** Pin current releases of `fastapi`, `uvicorn`, `pydantic`, `networkx`, `numpy`, `pycolmap`, `opencv-python-headless`, `google-genai` (check ≥ 2.33.0, the version whose Interactions surface was verified on 24 Oct), `httpx`, `playwright`, `pytest` and `pytest-asyncio`. Run `playwright install chromium`. Confirm `ffmpeg -version`, `ffprobe -version` and `python -c "import pycolmap; print(pycolmap.__version__)"`.
- [ ] **Step 4:** Write `tests/test_smoke.py::test_imports`, which imports `walktwin`. Run `pytest -q`. Expected: 1 passed.
- [ ] **Step 5:** In `frontend/`, run `npm create vite@latest . -- --template react-ts`, `npm i three@0.170.0` and `npm i -D vitest @types/three`. Run `npm run build`. Expected: success.
- [ ] **Step 6:** Commit: `chore: bootstrap walktwin with provenance README`.

### Task 2: Live API and SfM probes (gate for Tasks 8b, 9, 11, 13)

**Files:**
- Create: `backend/walktwin/genai_client.py`, `tools/probe.py`, `tests/test_genai_client.py`, `tests/fakes.py`

**Interfaces:**
- Produces:
  - `make_client() -> genai.Client`, reading `GEMINI_API_KEY`.
  - `async def upload_video(client, path: Path) -> UploadedFile`, where `UploadedFile(uri: str, mime_type: str, name: str)`. Waits until the file state is ACTIVE.
  - `async def run_background(client, *, deadline_s: float, poll_s: float = 3.0, **create_kwargs) -> tuple[Interaction, Receipt]`
  - `joined_text(interaction) -> str`
  - `count_steps(interaction, step_type: str) -> int`
  - `Receipt(interaction_id: str, provider_model: str | None, status: str, usage: dict, elapsed_ms: int, processing_calls: int)`
  - `tests/fakes.py::FakeClient`, scriptable per test: queued statuses, steps, function calls, and captured requests.

- [ ] **Step 1:** Write `test_run_background_polls_until_terminal`. The fake returns `in_progress, in_progress, completed`. Assert two `get` calls and `receipt.status == "completed"`.
- [ ] **Step 2:** Write `test_run_background_deadline`. The fake stays `in_progress`. With `deadline_s=0.05`, assert `TimeoutError` and one call to `interactions.cancel`.
- [ ] **Step 3:** Write `test_joined_text_concatenates_model_output_steps`: two `model_output` steps, `"{\"a\":"` and `"1}"`, give `'{"a":1}'`. Also write `test_processing_calls_counted`: three `processing_call` steps give `receipt.processing_calls == 3`.
- [ ] **Step 4:** Implement. `run_background` treats `requires_action`, `failed`, `cancelled` and `incomplete` as terminal and returns them; the caller decides. Run the tests. Expected: PASS.
- [ ] **Step 5:** Write `tools/probe.py`. Each probe writes `runtime/probes/<name>.json` with its receipt and the SDK version, and no secrets.
  - (a) `text`: direct Argon, one sentence.
  - (b) `video_static`: upload a 20 s phone clip with a JSON schema `{"doors_seen": int}` and `processing={"type":"static","fps":1}`.
  - (c) `video_agentic`: the same clip with `processing="agentic"`. Record `processing_calls`.
  - (d) `video_chain`: a second turn with `previous_interaction_id` from (c). It adds one image and a static clipped part of the **same** URI (`start_offset`/`end_offset`, fps 5, `resolution:"high"`). Record whether a URI may appear twice, and the `usage` difference (the cost of keeping video context).
  - (e) `agent_tool`: managed agent with `tools=[{"type":"code_execution"}, echo_number(n:int)]` and `max_total_tokens: 300000`. Answer `requires_action` with a `function_result` (`previous_interaction_id`, `environment=interaction.environment_id`). Assert the final status is `completed` and `provider_model == "gemini-4-argon"`.
  - (f) `agent_env`: create an environment with network on and run `pip install networkx pydantic`. Then reuse its `environment_id` with the network disabled and import both packages. Also try a saved agent on `gemini-4-argon`; the docs conflict, so record a refusal as a refusal.
  - Each direct probe also records whether the pinned SDK accepts `thinking_summaries:"auto"`.
- [ ] **Step 6:** Run `python tools/probe.py all`. Expected: receipts for (a)–(f). Gates:
  - If (b) or (c) rejects `uri` input, retry inline base64 for a clip under 20 MB and use whichever worked.
  - If (c) shows `processing_calls == 0`, agentic didn't run. Make `static_hifps` the main mode and say so in the README.
  - If (d) rejects a repeated URI, Task 11 skips zoom parts.
  - If (f) can't reuse the environment with the network off, Task 13 runs with an allowlist, and the README says so.
  - Record elapsed times; they set every deadline in Tasks 9, 11 and 13.
- [ ] **Step 7:** Run `python -m walktwin.sfm runtime/probe_clip.mp4` once Task 8b exists, or the equivalent pycolmap script now. Expected: at least 80% of sampled frames registered. Record the wall-clock time.
- [ ] **Step 8:** Commit: `feat: genai client helpers and live probes`.

### Task 3: Contracts and revision hashing

**Files:**
- Create: `backend/walktwin/contracts.py`, `tests/test_contracts.py`, `tests/fixtures/office_graph.json` (hand-authored today: 4 zones, 6 doors, 2 exits, 5 keyframes)

**Interfaces:**
- Produces (exact names, used by every later task):
  - `Evidence(start_s: float >= 0, end_s: float >= start_s, note: str max 200)`
  - `Measure(low_m: float > 0, high_m: float >= low_m, basis: Literal["anchor_measured","estimated","assumed"])`
  - `Zone(id: str pattern ^Z\d{1,3}$, name: str max 60, rect: tuple[float,float,float,float], occupants: int >= 0, furniture_seen: bool = False, evidence: list[Evidence])`. `rect` is (x, y, w, h) in meters, with w and h > 0.
  - `Door(id: str pattern ^D\d{1,3}$, a: str, b: str, kind: Literal["door","opening","exit","stair"], state: Literal["open","closed","locked","unknown"], clear_width: Measure, position: tuple[float,float], evidence: list[Evidence])`. `b` is a zone id or `"OUTSIDE"`.
  - `Keyframe(t_s: float >= 0, zone_id: str, x: float, y: float, heading_deg: float in [0,360))`
  - `Anchor(door_id: str, measured_width_m: float > 0)`
  - `VenueGraph(schema_version: Literal["1"], video_sha256: str, anchor: Anchor | None, zones: list[Zone], doors: list[Door], keyframes: list[Keyframe])`. Its `revision` property is `"g-" + sha256(canonical JSON)[:16]`, where canonical JSON has sorted keys, no whitespace, and floats rounded to 3 decimals.
  - `Hazard(door_id: str, kind: Literal["fire"], from_s: float = 0)`
  - `Scenario(hazards: list[Hazard] = [], interventions: list[str] = [])`. Interventions look like `"OPEN:D3"`. `scenario.hash` is `"s-" + sha256[:12]`.
  - `FlowParams(dt_s: int = 2, horizon_s: int = 120, specific_flow_p_per_m_s: float = 1.3, boundary_layer_m: float = 0.15, walk_speed_m_s: float = 1.2)`
  - `apply_anchor(graph: VenueGraph, anchor: Anchor, uncertainty: float = 0.20) -> VenueGraph`
- [ ] **Step 1:** Write the tests:
  - `test_revision_stable_under_key_order`: the same graph built from two dicts with different key order has an equal revision.
  - `test_revision_changes_on_width`: changing one `low_m` by 0.01 changes the revision.
  - `test_rejects_bad_ids`: zone id `"room1"` raises `ValidationError`.
  - `test_apply_anchor_scales_and_bands`: an anchor door estimated at (0.9, 1.1) and measured at 0.85 m becomes `Measure(0.85, 0.85, "anchor_measured")`. Another door estimated at (1.8, 2.2) has midpoint 2.0 × factor 0.85 = 1.70, so it becomes `low_m = 1.36`, `high_m = 2.04`, `basis = "estimated"`. Zone rects scale by the same factor.
- [ ] **Step 2:** Run `pytest tests/test_contracts.py -v`. Expected: FAIL (module missing).
- [ ] **Step 3:** Implement the models and `apply_anchor`. The factor is `measured / midpoint(anchor estimate)`. Non-anchor widths become `mid*f*(1±uncertainty)`. Doors with basis `assumed` keep that basis.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: venue contracts with revision hashing and anchor scaling`.

### Task 4: Graph checks

**Files:**
- Create: `backend/walktwin/graph_checks.py`, `tests/test_graph_checks.py`

**Interfaces:**
- Consumes: Task 3 models.
- Produces:
  - `Finding(code: str, severity: Literal["error","warning"], element_id: str | None, message: str)`
  - `check_graph(graph: VenueGraph, video_duration_s: float) -> list[Finding]`
  - `has_errors(findings) -> bool`
  - `reachable_zones(graph, scenario: Scenario | None = None) -> set[str]`. Walks doors that are effectively open: `open` state or an `OPEN:` intervention, and not under a hazard. `unknown`, `closed` and `locked` count as closed.
- Error codes:
  - `DUPLICATE_ID`, `UNKNOWN_ZONE_REF`
  - `DOOR_OFF_BOUNDARY`: more than 0.5 m from the shared edge of `a` and `b`, or from `a`'s edge for OUTSIDE
  - `ZONE_OVERLAP`: intersection area > 0.25 m²
  - `NO_EXIT`, `EVIDENCE_OUT_OF_RANGE`, `KEYFRAME_UNKNOWN_ZONE`
- Warning codes: `UNREACHABLE_ZONE`, `UNKNOWN_DOOR_STATE`.
- [ ] **Step 1:** Write the tests:
  - `test_fixture_clean`: `office_graph.json` gives `[]`.
  - `test_door_off_boundary`: moving D1 by 2 m gives exactly one `DOOR_OFF_BOUNDARY` for `"D1"`.
  - `test_overlap`: two rects overlapping by 1 m² give `ZONE_OVERLAP`.
  - `test_no_exit`: removing both exits gives `NO_EXIT`.
  - `test_evidence_out_of_range`: `end_s=200` with a 90 s video gives `EVIDENCE_OUT_OF_RANGE`.
  - `test_unreachable_zone_warning`: locking the only door into Z4 gives a `UNREACHABLE_ZONE` warning for `"Z4"`, and `has_errors` is False.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement with plain geometry (rect edges are axis-aligned). Reachability is a BFS from the OUTSIDE side over effectively open doors.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: deterministic venue graph checks`.

### Task 5: Egress flow solver

**Files:**
- Create: `backend/walktwin/flow.py`, `tests/test_flow.py`

**Interfaces:**
- Consumes: `VenueGraph`, `Scenario`, `FlowParams`.
- Produces:
  - `FlowRun(run_id: str, graph_revision: str, scenario_hash: str, params: FlowParams, total: int, reached_exit: int, remaining_by_zone: dict[str,int], in_transit_end: int, door_flows: dict[str, list[int]], zone_occupancy: list[dict[str,int]], transit_by_step: list[int], reached_by_step: list[int])`
    - `door_flows[d][k]`: people entering door `d` during step `k`, signed `a→b` positive and `b→a` negative.
    - `zone_occupancy[k]`, `transit_by_step[k]` and `reached_by_step[k]`: people in each zone, people in transit, and cumulative people at exits, at the start of step `k`, for `k = 0..horizon/dt`.
    - `run_id` is `"r-" + sha256(graph_revision + scenario_hash + params)[:12]`, so it is deterministic.
  - `door_rate_per_step(door: Door, params: FlowParams) -> float = specific_flow * max(0, door.clear_width.low_m - 2*boundary_layer_m) * dt_s`. This is effective width, using the conservative low estimate.
  - `door_capacity_at_step(door: Door, k: int, params: FlowParams) -> int = floor((k+1)*c) - floor(k*c)`, with `c = door_rate_per_step(door, params)`. Cumulative rounding loses under one person over the whole horizon. A per-step floor would lose up to 30% on an 0.85 m door (c = 1.43 → 1).
  - `travel_steps(graph, door, from_zone, to_zone, params) -> int = max(1, ceil((dist(centroid(from), door.position) + dist(door.position, centroid(to) or door.position for OUTSIDE)) / walk_speed / dt))`
  - `solve(graph, scenario, params) -> FlowRun`
- **Algorithm (not determined by the signature):** build a time-expanded network.
  - Nodes: `(zone, k)` for k in 0..K, a super-source and a super-sink.
  - Edges:
    - source → `(z, 0)` with capacity `occupants`
    - holdover `(z, k)` → `(z, k+1)`, unbounded
    - for each effectively open door and each direction: `(from, k)` → a per-door-step gate node with capacity `door_capacity_at_step(door, k)`, then to `(to, k + travel_steps)` if that is ≤ K
    - exits: to the sink when `k + travel_steps ≤ K`
    - the gate node is shared by both directions, so capacity is per door, not per direction
  - A hazard closes the door for steps `k ≥ ceil(from_s/dt)`.
  - Use `networkx.maximum_flow` with integer capacities. Read edge flows back into `door_flows`, `zone_occupancy`, `transit_by_step` and `reached_by_step`. Whatever hasn't reached the sink by the horizon goes to `remaining_by_zone`, or to `in_transit_end` for people still in transit.
- [ ] **Step 1:** Write the tests:
  - `test_single_room_single_exit`: one 10×10 zone with 50 occupants and one exit, `Measure(1.0, 1.0)`, at the room edge 5 m from the centroid.
    - Effective width is 0.7 m, so `c = 1.3*0.7*2 = 1.82`. Travel is `ceil(5/1.2/2) = 3` steps.
    - With K = 60, `reached_exit == 50`.
    - With `horizon_s=20` (K = 10), departures run at k = 0..7, so `reached_exit == floor(8*1.82) == 14`.
  - `test_cumulative_rounding`: a door with `c = 1.43` has `sum(door_capacity_at_step(d, k) for k in range(10)) == 14`.
  - `test_narrow_door_effective_width_zero`: clear width (0.28, 0.30) gives rate 0 and `reached_exit == 0`.
  - `test_hazard_closes_exit`: fire on the only exit from 0 s gives `reached_exit == 0` and `remaining_by_zone == {"Z1": 50}`.
  - `test_intervention_opens_locked_door`: the fixture with D5 locked, against `interventions=["OPEN:D5"]`. The second has `reached_exit ≥` the first.
  - `test_unreachable_zone_counts_as_remaining`: sealed Z4 with 10 occupants gives `remaining_by_zone["Z4"] == 10`.
  - `test_conservation_every_step`: for every k, `sum(zone_occupancy[k].values()) + transit_by_step[k] + reached_by_step[k] == total`.
  - `test_deterministic_run_id`: two solves give identical `run_id` and `door_flows`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement as above.
- [ ] **Step 4:** Run the tests. Expected: PASS. Also time `solve` on the fixture with `horizon_s=120`; expected under 1 s, printed in the test output.
- [ ] **Step 5:** Commit: `feat: time-expanded max-flow egress solver`.

### Task 6: Independent checker

**Files:**
- Create: `backend/walktwin/checker.py`, `tests/test_checker.py`

**Interfaces:**
- Consumes: `VenueGraph`, `Scenario`, `FlowParams` and `FlowRun`. It must **not** import `flow.py`. It recomputes effective width, cumulative-rule capacities and travel steps with its own small functions.
- Produces: `CheckResult(ok: bool, run_id: str, violations: list[str])`, and `check_run(graph, scenario, params, run) -> CheckResult`.
- Checks:
  - the run's revision and hash match the inputs
  - every door in `door_flows` exists
  - |flow| at step k ≤ the cumulative-rule capacity for step k
  - zero flow on effectively closed doors at hazard steps
  - per-step conservation (`zone_occupancy` + `transit_by_step` + `reached_by_step` == total), and `reached_by_step` never decreases
  - `total == sum(occupants)`
  - `reached_exit == reached_by_step[-1]` == the sum of exit inflows arriving by K
  - occupancy is never negative
- [ ] **Step 1:** Write the tests:
  - `test_honest_run_passes`: a fixture solve gives `ok` True.
  - `test_inflated_door_flow_fails`: adding 5 to `door_flows["D1"][3]` gives `ok` False, with a violation that mentions `"D1"` and `"capacity"`.
  - `test_flow_through_hazard_fails`: flow inserted on a fire-closed exit.
  - `test_inflated_total_fails`: `reached_exit += 1`.
  - `test_stale_revision_fails`: checking against a graph with a changed width.
  - `test_suboptimal_flow_still_valid`: a run built with plain per-step floors (lower flows) still passes. Lower flow is legal; the checker enforces upper bounds and conservation, not optimality.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement `check_run`.
- [ ] **Step 4:** Run the tests. Expected: PASS. Then `grep -n "from .flow\|import flow" backend/walktwin/checker.py`. Expected: no output.
- [ ] **Step 5:** Commit: `feat: independent egress run checker`.

### Task 7: ADA egress rules

**Files:**
- Create: `backend/walktwin/egress_rules.py`, `tests/test_egress_rules.py`

**Interfaces:**
- Produces:
  - `RuleResult(rule_id: str, element_id: str, statement: str, threshold_m: float, measured: Measure | None, status: Literal["pass","fail","cannot_measure"], reason: str | None, citation: str)`
  - `evaluate_rules(graph: VenueGraph) -> list[RuleResult]`
  - `ALWAYS_CANNOT_MEASURE: list[tuple[str, str]]`, pairs of (rule_id, statement)
- Rules (2010 ADA Standards):
  - **`ADA-404.2.3` door clear width**, for `kind == "door"` and `"exit"`. A doorway deeper than 24 in needs 36 in (0.914 m) instead of 32 in (0.813 m), and video can't see depth. So `pass` only if `low_m ≥ 0.914`; `fail` if `high_m < 0.813`; otherwise `cannot_measure`. When the range touches 0.813–0.914 m, the reason is `"doorway depth unknown"`.
  - **`ADA-403.5.1` route clear width ≥ 0.914 m**, for `kind == "opening"`. `pass` if `low_m ≥ threshold`, `fail` if `high_m < threshold`, otherwise `cannot_measure`.
  - **`ADA-304.3.1` 1.524 m turning circle**, per zone, measured as `min(w, h)`. The statement says "room footprint only". The status is `cannot_measure` with reason `"furniture seen"` when `zone.furniture_seen`.
  - Basis `assumed` is always `cannot_measure`.
- `ALWAYS_CANNOT_MEASURE`:
  - `ADA-404.2.5` thresholds
  - `ADA-404.2.7` hardware
  - `ADA-404.2.9` opening force
  - `ADA-405.2` ramp slope
  - signage
  - `"IBC/NFPA occupant load: copyrighted model code; we cite section numbers and published factors, not code text"`
- [ ] **Step 1:** Write the tests:
  - `test_door_pass`: (0.95, 0.95, anchor_measured) gives `pass`.
  - `test_door_32_to_36_cannot_measure`: (0.85, 0.85, anchor_measured) gives `cannot_measure` with reason `"doorway depth unknown"`.
  - `test_door_fail`: (0.70, 0.78, estimated) gives `fail`.
  - `test_door_band_straddles`: (0.75, 0.90) gives `cannot_measure`.
  - `test_turning_furniture_cannot_measure`.
  - `test_assumed_is_cannot_measure`.
  - `test_citations_present`: every `citation` starts with `"2010 ADA Standards §"`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: ADA width and turning checks with cannot-measure`.

### Task 8: Video prep and frames

**Files:**
- Create: `backend/walktwin/media.py`, `tests/test_media.py`, `tests/fixtures/make_clips.sh` (synthetic clips made with ffmpeg `testsrc`, including an HEVC portrait `.mov` and a 5 s solid-colour clip)

**Interfaces:**
- Produces:
  - `PreparedVideo(path: Path, sha256: str, duration_s: float, width: int, height: int)`
  - `prepare_video(src: Path, out_dir: Path, max_s: float = 180) -> PreparedVideo`: H.264 mp4, long edge 1280, constant 30 fps, rotation applied, audio dropped. Raises `ValueError("too_long")` above `max_s`.
  - `extract_frame(video: Path, t_s: float, out: Path) -> Path` (JPEG)
  - `sample_frames(video: Path, fps: float, out_dir: Path) -> list[tuple[float, Path]]`
- [ ] **Step 1:** Write the tests:
  - `test_prepare_hevc_portrait_mov`: a 1080×1920 HEVC `.mov` gives an mp4 with `height > width`, `ffprobe` codec `h264`, and `|duration - 5| < 0.2`.
  - `test_too_long_rejected`: a 200 s clip raises `too_long`.
  - `test_extract_frame`: the 2.5 s frame exists and is larger than 1 KB.
  - `test_sample_frames_timestamps`: a 5 s clip at 2 fps gives 10 frames with `t_s` of 0.0, 0.5, … 4.5.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement with `subprocess.run([...], check=True)`.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: video prep and frame extraction`.

### Task 8b: Structure-from-motion camera path

**Files:**
- Create: `backend/walktwin/sfm.py`, `tests/test_sfm.py`, `tests/fixtures/sfm_synthetic.py` (synthetic floor and wall points plus a camera path, no video)

**Interfaces:**
- Consumes: `PreparedVideo`, `sample_frames`, `VenueGraph`.
- Produces:
  - `SfmFrame(t_s: float, center: tuple[float,float,float], R: list[list[float]], K: list[list[float]])`, with a camera-to-world rotation and intrinsics.
  - `SfmResult(status: Literal["completed","failed"], frames: list[SfmFrame], points: list[tuple[float,float,float]], registered_fraction: float, elapsed_ms: int, error: str | None)`
  - `run_sfm(video: PreparedVideo, work_dir: Path, fps: float = 2.0) -> SfmResult`:
    - sample at 2 fps
    - pycolmap SIFT extraction and sequential matching (overlap 10)
    - the GLOMAP global mapper, falling back to incremental mapping
    - keep the largest model
    - never raises; failures return `status="failed"`
  - `Alignment(scale: float, yaw_rad: float, tx: float, ty: float, floor_normal: tuple[float,float,float], floor_offset: float, residual_m: float, eye_height_m: float, hash: str)`
  - `fit_alignment(sfm: SfmResult, graph: VenueGraph) -> Alignment`:
    - fit the floor plane by RANSAC, choosing the plane below the camera path
    - project camera centres onto the floor
    - fit a 2D Umeyama similarity from the projected centres at keyframe times (nearest SfM frame within 0.5 s) to the graph keyframes' (x, y)
    - `eye_height_m` = mean camera height above the floor × scale
    - `hash` = sha256 of the parameters rounded to 4 decimals
  - `to_graph_xy(alignment, p_xyz) -> tuple[float, float]` and `height_above_floor_m(alignment, p_xyz) -> float`
  - `scale_badge(alignment) -> Literal["agrees","disagrees"]`: `"agrees"` when `eye_height_m` is within 1.5 ± 0.1 m (declared) and `residual_m ≤ 0.5`.
- **Fit the alignment once, on the iteration-0 graph, and freeze it.** Later rounds reuse its hash. Re-fitting each round would let the score improve without any real fix.
- The tape-measured anchor stays the authority for scale; the badge is a cross-check.
- [ ] **Step 1:** Write the tests:
  - `test_fit_alignment_recovers_known_transform`: synthetic points on the floor plane z = 0 and on walls, with cameras at 1.5 m. Apply a known similarity (scale 0.37, yaw 30°, shift (2, −1)) to make the "SfM" frame. The fit recovers scale within 1%, yaw within 1°, `eye_height_m` within 0.02 m, and `residual_m < 0.05`.
  - `test_alignment_hash_stable`.
  - `test_scale_badge_disagrees_when_eye_height_off`: scale × 1.3 gives `"disagrees"`.
  - `test_run_sfm_failed_on_blank_video`: the 5 s solid-colour clip gives `status == "failed"`, a set `error`, and no exception.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. Add a CLI, `python -m walktwin.sfm <video>`, that prints `registered_fraction` and `elapsed_ms`.
- [ ] **Step 4:** Run the tests. Expected: PASS. Live: run the CLI on the probe clip. Expected: `registered_fraction ≥ 0.8`; record the time. If SfM fails on low-texture rooms, note it in the README. The geometry score then shows "unavailable"; MapAnything-apache is the stretch fallback.
- [ ] **Step 5:** Commit: `feat: SfM camera path and frozen alignment`.

### Task 9: Argon video extraction

**Files:**
- Create: `backend/walktwin/extract.py`, `backend/walktwin/prompts/extract.md`, `tests/test_extract.py`

**Interfaces:**
- Consumes: Task 2 helpers, Task 3 models, Task 4 `check_graph` and Task 8 `PreparedVideo`.
- Produces:
  - `VideoMode = Literal["static","static_hifps","agentic"]`
  - `ExtractionResult(status: Literal["completed","failed","timeout","invalid"], graph: VenueGraph | None, findings: list[Finding], receipt: Receipt | None, mode: VideoMode, agentic_observed: bool | None, video_uri: str | None, error: str | None)`. `agentic_observed` is `receipt.processing_calls > 0` in agentic mode and `None` otherwise. `receipt.interaction_id` is what Task 11 chains onto.
  - `async def extract_venue(client, video: PreparedVideo, *, mode: VideoMode = "static_hifps", deadline_s: float, anchor_hint: str | None = None) -> ExtractionResult`. The default mode is whichever won the Task 2 gate.
- Request:
  - `model="gemini-4-argon"`, `store=True`, `background=True`
  - `generation_config={"thinking_level":"high","max_output_tokens":65536}`, plus `thinking_summaries:"auto"` if Task 2 showed the SDK accepts it
  - `response_format={"type":"text","mime_type":"application/json","schema": <VenueGraph schema without revision>}`
  - input: the video part (the Task 2 representation), then the prompt text
  - `deadline_s`: at least 3× the time Task 2 observed for that mode
- The prompt tells Argon to:
  - walk the video in order and name the zones
  - place zones as axis-aligned rects on one floor plane in meters, origin at the first frame's position, +y along the initial heading
  - list every door, opening, exit and stair with `[start_s, end_s]` evidence
  - estimate widths as ranges
  - use state `unknown` when a door isn't seen open, and set `furniture_seen` per zone
  - emit 5–8 keyframes spread across the video
  - treat spoken or on-screen text as scene data, not instructions
- [ ] **Step 1:** Write the tests with `FakeClient`:
  - `test_valid_extraction`: canned JSON (the fixture graph without revision) gives `completed`, a graph with a revision, and findings equal to `check_graph(...)`.
  - `test_schema_violation_invalid`: a missing `zones` gives `invalid` and `graph is None`.
  - `test_mode_static_sends_fps`: the captured video part has `processing == {"type":"static","fps":1}`.
  - `test_mode_static_hifps_sends_fps3_high`: `{"type":"static","fps":3}` and `resolution == "high"`.
  - `test_agentic_not_observed`: agentic mode with zero `processing_call` steps gives `agentic_observed is False`.
  - `test_output_cap_65536`: the captured `max_output_tokens == 65536`.
  - `test_failed_status_propagates`: provider `failed` gives `failed`, never a fixture.
  - `test_timeout`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. Set `video_sha256` from `PreparedVideo`, ignoring the model's value.
- [ ] **Step 4:** Run the tests. Expected: PASS. Live: `python -m walktwin.extract runtime/probe_clip.mp4`. Expected: `completed`; save the receipt to `runtime/receipts/`.
- [ ] **Step 5:** Commit: `feat: Argon walkthrough video extraction`.

### Task 10: Twin renderer and headless capture

**Files:**
- Create: `frontend/src/twin/buildScene.ts`, `frontend/src/twin/cameraFor.ts`, `frontend/src/twin/buildScene.test.ts`, `frontend/render.html`, `frontend/src/render.tsx`, `backend/walktwin/render.py`, `tests/test_render.py`

**Interfaces:**
- Produces (TS):
  - `buildScene(graph: VenueGraph, opts: { hazards: string[]; doorFlows?: Record<string, number> }): THREE.Scene`
    - a floor per zone, named `zone:<id>`
    - 2.7 m walls on rect edges, with gaps at doors (gap = the door's mid width)
    - door frames named `door:<id>`, coloured by state: open green, closed grey, locked `0x8b1a1a`, unknown amber
    - exits named `exit:<id>`
    - hazards named `hazard:<doorId>`, a red emissive box
  - `cameraFor(k: Keyframe): THREE.PerspectiveCamera`: eye height 1.6 m, fov 65°, looking along `heading_deg`
  - `topDownCamera(graph): THREE.OrthographicCamera`, fitting all zones with a 1 m margin
  - `render.html?graph=<url>&t=<t_s>`, or `&view=top`, renders one 1280×720 view and sets `window.__renderReady = true`
- Produces (Py):
  - `RenderedView(t_s: float | None, path: Path, kind: Literal["perspective","top"])`
  - `async def render_views(graph: VenueGraph, out_dir: Path, base_url: str) -> list[RenderedView]`: one perspective view per keyframe, plus one top-down view
- [ ] **Step 1:** Write the vitest tests: the fixture gives 4 `zone:*`, 6 `door:*` and 2 `exit:*` objects; `hazards: ["D2"]` adds `hazard:D2`; a locked door's colour is `0x8b1a1a`; `topDownCamera` bounds contain every zone rect.
- [ ] **Step 2:** Run `npx vitest run`. Expected: FAIL.
- [ ] **Step 3:** Implement `buildScene`, `cameraFor` and `topDownCamera` as pure functions with no DOM access, then `render.tsx`.
- [ ] **Step 4:** Run `npx vitest run`. Expected: PASS.
- [ ] **Step 5:** Write the pytest `test_render_views_writes_keyframes_plus_top`, marked `@pytest.mark.browser`. Serve `frontend/dist`. The fixture gives 6 PNGs (5 perspective, 1 top), each larger than 10 KB with mean pixel above 10.
- [ ] **Step 6:** Implement `render_views` with Playwright Chromium headless, `args=["--use-angle=swiftshader","--enable-unsafe-swiftshader"]`, waiting for `window.__renderReady`.
- [ ] **Step 7:** Run `pytest -m browser`. Expected: PASS. If headless WebGL fails, record the flags that work in the README.
- [ ] **Step 8:** Commit: `feat: three.js twin renderer and headless capture`.

### Task 10b: Geometry score (the separate critic)

**Files:**
- Create: `backend/walktwin/geometry_score.py`, `tests/test_geometry_score.py`

**Interfaces:**
- Consumes: `VenueGraph`, `SfmResult`, `Alignment`, `to_graph_xy`, `height_above_floor_m` and `extract_frame`.
- Produces:
  - `Crossing(t_s: float, x: float, y: float, edge: str)`, where `edge` is `"<zone id>.<north|south|east|west>"` or `"outside"`
  - `GeometryScore(alignment_hash: str, illegal_crossings: list[Crossing], wall_support: float, unexplained_points: float, edge_chamfer_px: float | None, edge_within_5px: float | None, heldout_t_s: list[float])`
  - `score_geometry(graph, sfm, alignment, video: PreparedVideo | None = None, heldout_t_s: list[float] = []) -> GeometryScore`
  - `is_regression(before: GeometryScore, after: GeometryScore) -> bool`: True if crossings increase, if `wall_support` drops by more than 0.02, or if `edge_within_5px` drops by more than 0.05 (when both are present). Raises `ValueError` if the alignment hashes differ.
- Definitions (thresholds are declared; tune them on the day's captures):
  - **Wall:** every zone-rect edge minus door gaps (door position ± mid width / 2). Shared edges count once.
  - **Illegal crossing:** a segment between consecutive SfM camera positions, projected to graph xy, that crosses a wall more than 0.5 m from any door on that edge. Leaving every zone also counts, with edge `"outside"`. The walker can't walk through a wall, so each crossing is a timestamped error.
  - **Wall support:** of the SfM points 0.5–2.0 m above the floor, the share within 0.15 m of a wall.
  - **Unexplained points:** of those points, the share more than 0.15 m outside every zone rect.
  - **Edge alignment, held-out frames only:**
    - project the twin's floor-wall lines and door jambs through the SfM poses into frames never sent to the critique
    - detect Canny edges and compute a distance transform
    - report the mean distance and the share within 5 px
    - never use SSIM or LPIPS, which track appearance rather than geometry
- [ ] **Step 1:** Write the tests:
  - `test_path_through_wall_is_crossing`: two zones share an edge with no door, and the path runs from Z1's centre to Z2's centre. Expect 1 crossing on that edge, with the segment's `t_s`.
  - `test_door_removes_crossing`: adding a door at the crossing gives 0.
  - `test_crossing_near_door_tolerated`: a path 0.4 m from a door gap gives 0.
  - `test_wall_support`: synthetic points on modelled walls give ≥ 0.95; shifting the walls 1 m gives ≤ 0.2.
  - `test_is_regression`, and `test_is_regression_rejects_mismatched_alignment`.
  - `test_edge_chamfer_zero_on_synthetic_frame`: draw the projected edges onto a blank image and use it as the frame. Chamfer < 1 px.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement with numpy and OpenCV (`cv2.Canny`, `cv2.distanceTransform`).
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: measured geometry score from the walker's path`.

### Task 11: Chained critique, patch and refine loop

**Files:**
- Create: `backend/walktwin/patch.py`, `backend/walktwin/critique.py`, `backend/walktwin/loop.py`, `backend/walktwin/prompts/critique.md`, `tests/test_patch.py`, `tests/test_critique.py`, `tests/test_loop.py`

**Interfaces:**
- Produces:
  - `PatchOp`, a discriminated union on `op`:
    - `add_door{door: Door}`, `remove_door{id}`
    - `update_door{id, position?, clear_width?, state?, kind?}`
    - `add_zone{zone: Zone}`, `update_zone{id, rect?, name?, furniture_seen?}`, `remove_zone{id}`
    - each has `cite_t_s: float` and `reason: str` (max 200)
  - `PatchOutcome(graph: VenueGraph, applied: list[int], rejected: list[tuple[int, str]])`
  - `apply_patch(graph, ops, video_duration_s) -> PatchOutcome`. Apply ops in order. Reject an op with unknown ids, or one that adds an error-severity finding it didn't have before. Revert the rejected op and continue.
  - `Discrepancy(t_s: float, element_id: str | None, description: str)`
  - `CritiqueResult(status, discrepancies: list[Discrepancy], ops: list[PatchOp], interaction_id: str | None, receipt)`
  - `async def critique(client, graph, pairs: list[tuple[Path, Path, float]], *, previous_interaction_id: str, video_uri: str, topdown: Path, zoom: list[tuple[str, float, float]] = [], deadline_s: float) -> CritiqueResult`
    - `pairs` are (video frame, render, t_s), at most 8. `zoom` entries are (door id, start_s, end_s).
    - **Chained:** round 1 uses the extraction's `interaction_id` as `previous_interaction_id`; later rounds use the previous critique's id. The video stays in server-side context, so the prompt refers to it instead of re-sending it.
    - Input order: for each pair, text `"t=<t_s> VIDEO"`, the frame, text `"RENDER"`, the render; then text `"TOP-DOWN PLAN"` and `topdown`; then, if allowed by the Task 2 probe (d), one static clipped part of `video_uri` per zoom entry (`start_offset`/`end_offset`, fps 5, `resolution:"high"`); then the graph JSON and the prompt.
    - `thinking_level:"high"`, `max_output_tokens:65536`, schema output.
  - `Iteration(index: int, graph_revision: str, discrepancy_count: int, applied: list[int], rejected: list[tuple[int,str]], findings: list[Finding], geometry: GeometryScore | None, renders: list[RenderedView], receipt: Receipt | None, stop_reason: str | None)`
  - `async def refine(client, graph, video: PreparedVideo, extraction: ExtractionResult, *, sfm: SfmResult | None, alignment: Alignment | None, base_url: str, max_iterations: int = 4, deadline_s: float) -> list[Iteration]`
  - Stop reasons: `"no_discrepancies"`, `"no_ops_applied"`, `"repeated_revision"`, `"measured_regression"`, `"max_iterations"`, `"provider_failed"`.
- **Loop behaviour:**
  1. Render views.
  2. Extract the frames at the keyframes.
  3. Critique, with zoom parts for the doors named in the previous round's discrepancies (±2 s around their evidence).
  4. `apply_patch`, then `check_graph`.
  5. If SfM is available, `score_geometry` on held-out frames (SfM frames more than 1 s from any keyframe). If `is_regression(prev, new)`, revert the whole round's patch, record it as rejected with reason `measured_regression`, and stop.
  - Without SfM, the loop runs on model-reported counts only, and `geometry` is `None`.
- **Labels:** `discrepancy_count` is "model-reported"; geometry rows are "measured".
- [ ] **Step 1:** Write the tests:
  - `test_patch_rejects_unknown_and_breaking_ops`: ops `[update_door D9 (unknown), update_door D1 position +3 m (DOOR_OFF_BOUNDARY), update_door D2 state open]` give `applied == [2]`, rejected reasons containing `"unknown id"` and `"DOOR_OFF_BOUNDARY"`, and D2 open.
  - `test_patch_add_door_then_check`.
  - `test_critique_parses_ops`: two ops validate as `PatchOp`.
  - `test_critique_chains_previous_interaction`: round 1's captured request has `previous_interaction_id` equal to the extraction's id; round 2's equals round 1's critique id; every request includes the top-down image.
  - `test_loop_stops_on_repeated_revision`: a critique that alternates add D7 / remove D7 gives `stop_reason == "repeated_revision"` by round 3.
  - `test_loop_rejects_measured_regression`: a fake critique removes a door the path passes through, crossings increase, the patch is reverted, `stop_reason == "measured_regression"`, and the graph revision is unchanged.
  - `test_loop_stops_no_discrepancies`.
  - `test_loop_provider_failure_keeps_last_graph`.
  - `test_loop_without_sfm_labels_unavailable`: `sfm=None` gives `geometry is None` on every iteration.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement `patch.py`, then `critique.py`, then `loop.py`.
- [ ] **Step 4:** Run the tests. Expected: PASS. Live: run `refine` on the probe clip with SfM. Expected: at least one round completes, with receipts and geometry scores saved.
- [ ] **Step 5:** Commit: `feat: chained critique loop graded by measured geometry`.

### Task 12: Benchmark and answer keys

**Files:**
- Create: `backend/walktwin/benchmark.py`, `tests/test_benchmark.py`, `bench/<venue>/answer_key.json` (×3)

**Interfaces:**
- Produces:
  - `KeyDoor(t_s: float, kind: Literal["door","opening","exit","stair"], measured_width_m: float | None)`
  - `AnswerKey(venue: str, video_sha256: str, source: Literal["tape","roomplan"], doors: list[KeyDoor])`
  - `BenchmarkScore(mode: str, door_precision: float, door_recall: float, door_f1: float, exit_recall: float, width_mae_m: float | None, final_illegal_crossings: int | None, agentic_observed: bool | None, matched: list[tuple[str, int]])`
  - `score(graph: VenueGraph, key: AnswerKey, tolerance_s: float = 2.0) -> BenchmarkScore`
    - A predicted door matches a key door when one of its evidence intervals, widened by ±`tolerance_s`, contains the key's `t_s`.
    - Kinds are compatible within exit/stair and within door/opening.
    - Matching is greedy and one-to-one, by nearest interval midpoint.
    - Exit recall covers key exits. Width MAE uses matched doors that have measured widths.
  - CLI: `python -m walktwin.benchmark run --venue bench/office --modes static,static_hifps,agentic,agentic_loop` writes `runtime/bench/<venue>.json` with one `BenchmarkScore` per mode, plus receipts.
    - An `agentic` row with `agentic_observed == False` is labelled `agentic (not observed)`.
    - Flat results are reported flat. The geometry loop's improvement is a separate measured claim.
- **Human capture (Nihal + Charlie, start at kickoff):**
  - Get SHACK15 staff permission.
  - Film three walkthroughs of 90–150 s each: a SHACK15 area, an office, and a home (homes also answer a likely "does it work in a home?" question).
  - Film in landscape, walk slowly, pause about 2 s facing each door, and keep identifiable people out of frame.
  - A second person notes the timestamp at each door and exit.
  - Tape-measure at least 5 clear widths per venue, including the anchor door.
  - If a teammate has a LiDAR iPhone, also save a RoomPlan scan as a second key with `source: "roomplan"`.
  - Record each video's sha256 after `prepare_video`.
- [ ] **Step 1:** Write the tests:
  - `test_perfect_match`: key doors at t = 10, 20, 30, with predicted evidence covering them, give F1 1.0.
  - `test_kind_mismatch_not_matched`.
  - `test_tolerance`: evidence [12.5, 13] and key t = 15 match at tolerance 2.0 and don't at 1.0.
  - `test_width_mae`: errors of 0.05 and 0.15 give 0.10.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement `score` and the CLI.
- [ ] **Step 4:** Run the tests. Expected: PASS. Live: run all four modes on all three venues. Put the real numbers in the README under "Measured results". **Never** put a number there that the CLI didn't produce.
- [ ] **Step 5:** Commit: `feat: answer-key benchmark for four extraction modes`.

### Task 13: Managed agent sandbox sweep

**Files:**
- Create: `backend/walktwin/agent.py`, `backend/walktwin/prompts/agent.md`, `agent_env/AGENTS.md`, `agent_env/skills/sweep/SKILL.md`, `agent_env/skills/ada/SKILL.md`, `agent_env/hooks/pre_tool_execution.py`, `tests/test_agent.py`

**Interfaces:**
- Consumes: `solve`, `check_run`, `reachable_zones`, the Task 2 client and `render_views` (top-down).
- Produces:
  - `allowed_interventions(graph, scenario) -> list[str]`: `"OPEN:<id>"` for each door in state `closed`, `locked` or `unknown` that isn't under a hazard. Sorted, at most 6.
  - `InterventionResult(intervention_id: str, run_id: str, reached_exit: int, total: int, delta_vs_current: int, check_ok: bool, limiting_doors: list[str])`. Limiting doors are those at capacity for ≥ 50% of the steps they carried flow.
  - `Recommendation(intervention_id: str | None, claimed_reached_exit: int | None, rationale: str max 600, caveats: list[str] max 5)`
  - `LedgerEntry(call_id: str, kind: Literal["client_function","sandbox_step"], name: str, args: dict, result: dict | None, executed_at: str)`
  - `Investigation(investigation_id: str, graph_revision: str, scenario_hash: str, status: Literal["completed","failed","timeout","incomplete","cancelled"], interaction_id: str | None, environment_id: str | None, ledger: list[LedgerEntry], sandbox_runs: int, results: list[InterventionResult], recommendation: Recommendation | None, best: InterventionResult | None, disagreement: str | None, hook_denials: int, receipt: Receipt | None)`
  - `async def prepare_environment(client) -> str`. Run once and cache in `runtime/agent_env.json`:
    - create a remote environment with the network on
    - inline-mount `backend/walktwin/{contracts,flow,graph_checks}.py` and `agent_env/` (read-only where supported); total under 2 MB
    - `pip install networkx pydantic`
    - return the `environment_id`
  - `async def investigate(client, graph, scenario, params, *, environment_id: str, topdown_png: Path, deadline_s: float = 180, max_rounds: int = 4) -> Investigation`. `topdown_png` is the top-down render from `render_views` with the hazard drawn in.
- **Request:**
  - `agent="antigravity-preview-09-2026"` with the Global Constraints `agent_config` (`max_total_tokens: 300000`)
  - `environment`: the prepared environment with the network disabled, per the Task 2 probe (f)
  - `tools`: `code_execution` plus two client functions:
    - `evaluate_interventions(ids: list[str], 1–4 items)`
    - `submit_recommendation(intervention_id: str|null, claimed_reached_exit: int|null, rationale: str, caveats: list[str])`
  - no `google_search` or `url_context`
- **Input:** text giving zones, doors with states, hazards, the current checked `reached_exit/total` and the allowed interventions, plus the top-down render as an inline base64 PNG. The scenario JSON is also written into the sandbox.
- **Tiering:**
  - The agent may sweep broadly in the sandbox: door combinations, other hazard placements, ±20% sensitivity on declared parameters, bottleneck ranking.
  - Only a shortlist goes to `evaluate_interventions`, which runs the local solver and checker.
  - `sandbox_runs` counts `code_execution` steps, labelled "sandbox runs, unverified".
- **Execution:**
  - The client executes only `evaluate_interventions` and `submit_recommendation`.
  - Any other `function_call` is a sandbox tool. Log it as `sandbox_step` and never execute it locally.
  - Before executing, look up `call_id`. If present, reuse the stored result and don't run it again.
  - Persist the ledger to `runtime/sessions/<id>/ledger.json` after each call.
- **Verdict, decided locally:** `best` is the highest `reached_exit` among `check_ok` results with `delta_vs_current > 0`, otherwise `None` ("No allowed change improves this case"). If `recommendation.claimed_reached_exit` differs from the checker's figure for that id, `disagreement` names both numbers. The UI shows both side by side.
- **Hook:** `pre_tool_execution` denies writes to `/workspace/accepted_graph.json`; denials are counted and shown. Hooks fail open on a crash or timeout and don't fire for custom functions, so call it an "audit hook". Authority stays local.
- **Continuation:** `previous_interaction_id=interaction.id`, `environment=interaction.environment_id`, input `[{"type":"function_result","name":..., "call_id":..., "result":...}]`.
  - Handle every status. On `incomplete`, resume once (it gets a fresh budget) only if time remains before the deadline.
  - Stop at `max_rounds` or the deadline; cancel the provider interaction at the deadline.
- [ ] **Step 1:** Write the tests with `FakeClient`:
  - `test_happy_path_sweep_then_verify`: three `code_execution` steps, then `requires_action` with `evaluate_interventions(["OPEN:D5"])`, then `submit_recommendation("OPEN:D5", claimed 58)`, then `completed`. Expect `sandbox_runs == 3`, one `client_function` ledger entry for evaluate, `best.intervention_id == "OPEN:D5"`, and `disagreement is None` when the checker also says 58.
  - `test_disagreement_flagged`: claimed 70 against the checker's 58 gives a `disagreement` containing `"70"` and `"58"`; `best` still comes from the checker.
  - `test_unknown_function_not_executed`: a `write_file` call isn't run locally and is logged as `sandbox_step`.
  - `test_duplicate_call_id_not_reexecuted`: patch `solve` to count calls; the count is 1.
  - `test_not_allowed_id`: `"OPEN:D1"` where D1 is already open gives `{"error":"not_allowed"}`.
  - `test_no_improvement_best_none`.
  - `test_incomplete_resumes_once`.
  - `test_request_shape`: the captured tools include `code_execution` and both functions and exclude search and URL context; `agent_config.model == "gemini-4-argon"`; `max_total_tokens == 300000`; the input contains one image part.
  - `test_deadline_cancels`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement `prepare_environment` and `investigate`. Then write `AGENTS.md`: the copy rules, and that numbers on screen come only from `evaluate_interventions`. Write the `sweep` skill (method and output format) and the `ada` skill (paraphrased §404.2.3, §403.5.1 and §304.3.1 with citations, so citations never need web search).
- [ ] **Step 4:** Run the tests. Expected: PASS. Live: `prepare_environment`, then investigate the fixture with fire on D2. Expected: `completed` with `provider_model == "gemini-4-argon"`; save the receipt and ledger.
- [ ] **Step 5:** Commit: `feat: managed agent sandbox sweep with local verification`.

### Task 14: Session API

**Files:**
- Create: `backend/walktwin/sessions.py`, `backend/walktwin/api.py`, `tests/test_api.py`

**Interfaces:**
- Produces:
  - `Session(id, video: PreparedVideo, anchor: Anchor | None, sfm: SfmResult | None, alignment: Alignment | None, draft_graph: VenueGraph | None, accepted_graph: VenueGraph | None, scenario: Scenario, current_run: FlowRun | None, current_check: CheckResult | None, iterations: list[Iteration], extraction: ExtractionResult | None, investigations: list[Investigation], approvals: list[Approval], jobs: dict[str, JobState])`
  - `JobState(kind, status: Literal["queued","running","done","failed"], error: str | None)`
  - `Approval(intervention_id, investigation_id, graph_revision, scenario_hash, run_id, note_path, approved_at)`
  - `SessionStore(root: Path)` with `.create(video, anchor)`, `.get(id)` and `.save(session)`
- Endpoints (JSON). Every mutating body carries `expected_revision`, the revision of the object it changes:
  - `POST /api/sessions` (multipart `video`, optional `anchor_door_hint`, `anchor_width_m`) → `{id}`. Starts an `sfm` job immediately, so the judge's path appears before Argon finishes.
  - `POST /api/sessions/{id}/extract {mode}` → 202
  - `POST /api/sessions/{id}/refine {expected_revision}` → 202. Fits the alignment on the first refine and freezes it.
  - `PUT /api/sessions/{id}/graph {expected_revision, graph}` → 200 with the new revision, or 409
  - `POST /api/sessions/{id}/accept {expected_revision}` → 200 when `check_graph` has zero errors: apply the anchor, solve, check, then start background investigations. Otherwise 409 if stale or 422 with findings.
  - `POST /api/sessions/{id}/scenario {expected_revision, hazards}` → re-solve and check
  - `POST /api/sessions/{id}/investigate {expected_revision, expected_scenario}` → 202
  - `POST /api/sessions/{id}/approve {expected_revision, expected_scenario, investigation_id, intervention_id}` → apply the intervention, re-solve, check and draft the note
  - `GET /api/sessions/{id}` → snapshot, including `ghost_path: [{t_s, x, y}]` (SfM camera centres through `to_graph_xy`, empty without SfM)
  - `GET /api/sessions/{id}/report` and `/report.html`
  - `GET /api/sessions/{id}/video`, `GET /api/sessions/{id}/frame?t=`
  - static `frontend/dist` mounted **last**
- **Background precomputation on accept:** pick the top 3 exits by baseline flow. For each, run an investigation with scenario "fire on that exit", at most 3 at once, each tagged with its own graph revision and scenario hash. When the judge drops fire on one of those exits, the matching investigation is ready, and only the sub-second local solve runs live.
- **Approval requires:** the investigation's `graph_revision` and `scenario_hash` match current state, the intervention appears in its `results` with `check_ok`, and it is in `allowed_interventions`.
- [ ] **Step 1:** Write the TestClient tests, with fakes injected through `app.dependency_overrides`:
  - `test_upload_starts_sfm_job`
  - `test_accept_rejects_errors_422`
  - `test_put_graph_stale_409`
  - `test_scenario_resolve_returns_checked_run`: `current_check.ok` is True
  - `test_accept_starts_three_precomputed_investigations`
  - `test_precomputed_investigation_matches_hazard`: fire on exit D1 picks the investigation whose `scenario_hash` equals the new scenario's; fire on a door without one exposes no ready investigation
  - `test_stale_investigation_rejected`: change hazards after an investigation, then approve, gives 409 `"stale_investigation"`
  - `test_approve_unchecked_intervention_rejected`
  - `test_static_mount_does_not_shadow_api`: `GET /api/sessions/x` returns a 404 JSON, not HTML
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. Jobs are `asyncio` tasks. At most one job per kind per session, except up to 3 `investigate` jobs. Another job of a running kind returns 409 `"job_running"`.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: session API with revision guards and precomputed investigations`.

### Task 15: Verification report and note to security

**Files:**
- Create: `backend/walktwin/report.py`, `tests/test_report.py`

**Interfaces:**
- Produces:
  - `Requirement(id: str, statement: str, method: Literal["measured","checker","model_reported","outside_model"], status: Literal["pass","fail","cannot_measure","not_run"], value: str | None, evidence: str)`
  - `Report(session_id, graph_revision, scenario_hash, run_id, verdict: Literal["verified_within_model","failed","incomplete"], requirements: list[Requirement], rules: list[RuleResult], hand_checks: list[str], declared_parameters: dict, provenance: list[str])`
  - `build_report(session) -> Report`
  - `render_html(report) -> str`: self-contained, no scripts, no external URLs, with `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">`
  - `draft_security_note(session, approval) -> str`: markdown whose first line is `# DRAFT — not sent`, addressed to security. For each door it gives door, state, check time and video timestamp, for example `D3 must stay unlocked and clear; checked 18:42; video t=01:12`. It then gives the hazard, the before/after `reached_exit` from checked runs, the limiting doors and the receipts. It ends with the hand-check to-do list (`- [ ] Check threshold height at D3`).
- Requirements:
  - population conserved (measured)
  - checker verdict (checker)
  - graph has zero errors (measured)
  - every exit has video evidence (measured)
  - final illegal crossings, wall support and held-out edge alignment (measured, or `not_run` without SfM)
  - alignment residual and scale badge (measured)
  - final loop discrepancy count (model_reported)
  - each `RuleResult` mirrored
  - every `ALWAYS_CANNOT_MEASURE` item (outside_model)
- `hand_checks` turns every `cannot_measure` row and `ALWAYS_CANNOT_MEASURE` item into a to-do line naming its door or zone.
- **Verdict:** `verified_within_model` only with zero `fail` rows and a checker pass; `incomplete` without an accepted run.
- [ ] **Step 1:** Write the tests:
  - `test_verdict_verified`: a fixture session with a checked run.
  - `test_failed_rule_fails_verdict`.
  - `test_geometry_rows_measured_or_not_run`.
  - `test_hand_checks_cover_cannot_measure`: `len(report.hand_checks) >= 6`, and each one mentions an element id or "venue".
  - `test_html_has_no_script_or_external`: no `<script` and no `http` in the output.
  - `test_security_note_header_and_timestamp`: the first line is `# DRAFT — not sent`, and the text contains `video t=`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: verification report and drafted security note`.

### Task 16: Frontend workflow

**Files:**
- Create: `frontend/src/api.ts`, `frontend/src/twin/ghostWalker.ts`, `frontend/src/twin/crowdDots.ts`, `frontend/src/app/App.tsx`, `frontend/src/app/{Capture,Review,Loop,Twin,Investigate,ReportDrawer}.tsx`, `frontend/src/api.test.ts`, `frontend/src/twin/ghostWalker.test.ts`, `frontend/src/twin/crowdDots.test.ts`

**Interfaces:**
- Consumes: the Task 14 endpoints, `buildScene` and `cameraFor`.
- Produces (pure, tested):
  - `ghostPath(snapshot): {t_s, x, y}[]`, read from the snapshot's `ghost_path` (the backend holds the frozen alignment)
  - `ghostFlashes(score: GeometryScore): {t_s, x, y}[]`, one per illegal crossing
  - `dotsForStep(run: FlowRun, k: number): {zoneId: string; count: number}[]`, where the counts equal `zone_occupancy[k]`
  - `formatHero(reached, total)`
- **Screens:** one page with steps along the top. The twin and the video are the hero; this is **not** a dashboard.
  1. **Capture:** record or upload. A phone opens `http://<laptop-ip>:8000` and uses `<input type=file accept="video/*" capture="environment">`. Fallbacks: personal hotspot, or AirDrop/USB then upload. Optional anchor: pick a door later and type its tape-measured width. The judge's SfM path appears as soon as the `sfm` job finishes.
  2. **Review:** the video beside a plan view, with an evidence timeline of one bar per element. Clicking a bar seeks the video to `start_s`. Edit door state, kind and width, drag rects, see findings inline. **Accept** is disabled while there are errors.
  3. **Loop:** per-round rows of frame | render pairs, the measured geometry row (crossings, wall support, edge alignment) next to the discrepancy count labelled "model-reported", and applied and rejected ops with reasons, including any `measured_regression` rejection.
  4. **Twin:** the 3D twin.
     - The ghost walker plays the SfM path through the twin and flashes red at each illegal crossing; clicking a flash seeks the video.
     - Drop Fire on a door or exit.
     - Hero text: "`<reached>` of `<total>` reach a modeled exit in 120 s · checked".
     - Crowd dots are driven 1:1 by `zone_occupancy`, with a counter that reconciles to the hero number; door flow is shown as arrow thickness.
  5. **Investigate:** streamed `code_execution` and `function_call` steps as evidence (never a fake timer). The sandbox figure and the checker figure sit side by side, with a disagreement flag. The agent's rationale is labelled "Agent's explanation". **Approve** is enabled only for a checked `best`; clicking the door opens its video evidence.
  6. **Report drawer** (for Q&A): the requirements table, ADA rows with citations, the hand-check to-do list, the HTML export and the security note draft.
- `api.ts` validates every response shape before render and drops any response whose `graph_revision` isn't current.
- [ ] **Step 1:** Write the vitest tests:
  - `parseSnapshot` rejects a snapshot whose `current_check.run_id !== current_run.run_id`
  - `isCurrent(result, snapshot)` is false after the revision changes
  - `formatHero(60, 120)` returns `"60 of 120 reach a modeled exit in 120 s"`
  - `dotsForStep` total equals `sum(zone_occupancy[k])` for every k of the fixture run
  - `ghostFlashes` length equals `illegal_crossings.length`
- [ ] **Step 2:** Run `npx vitest run`. Expected: FAIL.
- [ ] **Step 3:** Implement the pure modules, then `api.ts`, then the screens. Keep copy within the Global Constraints wording.
- [ ] **Step 4:** Run `npx vitest run && npm run build`. Expected: PASS and build success. Then click through the whole flow in the browser with the fixture session at 1280 px and 390 px widths. Check: no horizontal scroll, Accept/Approve gating works, stale results disappear after a hazard change, and the dot counter equals the hero number.
- [ ] **Step 5:** Commit: `feat: walkthrough-to-twin workflow UI with ghost walker`.

### Task 17: Rehearsal, demo video, submission

**Files:**
- Modify: `README.md` (Measured results, Demo, Limits)
- Create: `docs/DEMO.md`

- [ ] **Step 1:** Prepare a full SHACK15 session in advance: extracted, refined with SfM, accepted, with the three investigations precomputed and receipts saved. It is shown as a **saved live run** with its timestamp, while the judge's own clip processes.
- [ ] **Step 2:** Write `docs/DEMO.md` with three beats, each ending on one state change the judge sees. No slides.

  | Beat | Time | The judge sees | Say |
  |---|---|---|---|
  | 1. Your walk becomes the twin | 0:00–0:55 | The judge films about 40 s of one room (a single room keeps Argon's output small and fast). Their SfM path appears while Argon works. The saved full-floor run opens, and clicking a door's evidence seeks the video. | "Every event moves the tables. Nobody re-checks the exits. Film the room." |
  | 2. Argon proposes, geometry disposes | 0:55–1:50 | The ghost walker passes through a wall and flashes red. Argon's patch adds the door, citing its timestamp. Illegal crossings drop (for example 3 → 0) and held-out edge alignment improves. One patch is rejected, with its reason. | "Argon compared its twin with the whole video. Your footsteps checked Argon." Add benchmark numbers from `runtime/bench` only. |
  | 3. Fire, fix, approve | 1:50–2:50 | The judge drops Fire on the main exit; the hero number falls, marked checked. The sandbox sweep and the checker's verified figure appear side by side. The proposal is to open D3; the judge clicks its evidence, approves, the number recovers, and the note appears headed "DRAFT — not sent". | "The agent investigated, our checker measured, you approved. Nothing leaves this laptop." |

  The closing 10 seconds show the judge's own clip result, or its measured stage time stated honestly ("this takes about N minutes; here is the run from 09:40"). The ADA rows, the report and the benchmark table stay in the drawer for Q&A.
- [ ] **Step 3:** Prepare one Q&A sentence per likely lens:
  - **Invented doors:** every element has a timestamp, a human accepts the graph, footsteps catch missed doors, and precision and recall are reported against tape-measured keys.
  - **Who pays:** the venue operator, at every layout change; today the walk is visual with no record. Don't quote market sizes.
  - **Does it work in a home:** the home benchmark row.
- [ ] **Step 4:** Rehearse three times and record each stage's measured time. Set the narration hints from the measured times, never from a fixed timer.
- [ ] **Step 5:** Record the one-minute submission video showing only features built at the event. Check that the repo is public, the demo link works and all members are on the submission.
- [ ] **Step 6:** Commit: `docs: demo runbook and measured results`.

---

## Stretch (only if ahead by mid-afternoon)

- **Splat "X-ray" overlay** on the saved run only: Brush (Apache-2.0) trains on the COLMAP output, and Spark (MIT) renders the splat with the graph inside. Spark needs three.js r180 or later, so the lockfile owner must bump `three@0.170.0` first.
- **Metric-depth scale badge:** the median ratio of MoGe-2 (MIT) or DA3METRIC-LARGE (Apache-2.0) depth to SfM depth, next to the eye-height badge.
- **SfM fallback for blank walls:** MapAnything-apache weights. Mac speed is unmeasured.
- **Independent egress cross-check:** JuPedSim (LGPL-3.0, pip dependency) on the same geometry, labelled "independent model".

## Risks and fallbacks

| Risk | Fallback |
|---|---|
| Extraction, chained critique and the agent are all untimed, and agentic video can raise time to first token | Judge clips of one room (about 40 s). Show the saved live run with its timestamp. Run local SfM first. Precompute investigations on accept. |
| The benchmark comes out flat (Google favours static for clips under 5 minutes) | Report it flat. The geometry loop's improvement is a separate measured claim. Lead with `static_hifps` if it wins. |
| `uri` video input or a repeated URI isn't accepted | Inline base64 for clips under 20 MB; skip zoom parts. |
| SfM fails on blank walls or glass | Geometry shows "unavailable"; the loop runs on model-reported counts; try MapAnything-apache. |
| The environment can't be reused with the network disabled, or saved agents refuse Argon | Run with an allowlist and inline config, and say so in the README. |
| The phone can't reach the laptop on venue Wi-Fi (client isolation) | Personal hotspot, or AirDrop/USB then upload. |
| Headless WebGL fails | SwiftShader flags; otherwise render in a visible Chromium window. |
| Monocular scale is too coarse for ADA thresholds (about 16% error for metric models) | Tape-measured anchor door; widths as ranges; cannot measure when a range straddles a threshold. |
| Argon invents doors | Evidence timestamps, human review before accept, the geometry score, and benchmark precision shown honestly. |
| Credits or rate limits | Probe early, cache receipts, and cap precomputed investigations at 3. |
| Pitch claims nobody has verified (for example LVBench 91.7%) | Recheck on the launch blog before saying it; don't present Flash-model efficiency figures as Argon's. |
