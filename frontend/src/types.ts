export interface RunContext {
  state_epoch?: string;
  geometry_revision: string;
  scenario_revision: number;
  physical_revision: number;
  parameters_revision: string;
  solver_version: string;
  context_hash?: string;
}

export type EntityType = 'portal' | 'boundary';
export type TargetId = 'P1' | 'P2' | 'B2';
export type AlternativeId = 'KEEP_CURRENT' | 'OPEN_P3';
export type GateObservedState = 'OPEN' | 'CLOSED' | 'TRANSIT' | 'UNKNOWN' | 'FAULT';
export type GroundingStatus = 'matched' | 'ambiguous' | 'no_match';
export type ThinkingLevel = 'low' | 'medium' | 'high';
export type FixtureTarget = TargetId | 'ambiguous' | 'no_match';
export type InvestigationMode = 'live' | 'local';

export interface CaptureRequest {
  capture_id: string;
  timestamp_iso: string;
  dimensions: [number, number];
  source_context: RunContext;
  source_kind: 'tabletop_camera' | 'annotated_plan' | 'fixture';
  mode: 'live' | 'fixture';
  image_base64?: string;
  fixture_target?: FixtureTarget;
  thinking_level: ThinkingLevel;
  image_sha256?: string;
  deadline_seconds?: number;
  /** Video clips travel in video_base64 (up to 12M chars) with video_mime set; the default is an image still. */
  video_base64?: string;
  media_kind?: MediaKind;
  video_mode?: VideoMode;
  video_mime?: string;
  video_duration_seconds?: number;
}

export interface CaptureEvidence extends CaptureRequest { image_sha256?: string; }

export interface GroundingResult {
  proposal?: GroundingProposalV1 | null;
  proposal_id?: string | null;
  provenance: 'live' | 'fixture' | 'unavailable';
  status: 'completed' | 'failed' | 'unavailable' | 'timed_out' | 'cancelled';
  errors: string[];
  provider_interaction_id?: string | null;
  provider_model?: string | null;
  token_usage: Record<string, number>;
  latency_ms: number;
  sdk_version?: string | null;
}

export interface ValidatorReport {
  is_valid: boolean;
  checks_run: string[];
  reasons: string[];
  conservation_verified: boolean;
  unassigned_accounted: boolean;
  capacities_respected: boolean;
  quota_respected: boolean;
}

export interface TimelineStep {
  step: number;
  time_seconds: number;
  event_occupancy: number;
  west_occupancy: number;
  east_occupancy: number;
  reserve_occupancy: number;
  in_transit_occupancy?: number;
  b1_cumulative: number;
  b2_cumulative: number;
  total_completed: number;
}

export interface EvaluationEnvelope {
  run_id: string;
  base_context: RunContext;
  candidate_hash: string;
  alternative_id: AlternativeId;
  status: string;
  initial_population: number;
  completed_crossings: number;
  remaining_population: number;
  horizon_seconds: number;
  time_step_seconds: number;
  boundary_breakdown: Record<string, number>;
  zone_occupancy: Record<string, number>;
  timeline?: TimelineStep[];
  bottlenecks: string[];
  assumptions: string[];
  validator_report: ValidatorReport;
  timings_ms: number;
  provenance: string;
}

export interface GroundingProposalV1 {
  version: string;
  capture_id: string;
  source_context: RunContext;
  status: GroundingStatus;
  candidate_ids: string[];
  selected_entity_type?: EntityType | null;
  selected_entity_id?: string | null;
  operation: string;
  evidence: string;
  box_2d?: [number, number, number, number] | null;
}

export interface ToolCallLedgerEntry {
  call_id: string;
  function_name: string;
  arguments: Record<string, any>;
  status: 'requested' | 'executed' | 'failed' | 'duplicate';
  result?: Record<string, any>;
  error?: string | null;
  execution_time_ms: number;
}

export interface InvestigationResult {
  investigation_id: string;
  base_context: RunContext;
  configured_agent: string;
  configured_model: string;
  status: string;
  candidate_envelopes: EvaluationEnvelope[];
  recommended_alternative?: AlternativeId | null;
  tool_ledger: ToolCallLedgerEntry[];
  agent_explanation: string;
  token_usage: Record<string, number>;
  deadline_seconds: number;
  errors?: string[];
  provenance?: 'live' | 'local' | 'unavailable';
  provider_interaction_id?: string | null;
  provider_environment_id?: string | null;
  provider_model?: string | null;
  sdk_version?: string | null;
  latency_ms?: number;
  replayed?: boolean;
  last_provider_status?: string | null;
  provider_progress?: ProviderProgress[];
}

export interface ProviderProgress {
  elapsed_ms?: number;
  phase: string;
  data?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface InvestigationProgress {
  investigation_id: string;
  status: 'running' | 'completed' | 'failed' | 'incomplete' | 'cancelled' | 'timed_out' | 'not_found';
  provider_progress: ProviderProgress[];
  investigation?: InvestigationResult | null;
}

export interface ScenarioSnapshot {
  context: RunContext;
  blocked_portals: string[];
  blocked_boundaries: string[];
  physical_gate_state: GateObservedState;
  last_hardware_boot_id?: string;
  last_gate_epoch?: number;
  current_plan?: EvaluationEnvelope | null;
  timestamp_iso: string;
}

export interface HealthStatus {
  status: string;
  investigation_running?: boolean;
  live_api_configured: boolean;
  hardware_mode: string;
  serial_port: string;
  current_context: RunContext;
  physical_gate_state: GateObservedState;
  ai?: {
    direct: { configured: boolean; verified: boolean };
    managed: { configured: boolean; verified: boolean };
    fixtures_enabled: boolean;
  };
}

export type ReserveBasis = 'reported' | 'closed_benchmark';
export type ScenarioCaseId = 'baseline' | 'p1_blocked' | 'p2_blocked' | 'b2_blocked';
export interface ScenarioLabCase {
  id: ScenarioCaseId;
  title: string;
  blocked_portals: string[];
  blocked_boundaries: string[];
  keep_current: EvaluationEnvelope;
  open_p3: EvaluationEnvelope;
  net_gain: number | null;
  comparable: boolean;
  reasons: string[];
}
export interface ScenarioLabResult {
  base_context: RunContext;
  generated_at_iso: string;
  hypothetical: true;
  provenance: 'local_scenario_lab';
  reserve_basis: ReserveBasis;
  p3_physical_open: boolean;
  cases: ScenarioLabCase[];
  comparable: boolean;
  errors: string[];
}

export type MediaKind = 'image' | 'video';
export type VideoMode = 'static' | 'agentic';

export interface AiCapabilities {
  video_static: boolean;
  video_agentic: boolean;
  managed_model: string | null;
  managed_model_fallback: boolean;
  receipts_source: string;
  /** Optional: age of the newest completed live receipt, when the server reports it. */
  last_live_receipt_age_seconds?: number | null;
  last_live_receipt_at?: string | null;
}

export type HazardAlternativeId = 'KEEP_CURRENT' | 'OPEN_P3';
export interface HazardClosureEvent { element_id: string; close_at_s: number; }
export interface HazardSimulateRequest { alternative_id: HazardAlternativeId; events: HazardClosureEvent[]; }
export interface HazardSimulateResponse {
  tool: string;
  alternative_id: HazardAlternativeId;
  is_valid: boolean;
  reasons: string[];
  status: string;
  completed_crossings: number;
  remaining_population: number;
  baseline_completed_crossings: number;
  modeled_exposure_people_seconds: number;
  exposure_label: string;
  /** Per-boundary crossings of this forecast (B1, B2). Older servers omit it. */
  boundary_breakdown?: Record<string, number>;
}

export interface CommandResponse { snapshot: ScenarioSnapshot; [key: string]: unknown; }
export interface OperatorApproveResponse {
  status: 'APPROVED_AND_COMMANDED';
  acknowledged: boolean;
  command_id: string;
  target: string;
  operator?: string;
  notice?: string;
}
export interface ResetGateResponse { status: 'ALREADY_CLOSED' | 'CLOSE_ACKNOWLEDGED'; command_id?: string; }
export interface StopResponse { status: 'STOP_ACKNOWLEDGED'; command_id: string; }
