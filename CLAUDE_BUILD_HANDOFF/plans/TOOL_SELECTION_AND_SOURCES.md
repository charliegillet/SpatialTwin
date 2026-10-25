> Current implementation target: `charliegillet/SpatialTwin`, project root `/Users/nihalnihalani/Desktop/Github/SpatialTwin`. Read root `BUILD_PLAN.md` first. References to `winners/spatialtwin_argon_winner` below describe the historical source review, not a directory to clone or build. Prices, capabilities and source checks retain their original recorded dates.

# SpatialTwin — tool selection and research sources

Research date: 23 October 2026. Read with the [build plan](SPATIALTWIN_BUILD_PLAN.md) and [architecture review](ARCHITECTURE_REVIEW.md).

For the user-confirmed SHACK15 demo, see the [venue playbook](SHACK15_DEMO_PLAYBOOK.md), including official location/map sources, map-use restrictions, optional RoomPlan/Scaniverse capture research, and the current floor-aware demonstration scope.

The [current Argon/UI review](DEMO_UI_UX_AND_ARGON.md) adds fresh official model and image-guide checks, managed-agent restrictions, verified Three.js picking/instancing/import APIs and an interaction-study verification record. It supersedes assumptions that Argon supports Live API or that managed agents accept all direct-model modalities.

## 1. Recommended stack

| Layer | Selection | Why it earns a place | Scope boundary |
|---|---|---|---|
| Browser | React + TypeScript + Vite | Interactive editor and cockpit with a simple local build | A heavy full-stack framework is unnecessary for the demo |
| Geometry/rendering | Three.js + React Three Fiber | Generate the cutaway from validated plan shapes; handle scene interactions | Does not reconstruct buildings from pixels |
| 2D editor | Small SVG editor over the canonical schema | Fast, legible, easy to perturb and available as a graphics fallback | Constrained room/portal operations rather than general CAD |
| Backend | FastAPI + Pydantic | Typed commands, semantic validation, runs and event stream | Pin the actual documented SSE-capable release |
| Local data | SQLite | Atomic event/revision updates, reproducible replay and local launch | Serialize writes; no shared network-disk database |
| Planning | NetworkX | Inspectable integer maximum/minimum-cost flow and small reproducible fixtures | Time/occupancy modeling is application work |
| AI | `google-genai`, model interactions | Argon semantic/image proposals with validated structured outputs | Model output is proposed state |
| Agent | Antigravity managed agent through a dedicated adapter | Bounded scenario investigation with genuine tool trace | No control of real doors/fans and no dependence for local replanning |
| Browser verification | Playwright | Exercise edits, state races, disconnected network and replay | Screenshots alone cannot prove numerical correctness |
| Numerical verification | Python tests + generated small-graph cases | Conservation, capacity, timing, blocked paths, independent checks | Do not merely assert the solver's own success flag |

Use Python 3.12 as an initial compatibility target for the backend and managed sandbox, then pin versions that pass Phase 0. Use one Three.js installation and matching React/R3F versions. Keep package locks, generated API types and a local launcher in the eventual implementation.

## 2. Open-source and optional tools considered

“Later” means useful when its stated trigger exists; it is not another dependency to install during the demo sprint.

| Tool | Choice | Useful role | Why not put it in the core path? |
|---|---|---|---|
| Three.js / R3F | Use | 2.5D facility, routes, cutaway and interaction | Rendering is separate from geometry/topology inference |
| OpenCV ArUco + homography | Optional next | A4 map and flat cards under one camera | Requires calibration, lighting and quality gates |
| Browser `getUserMedia` | Use if camera mode chosen | Local capture without a separate video platform | Permission and secure-origin requirements; phone LAN setup adds work |
| Three.js SVGLoader | Later | Import a controlled, self-authored SVG plan | SVG paths are not rooms/doors/exits; current docs deprecate `createShapes` |
| IfcOpenShell | Later, preferred offline IFC path | Extract geometry, placements, units and element IDs | Native dependencies and missing/ambiguous walkable topology |
| web-ifc | Later browser IFC alternative | Read IFC using WASM | JS/WASM compatibility and semantic adapter required |
| That Open Components | Later BIM-focused alternative | Ready-made BIM browser controls and viewer features | Adds its own scene ecosystem; avoid casually mixing it into R3F |
| Bonsai Studio / Blender | Optional asset-authoring tool | Make an owned IFC facility or rendered test footage | Authoring tool, not the live evacuation engine |
| OR-Tools | Profile-driven upgrade | Faster compiled flow; later constrained optimization | Switching libraries does not fix an invalid capacity/time model |
| JuPedSim | Later validation layer | Microscopic pedestrian dynamics, geometry and journey behavior | Different computational/modeling scope from flow optimization |
| PedPy | Later analysis tool | Compute pedestrian density/flow metrics from trajectory data | Analysis library; not a route optimizer |
| Mesa | Later only for research | Custom behavior experiments or agent-based policy studies | Requires authoring/calibrating behavior; not automatic crowd physics |
| SUMO | Later campus/city extension | Outdoor transport and larger networks; pedestrian integration | Excess stack for a single indoor floor |
| CFAST | Later physics integration | Precompute specific compartment-fire scenarios | Needs fire/environment inputs and validation; not inference from a red token |
| FDS / Smokeview | Later specialist workflow | High-fidelity fire CFD and visual inspection | Computational and domain burden; keep outside live loop |
| PyroSim | Optional paid specialist authoring | Build/manage FDS models through a GUI | Not open-source core; license/access required |
| ProcTHOR / AI2-THOR | Later test-data generation | Diverse indoor synthetic scenarios and camera experiments | Houses/assets and simulator setup do not constitute evacuation validation |
| Habitat-Sim | Later sensor/navigation research | Synthetic viewpoints and embodied navigation experiments | Native/GPU setup and independent dataset terms |
| Gazebo | Later robotics extension | Simulated sensors/robots/actuator topics and hardware integration | Unnecessary for map perturbation and routing |
| Remote MCP | Optional interoperability | Expose the same bounded scenario tools to a cloud agent | Authentication/transport/public reachability work; function calls suffice first |
| Firecrawl | Used for research; optional preparation tool | Read technical docs and gather source material | Not a hazard sensor, occupancy source or incident-loop dependency |

No vector database, Kubernetes cluster, streaming broker or multi-agent runtime is required for this version. Add infrastructure in response to measured operational needs. A 2D floorplan plus a reproducible optimizer demonstrates the central value before any of those systems become useful.

## 3. Verified APIs and example locations

These are documentation/source findings. Only the small NetworkX formulation experiment below was executed; the eventual application's SDK combinations still require Phase 0 verification.

| Component | Verified API or pattern | Copy-ready primary source |
|---|---|---|
| Three.js | `new ExtrudeGeometry(shapes, options)`; `depth`, `bevelEnabled` | [ExtrudeGeometry constructor and options](https://threejs.org/docs/pages/ExtrudeGeometry.html) |
| R3F | `Canvas`, `useFrame`, JSX geometry and mesh pointer events | [Introduction examples](https://r3f.docs.pmnd.rs/getting-started/introduction) |
| SVGLoader | `parse(text)` returns paths/XML; static `createShapes` deprecated in current docs | [SVGLoader methods](https://threejs.org/docs/pages/SVGLoader.html) |
| Camera | `navigator.mediaDevices.getUserMedia(constraints)` returns `Promise<MediaStream>` | [MDN syntax, constraints and security](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia) |
| ArUco | `cv::aruco::ArucoDetector`, `detectMarkers`, predefined dictionaries, `generateImageMarker` | [OpenCV marker tutorial](https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html) |
| Homography | `cv.findHomography(source_points, destination_points)`; `cv.warpPerspective` | [OpenCV homography examples](https://docs.opencv.org/4.x/d9/dab/tutorial_homography.html) |
| web-ifc | `IfcAPI`, `Init`, `SetWasmPath`, `OpenModel(data: Uint8Array, settings?)`, `CloseModel` | [Current source typings](https://github.com/ThatOpen/engine_web-ifc/blob/main/src/ts/web-ifc-api.ts), [usage examples](https://github.com/ThatOpen/engine_web-ifc/tree/main/examples/usage) |
| IfcOpenShell | `ifcopenshell.open`, `geom.settings`, `geom.iterator`, `util.unit.calculate_unit_scale` | [Geometry, placements and units examples](https://docs.ifcopenshell.org/ifcopenshell-python/geometry_processing.html) |
| NetworkX | `maximum_flow_value(flowG, _s, _t, capacity='capacity', flow_func=None, **kwargs)` | [Maximum-flow reference](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.flow.maximum_flow_value.html) |
| NetworkX | `min_cost_flow(G, demand='demand', capacity='capacity', weight='weight')` | [Minimum-cost-flow reference and example](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.flow.min_cost_flow.html) |
| OR-Tools | `min_cost_flow.SimpleMinCostFlow`, `add_arcs_with_capacity_and_unit_cost`, `set_nodes_supplies`, `solve` | [Official complete program](https://developers.google.com/optimization/flow/mincostflow) |
| Gemini model | `client.interactions.create(model=..., input=..., response_format=...)`; Pydantic parse of `output_text` | [Structured-output recipe](https://ai.google.dev/gemini-api/docs/structured-output#structured-output-examples) |
| Managed agent | `agent='antigravity-preview-09-2026'`; model under `agent_config` | [Model selection](https://ai.google.dev/gemini-api/docs/antigravity-agent#model-selection) |
| Environment | Create with `environment='remote'`; reuse with `environment=interaction.environment_id` | [Configure/reuse example](https://ai.google.dev/gemini-api/docs/agent-environment#configure-an-environment) |
| Skills | Mount `.agents/skills/<name>/SKILL.md` via environment sources | [File-based customization](https://ai.google.dev/gemini-api/docs/custom-agents) |
| Streaming | Managed quickstart streams typed events and inspects `step.stop` usage | [Agent streaming example](https://ai.google.dev/gemini-api/docs/managed-agents-quickstart#stream-response) |
| FastAPI | `EventSourceResponse` from `fastapi.sse`; `yield` from path operation | [SSE tutorial](https://fastapi.tiangolo.com/tutorial/server-sent-events/) |
| SQLite | WAL permits readers with a writer, with a single writer | [WAL concurrency and restrictions](https://www.sqlite.org/wal.html) |
| Playwright | Install/test runner workflow and browser setup | [Getting started](https://playwright.dev/docs/intro) |

Implementation cautions from these sources:

- Three.js assumes a different default up axis from the canonical `(x,y,z-up)` plan. Use one adapter, for example `(x,z,-y)`, and test rotations and overlays.
- ArUco IDs and marker corner ordering determine correspondence. A tall block's top center has parallax; use a flat token or its ground contact point. Fit a plane, measure held-out positions, and distinguish physical page meters from represented building meters.
- `getUserMedia` needs permission and a secure context. `http://localhost` on a laptop does not make `http://laptop-ip` a secure origin on a phone.
- web-ifc's README is looser than current typings about input data; follow pinned `Uint8Array` typings. Match JS/WASM versions and close models to release memory.
- Raw IFC project units and already-tessellated geometry can differ. Do not double-scale or discard element placement transforms.
- NetworkX uses negative demand for supply; OR-Tools uses positive supply. Adapter tests must catch a sign reversal.
- A managed-agent environment and conversation are separate state resources. Conversation history is not the application's current building state.
- Model structured output and managed-agent output are different capabilities. Do not merge examples between them.
- Official MCP naming prose is inconsistent with its displayed regex; a simple lowercase name such as `facility` avoids that ambiguity. Use Streamable HTTP for the documented managed-agent MCP path.

## 4. Source-grounded simulation comparison

| Source | What was read | Architectural conclusion |
|---|---|---|
| [NetworkX minimum cost flow](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.flow.min_cost_flow.html) | Demands, capacities, integer warning, exceptions and example | Appropriate for a small integer flow model; not automatic pedestrian simulation |
| [OR-Tools minimum cost flow](https://developers.google.com/optimization/flow/mincostflow) | Solver setup, vectorized arcs/supplies, solve and full code | Benchmark as an interchangeable solver after model correctness |
| [JuPedSim journeys notebook](https://www.jupedsim.org/stable/notebooks/journey.html) | Simulation geometry, stages/journeys and agents | Later microscopic validation needs its own behavior assumptions |
| [PedPy documentation](https://pedpy.readthedocs.io/stable/index.html) | Purpose and installation | Analyze trajectories rather than replace the planner |
| [Mesa overview](https://mesa.readthedocs.io/stable/overview.html) | Agent/model/scheduler research scope | More modeling freedom means more behavior/calibration work |
| [SUMO JuPedSim integration](https://sumo.dlr.de/docs/jupedsim.html) | Pedestrian-simulation scope and integration context | Useful for larger outdoor scenarios, not a prerequisite here |
| [NIST CFAST](https://pages.nist.gov/cfast/) | Two-zone fire modeling scope and links | Prebuilt compartment scenarios, not live inferred smoke physics |
| [NIST advanced fire modeling](https://www.nist.gov/programs-projects/advanced-fire-modeling) | Fire-modeling program and FDS scope | Requires specialist inputs and validation |
| [PyroSim](https://www.thunderheadeng.com/pyrosim) | Modeling/management role and commercial licensing options | Optional authoring convenience, not open-source dependency |

### Small experiments performed during planning

An isolated NetworkX 3.7 environment first ran a tiny maximum-flow → fixed-flow minimum-cost-flow API check. It was superseded as the product formulation after review identified that selected-flow models can omit remaining occupants' occupancy.

The final experiment injected all 12 occupants into a time-expanded room, with boundaries at 0, 5, 10 and 15 seconds. Each open direct exit admitted 2 people per slot with one-slot travel. Two minimum-cost-flow passes first maximized successful exits, then fixed the exit/remaining totals and minimized schedule cost. The first pass used only an exit-collector reward of `−1`; no large penalty constant was needed.

| Exits open | Assigned by 15 s | Remaining | Room occupancy at the four boundaries |
|---|---:|---:|---|
| 2 | 12 | 0 | `[12, 8, 4, 0]` |
| 1 | 6 | 6 | `[12, 10, 8, 6]` |
| 0 | 0 | 12 | `[12, 12, 12, 12]` |

Copy-ready application pattern, adapted to a compiler-created graph:

```python
nx.set_node_attributes(G, 0, 'demand')
G.nodes[S]['demand'], G.nodes[T]['demand'] = -N, N
# All objective costs are zero except EXIT -> T, whose cost is -1.
first = nx.min_cost_flow(G, capacity='capacity', weight='objective_cost')
F = first[EXIT][T]
second = G.copy()
second.remove_node(T)
second.nodes[EXIT]['demand'] = F
second.nodes[UNASSIGNED]['demand'] = N - F
schedule = nx.min_cost_flow(second, capacity='capacity', weight='schedule_cost')
```

The compiler must set finite integer capacities on all arcs, including source injection and collector arcs; injection capacity totals `N`. Only physical states at the horizon connect to `UNASSIGNED`. Actual exit connections respect their shared throughput. The forward-time structure prevents negative cycles. All second-pass schedule costs are nonnegative integers. Check source saturation, both collector totals and all-person occupancy independently. Permanent hazard movement closures retain physical holding for trapped people; a hazardous hold is unresolved exposure, never a successful exit path.

This establishes the API/formulation behavior on tiny fixtures, including the simple time-expanded room. It does **not** establish the complete corridor/transit/hazard compiler, real-world evacuation accuracy, cross-version tie-breaking stability, or application performance. Require stable graph insertion order and a documented tie-break policy if exact replay across solver versions is required.

## 5. Licensing, assets and reproducibility

Repository-reported identifiers checked during research: Three.js MIT; R3F MIT; OpenCV Apache-2.0; web-ifc MPL-2.0; That Open Components MIT; IfcOpenShell LGPL-3.0; ProcTHOR Apache-2.0; Habitat-Sim MIT; gz-sim Apache-2.0. Bonsai's own `COPYING` was read and identifies GPL v3. This is a component inventory, not a legal determination for an eventual distribution; preserve the notices for exact pinned versions.

Engine licenses do not grant rights to redistribute third-party building models, indoor datasets, textures, furniture or camera footage. Dataset terms for Matterport3D, Gibson, Replica and downloadable scene packs were not verified. Do not bundle them by default. Prefer self-authored geometry, procedural simple shapes and owned demo images.

For each external asset, record author, source URL, license, retrieval date, hash, attribution and transformation history. For every benchmark, record model ID, SDK version, graph/compiler version, solver version, laptop specifications, horizon/time step, graph size and seed. Store sanitized example responses and error fixtures; never store API keys or signed download URLs in published artifacts.

## 6. Repository evidence and current limits

All six source documents were read at the recorded commit:

- [Project README](https://github.com/nihalnihalani/winners/blob/9fd96f7bfa93d82ce9fa6eac84cffc1e62829745/spatialtwin_argon_winner/README.md): initial outcome, event and architecture claims.
- [Historical patterns and debate](https://github.com/nihalnihalani/winners/blob/9fd96f7bfa93d82ce9fa6eac84cffc1e62829745/spatialtwin_argon_winner/01_historical_patterns_and_judges_debate.md): unsupported win probabilities and project-selection rationale.
- [Architecture and managed agents](https://github.com/nihalnihalani/winners/blob/9fd96f7bfa93d82ce9fa6eac84cffc1e62829745/spatialtwin_argon_winner/02_spatialtwin_architecture_and_managed_agents.md): proposed controller, Python snippet and skill policy.
- [Hardware/demo playbook](https://github.com/nihalnihalani/winners/blob/9fd96f7bfa93d82ce9fa6eac84cffc1e62829745/spatialtwin_argon_winner/03_tabletop_hardware_and_2min_demo_playbook.md): tabletop and paper alternatives, pitch and latency claims.
- [Bill of materials/checklist](https://github.com/nihalnihalani/winners/blob/9fd96f7bfa93d82ce9fa6eac84cffc1e62829745/spatialtwin_argon_winner/04_complete_bill_of_materials_and_event_checklist.md): hardware assumptions and fallback.
- [Stagecraft](https://github.com/nihalnihalani/winners/blob/9fd96f7bfa93d82ce9fa6eac84cffc1e62829745/spatialtwin_argon_winner/05_legendary_demo_stagecraft_and_theatrics.md): presentation and physical-effect proposals.

The private repository was read through authenticated `gh` after both the connected GitHub fetch and public Firecrawl scrape returned 404. Firecrawl was used for external technical research and the organizer page; a successful scrape was inspected for content rather than assumed valid. Browser inspection and public access are not required for the saved plan.

The [organizer's own event page](https://cerebralvalley.ai/e/gemini-4-argon-sf) supports the listed event, team cap and prize categories. Current [Gemini Interactions overview](https://ai.google.dev/gemini-api/docs/interactions-overview), [managed-agent documentation](https://ai.google.dev/gemini-api/docs/antigravity-agent) and [environments guide](https://ai.google.dev/gemini-api/docs/agent-environment) support the API corrections. These sources do not prove that this particular account has access or that latency targets will be met.

**Confidence:** high for the documented API shapes and architectural boundaries; medium for implementation effort estimates; unmeasured for stage latency, camera accuracy and the complete planner. No working application or production emergency system is claimed.
