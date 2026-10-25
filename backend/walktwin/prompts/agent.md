WalkTwin what-if investigation $investigation_id
Graph revision $graph_revision, scenario hash $scenario_hash.
$network

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

Declared parameters (model assumptions, not measurements): $params_json

Inputs for this investigation (write-once, audit-hooked): $inv_dir/graph.json,
$inv_dir/scenario.json, $inv_dir/params.json. Before sweeping, check that
`VenueGraph(...).revision == "$graph_revision"` and `Scenario(...).hash ==
"$scenario_hash"`. If a file is missing, write it from the JSON below. If it is
present but does not match, write the JSON below to $inv_dir/from_prompt/ and use
those copies instead. Never use files from another investigation directory.

graph.json:
$graph_json

scenario.json:
$scenario_json

params.json:
$params_json

The attached image is the top-down render of the twin with the hazard drawn in.
Sandbox numbers are unverified; only `evaluate_interventions` figures go on screen.
