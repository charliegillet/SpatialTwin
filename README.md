# WalkTwin

Phone walkthrough video to Gemini 4 Argon venue graph to 3D twin to egress check.

## Built at the Gemini 4 Argon SF Hackathon (25 Oct 2026)

Everything in this repo.

## Prior work, not presented

Before the event the team built a hardware tabletop prototype (SpatialTwin). No code, data or assets from it are in this repo.

## Limits

WalkTwin shows these as "cannot measure" and turns them into a hand-check to-do list:

- survival, and approved or code-official egress capacity
- IBC/NFPA occupant load
- doorway depth, which decides whether a door needs 32 in or 36 in
- turning space reduced by furniture
- door hardware and opening force, thresholds, ramp slopes, signage, fire separation
- crowd density effects, and people moving during the event
- any area not filmed

## Where this lives

Branch `charlie` of `charliegillet/SpatialTwin`, a history that starts at the event.

## Headless twin render (Task 10)

`walktwin.render.render_views(graph, out_dir, base_url, hazards=())` drives Playwright Chromium against
`<base_url>/render.html` (serve `frontend/dist`; build with `npm ci && npm run build` in `frontend/`).
Headless WebGL works on macOS with `--use-angle=swiftshader --enable-unsafe-swiftshader`. Run it with
`pytest -m browser`.
Note: a plain `pytest` run includes the browser tests (use `-m 'not browser'` to skip them); they need Chromium (`playwright install chromium`) and build `frontend/dist` if missing.

## Measured results

live: pending key. No benchmark has been run yet; numbers will be pasted here only from `runtime/bench/<venue>.json` produced by `python -m walktwin.benchmark run`.
