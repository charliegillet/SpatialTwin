// Frozen contract for the building-v2 twin (Simulation and Camera twin modes).
// The backend (backend/app/venues/) is canonical; these types mirror it field for field.
// Units are metres: x grows east, y grows north, origin at the south-west corner.

export type HazardType = 'FIRE' | 'SMOKE' | 'GAS' | 'CHEMICAL' | 'WATER';
export const HAZARD_TYPES: readonly HazardType[] = ['FIRE', 'SMOKE', 'GAS', 'CHEMICAL', 'WATER'];

export type Point2 = [number, number];
export type DoorActuation = 'hold_open' | 'simulated_servo' | 'motorized' | 'indicator_only' | 'fixed';
export type DoorKind = 'fire_door' | 'smoke_door' | 'room_door' | 'servo_door' | 'roller_door' | 'opening';

// GET /api/venues/building-v2
export interface VenueZone {
  id: string;
  name: string;
  max_capacity: number;
  initial_occupants: number;
  polygon: Point2[];
}
export interface VenueDoor {
  id: string;
  zones: [string, string];
  position: Point2;
  width: number;
  throughput_per_sec: number;
  travel_time_seconds: number;
  default_state: 'open' | 'closed';
  kind: DoorKind;
  actuation: DoorActuation;
  planner_can_open: boolean;
  note?: string;
}
export interface VenueExit {
  id: string;
  zone: string;
  name: string;
  position: Point2;
  width: number;
  service_rate_per_sec: number;
}
export interface HazardDefaults {
  untenable_s?: number;
  throughput_multiplier?: number;
  travel_multiplier?: number;
}
export interface VenueV2 {
  schema_version: '2.0.0';
  venue_id: 'building-v2';
  geometry_revision: string;
  provenance: string;
  units: 'm';
  extent: Point2;
  default_horizon_seconds: number;
  time_step_seconds: number;
  zones: VenueZone[];
  doors: VenueDoor[];
  exits: VenueExit[];
  led_map: Record<string, [number, number]>;
  hazard_defaults: Record<HazardType, HazardDefaults>;
}

// POST /api/venues/building-v2/door-plan
export interface HazardInput {
  id: string;
  type: HazardType;
  position: { x: number; y: number };
  /** Optional; when given it must match the zone that contains `position` (422 zone_mismatch otherwise). */
  zone_id?: string | null;
  source: 'simulated' | 'camera';
  /** Seconds until the zone is untenable. Even, 0 <= T < horizon. Defaults from venue.hazard_defaults; ignored for WATER. */
  untenable_s?: number | null;
  proposal_id?: string | null;
}
export interface DoorPlanRequest {
  hazards: HazardInput[];
  horizon_seconds?: number;
}

export type ZoneStatus = 'passable' | 'slowed' | 'no_entry';
export type DoorLamp = 'green' | 'red' | 'red_static' | 'off';
export type ExitLamp = 'green_flash' | 'green' | 'red_x' | 'red_static';
export type DecidedBy = 'default' | 'hazard_rule' | 'door_planner' | 'gas_lock';

export interface HazardEcho extends HazardInput {
  zone_id: string;
  /** False when a higher-precedence hazard in the same zone decides the zone status. */
  effective: boolean;
  effects: string[];
  /** Provenance of the confirmed camera read this hazard came from; null for simulated hazards. */
  camera_provenance?: 'live' | 'fixture' | null;
}
export interface PlanDoor {
  id: string;
  state: 'open' | 'closed';
  lamp: DoorLamp;
  /** Zones that may not be entered through this door. */
  entry_denied_into: string[];
  reason: string;
  actuation: DoorActuation;
  changed: boolean;
  locked: boolean;
  decided_by: DecidedBy;
}
export interface PlanExit {
  id: string;
  zone: string;
  safe: boolean;
  lamp: ExitLamp;
  reason: string;
  modeled_crossings: number;
}
export interface PlanZone {
  id: string;
  status: ZoneStatus;
  hazard_type: HazardType | null;
  untenable_at_s: number | null;
  throughput_multiplier: number | null;
  initial_occupants: number;
  remaining_at_horizon: number;
}
export interface PlanRoute {
  origin: string;
  path: string[];
  via_doors: string[];
  exit_id: string;
  people: number;
  slowed: boolean;
}
export interface TimelineFrameV2 {
  step: number;
  time_seconds: number;
  occupancy: Record<string, number>;
  exits_cumulative: Record<string, number>;
  in_transit: number;
  total_completed: number;
}
export interface ValidatorReportV2 {
  is_valid: boolean;
  checks_run: string[];
  reasons: string[];
}
export interface PlanOutcome {
  run_id: string;
  candidate_hash: string;
  status: 'COMPLETE_WITHIN_MODEL' | 'PARTIAL_WITHIN_HORIZON' | 'NO_FEASIBLE_EXIT' | 'SOLVER_INFEASIBLE';
  initial_population: number;
  completed_crossings: number;
  remaining_population: number;
  horizon_seconds: number;
  time_step_seconds: number;
  exit_breakdown: Record<string, number>;
  timeline: TimelineFrameV2[];
  validator_report: ValidatorReportV2;
  modeled_exposure_people_seconds: number;
  exposure_label: string;
}
export interface PlanAlternative {
  door_states: Record<string, 'open' | 'closed'>;
  completed_crossings: number;
  modeled_exposure_people_seconds: number;
  is_valid: boolean;
  rank: number;
  run_id: string;
}
export type LightCode = 'F' | 'g' | 'X' | 'S' | 'O' | 'B' | 'L' | '0';
export interface LightSegment {
  element_id: string;
  range: [number, number];
  code: LightCode;
}
export interface PlanLights {
  /** 24 characters, one LightCode per on-screen pixel; mirrors led_map. Screen only for building-v2. */
  px: string;
  segments: LightSegment[];
  /** Element ids whose lights were set static red once because of a gas hazard. */
  held: string[];
}
export interface DoorPlanResponse {
  plan_id: string;
  venue_id: 'building-v2';
  geometry_revision: string;
  hypothetical: true;
  provenance: 'local_door_planner_v1';
  hazards: HazardEcho[];
  doors: PlanDoor[];
  exits: PlanExit[];
  zones: PlanZone[];
  routes: PlanRoute[];
  chosen: PlanOutcome;
  /** Same hazards, every door at its default state; for the "+N" delta. */
  baseline: { completed_crossings: number; run_id: string };
  /** No-hazard reference for the hero ("of 125"). */
  no_hazard_completed: number;
  alternatives: PlanAlternative[];
  lights: PlanLights;
  advisories: string[];
  /** Plain-language restatement of this plan for a simulated announcement; empty with no hazard. */
  announcement: string;
  model_assumptions: string[];
  timings_ms: number;
}

// Placement in the UI (App state). Converted to HazardInput for the request.
export interface PlacedHazard {
  id: string;
  type: HazardType;
  x: number;
  y: number;
  zone_id: string;
  untenable_s: number | null;
  source: 'simulated' | 'camera';
  proposal_id?: string | null;
}

// Camera twin (backend/app/venues/camera.py). Card positions are mapped onto the reviewed floor
// plan through a homography from four printed corner markers; nothing is reconstructed in 3D.
export type CornerId = 'TL' | 'TR' | 'BR' | 'BL';

// POST /api/venues/building-v2/camera/calibration
export interface CalibrationRequest {
  corners_px: Record<CornerId, [number, number]>;
  image_size: [number, number];
}
export interface CalibrationResponse {
  calibration_id: string;
  source: 'clicked';
  reprojection_error_m: number;
  corners_px: Record<CornerId, [number, number]>;
  image_size: [number, number];
}

// POST /api/venues/building-v2/camera/hazard-read
export interface FixtureCard {
  type: HazardType;
  point: [number, number];
  box_2d: [number, number, number, number];
  label_text?: string | null;
}
export interface HazardReadRequest {
  capture_id: string;
  timestamp_iso: string;
  image_base64?: string;
  image_sha256?: string;
  dimensions: [number, number];
  calibration_id?: string | null;
  /** Ask Gemini to point at the four corner markers when no clicked calibration exists. */
  auto_corners?: boolean;
  mode: 'live' | 'fixture';
  fixture_cards?: FixtureCard[];
  thinking_level?: 'low' | 'medium' | 'high';
  deadline_seconds?: number;
}
export type CardRejection = 'no_calibration' | 'outside_building' | 'crosses_building_edge';
export interface CardCandidate {
  candidate_id: string;
  type: HazardType;
  /** [y, x] normalised 0-1000 in the still that was sent. */
  point: [number, number];
  box_2d: [number, number, number, number];
  label_text: string;
  evidence: string;
  confidence: 'high' | 'low';
  low_confidence_reason: string | null;
  floor: { x: number; y: number } | null;
  zone_id: string | null;
  usable: boolean;
  rejected_reason: CardRejection | null;
  confirmed: boolean;
}
export interface HazardReadResponse {
  /** Null unless status is completed; only completed reads can be confirmed. */
  read_id: string | null;
  status: 'completed' | 'failed' | 'timed_out' | 'unavailable' | 'cancelled';
  provenance: 'live' | 'fixture' | 'unavailable';
  errors: string[];
  calibration: { calibration_id: string; source: 'clicked' | 'gemini_corners'; reprojection_error_m: number } | null;
  candidates: CardCandidate[];
  provider_interaction_id: string | null;
  provider_model: string | null;
  token_usage: Record<string, number>;
  latency_ms: number;
  mapping_note: string;
}

// POST /api/venues/building-v2/camera/reads/{read_id}/confirm  body { candidate_ids }
// Only confirmed camera hazards are accepted by the door planner (422 unconfirmed_camera_hazard /
// camera_hazard_mismatch otherwise), so send the returned hazards unchanged.
export interface ConfirmResponse {
  read_id: string;
  provenance: 'live' | 'fixture';
  hazards: (HazardInput & { source: 'camera'; proposal_id: string; zone_id: string })[];
}

// venue/print/sheet_v2.json: where the printed corner markers sit on the floor (metres).
export const SHEET_FIDUCIALS_M: Record<CornerId, [number, number]> = {
  TL: [-2.5, 26.5],
  TR: [42.5, 26.5],
  BR: [42.5, -2.5],
  BL: [-2.5, -2.5],
};

export type TwinMode = 'tabletop' | 'camera' | 'sim';

// Props of the lazily loaded 3D scene (src/scene/TwinScene3D.tsx). The scene never fetches.
export interface TwinScene3DProps {
  venue: VenueV2;
  plan: DoorPlanResponse | null;
  hazards: PlacedHazard[];
  armedType: HazardType | null;
  selectedHazardId: string | null;
  lowGraphics: boolean;
  reducedMotion: boolean;
  /** Floor point in metres where the judge dropped the armed hazard (raw; App validates). */
  onPlace: (point: { x: number; y: number }) => void;
  onSelectHazard: (id: string | null) => void;
}

// --- Door agent (POST /api/venues/building-v2/investigate) -------------------------------------------------------
export type DoorAgentMode = 'live' | 'local';
export type DoorAgentStatus = 'completed' | 'failed' | 'incomplete' | 'cancelled' | 'timed_out' | 'in_progress' | 'requires_action';
export type DoorAgentProvenance = 'live' | 'local' | 'unavailable';
export type DoorStateMap = Record<string, 'open' | 'closed'>;

export interface DoorAgentToolCall {
  call_id: string;
  function_name: string;
  arguments: Record<string, unknown>;
  status: 'requested' | 'executed' | 'failed' | 'duplicate';
  error?: string | null;
  execution_time_ms: number;
}

export interface DoorAgentResult {
  investigation_id: string;
  status: DoorAgentStatus;
  provenance: DoorAgentProvenance;
  free_doors: string[];
  /** The agent's suggestion, or null when it gave none (or the run did not complete). Never applied to the plan. */
  recommended_door_states: DoorStateMap | null;
  /** The local checker's best state. This is what the plan shows. */
  checked_best_door_states: DoorStateMap;
  checked_best_completed: number | null;
  checked_best_is_valid: boolean | null;
  baseline_completed: number | null;
  initial_population: number | null;
  total_states: number;
  agrees_with_checker: boolean;
  /** "Agent suggested X; the checker's best is Y." (or the agreement / no-recommendation variants). */
  agreement_note: string;
  explanation: string;
  tool_ledger: DoorAgentToolCall[];
  token_usage: Record<string, number>;
  provider_interaction_id: string | null;
  provider_model: string | null;
  latency_ms: number;
  errors: string[];
  disclaimer: string;
}

export interface DoorAgentProgressEvent {
  phase: string;
  elapsed_ms?: number;
  status?: string;
  [key: string]: unknown;
}

export interface DoorAgentProgress {
  investigation_id: string;
  /** "running" until the result is saved, then the result's status. */
  status: string;
  provider_progress: DoorAgentProgressEvent[];
  investigation: DoorAgentResult | null;
}
