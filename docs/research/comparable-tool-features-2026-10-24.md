# Comparable tools → SpatialTwin features

Research date: 24 October 2026. This records the pre-implementation inspection; the resulting implementation and fixes are documented in feature-additions-2026-10-24.md. Four Firecrawl CLI searches (one returned no results) and eight targeted primary pages. No app files, installs, provider/device calls or browser actions during this research.

## Three features worth implementing now

### 1. Computed schedule explorer

Primary evidence:
- Pathfinder measurement regions: https://www.thunderheadeng.com/docs/2026-1/pathfinder/output/measurement-regions/
- MassMotion: https://www.oasys-software.com/products/pedestrian-simulation-software/massmotion/
- Bentley LEGION: https://www.bentley.com/software/legion/ (redirects to current products/legion page)

Pathfinder documents per-time-step region count/density/speed and time-history graphs. MassMotion presents tables, heatmaps and graphs for examining congestion and iterative scenarios. LEGION combines overview heatmaps with more specific line graphs, histograms, cumulative values and raw data.

SpatialTwin adaptation: a single synchronized time cursor over an actual checked run; plot cumulative modeled crossings and remaining population, plus B1/B2 breakdown. Label selected time, horizon, source run and synthetic population. Use playback as optional aggregate model playback; scrubbing must not mutate the accepted scenario or hardware. If the parent supplies a same-context predicted OPEN_P3 result with equal population/horizon/step, overlay that real series on the same time axis. A synchronized shared cursor prevents misleading before/after differences caused by different playheads.

Data guard: validate finite ordered time, cumulative monotonic counts, bounds, B1+B2 totals, final envelope agreement and equal comparison assumptions. The currently inspected frontend TimelineStep does not contain transit counts or decomposed occupant paths. Do not animate people, claim real crowd trajectories, infer density per square meter or make complete occupancy claims from wait-state counts. Remaining=N-cumulative crossings is a truthful aggregate ledger if the series is valid. Invalid/missing timelines get a clear unavailable state, not invented frames or interpolation. The old PlanView2D has hardcoded fallback horizon40/20steps; do not reactivate that fallback for a new computed explorer.

### 2. Read-only scenario lab

Primary evidence:
- Pathfinder capabilities: https://www.thunderheadeng.com/pathfinder/capabilities/
- AnyLogic Compare Runs: https://www.anylogic.com/resources/educational-videos/how-to-video-compare-runs-experiment/
- AnyLogic Pedestrian Library: https://www.anylogic.com/features/libraries/pedestrian-library/

Pathfinder supports keeping variants in a single project and switching between their results. AnyLogic's Compare Runs experiment lets a user enter parameters, run cases and compare chart outputs. Its Pedestrian Library describes layout/queue/evacuation what-if studies with 2D/3D output.

SpatialTwin adaptation: show a small declared matrix of baseline and supported hypothetical closure cases, with checked KEEP_CURRENT and OPEN_P3 counts and residuals. Restrict cases to portal:P1, portal:P2 and boundary:B2; keep P3 as an internal connection to existing B2. Label every case as a hypothetical snapshot, share the same initial population and horizon, and show no-benefit cases normally. One explicit Evaluate action can populate the matrix; selecting a row inspects it only. A separate Preview/Apply flow is needed to turn a lab choice into an accepted local command, and physical approval stays separate.

Guard: lab evaluation must use immutable snapshots and preserve source geometry/physical/parameter/solver context. Never reuse a case under later revisions. This is a comparison of allowed inputs, not new geometry editing, finite-rate calibration, Monte Carlo probability or automatic evacuation advice.

### 3. Portable human-readable run brief

Primary evidence:
- Pathfinder visualization/report capabilities: https://www.thunderheadeng.com/pathfinder/capabilities/
- Pathfinder exporting data: https://www.thunderheadeng.com/docs/2026-1/results/exporting-data/

Pathfinder documents plots/screenshots/report assets plus CSV/TSV export of chosen time-series data, selected occupants and time ranges. These are useful communication patterns; SpatialTwin does not have individual-occupant trajectories to export.

SpatialTwin adaptation: printable HTML brief or saved report containing accepted changes, illustration/source scope, current checked totals, the two real alternatives, population/horizon, assumptions, checker findings, run/context IDs, actual AI/tool evidence and reported physical state. Pair it with the existing complete JSON evidence export and optionally a properly labeled schedule CSV. A concise report is useful for judges who cannot inspect a JSON blob.

Guard: export an immutable snapshot captured when requested; label historical/stale evidence, prediction versus observed result, live/fixture/local/replay and simulator versus physical. The print/export operation must not call a provider, rerun a solve or move hardware. Keep credentials and raw hidden traces out of the output.

## Existing frontend features, so avoid duplicates

- Main App already has manual target review/apply and an accepted checked result.
- InvestigationPanel already compares actual KEEP_CURRENT and OPEN_P3 candidates.
- WorkspaceDetails already has source/receipt evidence and JSON download.
- SpatialViewport already switches stable plan/cutaway and supports canonical target selection.
- Old PlanView2D has a timeline but is not the main spatial viewport; it has fallback data that should not be reused.

These findings favor extending explanation and reproducibility rather than adding another visual dashboard or a new UI framework.

## Additional reference: indoor digital twin organization

Esri ArcGIS Indoors: https://www.esri.com/en-us/arcgis/products/arcgis-indoors/overview

Its floor-aware 2D/3D maps unify spaces, assets and source facility data; this reinforces canonical IDs and a shared spatial source. Its real indoor positioning, turn-by-turn navigation and emergency mapping are broader capabilities; do not imply SpatialTwin currently has those. A current three-target tabletop does not need floor pickers, BIM import, people tracking or asset-management features just because a mature vendor has them.

## Cached primary pages

- feature-research-pathfinder-capabilities.md
- feature-research-pathfinder-regions.md
- feature-research-pathfinder-export.md
- feature-research-massmotion.md
- feature-research-anylogic-library.md
- feature-research-anylogic-compare.md
- feature-research-legion.md
- feature-research-arcgis-indoors.md

Search metadata feedback was submitted promptly for all three nonempty searches via CLI --silent (exit0; server acceptance/refunds not confirmed). The combined-domain search returned no results, so no feedback was sent for it. No credit/daily-limit exhaustion occurred.

