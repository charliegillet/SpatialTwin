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
  source_kind: 'tabletop_camera' | 'fixture';
  mode: 'live' | 'fixture';
  image_base64?: string;
  fixture_target?: FixtureTarget;
  thinking_level: ThinkingLevel;
  image_sha256?: string;
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
