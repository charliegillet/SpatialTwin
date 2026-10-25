export interface RunContext {
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

export interface ValidatorReport {
  is_valid: boolean;
  checks_run: string[];
  reasons: string[];
  conservation_verified: boolean;
  unassigned_accounted: boolean;
  capacities_respected: boolean;
  quota_respected: boolean;
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
}
