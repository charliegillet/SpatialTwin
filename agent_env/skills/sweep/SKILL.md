---
name: sweep
description: What-if sweep over door interventions with the WalkTwin solver in the sandbox, then a shortlist for local verification
---
# Sweep

Use this when asked which allowed door change lets the most people reach a
modeled exit in 120 s.

## Method

1. Load the inputs.

   ```python
   import json, sys
   sys.path.insert(0, "/workspace")
   from walktwin.contracts import VenueGraph, Scenario, FlowParams
   from walktwin import flow
   g = VenueGraph.model_validate_json(open("/workspace/accepted_graph.json").read())
   s = Scenario.model_validate_json(open("/workspace/scenario.json").read())
   p = FlowParams()  # declared: dt 2 s, horizon 120 s, 1.3 p/m/s, 0.15 m layer, 1.2 m/s
   base = flow.solve(g, s, p).reached_exit
   ```

2. Single interventions: for each allowed id, add it to `s.interventions`, solve,
   record `reached_exit - base`.
3. Pairs of allowed ids (for context only; `evaluate_interventions` checks single
   ids).
4. Hazard robustness: move the hazard to each other exit in turn and re-run the
   top singles.
5. Sensitivity: scale the declared `specific_flow_p_per_m_s` and
   `walk_speed_m_s` by 0.8 and 1.2 and re-run the top singles. Note any ranking
   flip.
6. Bottlenecks: for the best single, list doors whose flow equals
   `flow.door_capacity_at_step(door, k, p)` on most steps they carry flow.

Keep each code run short. Write scratch files under `/workspace/work/` only.

## Output

Shortlist at most 4 allowed ids, best first, and call
`evaluate_interventions(ids=[...])` once. Then call `submit_recommendation` with:

- `intervention_id`: the id whose **checker verified** figure is highest and
  above the current figure. Leave it out if none is.
- `claimed_reached_exit`: that id's figure from `evaluate_interventions`, not
  your sandbox figure.
- `rationale`: up to 600 characters, for example: "Argon proposed OPEN:D5. Checker
  verified 58 of 58 reach a modeled exit in 120 s (current 40). Sandbox runs,
  unverified: ranking held under ±20% declared flow and speed."
- `caveats`: up to 5, such as declared parameters, estimated widths, or a ranking
  flip under sensitivity.
