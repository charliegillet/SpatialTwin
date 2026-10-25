# Winning-project feature research — 24 October 2026

This is product research, not a claim that SpatialTwin has won an award. Five patterns below come from organizer winners announcements. Two have explicit named award categories; three are highlighted in Google's winners article without recoverable placement/category details. Proposed adaptations are our design inferences, not features claimed by those projects. No application, provider, browser or device calls were made for this research.

## Evidence standard and historical-source correction

The repository's [tool/source register](../plans/TOOL_SELECTION_AND_SOURCES.md) identifies `nihalnihalani/winners/spatialtwin_argon_winner` as historical source material. That folder name proves no award. Its [historical patterns document at the recorded commit](https://github.com/nihalnihalani/winners/blob/9fd96f7bfa93d82ce9fa6eac84cffc1e62829745/spatialtwin_argon_winner/01_historical_patterns_and_judges_debate.md) claims project placements and assigns SpatialTwin a 92% win probability. It does not establish an empirical probability or organizer confirmation. Those figures should not inform product claims or judging forecasts.

For award status, an organizer announcement outweighs a project README. A submission page is primary evidence of what the team presented, not independent proof that the implementation works. Gallery ordering, finalist status and cash-prize descriptions do not establish a project's prize placement.

## Five relevant examples

| Project | Award evidence and precise limit | Feature evidence | Scoped SpatialTwin adaptation |
|---|---|---|---|
| **OutDraw** | Named in Google's 21 November 2024 Gemini API Developer Competition winners announcement. The retrieved article does not identify its exact prize category or rank. | Google describes a human-versus-AI party game. [Official announcement](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-developer-competition-winners/) | Ask the judge to predict which blockage benefits most from P3 before running checked comparisons. Reveal all four cases, including zero gain, rather than stage a guaranteed success. |
| **everies** | Named in the same organizer winners announcement; exact category/rank not recovered. | Google describes bringing the surrounding world to life with AR. [Official announcement](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-developer-competition-winners/) | Keep canonical target identity consistent across the held image, selected plan target and model highlight. A clear evidence overlay is useful without adding an AR stack. |
| **Jayu** | Named in the same organizer winners announcement; exact category/rank not recovered. | Google describes an assistant spanning the computer screen. [Official announcement](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-developer-competition-winners/) | Provide short contextual questions such as “Why did this target reduce crossings?” Answer from saved checked ledger data, with source/run IDs and a stale-state guard. A generic autonomous desktop assistant is outside scope. |
| **G.R.O.W. / Team I.O.** | Explicit **Local Impact Award**, 2024 NASA Space Apps; announced 16 January 2025. | NASA identifies the wildfire project and its focus on translating complex GIS information into accessible communication. [NASA winners announcement](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-international-space-apps-challenge-announces-2024-global-winners/) | Pair each canonical blockage with a plain-language explanation of the finite-capacity consequence. Keep evidence, assumptions and the resulting model change visible together. Do not import wildfire data or imply validated hazard forecasting. |
| **Connected Earth Museum** | Explicit **Art & Technology Award**, 2024 NASA Space Apps, in the same NASA announcement. | NASA describes an AI host, connected 2D/3D displays and environmental time series. [NASA winners announcement](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-international-space-apps-challenge-announces-2024-global-winners/) | Offer a synchronized read-only timeline of a saved checked schedule: current time, completed crossings, people still in zones/transit, and corresponding model state. Every frame must conserve all 120 synthetic occupants. |

The first three are evidence of organizer-highlighted competition winners, not proof of a specific award tier. Google's original [competition gallery URL](https://ai.google.dev/competition) redirected to current AI Studio content during this check, so it could not independently recover category details.

## Spatial/physical example checked but not promoted to a verified prize winner

[Sky Guardian's organizer-hosted submission](https://cerebralvalley.ai/e/google-io-hackathon/hackathon/gallery/113) describes aerial mapping of survivors/hazards and a second drone for close inspection. It gives a useful **overview → selected subject → close inspection** pattern. For SpatialTwin, a safe adaptation is selecting P1/P2/B2 in the model and inspecting the matching held capture/evidence, with human approval required for any mutation.

The [Google I/O event page](https://cerebralvalley.ai/e/google-io-hackathon) confirms Cerebral Valley/Google DeepMind hosting and prize categories. The [gallery](https://cerebralvalley.ai/e/google-io-hackathon/hackathon/gallery) shows 152 projects and six finalists. Neither retrieved page, nor the Sky Guardian submission, establishes the historical document's claimed second place. AgentGym's claimed third place/managed-agent prize was likewise not corroborated here. These remain unverified placement claims. A drone control or Gemini Live capability claim from another model/project does not establish support in SpatialTwin's direct Argon or managed adapter.

## Recommended order for this board

1. **A checked challenge table with an optional judge prediction.** Run four independent hypothetical presets: baseline, P1 blocked, P2 blocked and B2 blocked. Compare KEEP_CURRENT and OPEN_P3 using identical population, horizon and timestep. Label reported reserve state versus an explicitly closed-reserve benchmark. This adds an honest, inspectable interaction to the existing demo without a new cloud call or physical command.
2. **A concise explanation tied to checked results.** State which passage or receiving boundary limits the case, the completed/remaining totals and the P3 delta. Do not infer survival, free capacity or a new exit from a nice-looking path.
3. **Saved-schedule inspection.** Add the timeline only when the data contract exposes checked zone/transit occupancy and boundary crossings at each timestep. Do not animate decorative dots as measured people. A paused/recorded schedule remains a prediction or replay, never fresh physical observation.
4. **Evidence anchoring as polish.** Reuse existing capture, target highlight, provenance and context machinery. Avoid building an unrelated AR subsystem.

The current UI already has explicit sources, reviewed target changes, checked comparison, local/live receipts and a model selector. A new feature must deepen the judge's understanding or stress a real invariant; renaming the existing guide as an “AI tour” adds little. The four-case table should be a separately labeled hypothetical workspace and must not silently change authoritative board state.

Acceptance for the challenge table: four distinct required case IDs; complete checked pairs; equal synthetic population/horizon/timestep; only the declared reserve delta; current full RunContext; incomplete/corrupt cases displayed unavailable; no winner from missing data; clear ties; no automatic provider request, local scenario mutation or physical approval.

## Retrieval record

Firecrawl CLI 1.23.3, four searches and six distinct targeted pages. One concurrent Firecrawl operation was used by this workstream. Search feedback was submitted for all four searches while results were fresh. No installs or app-code edits were made in this research pass.

| Cache under ignored `.firecrawl/` | Source/result |
|---|---|
| `winner-features-search-gemini.json` | Search ID `01a16c50-ca4a-72df-8311-94bc7bde7149`; official Google winners announcement discovered |
| `winner-features-search-spatial.json` | Search ID `01a16c51-820a-7679-a298-b79fdfd86ae6`; organizer I/O gallery discovered |
| `winner-features-search-placement.json` | Search ID `01a16c52-4849-70f3-a974-6de0525cbedb`; no independent placement confirmation |
| `winner-features-search-disaster.json` | Search ID `01a16c52-d909-718e-baa0-4a38fb12f9c5`; NASA winners announcement discovered |
| `winner-features-google-competition.md` | Redirected/current AI Studio content; not used as award proof |
| `winner-features-google-announcement.md` | Google announcement, published 21 November 2024 |
| `winner-features-google-io-gallery.md` | Organizer gallery; finalist count, not verified placements |
| `winner-features-google-io-event.md` | Organizer identity and available prize categories |
| `winner-features-sky-guardian.md` | Team-authored feature description hosted by organizer |
| `winner-features-nasa-announcement.md` | NASA explicit award categories and feature descriptions, published 16 January 2025 |

This bounded search does not establish a universal “winning formula.” It supports a few product patterns, with award and implementation-evidence limits kept visible.
