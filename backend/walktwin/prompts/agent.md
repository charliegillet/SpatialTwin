WalkTwin what-if investigation $investigation_id
Graph revision $graph_revision, scenario $scenario_hash.

Task: find which single allowed door change lets the most people reach a modeled
exit in $horizon_s s under the hazard below. Sweep in the sandbox (skill `sweep`),
shortlist at most 4 allowed ids, call `evaluate_interventions` once, then call
`submit_recommendation` once. Follow the copy rules in AGENTS.md.

Zones (id, name, occupants, rect x,y,w,h in m):
$zones

Doors (id, a -> b, kind, state, clear width low-high m and basis, position):
$doors

Hazards: $hazards
Current scenario interventions: $interventions

Checker verified, current scenario: $reached_exit/$total reach a modeled exit in $horizon_s s.

Allowed interventions: $allowed

Declared parameters (model assumptions, not measurements): $params

Files: /workspace/accepted_graph.json (read-only), /workspace/scenario.json.
If /workspace/scenario.json is missing, write this JSON to it:
$scenario_json

The attached image is the top-down render of the twin with the hazard drawn in.
Sandbox numbers are unverified; only `evaluate_interventions` figures go on screen.
