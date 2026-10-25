> Current implementation target: `charliegillet/SpatialTwin`, project root `/Users/nihalnihalani/Desktop/Github/SpatialTwin`. Read root `BUILD_PLAN.md` first. References to `winners/spatialtwin_argon_winner` below describe the historical source review, not a directory to clone or build. Prices, capabilities and source checks retain their original recorded dates.

# SpatialTwin — devil's advocate review and decisions

Reviewed 23 October 2026. This document challenges the [build plan](SPATIALTWIN_BUILD_PLAN.md), explains the decisions it changed, and defines the failures the implementation must survive. The tool evidence and exact APIs are in the [source register](TOOL_SELECTION_AND_SOURCES.md).

**Venue update:** Nihal confirmed SHACK15. The [venue demo playbook](SHACK15_DEMO_PLAYBOOK.md) adds correct-floor grounding, a fresh photo/plan interpretation challenge, finite floor-transfer boundary rates, and an assumption-sensitive intervention comparison. A ground-level marketplace map cannot stand in for the upstairs event room, and a floor-transfer result cannot be described as full-building evacuation.

## 1. Verdict

The strongest architecture for this demonstration is a measured scenario workbench with an authoritative local state, generated 3D visualization, a fixed numerical planner and bounded Gemini interpretation/investigation. The audience can alter the scenario without a detailed physical model. The system's ability to report partial or impossible evacuation is a core product behavior.

This choice is optimized for the four-contributor team of Nihal, Charlie, Codex and Claude, and a short demonstration build. The build plan assigns ownership and handoffs across two humans and two AI collaborators. A system intended for live operational emergency guidance would have different evidence, integration and validation requirements. The same software should not acquire that claim merely by connecting a real camera or installing a fire simulator.

Three independent reviews covered demo/geometry tools, solver documentation/experiments and a skeptical source audit. The final plan incorporated their findings. The main changes from the source playbook are architectural, not cosmetic.

## 2. Source audit: failures the original plan would encounter

Source locations refer to the recorded repository commit. The architecture document is [02_spatialtwin_architecture_and_managed_agents.md](https://github.com/nihalnihalani/winners/blob/9fd96f7bfa93d82ce9fa6eac84cffc1e62829745/spatialtwin_argon_winner/02_spatialtwin_architecture_and_managed_agents.md); other source links are in the source register.

| Severity | Challenge and evidence | Concrete failure | Decision and proof required |
|---|---|---|---|
| Critical | Supplied Python has an extra indentation at architecture line 173; parsing reproduced the error | First execution fails before any simulation | Implement a versioned package; compile and run fixtures before AI integration |
| Critical | Architecture lines 184–200 independently call shortest path and inspect summed loads | A 65-person group keeps choosing the same overloaded path; capacity metadata does not constrain it | Use time/occupancy flow and independently verify the returned schedule |
| Critical | Architecture lines 133–184 use static radius/midpoint distance | Hazard at corridor endpoint is missed; time slider has no mathematical effect | Use declared permanent hazard closures with explicit time/units, not a claim of smoke physics |
| Critical | Source skill at architecture lines 224–226 says rerun until `VERIFIED_SAFE` | Both exits are blocked, but the loop must manufacture success or run forever | Zero/partial results are valid outcomes; no unbounded success loop |
| Critical | Demo document repeatedly claims 99.4% survival | Precise output has no dose, injury, behavior or calibration model | Remove survival output; use reproducible assignment/queue/timing metrics |
| High | Arbitrary sketch-to-watertight-3D and exact zero-marker geometry have no implementation | Incorrect doorway/topology silently becomes a route | Known metric templates first; images produce proposals with a review/scale step |
| High | Mutable module state holds one interaction/environment ID, architecture lines 63–74 and 113–126 | An old frame overwrites a newer blockage, or sessions interfere | Source timestamps, scenario revisions, hashes, latest-only requests and publish guards |
| High | Normalized prompt coordinates and 10–100 graph coordinates have no shared units | Perception, renderer and solver disagree spatially | One metric schema and tested camera/render transforms |
| High | Every incident depends on a cloud code-execution request | Wi-Fi or sandbox wakeup stalls the whole product | Local numerical path; cloud adapters have explicit unavailable/time-out states |
| High | Generic hardware list assumes fan reversal and agent-controlled doors | Purchased fan cannot reverse, UI claims action without acknowledgment | Simulated devices first; a specific tested local hardware contract only if useful |
| High | Hardcoded fan/gate actuation is independent of validated incident state | A stale plan triggers the wrong device action | No real facility control tools; current-revision policy and acknowledgment for any demo hardware |
| Medium | Prescribed first failure and second success in the pitch | Canned logs do not match the actual solve | Display actual tool/validator events; clearly identify a naïve baseline |
| Medium | Claimed win rates/judge preferences have no causal methodology | Scope follows prize theater rather than product reliability | Build around observable user behavior; do not repeat odds or guaranteed scores |

Current official documentation confirms Argon and managed agents exist. The review therefore does not treat their existence as fabricated. It corrects the agent ID/configuration and requires a real account-level compatibility spike. Similarly, current examples document `interaction.steps` and `output_text`; the issue is using an untested provider shape as the application's state model.

## 3. Architecture debate

### Challenge: “A browser floorplan is less impressive than physical robotics.”

**Case for hardware:** a tangible response is memorable and can demonstrate an end-to-end device interface.

**Case against depending on it:** wiring, drivers, power, camera placement and actuator mechanics add separate failure modes. None solves the main question of whether changed geometry/hazards lead to a correct changed allocation.

**Decision:** primary demo is software with audience-controlled changes. A printed map and flat tokens are an optional grounding input. Simulated door/LED states show the command contract. Add a tested indicator or servo only when the local demonstration is already stable.

**Revisit trigger:** the customer problem or event requirement explicitly depends on a particular device action, and that device has a tested interface.

### Challenge: “The model should infer the entire world directly from live video.”

**Case for model-first reconstruction:** richer onboarding and stronger multimodal reasoning.

**Counterargument:** video does not automatically establish metric scale, hidden topology, live door mechanics, person identity or reliable occupancy. A plausible 3D image can conceal a wrong navigation graph.

**Decision:** authoritative declared map; model-produced observations/proposals; explicit calibration for planar position; human review for new topology. Show source and uncertainty separately.

**Revisit trigger:** measured held-out geometry/perception performance is adequate for the intended input class, with a documented rejection path.

### Challenge: “Use managed agents to generate and repair the solver live.”

**Case for dynamic code:** showcases coding capabilities and self-correction.

**Counterargument:** changes to the numerical model would be unreviewed at precisely the moment the output is supposed to be trusted. Package installation, code edits and cloud latency become part of every incident.

**Decision:** pinned solver and independent validator; managed agent selects allowed experiments, executes fixed tools and explains checked artifacts. Any future solver changes happen in an offline engineering workflow with regression review.

**Revisit trigger:** the product is specifically a simulation-development assistant rather than an operational scenario workbench.

### Challenge: “Multiple specialist agents are the best architecture.”

**Case for specialists:** perception, investigation and reporting have different prompts and tools.

**Counterargument:** multiple prompts do not establish independent truth. More agents introduce latency, inconsistent snapshots and larger debugging surfaces. Numeric constraints remain deterministic regardless of agent count.

**Decision:** one bounded managed investigation plus direct model interpretation. Use ordinary software modules for graph compilation, optimization and validation. Add agents only when a concrete independent task produces measurable benefit.

### Challenge: “Use a proper fire/crowd simulator from the beginning.”

**Case for scientific engines:** stronger physical models and existing research tooling.

**Counterargument:** engines require suitable source conditions, geometry, parameters and calibration. A fire simulator does not infer those inputs from a colored card. Pedestrian motion and route allocation are different modeling problems.

**Decision:** explicit synthetic hazard envelope and constrained flow first; later compare against JuPedSim/PedPy and prebuilt CFAST/FDS scenarios. Avoid claiming physical fidelity from a particle effect.

### Challenge: “Cloud deployment and microservices make it production-ready.”

**Case for services:** independent scaling, shared access and managed availability.

**Counterargument:** an event demo needs deterministic startup, state consistency and a short debugging loop. A distributed architecture does not validate a mistaken map or solver.

**Decision:** local modular monolith with explicit interfaces. Add authentication, shared storage, durable workers and PostgreSQL when shared deployment creates those needs.

## 4. A flaw found in the revised architecture — and the stronger formulation

The initial research proposal maximized successful flow, then minimized its cost. A skeptical review asked: **where are the people who did not receive an exit route?** If they are omitted from the time-expanded graph, their occupancy disappears. That can make shared space appear freer than it is.

A narrow workaround could reserve every remaining person in a non-transit source room. The final plan uses a stronger all-population formulation instead:

1. Inject every person into the occupancy network at time zero.
2. Allow only two outcomes: successful exit, or physically accounted presence at the horizon.
3. In pass one, maximize exit count using an exact `−1` exit reward with no competing costs.
4. In pass two, fix those exited/remaining totals and minimize the schedule cost.
5. Decompose and validate both kinds of paths, including every waiting and transit slot.

The NetworkX 3.7 experiment returned the expected 12/6/0 exit totals for two/one/zero exits, while retaining the remaining room occupancy. This verifies a small fixture, not the full building compiler.

Hazards create a second subtlety: deleting the wait state of a trapped person would also delete their physical presence. The final MVP keeps physical holding but permanently disables hazardous movement and exit connections. People who remain after their cell becomes hazardous are labeled unresolved/potentially exposed. They cannot rejoin a successful path. Temporary hazard reopening or exposure-dose tracking needs a richer state model and is deferred.

This is why a green global “safe” badge is inappropriate. The product must distinguish successful-path constraint validity, complete population accounting, and whether everyone exits within the horizon.

## 5. Adversarial acceptance suite

| Attack | Expected behavior |
|---|---|
| Block every exit | Zero assigned; all occupants remain accounted for; no fabricated route or device action |
| Keep one exit narrow | Throughput respects per-slot quota; remaining occupants still consume space |
| Hazard arrives while a person waits/travels | Successful route is excluded; physical stranded occupancy remains visible |
| Hazard later “clears” | Reject unsupported temporal semantics in MVP or require a richer tested model |
| Two edits arrive while the old solve is running | Current revision invalidates old output immediately; stale result cannot publish |
| Reorder two model responses | Old source revision/timestamp cannot overwrite current state |
| Camera loses anchors or shifts | Calibration invalid/stale; no invented new metric coordinates |
| Token placed on room boundary | Uncertainty gate or explicit review instead of arbitrary room selection |
| Model outputs an unknown door ID or negative count | Reject semantically even if JSON is syntactically valid |
| Imported drawing contains prompt-like instructions | Treat them as input data; no permission/tool expansion |
| Input map is disconnected but geometrically valid | Accept scenario and report unreachable sources |
| Room initially exceeds declared occupancy | Explicit invalid input or visible assumption change; no silent deletion |
| Low service rate rounds below one person/slot | Cumulative integer tokens preserve documented total service; no silent capacity inflation |
| Opposing corridor flows requested | Reject unsupported shared-direction semantics or use predeclared separated lanes |
| Very large map/horizon uploaded | Reject or require an explicit smaller scenario; no unbounded optimizer job |
| Managed agent returns incomplete/failed/malformed artifact | Show its status; local planner remains available; invalid artifact cannot publish |
| Device disconnected | Simulated state stays labeled; no physical success acknowledgment is fabricated |
| Network removed before startup | Local assets/editor/solver start; AI controls show offline |
| Replay launched | Recorded evidence is labeled; replay has its own state/session |

Numerical tests should use hand-computable cases and independent constraints. A test that merely repeats the compiler's own assumptions can miss the same error twice. Include one deliberately corrupted schedule and prove the independent validator rejects it.

## 6. Decisions still requiring evidence

| Unknown | Cheapest experiment | Cut line if it fails |
|---|---|---|
| Actual Argon/agent account access and SDK compatibility | Tiny text/image schema call and environment reuse | Keep supported model path; disclose unavailable managed integration |
| Local solver envelope | Representative graph/horizon on the demo laptop | Explicit smaller supported scenario and deadline; no hidden assumption changes |
| Paper camera accuracy | Held-out flat-token positions and anchor-loss trial | Editor and still-image input |
| IFC conversion correctness | One owned model with measured scale and verified portals | Templates only |
| Agent runtime acceptable on stage | Measure warm/cold/resumed run separately | Start earlier; show live local comparison; label any replay |
| Full occupancy/hazard compiler correctness | All-person path decomposition plus independent interval checks | Reduce map/topology scope; do not remove accounting or no-route behavior |
| Event submission/build rules | Organizer's current instructions | Adjust relative schedule and permitted preparation |

The architecture is ready to implement as a bounded prototype. Its credibility will come from those acceptance gates, a novel audience perturbation, and truthful handling of failure—not the number of integrated tools.
