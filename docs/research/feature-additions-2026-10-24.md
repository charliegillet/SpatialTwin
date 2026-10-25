# Research-backed feature additions — 24 October 2026

Three additions now extend the existing Observe → Review → Compare → Confirm workflow. Research used Firecrawl across comparable planning tools and organizer announcements for previous competition winners. These are adaptations to this project's small illustrative model, not claims of equivalent simulation capability or likely prizes.

## What was added

| Feature | Inspiration | SpatialTwin implementation |
| --- | --- | --- |
| Computed schedule explorer | [Pathfinder time histories](https://www.thunderheadeng.com/docs/2026-1/pathfinder/output/measurement-regions/), [MassMotion graphs and scenario analysis](https://www.oasys-software.com/products/pedestrian-simulation-software/massmotion/), NASA's [Connected Earth Museum](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-international-space-apps-challenge-announces-2024-global-winners/) | One stored-frame time cursor, step curve, keyboard scrubber, explicit play/pause, B1/B2 totals, all four holding zones, in-transfer population and a complete frame table. **Inspect plan** opens it. |
| Read-only scenario lab and judge prediction | [Pathfinder variants](https://www.thunderheadeng.com/pathfinder/capabilities/), [AnyLogic Compare Runs](https://www.anylogic.com/resources/educational-videos/how-to-video-compare-runs-experiment/), the human-versus-AI interaction in Google's [OutDraw winner announcement](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-developer-competition-winners/) | **Scenarios** opens four independent presets: baseline, P1 blocked, P2 blocked and B2 blocked. Optionally predict the largest benefit, then compute both KEEP_CURRENT and OPEN_P3 in every case. All eight solves share population, horizon, timestep and source context. |
| Portable scenario brief | [Pathfinder reports and export](https://www.thunderheadeng.com/pathfinder/capabilities/) and NASA's [G.R.O.W. communication pattern](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-international-space-apps-challenge-announces-2024-global-winners/) | **Evidence → Prepare printable brief → Download HTML** prepares a self-contained HTML snapshot with an inline preview and an explicit download link. It carries checked counts, accepted blockages, source labels, current/historical status, recorded comparison, assumptions, checker findings, context/run IDs and a supported held JPEG. Print locally with the browser. |

The adaptations in the table are design inferences from those sources. The existing app already had reviewed image grounding, a single AI comparison, plan/cutaway selection, receipts and JSON export; these additions extend those capabilities.

## Numerical and state guarantees

The schedule inspection found a real defect: intermediate zone counts used only waiting arcs and omitted departing or travelling occupants. The extraction now samples **after arrivals and boundary service, before departures**, with explicit in-transfer occupancy. At every stored frame:

`holding in EVENT + WEST + EAST + RESERVE + in transfer + completed crossings = initial population`

A separate checker enumerates allowed model edges, checks throughput and node conservation, and reconstructs the timeline using arrival/departure events. It compares that independent reconstruction with the exported frames. Tests include deliberately lost people, balanced but invented locations, unavailable edges, excessive throughput, invalid time grids, delayed travel, boundary-rate violations and terminal disagreement. The UI requires the named timeline checks, including `timeline_matches_flow`, before exposing playback; old or inconsistent schedules get an unavailable state.

Solver identity is now `spatialtwin-flow-v1.1`. Candidate hashes include the timestep and each computation receives a distinct run ID. Assumption text uses the model's actual boundary rates, 1.5 people/s each, instead of the old hardcoded 2. New process epochs and solver versions keep old evidence from becoming current after a reload.

The lab accepts only a current full context and one of two declared reserve bases:

- **Reported P3:** use OPEN/CLOSED from the current snapshot; reject uncertain reported states. If P3 is already open, opening it again yields no new gain.
- **Closed reserve benchmark:** explicitly assume P3 starts closed in each preview, regardless of reported position. This is a hypothesis, not a physical state claim.

Each case replaces the accepted blockages only inside its numerical input. The service performs exactly eight bounded local solves, rechecks context during and after calculation, and leaves accepted state, SQLite runs, physical commands and Gemini untouched. Invalid or unequal candidates withhold gain. Lab predictions never enter the movement-approval ledger. The legacy matrix route now delegates to the same checker-backed service and labels its closed-reserve benchmark explicitly.

With the closed reserve basis, the modeled results remain:

| Case | KEEP_CURRENT | OPEN_P3 | Gain |
| --- | ---: | ---: | ---: |
| Baseline | 120 | 120 | 0 |
| P1 blocked | 60 | 60 | 0 |
| P2 blocked | 60 | 117 | +57 |
| B2 blocked | 60 | 60 | 0 |

All totals concern 120 synthetic occupants over 40 seconds. Remaining occupants are preserved. P3 feeds the existing finite-rate B2 boundary and creates no exit or additional receiving capacity.

## Brief guarantees

The export is produced synchronously from the displayed evidence snapshot. Text is HTML-escaped; only a bounded JPEG data URI can be embedded. There are no scripts, external assets or automatic network requests. A restrictive content security policy accompanies the file. Lost connection, context drift, a rejected checker or uncertain gate state prevents a current-result label. Earlier valid results may appear as historical evidence. Hardware boot/epoch information is labeled **telemetry**, since it can exist during transit or fault and does not by itself prove an endpoint.

The brief complements the full JSON export. It does not rerun a solve, call Gemini, apply a closure or authorize a gate command. Lab previews are session-local hypotheses, separate from the accepted scenario and recorded AI investigation in the brief.

## Verification and limits

Verification passed: **245 backend tests, 49 frontend tests, production compilation and `git diff --check`**. The backend suite retains one existing Starlette/httpx TestClient deprecation warning. Exact evidence is recorded in `runtime/feature-upgrade/verification.json`. Browser review covers both reserve bases, honest +0 cases, prediction feedback, keyboard scrubbing, full frame table and stale-result hiding. The final build had zero axe violations, zero horizontal overflow and zero measured text-clipping warnings at 320/390/768/1440px. Desktop and 320px scenario-lab layouts were also inspected visually. Local runtime evidence and screenshots are intentionally ignored by Git.

The prepared brief was rendered in the inline preview and downloaded from the explicit **Download HTML** link using the browser's supported link-download API. The saved HTML was checked against the current run and copied to `runtime/feature-upgrade/scenario-brief.html`. Automatic download-event confirmation was unavailable in the embedded browser; the explicit link download succeeded. The file is also available at `~/Downloads/spatialtwin-scenario-brief-r1.html`.

The software reload starts a fresh simulator session with P3 closed; the existing Gemini server configuration is retained. No new Gemini inference or physical movement is part of these feature checks. Real-board capture accuracy, metric venue geometry and hardware bench verification remain separate. Aggregate numerical frames are not individual trajectories, density measurements, hazard forecasts or observed people. Automated accessibility results retain manual contrast checks over the architectural diagram/image layers.

## Research record

The broader [comparable-tool assessment](comparable-tool-features-2026-10-24.md) covers Pathfinder, MassMotion, AnyLogic, LEGION and ArcGIS Indoors. The [winning-project source review](winner-feature-sources-2026-10-24.md) distinguishes verified organizer announcements from unverified prize-placement claims. In particular, a repository folder named `winners` and earlier win-probability estimates are not award evidence. No probability of winning is asserted here.

The Firecrawl cache is under `.firecrawl/feature-research-*` and `.firecrawl/winner-features-*`. Research did not justify adding an unrelated AR stack, people tracking, a new AI agent framework, arbitrary floor-plan editing or automatic actuation.
