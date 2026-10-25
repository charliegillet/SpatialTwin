// Hand-built door-plan response with the contract's shape, for tests that run before the backend fixtures exist.
export function makePlan(over = {}) {
  const base = {
    plan_id: 'plan-1',
    venue_id: 'building-v2',
    geometry_revision: 'r1',
    hypothetical: true,
    provenance: 'local_door_planner_v1',
    hazards: [{ id: 'h1', type: 'FIRE', position: { x: 20, y: 4 }, zone_id: 'LOBBY', source: 'simulated', effective: true, effects: [] }],
    doors: [
      { id: 'D1', state: 'closed', lamp: 'red', entry_denied_into: ['LOBBY'], reason: 'fire in Lobby', actuation: 'hold_open', changed: true, locked: false, decided_by: 'hazard_rule' },
      { id: 'D2', state: 'open', lamp: 'green', entry_denied_into: [], reason: 'default', actuation: 'hold_open', changed: false, locked: false, decided_by: 'default' },
      { id: 'D4', state: 'open', lamp: 'green', entry_denied_into: [], reason: 'opens the north stair route', actuation: 'simulated_servo', changed: true, locked: false, decided_by: 'door_planner' },
      { id: 'D9', state: 'open', lamp: 'green', entry_denied_into: [], reason: 'opens the dock exit', actuation: 'motorized', changed: true, locked: false, decided_by: 'door_planner' },
    ],
    exits: [
      { id: 'E1', zone: 'LOBBY', safe: false, lamp: 'red_x', reason: 'fire in Lobby', modeled_crossings: 0 },
      { id: 'E2', zone: 'STAIR_N', safe: true, lamp: 'green_flash', reason: 'clear', modeled_crossings: 60 },
    ],
    zones: [], routes: [], alternatives: [
      { door_states: { D4: 'open', D9: 'open' }, completed_crossings: 91, modeled_exposure_people_seconds: 10, is_valid: true, rank: 1, run_id: 'run-chosen' },
      { door_states: {}, completed_crossings: 57, modeled_exposure_people_seconds: 30, is_valid: true, rank: 2, run_id: 'run-base' },
    ],
    chosen: { run_id: 'run-chosen', candidate_hash: 'x', status: 'COMPLETE_WITHIN_MODEL', initial_population: 125, completed_crossings: 91, remaining_population: 34, horizon_seconds: 40, time_step_seconds: 2, exit_breakdown: {}, timeline: [], validator_report: { is_valid: true, checks_run: [], reasons: [] }, modeled_exposure_people_seconds: 10, exposure_label: 'modeled' },
    baseline: { completed_crossings: 57, run_id: 'run-base' },
    no_hazard_completed: 125,
    lights: { px: 'FFFFFFXXXXXXgggggggggBBBB'.slice(0, 24), segments: [], held: [] },
    advisories: [],
    model_assumptions: [],
    timings_ms: 12,
  };
  return { ...base, ...over };
}
