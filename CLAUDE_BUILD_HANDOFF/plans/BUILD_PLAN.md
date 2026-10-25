# SpatialTwin — execution plan for this repository

## Primary goal

Let a judge change a physical floor-plan scenario and see a reproducible routing result, then approve one miniature intervention whose independently observed position produces a new checked result on both the screen and lights.

Prepared **24 October 2026** for **Nihal, Charlie, Codex and Claude**. Repository: `https://github.com/charliegillet/SpatialTwin`; local project root: `/Users/nihalnihalani/Desktop/Github/SpatialTwin`. This is the current plan for this repository. Earlier winners documents are historical architectural research.

## Current state and scope

At inspection this was an empty Git checkout with no commits or application files. It now contains the complete prior planning/handoff material, documentation references and fabrication fixtures. **No complete application, firmware, live Argon integration or physical validation has been built here.** Documentation checks are not device or provider tests.

Build one reviewed 6–10-zone schematic, three illuminated connections, two finite-rate floor-transfer boundaries, one servo-operated miniature internal connector and two independent endpoint switches. Judge targets are `portal:P1`, `portal:P2`, `boundary:B2`. `OPEN_P3` reconnects an internal route to existing B2; it never creates an exit or changes receiving capacity.

The supplied printable fixture is not a SHACK15 survey. Nihal must approve actual venue geometry/provenance before venue-specific claims. Synthetic population and declared scenario rates stay labeled. Counts describe modeled floor-transfer boundary crossings, not survival or street evacuation. Before/after runs restart with equal initial synthetic population/horizon; the prototype does not model real people moving during motor travel.

### Budget and resources

The [full sourced shopping list](docs/plans/PHYSICAL_DEMO_BOM.csv), checked 23 October, budgets **$148.99 electronics** including $18 generic allowances. Spares add $13.85; board/printing/props $30; application API allowance $25; tax/shipping reserve $60: **$277.84 planning total** with borrowed camera, mount and tools. Buying camera/mount/tools/hub raises the prior planning envelope to about $475–$500. These are dated quotes/allowances, not guaranteed checkout totals or arrival dates. Claude Code subscription/token usage is separate.

Nihal and Charlie must have the actual parts, soldering tools, meter and camera before the physical build window. Recheck availability/arrival and event preparation rules before committing the stage to hardware. Read the [exact physical plan](docs/plans/PHYSICAL_DEMO_BUILD_PLAN.md) and [wiring guide](docs/plans/PHYSICAL_DEMO_WIRING.md), not the original source's rough $15–$20 kit estimate.

## Ownership and planned application layout

| Owner | Responsibility | Concrete output |
|---|---|---|
| Nihal | Venue references, procurement, reviewed artwork, camera framing, judge trials/pitch | Accepted original schematic, parts in hand, fresh captures and rehearsed script |
| Charlie | Power, soldering, mechanics, endpoint switches, mounting and real bench checks | Calibrated mechanism, measured supply/current, reliable reset and 30 cycles |
| Codex | Bootstrap/shared contracts, backend state, planner/checker, firmware, serial, shared UI and integration | Local manual scenario → checked result → matching LEDs; approved motion → confirmed state → new solve |
| Claude team | Grounding, managed investigation, isolated proposal/evidence UI, AI fixtures/docs, independent critique | Actual bounded AI adapters and review interface, with honest live/fixture status |

Proposed code layout below is **to be created**, not existing implementation:

```text
backend/app/main.py
backend/app/contracts.py             # one owner: Codex
backend/app/state/
backend/app/planner/
backend/app/hardware/
backend/app/ai/grounding/              # Claude teammate
backend/app/ai/managed/                # Claude teammate
frontend/src/                        # Codex shell/store/API/scene
frontend/src/features/proposal-evidence/  # Claude isolated component
firmware/spatialtwin_board/
venue/                              # reviewed geometry + provenance + device mapping
tools/export_board.py
tests/planner/
tests/hardware_protocol/
tests/ai_contracts/
tests/adversarial_ai/
docs/ai/
runtime/                            # ignored local DB/captures
```

One bootstrap writer creates shared manifests/configuration/contracts. Claude teammates start documentation review, probes, fixtures and isolated components in parallel. While the repository has no HEAD, use disjoint owned paths in the current checkout. Check remote refs before the first project commit; reconcile any real remote history without destructive operations. Separate worktrees become an option only after an agreed committed baseline exists. Record the assigned implementation root so agents do not accidentally edit another checkout.

## Phase 0 — Read documentation, inventory and freeze contracts

**How this serves the primary goal:** it prevents incompatible AI, numerical and physical components from producing a convincing but incorrect demonstration.

**Owners:** Codex integration owner; Claude lead and documentation teammate; Nihal/Charlie inventory.

**Implement / prepare:**

1. Read root `AGENTS.md`, [physical plan](docs/plans/PHYSICAL_DEMO_BUILD_PLAN.md), [contract proposal](CLAUDE_BUILD_HANDOFF/CONTRACT_PROPOSAL.md) and [Google API guide](CLAUDE_BUILD_HANDOFF/GOOGLE_API_GUIDE.md). Resolve actual local/remote Git state and installed runtimes. Record the actual version/lockfile used rather than copying an assumed latest version.
2. Freeze `RunContext`: geometry, scenario, physical and parameter revisions, solver version and server-derived hash. Use canonical `geometry_revision` and `frontend/`; older `map_revision`/`app/` examples are aliases to normalize.
3. Freeze capture/proposal, immutable ScenarioService, checked result, investigation, UI callbacks and serial envelopes. Define exact supported type/ID pairs and how stale context is rejected.
4. Nihal reviews the actual room model/source; Charlie confirms parts/connectors, power rails, tools and mounting. Device-map null servo endpoints and unspecified metric/capacity fields must be filled through actual calibration/review before real use.
5. Claude independently verifies direct-model access, managed function/continuation shape and requested teammate models. Keep credentials server-side and report missing access without a model substitution or fake live success.

**Allowed API patterns, copied from the included official sources:**

- `google-genai`, `from google import genai`, `client.interactions.create` with direct `model="gemini-4-argon"` for structured proposals.
- Managed `agent="antigravity-preview-09-2026"`, `agent_config={"type":"antigravity","model":"gemini-4-argon",...}`, documented `max_total_tokens`, `previous_interaction_id`, returned environment identity and matching `function_result.call_id`.
- Handle `in_progress`, `requires_action`, `completed`, `failed`, `cancelled`, `incomplete`. Buffer full arguments/JSON before execution. Read actual pinned SDK types; generic OpenAPI field presence is not capability support.
- Proposed local service: `get_reviewed_context`, `evaluate_alternative(context, alternative_id, request_id)`, `get_checked_run`. These are application interfaces, not vendor APIs already implemented.

**References:** [Google guide: core contracts and smoke-test order](CLAUDE_BUILD_HANDOFF/GOOGLE_API_GUIDE.md); [20-page/OpenAPI source manifest](CLAUDE_BUILD_HANDOFF/reference/GOOGLE_SOURCES.json); [exact serial envelope](docs/plans/PHYSICAL_DEMO_BUILD_PLAN.md#minimal-application-contracts).

**Verification:** written contract/version/ownership map; actual account status; parts/tool inventory; no missing type for B2; no invented Git SHA. **Guards:** no managed structured response schema, no managed `max_output_tokens`/sampling config, no native Argon Live API claim, no hidden placeholder promoted to live evidence.

## Phase 1 — Scaffold the local app and manual scenario loop

**How this serves the primary goal:** judges retain a working, understandable local interaction even while cloud AI or hardware is unavailable.

**Owner:** Codex. Claude starts its isolated work against the frozen port.

**Implement:**

1. Create FastAPI/Pydantic backend, SQLite event/result storage and React/TypeScript frontend using the agreed existing-tool versions. Use one writer for dependencies and lockfiles.
2. Load a small original illustrative venue JSON first. Separate reviewed topology, hypothetical changes and physical observations. The server owns accepted state; the browser owns previews/camera position.
3. Build a stable 2D plan with known targets and manual `SET_UNAVAILABLE` proposal review. Selecting a target does not mutate accepted state; Apply uses expected revision and idempotency key.
4. Persist capture/proposal/command/result provenance. On accepted changes mark old results stale immediately. Use one event stream/reconnect snapshot contract; distinguish application events from Google streaming events.
5. Add the basic result panel: initial population, completed crossings, remaining population, horizon, assumptions and validation status. Until Phase 2, its fixture data must be visibly labeled.

**References:** [architecture state ownership](docs/plans/SPATIALTWIN_BUILD_PLAN.md#state-ownership-and-consistency); [UI screen architecture](docs/plans/DEMO_UI_UX_AND_ARGON.md#3-screen-architecture); [UI seam](CLAUDE_BUILD_HANDOFF/CONTRACT_PROPOSAL.md#5-ui-component-seam).

**Verification:** clean startup, manual selection/review/reset, duplicate Apply produces one event, old-context results cannot repaint current state, fixture/manual labels visible. **Guards:** no dependency on cloud inference for direct plan selection; no image/agent text writing directly to state.

## Phase 2 — Implement the fixed numerical planner and independent checker

**How this serves the primary goal:** the result changes because the judge changed a constrained calculation, not because a canned animation was selected.

**Owner:** Codex; independent adversarial cases from Claude's reviewer.

**Implement:**

1. Compile one fixed reviewed graph with zone storage, travel slots, passage throughput, wait states and finite receiving quotas at B1/B2. Keep metric dimensions and capacities explicit with units/provenance.
2. Use the all-population finite-horizon flow formulation in the architecture plan. First maximize completed modeled-boundary crossings; second minimize schedule cost at that fixed maximum, retaining everyone else in physical holding states. Keep disconnected/trapped people counted.
3. Write a checker independently from solver helpers: initial population conservation, storage/throughput, time/travel, unavailable edges, boundary quota and completed-plus-remaining totals. A failed check blocks publication.
4. Return typed checked results with base context, candidate input hash, alternative/delta, run ID, statuses, counts, assumptions and timings. The scenario service evaluates immutable copies; a prediction does not change observed topology.
5. Support `KEEP_CURRENT`/`OPEN_P3`, including a helpful P2-blocked case and a B2-blocked case with no recovered downstream capacity. Equal/worse alternatives remain legitimate.

**References:** [full solver architecture and earlier experiment](docs/plans/SPATIALTWIN_BUILD_PLAN.md); [ScenarioService/EvaluationEnvelope](CLAUDE_BUILD_HANDOFF/CONTRACT_PROPOSAL.md#3-ai-facing-scenarioservice-port).

**Verification:** analytical small-capacity cases, one/both/no boundary availability, blocked connector, constrained holding, delayed arrival, partial horizon and no-benefit alternative. Independently account for every person. **Guards:** static independent shortest paths do not enforce shared capacity; no fabricated survival or smoke physics; no unbounded solver blocking the API.

**Hour-3 gate:** an actual checked numerical result must exist. If it does not, narrow explicitly to a simple capacity fixture and label the reduced scope.

## Phase 3 — Bring up the board, firmware and observed-state loop

**How this serves the primary goal:** the audience can inspect whether the physical intervention really happened and whether the displayed result agrees with it.

**Owners:** Charlie physical build; Codex firmware/serial; Nihal artwork/camera.

**Implement:**

1. Assemble the 24 × 18 inch board with 35–40 mm underside clearance, removable artwork, short raised walls, three LED-stick indicators and one lightweight gate. Use the same canonical IDs in print, graph and UI.
2. Follow the exact wiring guide: UNO R4 Minima + Adafruit815 PCA9685; external 5 V/4 A load rail separate from USB positive, common ground; D6 through470Ω to24RGBpixels; D7OE with2.2k pull-up; A4/A5I2C; D2/D3 independent endpoint switches;10k servo-signal pull-down; capacitors and specified3.15A M fuse. No `Servo.h` in this design.
3. First test logic/pixels and PCA/servo separately. Calibrate small unloaded travel before attaching the horn/gate; record actual endpoint pulses. Verify COM/NO switch contacts with a meter.
4. Implement bounded NDJSON `HELLO`, `HEARTBEAT`, `READ_STATE`, `ARM`, `SET_GATE_TARGET`, `SET_DISPLAY`, `STOP_OUTPUTS`; distinguish device `ACK`, `OBSERVATION`, `FAULT`. Bind boot/session, sequence, gate epoch, calibration and command ID. Repeated IDs never restart motion.
5. Require explicit local approval of the named predicted action. ACK means accepted. Only fresh debounced endpoint telemetry establishes state; transit/unknown/fault/stale keeps P3 unavailable. Confirmed position creates a physical revision, a new checked solve and then current screen/LED output.
6. Heartbeat timeout/reconnect disarms; no boot sweep, automatic retry or replay. Disabling servo pulses does not prove the mechanism closes. Publish observed switch state and freshness honestly.

**References:** [pin map, power, OE and calibration](docs/plans/PHYSICAL_DEMO_WIRING.md); [device-map fixture](docs/plans/PHYSICAL_DEMO_DEVICE_MAP.json); [physical transaction](CLAUDE_BUILD_HANDOFF/CONTRACT_PROPOSAL.md#6-physical-action-is-a-separate-transaction).

**Verification:** measured polarity/current, independent switch truth table, 30 open/close cycles with lights active, missing endpoint, contradictory switches, serial timeout, USB reconnect and duplicate commands. Actual observations must come from Nihal/Charlie. **Guards:** no load current through UNO/breadboard; no powered open claim based on commanded angle; no route-light result from stale/unchecked data.

**Hour-5 gate:** manual edit → checked solve → lights and approved movement → endpoint → new solve must work. Otherwise keep the gate fixed and show only labeled predicted alternatives; a hand-operated sensed variant is acceptable only after testing.

## Phase 4 — Add direct Argon image grounding and review

**How this serves the primary goal:** a judge's fresh physical choice becomes a visible, inspectable proposed change in the digital model.

**Owner:** Claude grounding teammate; Nihal supplies fresh captures; UI teammate renders review.

**Implement:**

1. Fix the overhead camera and verify all labels/targets are visible. Capture only with hands clear and gate stationary, using a neutral/acknowledged light state. Send one chosen still, not an unbounded stream.
2. Read the included image/structured-output/Argon docs. Make the smallest real text/image/schema probes with the authorized account before declaring the combined workload supported by the pinned SDK.
3. Send the captured image, reviewed catalog and source context to direct Argon. Produce `matched`, `ambiguous` or `no_match`, known typed candidates, nullable selection, `SET_UNAVAILABLE` and concise evidence. Validate source IDs/revisions, type/ID pairs, completed JSON and candidate membership locally.
4. Show source photo + plan highlight. Apply commits only after human review. Unknown/multiple/between-pad targets request a choice or recapture. A manual canonical selection remains usable when AI is unavailable.
5. Keep the vendor's normalized `[ymin,xmin,ymax,xmax]` boxes distinct from polygons, image pixels, board millimeters and represented meters. For the first version printed IDs provide cooperative grounding; free-space calibration is optional extra work.

**References:** [grounding teammate prompt](CLAUDE_BUILD_HANDOFF/prompts/01_GROUNDING.md); [official model](CLAUDE_BUILD_HANDOFF/reference/google/argon-model.md); [image](CLAUDE_BUILD_HANDOFF/reference/google/image-understanding.md); [structured output](CLAUDE_BUILD_HANDOFF/reference/google/structured-output.md).

**Verification:** 20 varied fresh captures, with actual correct/corrected/abstained outcomes recorded; malformed output, wrong typed ID, occlusion, image instruction text, timeout and stale capture. **Guards:** no confidence percentage without calibration; no invented dimensions/occupancy/doors; no continuous Live API claim.

## Phase 5 — Add managed Argon's bounded alternative investigation

**How this serves the primary goal:** the AI can investigate actual evidence and explain the tradeoff created by the judge's scenario.

**Owner:** Claude managed-agent teammate; Codex supplies immutable local tools.

**Implement:**

1. Copy the documented initial/config/continuation pattern from the included managed guide, verifying actual SDK serialization and initial Argon selection.
2. Allow only read-only numerical tools for fixed alternatives on the accepted context. The local client executes those functions and returns checked results; a remote environment cannot call laptop localhost.
3. Handle `requires_action`, full argument assembly, pending call/result IDs, durable exactly-once execution, `previous_interaction_id` and returned environment reuse. Handle all lifecycle outcomes and a finite deadline.
4. Start with20,000-token best-effort `agent_config.max_total_tokens`, at most two alternatives/four accepted function calls and cumulative continuation/usage accounting. A resumed interaction may receive another provider budget; do not chain it indefinitely.
5. Assemble application results from the checked tool ledger. Agent prose supplies concise explanation only. Incomplete/stale/failed results cannot declare a winning option. The cloud receives no motor, arbitrary local shell/code or serial tool.

**References:** [managed teammate prompt](CLAUDE_BUILD_HANDOFF/prompts/02_MANAGED_AGENT.md); [official managed guide](CLAUDE_BUILD_HANDOFF/reference/google/antigravity-agent.md); [quickstart](CLAUDE_BUILD_HANDOFF/reference/google/managed-quickstart.md); [OpenAPI](CLAUDE_BUILD_HANDOFF/reference/google/interactions.openapi.json); [streaming](CLAUDE_BUILD_HANDOFF/reference/google/streaming.md).

**Verification:** actual one-function continuation if access exists, duplicate calls, budget incomplete, timeout/cancellation, no-improvement, unknown alternatives, context drift and prose/ledger disagreement. Fixture and live results remain separate. **Guards:** no managed structured-output schema, unsupported generation config, fake steps, partial argument execution or direct cloud actuation.

## Phase 6 — Integrate the judge-facing 2D/3D and evidence UI

**How this serves the primary goal:** judges can understand what they changed, what happened and what proves the result without interpreting raw implementation logs.

**Owners:** Codex shared shell/scene/state; Claude isolated proposal/evidence component.

**Implement:**

1. Generate a roofless 2.5D cutaway from the same reviewed source as the stable 2D plan. Use 3D for recognition, plan view for precise targets; keep a WebGL-independent plan fallback.
2. Add presenter/judge handoff, labeled targets, explicit Apply, resolved ambiguity and Escape hand-back. Give one operator ownership of physical commands.
3. Compare equal-population/horizon conditions at the same camera/time. Separate baseline, predicted OPEN_P3, command/motion status and confirmed observed result. Candidate hashes differ only by declared allowed deltas; observed confirmation creates a new physical context.
4. Show completed modeled-boundary crossings, remaining people, relevant queue/time, assumptions and validity. Evidence drawer holds actual capture, revisions, model/tool records, command and endpoint receipts. Keep genuine progress, not staged timers or raw thought traces.

**References:** [UI specification](docs/plans/DEMO_UI_UX_AND_ARGON.md); [UI teammate prompt](CLAUDE_BUILD_HANDOFF/prompts/03_PROPOSAL_UI.md); [screen/fixture preview](docs/plans/UI_STUDY_PREVIEW.png).

**Verification:** inspect desktop/projector and narrow layouts; matched/ambiguous/no-match/stale/offline/timeout states; same-result ID on screen and device; no achieved-benefit display before confirmation. **Guards:** no decorative survival score, fake measured crowd dots, invisible disabled controls or independently rotating comparisons.

**Hour-7 gate:** freeze physical IDs/topology and decide whether vision is reliable enough for the stage. Keep manual selection and actual managed tool evidence if grounding must be cut.

## Phase 7 — Independent adversarial integration review

**How this serves the primary goal:** the demonstration remains truthful when the judge chooses an unfamiliar or unhelpful case.

**Owners:** independent Claude Opus reviewer, with each implementation owner fixing its own module.

**Implement / verify:**

- Reviewer derives small counterexamples independently and records trigger, observed/expected behavior, severity, reproduction and retest evidence. The reviewer does not edit the implementation it approves.
- Test old revisions arriving late, duplicate Apply/function/serial delivery, wrong typed IDs, image instruction text, partial provider arguments, unavailable account and malformed responses.
- Test all boundaries unavailable, residual population, closed downstream B2, invalid solver result, failed sensor, both switches pressed, USB restart and hardware stale state.
- Ensure manual/local computation survives cloud failure. Preserve predicted versus observed, fixture versus live, ACK versus arrival, and numerical completion versus checked validity throughout.

**References:** [reviewer prompt](CLAUDE_BUILD_HANDOFF/prompts/05_DEVILS_ADVOCATE.md); [acceptance matrix](docs/plans/PHYSICAL_DEMO_BUILD_PLAN.md#7-acceptance-checks); [architecture challenge](docs/plans/ARCHITECTURE_REVIEW.md).

**Exit:** critical correctness/truth failures fixed and independently retested, or the corresponding feature cut visibly. **Guards:** no checklist-only pass without evidence; no requirement for unrelated production infrastructure to validate a miniature prototype.

## Phase 8 — Package, rehearse and submit

**How this serves the primary goal:** the complete loop can be presented and recovered reliably within the judging window.

**Owners:** Nihal presentation; Charlie physical operation; Codex/Claude blocking defects and evidence.

**Implement / verify:** pin successful versions/lockfiles, cache local assets, record exact setup/reset commands, retain spares and label harnesses. Perform five complete clean-start rehearsals including unfamiliar target choices. Measure real grounding/investigation latency and usage; choose timeouts and stage sequence from measurements.

Use the two-minute target sequence: venue/scope → judge choice/prediction → captured match/review → checked consequence → actual tool comparison → approved miniature move → independently confirmed new result. If cloud work needs longer, continue into questions; saved runs/video are labeled replay.

Reserve about10 build hours,2 rehearsal/recovery hours and1 logistics hour if the actual event window permits. Freeze features at hour10. Confirm organizer schedule/build-period/submission rules; this elapsed-time plan is not a new event timetable.

**References:** [stage and recovery playbook](docs/plans/SHACK15_DEMO_PLAYBOOK.md); [physical script](docs/plans/PHYSICAL_DEMO_BUILD_PLAN.md#8-two-minute-presentation-and-recovery); [setup probe order](CLAUDE_BUILD_HANDOFF/GOOGLE_API_GUIDE.md#mandatory-live-smoke-test-order-for-claudes-implementation).

**Final proof:** no unsupported API parameters, no stale result publication, no partial input execution, all occupants counted, no direct cloud motor path, actual endpoint evidence, honest no-benefit case and clear source/provenance. Report tests actually run and remaining limits. Submission/publishing follows the user's actual authorization; planning files alone are not a shipped product.

## Parallel start instructions

Start with [Claude's team lead](CLAUDE_BUILD_HANDOFF/prompts/00_CLAUDE_TEAM_LEAD.md) and [Codex's parallel prompt](CLAUDE_BUILD_HANDOFF/prompts/06_CODEX_PARALLEL.md). Claude's lead creates five internal Opus/Sonnet teammates using the supplied briefs. The devil's advocate starts during Phase0, not after every design choice is locked.

Nihal/Charlie can acquire references, print the illustrative bench fixture and prepare parts while software probes run, subject to actual event rules. After contract freeze, phases2/3/4 proceed in parallel; phase5 integrates against the real numerical service when ready; UI fixture states can start early and become live integration in phase6.

Core cuts, in order: extra decorative geometry/scans, QR/voice, additional actuators, free-space token placement. Preserve explicit review, truthful provider status, population accounting, numerical validation and independent position confirmation.
