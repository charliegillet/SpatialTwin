# Winner analysis and implemented review features — 24 October 2026

This document answers two questions: why the hackathon winners collected in the local `winners` repository won, and which of their capabilities SpatialTwin lacked. It then records the two features built in response, their tests and the shared-file wiring requested from the Codex owner.

It is product research, not a forecast. Nothing here estimates SpatialTwin's chance of winning. The companion [winner source review](winner-feature-sources-2026-10-24.md) remains the record of organizer-verified award evidence; this document works from the collected gallery dataset and inherits its limits.

## Summary

- The four JSON files contain **355 real winner records across 63 events** after deduplication, not "134+" and "96" as the historical `01_historical_patterns_and_judges_debate.md` states. The Nebius file is a superset of the other three.
- The 01 document's central claim, that life-safety projects win "almost every single time" at Google/DeepMind events, is **not supported**. Of 17 first places at Google-branded events, one is a safety project (blartclaw) and one is outbreak-framed (Billie Gene). Creative and media projects took 7. The claim holds only for two 2026 agent-focused Google events: I/O, where four of six placements were crisis or safety framed, and Zero to Agent SF.
- The stronger signal is **physical-world projects that end in a measured verdict**. Since May 2026 the physical-world cluster holds 9 of 18 first places. Since September, verified engineering-artifact agents (Etch, MongoMation, Ripple, CAD Sandboxes) hold 4 of 7.
- SpatialTwin already has the physical loop, live perception, human approval and an independent numerical checker. Its gaps were a **requirement-level verification report with explicit "cannot measure" items** and **independent per-zone watchers with an orchestrated, local-only escalation**. Both are now implemented as local, deterministic, checker-derived features with no new provider calls. They are not yet mounted in the shared app shell; the exact wiring is below.

## 1. Data, deduplication and method

| Source file (in `/Users/nihalnihalani/winners`) | Events | Records | Relationship |
|---|---:|---:|---|
| `gemini_and_managed_agents/data/gemini_hackathons_winners.json` | 13 | 78 | All 13 events also in the Nebius file |
| `gemini_and_managed_agents/data/managed_agents_winners.json` | 10 | 55 | All 10 events also in the Nebius file |
| `data/cerebral_valley_sf_2026_all_winners.json` | 25 | 131 | All 25 events in the Nebius file; 130 records match. The remaining record is a placeholder named "my test team" |
| `nebius_winning_plan/data/cerebral_valley_all_winners.json` | 64 (1 empty) | 355 | Superset. Scraped 18 and 21 October 2026 from gallery ld+json award data |
| **Union, deduplicated by gallery URL** | **63 with real winners** | **355 real** | Date range 9 August 2025 – 17 October 2026 |

Three of the 355 records are entries in "The Rejection Challenge", an outreach challenge rather than a software build. Archetype shares below use the remaining **352 project winners across 62 hackathons**: 57 first places, 114 second or third places, and 181 finalists, fourth/fifth places and People's Choice awards.

**Method.** I read every description and assigned one primary archetype per project by hand. Cross-cutting traits such as multi-agent use and verification language were tagged by keyword over the full descriptions. Those trait counts are lower bounds, because many gallery descriptions are truncated.

**Limits.**

- **Survivorship.** The dataset contains winners only. The I/O gallery alone listed 152 projects, according to the companion review. A trait common among winners may be equally common among non-winners, so nothing here establishes cause.
- **Small samples.** There are 57 first places overall, 17 at Google-branded events and 6 placements at I/O.
- **Weak evidence.** Descriptions are team-written. Placements come from gallery structured data, and prize amounts are absent. Primary archetypes reflect one coder's judgment.

## 2. Discrepancies with the historical 01 document

| 01 document claim | What the data shows |
|---|---|
| "25 SF hackathons (134+ awarded projects)" | 25 events, 131 records, of which 130 are real; one is a "my test team" placeholder |
| "96 Google/DeepMind winning projects worldwide" | 96 = 78 (13 Gemini events) + 18 (3 Zero to Agent events). Adding Google DeepMind Bangalore (6) gives **102 across 17 Google-branded events**. Nano Banana Hackathon (10) is Gemini-model themed, but its sponsor is not recorded in the data |
| Life-safety wins "almost every single time" at Google events | 9 of 102 Google-event winners have the safety archetype as primary; 1 of 17 Google first places (blartclaw). Creative/media: 33 of 102 and 7 of 17 first places |
| Billie Gene "1st Place ($7,500)", Sky Guardian "2nd Place ($5,000)" | Placements match the JSON. **No prize amount appears in any JSON or CSV file.** $7,500 and $5,000 appear only in `gemini_4_argon_hackathon/README.md` as the *upcoming Argon* hackathon's prize table. Unverified |
| AgentGym "Winner $5K Managed Agents + 3rd, Google I/O" | JSON records **3rd Place** only. The managed-agents track win is asserted in `google_global_agent_hackathons.md` but is not in the award data |
| Kavach "1st, on-device security & safety agent" | The record named Kavach links `harshagw/kahani` and describes Kahani, a browser adventure game. The source data is internally inconsistent; the 01 characterization is unsupported |
| Sim Francisco "simulating city-wide population routing" | The description is a Census-seeded synthetic population for polling and forecasts, backtested against real results (for example 81.3% predicted vs 83.8% actual). It does no routing |
| "92% win probability" for SpatialTwin | Not empirical; the companion review already rejects it |

Other placements named in the 01 document match the JSON, including Etch, MongoMation, SplatForge, Tekton, Gallatin/CANOPY and blartclaw.

**Sky Guardian.** Its placement is supported only by the dataset's ld+json scrape. A live fetch of its organizer gallery page during this work (Firecrawl cache dated 24 October) showed no visible placement text, which agrees with the companion review.

## 3. Archetypes

| Primary archetype | All (n=352) | 1st | 2nd–3rd | Other | 1st-place rate |
|---|---:|---:|---:|---:|---:|
| Creative, media, games & sports media | 59 (17%) | 10 | 13 | 36 | 17% |
| Business / vertical workflow & commerce | 55 (16%) | 11 | 16 | 28 | 20% |
| Developer tools & software security | 55 (16%) | 8 | 21 | 26 | 15% |
| Personal assistant, voice & computer use | 34 (10%) | 3 | 10 | 21 | 9% |
| Agent infrastructure (gyms, evals, harnesses, memory) | 33 (9%) | 5 | 13 | 15 | 15% |
| Health & life science | 28 (8%) | 4 | 6 | 18 | 14% |
| Education, accessibility & civic | 23 (7%) | 2 | 11 | 10 | 9% |
| Physical-world safety, crisis & security | 16 (5%) | 3 | 6 | 7 | 19% |
| Verified engineering artifacts (CAD/PCB/PLC/embedded) | 15 (4%) | 5 | 4 | 6 | 33% |
| 3D, spatial, world model & digital twin | 15 (4%) | 1 | 6 | 8 | 7% |
| Robotics, drones & embodied lab | 13 (4%) | 2 | 7 | 4 | 15% |
| Space / plan compliance audit | 6 (2%) | 3 | 1 | 2 | 50% |

The base first-place rate among all winners is 16% (57/352).

**Physical-world cluster.** This groups safety, audit, robotics, engineering artifacts and 3D/twin projects.

| Window | Share of all winners | Share of first places |
|---|---:|---:|
| Whole dataset | 65 of 352 (18%) | 14 of 57 (25%) |
| Before May 2026 | 13% | 5 of 39 (13%) |
| May 2026 onward | 35 of 114 (31%) | 9 of 18 (50%) |

**Cross-cutting traits.** These keyword lower bounds are at most weakly tier-dependent. Multi-agent language appears in 14% of first places against 8% of finalists. 3D/spatial language appears in 16% against 10%. Verification language is flat at about 22% across tiers.

## 4. The Google/DeepMind-specific pattern

The 17 Google-branded events (102 winners) do not share one pattern:

- **The 2025–26 Gemini world tour** (12 events: TED AI, Gemini 3 SF/London/Bengaluru/Tokyo/Seoul/NYC/Singapore/Paris, Vibe Code SF/London, SuperHack). It rewarded **multimodal consumer and creative apps**: games, comics, sports overlays, try-on. 7 of its 12 first places are creative or consumer commerce. Live camera and video perception appears in 17% of Google-event winners against 11% overall.
- **Two 2026 Google events with the safety pattern** (Zero to Agent SF and I/O). These rewarded **high-stakes physical-world problems with visible multi-agent orchestration**:
  - blartclaw took 1st at Zero to Agent SF with watcher subagents per livestream reporting to an orchestrator.
  - At I/O, Billie Gene (outbreak vaccine design, 1st), Sky Guardian (drone search and rescue, 2nd), Gemini Lifeguard Rescue (three-drone mission commander) and Autonomous Infrastructure Auditor (district orchestrator plus three concurrent specialist agents) were four of six placements.
- **Other 2026 Google agent events did not follow it.** Zero to Agent NYC and London gave first place to business tools (a development-site evaluator and Jargon AI). DeepMind Bangalore's first-place record describes a browser game (see the Kavach discrepancy above).

I/O and Zero to Agent SF are the closest precedents for an Argon/managed-agents judging room, but they are 12 placements across two events and do not generalize to "Google always rewards safety".

## 5. Winning mechanics by archetype

| Archetype and examples | What judges could see | Multi-agent structure | Physical / actuated | Verifiable / quantified |
|---|---|---|---|---|
| **Safety & crisis**: blartclaw, Sky Guardian, Lifeguard, EvacuTrace, Krashless, AWW | Live feeds turning into a map or command UI; real drones flying (Mavic + Tello; three drones); a laser marking targets | Per-stream watcher subagents → orchestrator deciding escalation (blartclaw); mission commander assigning patrol/inspect/rescue roles (Lifeguard) | Drones, laser, radios | Usually weak. AWW shows its reasoning, crosses out exclusions and *waits for approval*. Krashless has a review panel where an engineer's rejection yields an adapted alternative |
| **Verified engineering artifacts**: Etch, MongoMation, Ripple, CAD Sandboxes | A real routed board / 3D viewer; a 3D control room with a live plant twin | A team of agents picks parts, writes spec, routes | Real OpenPLC runtime and Factory I/O; generated firmware actually runs | Etch: "requirements become measurable checks… a model only maps each requirement to a check; plain code measures every value… a requirement that can't be measured is reported as 'cannot measure', never guessed." Ripple: 0/4 → 3/4 on held-out specs. MongoMation: changes ship only if they beat a frozen benchmark |
| **Space/plan compliance audit**: HomeReady, CrossBeam, Plan Pass AI, Infrastructure Auditor | A guided walkthrough with LiDAR; blueprints annotated with code citations; 2D/3D compliant redesign | District orchestrator + three specialist agent types concurrently (Auditor); 13 concurrent skills (CrossBeam) | A caregiver walks a real home with a phone (HomeReady) | HomeReady: "the decisive finding is a measurement, not a vibe" (doorway too narrow for the walker); graded against CDC STEADI/HSSAT; "no fabricated risk score"; "every order and escalation is drafted, never auto-sent". Auditor: findings anchored to ADA code sections and measured slope physics |
| **Self-improving robotics & world models**: SplatForge, AGI Factory, LabRat, SPARKLETEAM | A success-rate curve climbing live; a splat twin of the tabletop | Proposer, critic and pilot roles | Real bench arms and a CNC pipette (LabRat) | AGI Factory: held-out score 66.5 → 92.8 and unsafe actions 21 → 0; a change is kept only if unseen runs improve |
| **3D/twin**: Tekton, Sim Francisco | 339 incremental construction states; a city of agents polled live | Thousands of persona agents (Sim Francisco) | — | Tekton: every component traces to a historical source. Sim Francisco: forecasts backtested against real outcomes |

## 6. Why they won: the mechanics that recur

1. **A measured verdict, not model prose.** The model maps intent to checks; deterministic code produces the verdict; unknowns are stated as unknown. This holds for Etch, HomeReady, Ripple, MongoMation, AGI Factory and the Infrastructure Auditor. It is the most consistent feature of recent first places and the best defense against a judge asking "did you fake it?"
2. **Visible specialist fan-out with an aggregator.** Watchers or specialists produce typed findings and an orchestrator reconciles them into one decision: blartclaw, Infrastructure Auditor, Twiage, Lifeguard.
3. **Real-world input or output on the table.** Drones, LiDAR walkthroughs, a PLC runtime, bench arms: the judge can see the world change.
4. **A problem that is legible in seconds and high stakes.** Rescue, falls after discharge, building code, evacuation. This matters most at 2026 Google agent events.
5. **Human authority preserved and shown.** Drafted, never sent (HomeReady); waits for approval (AWW); single review-and-accept (Twiage); a rejection produces an alternative (Krashless).

These are associations among winners, not proven causes. They are consistent with the 01 document's general direction but much narrower than its claims.

## 7. SpatialTwin gap analysis

| Mechanic | SpatialTwin before this work | Gap |
|---|---|---|
| Measured verdict | Independent checker with named checks; printable brief lists checks and assumptions | No requirement-level report pairing each claim with a measured value and threshold; no explicit list of what the model **cannot** measure |
| Specialist fan-out + aggregator | One managed investigator comparing KEEP_CURRENT vs OPEN_P3; solver `bottlenecks` strings | No per-zone/per-element watchers with typed records; no orchestrated escalation state or next step; no durable local escalation record |
| Real-world I/O | Tabletop board, overhead camera, servo gate, microswitches, LEDs | None for software in this run; physical validation remains Nihal/Charlie's |
| Legible high stakes | Evacuation framing with honest scope limits | None |
| Human authority | Apply, operator approval, ACK vs endpoint separation | None |

**Hypotheses tested.**

- *Multi-watcher fan-out*: confirmed as a gap, implemented deterministically.
- *Structured verification report*: confirmed as a gap, implemented.
- *Held-out perception accuracy* (Ripple/AGI-style): also a real gap, but it requires recorded real-board captures. Building it without them would fabricate evidence, so it was not built.

## 8. Implemented features

Both features read the **accepted, checker-approved run** plus reported state. They never call the solver, Gemini or the hardware bridge, and they never mutate scenario state; tests enforce this by patching `FlowPlanner.solve` to fail. Every numeric value is re-read from the checked envelope and the reviewed venue spec. Neither feature predicts the benefit of an alternative; that remains the comparison's job.

### 8.1 Zone watch with local escalation (blartclaw / Lifeguard / Infrastructure Auditor pattern)

`backend/app/review/watch.py` runs nine independent watchers over the same immutable frames:

- 4 zones;
- the blockable passages P1 and P2;
- boundaries B1 and B2;
- the P3 reserve gate.

Each emits typed records (`RESIDUAL_HOLDING`, `CAPACITY_PRESSURE`, `PASSAGE_UNAVAILABLE`, `BOUNDARY_UNAVAILABLE`, `BOUNDARY_AT_QUOTA`, `BOUNDARY_IDLE`, `RESERVE_OBSERVED`, `RESERVE_UNCONFIRMED`, `TELEMETRY_MISSING`, `SIMULATED_ENDPOINT`, `NOMINAL`). Records carry a severity, value, limit, time and evidence pointers (`run_id` plus field path, venue spec or reported state).

The orchestrator derives `nominal | advisory | escalated` and a next workflow step:

- `await_endpoint` if P3 is not observed OPEN/CLOSED;
- `compare_alternatives` if escalated with people held and P3 observed closed;
- `no_allowed_alternative` if P3 is already open;
- otherwise `none`.

`backend/app/review/escalations.py` stores one idempotent **local** record per escalated context and run, in its own SQLite table. Every watch and record states: *"Local simulated escalation record. No message, notification, authority dispatch or device command was sent."*

These watchers are deterministic code. They are not AI agents, and nothing claims otherwise.

Real outputs on the illustrative board:

| State | Escalation | Key records | Next step |
|---|---|---|---|
| Startup, P3 UNKNOWN | escalated | P3 reserve unconfirmed | await_endpoint |
| Baseline, P3 CLOSED | nominal | B1/B2 at 60/60 quota (info: everyone completed) | none |
| P2 blocked | escalated | 60 held in Event Hall at 40s; P2 unavailable; B1 at 60/60 (advisory); B2 available but 0/60 | compare_alternatives |
| P2 blocked, P3 confirmed OPEN | escalated | 3 still held at 40s; B2 57/60 | no_allowed_alternative |
| B2 blocked | escalated | B2 unavailable (0 crossings); 60 held | compare_alternatives (the checked comparison then shows +0) |

### 8.2 Verification report (Etch / HomeReady / Infrastructure Auditor pattern)

`backend/app/review/verification.py` produces about 25 requirements. Each has a statement, a method (`measured`, `checker`, `outside_model`) and a status (`pass`, `fail`, `checker_attested`, `cannot_measure`, `not_run`), plus measured and expected values and evidence pointers.

- **Measured here, independently of solver helpers:**
  - population conservation;
  - per-frame conservation (21/21);
  - residual located in named zones;
  - per-zone peak versus declared capacity;
  - per-boundary quota and per-step rate;
  - blocked-boundary zero flow at every frame;
  - unreachable zones empty, from a reachability pass over the venue spec (for example, with P2 blocked and P3 closed, the east corridor and reserve must hold no one);
  - status consistency, terminal frame and context currentness;
  - observed reserve state.
- **Checker-attested:** flow-witness edge use. This names `schedule_allowed_edges`, `schedule_flow_conservation` and `timeline_matches_flow`, because the witness is only available to the server checker.
- **Comparison:** when a saved investigation id is supplied, the report checks currentness, equal population/horizon/timestep and that the gain equals checked counts. It labels the source *live managed investigation receipt* or *local solver comparison, no Gemini call*. P2 blocked gives +57; B2 blocked gives an honest +0.
- **Always listed as cannot measure:**
  - survival or street evacuation;
  - surveyed venue geometry;
  - measured capacities and rates (they are declared parameters);
  - real-board camera accuracy;
  - physical gate reliability (simulator or single observation);
  - occupant movement during actuation.

The verdict is `verified_within_model` only with zero failures. Tests show that the report re-measures rather than trusting the checker flag: tightening a declared rate or capacity makes quota, step-rate and capacity rows fail.

### 8.3 Route and UI

`backend/app/review/routes.py` exposes `build_review_router(state_manager, hardware_mode)`. It serves `POST /api/scenarios/{scenario_id}/review` with body `{expected_context, investigation_id?}` and fails closed:

- stale context → 409;
- no reviewable checked run → 409 with a fixed code;
- unknown scenario → 404;
- extra or malformed fields → 422.

`frontend/src/features/proposal-evidence/review.ts` validates the payload before anything renders. It hides everything on context drift, a different run, understated severity or escalation, orphan or borrowed records, evidence pointing at another run, a next step inconsistent with the reserve state, miscounted summaries, an optimistic verdict, a report with no cannot-measure items, or an escalation record that is missing, mismatched or not `local_record_only`.

`ReviewPanel.tsx` re-reads each newly accepted run with request-gate and abort guards. It shows:

- the escalation banner;
- nine watcher tiles;
- the verdict with counts and a collapsible requirement table;
- an always-visible "Outside the model" list;
- JSON and self-contained printable HTML export, with no scripts, external resources or links and a restrictive CSP.

A throwaway scratchpad harness rendered the panel with real backend payloads at 1280px and 500px; it showed no horizontal overflow.

## 9. Deliberately not built

- **LLM watcher fan-out.** One Argon call per pad or zone would triple provider calls at the latency-critical capture step. It would add no information the checked run lacks. Its accuracy would also be unverifiable offline, and claiming it without a live trial would break the evidence rule.
- **A new tool for the managed agent.** Changing the managed tool set or system instruction would invalidate the 24 October live smoke evidence for that path.
- **A held-out perception accuracy board.** It needs the 20 recorded real-board captures named in BUILD_PLAN Phase 4; none exist yet.
- **Self-improving loops and authority notification.** Self-improvement is out of scope for a miniature board. Any notification or dispatch is out of scope and forbidden: escalation is a local record only.
- **Wiring in shared files.** Not done, by the ownership rules.

**Observation for Codex.** The existing `frontend/src/features/proposal-evidence/ProposalEvidencePanel.tsx` (924 lines) is not imported by `App.tsx`.

## 10. Requested shared-file wiring (for the Codex owner)

**`backend/app/main.py`.** Add the import with the other app imports:

```python
from backend.app.review.routes import build_review_router
```

Then add the router **before** the `frontend_dist` static mount, because a `Mount("/")` registered first would shadow it:

```python
app.include_router(build_review_router(
    state_manager, lambda: "simulator" if hardware_bridge.is_simulator else "physical_serial"))
```

**`frontend/src/App.tsx`.** Add the import:

```tsx
import { ReviewPanel } from './features/proposal-evidence/ReviewPanel';
```

Then add the panel inside `<div className="workspace-exploration">`, after `<ScenarioLab … />`:

```tsx
<ReviewPanel snapshot={snapshot} isCurrent={planCurrent}
  investigationId={investigationCurrent ? investigation?.investigation_id ?? null : null} />
```

`planCurrent` already requires a connection, a valid current plan and a certain physical state. The panel's own CSS spans the two-column exploration grid.

**Optional.** Add a rail or workflow button that calls `focusSection('zone-watch')`.

No contract, type, API-client, lockfile or dependency change is required. The frontend fetch helper and types live in the feature folder, and the backend models live in `backend/app/review/`.

## 11. Verification record

| Check | Result |
|---|---|
| Backend baseline before changes, `.venv/bin/python -m pytest -q` | 245 passed |
| Backend after changes | **270 passed** (245 existing + 25 new in `tests/review/`); no failures; one pre-existing Starlette deprecation warning |
| Frontend `npm test` before / after | 49 → **57 passed** (8 new in `review.test.mjs`) |
| `npx tsc` (noEmit) | clean |
| `npm run build` | succeeded; `frontend/dist` is gitignored, so no tracked output changed |
| Cross-language contract | Real backend payloads for four states (startup UNKNOWN, baseline, P2 blocked, P2 + P3 open) are all accepted by the TypeScript validator. This was a one-off scratchpad check and is not a committed test |
| Live provider or device | **Not run.** No Gemini, serial or servo action was part of this work |

There were no pre-existing failures in either suite. No tracked file was modified; all changes are new files.

## Appendix: physical-world cluster membership (65)

Names are as recorded in the data. Some are team names: Mike = CrossBeam; mincasurong = GeminiSpace; Aniket = blueprint-to-3D bill of quantities; Alexis Chapellier = Wrench Board.

- **Safety, crisis & security (16):** Safe Home Inventory (1st), ForensightAI (2nd), Clear Witness (F), EvacuTrace (F), Echofold/CARN (F), Krashless (2nd), Sharelock (2nd), blartclaw (1st), AlphaVector (F), Gallatin (1st), CANOPY (2nd), AWW (3rd), TAK Phone (4th), Sky Guardian (2nd), Gemini Lifeguard Rescue (F), RingZero (F).
- **Compliance audit (6):** Accessibilify (3rd), CrossBeam (1st), Please Pass (F), Plan Pass AI (1st), Autonomous Infrastructure Auditor (F), HomeReady (1st).
- **Robotics & embodied (13):** IRRS (3rd), GeminiSpace (1st), RPG (F), Chase Brignac (2nd), RoboStore (3rd), jimmy (F), SplatForge (1st), Soren (F), AstraBot (2nd), LabRat (2nd), Muscle Memory (F), SPARKLETEAM (2nd), AGI Factory (3rd).
- **Engineering artifacts (15):** SAV.ai/NNPort (1st), Dosa (F), Enginuity (2nd), Scopecreep (2nd), Wrench Board (2nd), OmniBridge (F), MaestrIA (F), field-ratchet (F), blueprint-to-3D BoQ (2nd), CAD Sandboxes (1st), Ripple (1st), Da Vinci CAD (F), Made to Fit (F), MongoMation (1st), Etch (1st).
- **3D, spatial & twin (15):** SkyStudio (2nd), seakkx (3rd), next-state (F), LaMaison (F), interior architect tool (F), Tekton (1st), Sim Francisco (2nd), Custom Universe (3rd), Rewild Earth (F), Homebuddy (2nd), Astra(l) Projection (F), Astratorial (F), CyclopsDiary (F), Wayfinder (3rd), WorldSTATE (F).
