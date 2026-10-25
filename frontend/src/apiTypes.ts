// Session API shapes. Field names mirror the Python models exactly (snake_case).
import type { Anchor, Measure, VenueGraph } from './types'

export type JobStatus = 'queued' | 'running' | 'done' | 'failed'
export interface JobState { kind: string; status: JobStatus; error: string | null }

export interface PreparedVideo { path: string; sha256: string; duration_s: number; width: number; height: number }

export interface SfmFrame { t_s: number; center: [number, number, number]; R: number[][]; K: number[][] }
export interface SfmResult {
  status: 'completed' | 'failed'
  frames: SfmFrame[]
  points: [number, number, number][]
  registered_fraction: number
  elapsed_ms: number
  error: string | null
}

export interface Alignment {
  scale: number; yaw_rad: number; tx: number; ty: number
  floor_normal: [number, number, number]; floor_offset: number
  residual_m: number; eye_height_m: number; hash: string
}

export interface Hazard { door_id: string; kind: 'fire'; from_s: number }
export interface Scenario { hazards: Hazard[]; interventions: string[] }

export interface FlowParams {
  dt_s: number; horizon_s: number; specific_flow_p_per_m_s: number; boundary_layer_m: number; walk_speed_m_s: number
}

export interface FlowRun {
  run_id: string
  graph_revision: string
  scenario_hash: string
  params: FlowParams
  total: number
  reached_exit: number
  remaining_by_zone: Record<string, number>
  in_transit_end: number
  door_flows: Record<string, number[]>
  zone_occupancy: Record<string, number>[]
  transit_by_step: number[]
  reached_by_step: number[]
}

export interface CheckResult { ok: boolean; run_id: string; violations: string[] }

export interface Finding { code: string; severity: 'error' | 'warning'; element_id: string | null; message: string }

export interface Receipt {
  interaction_id: string; provider_model: string | null; status: string
  usage: Record<string, unknown>; elapsed_ms: number; processing_calls: number
}

export interface Crossing { t_s: number; x: number; y: number; edge: string }
export interface GeometryScore {
  alignment_hash: string
  illegal_crossings: Crossing[]
  wall_support: number
  unexplained_points: number
  edge_chamfer_px: number | null
  edge_within_5px: number | null
  heldout_t_s: number[]
}

export interface RenderedView { t_s: number | null; path: string; kind: 'perspective' | 'top'; url?: string }

export interface Iteration {
  index: number
  graph_revision: string
  discrepancy_count: number
  applied: number[]
  rejected: [number, string][]
  findings: Finding[]
  geometry: GeometryScore | null
  renders: RenderedView[]
  receipt: Receipt | null
  stop_reason: string | null
}

export type VideoMode = 'static' | 'static_hifps' | 'agentic'
export interface ExtractionResult {
  status: 'completed' | 'failed' | 'timeout' | 'invalid'
  graph: VenueGraph | null
  findings: Finding[]
  receipt: Receipt | null
  mode: VideoMode
  agentic_observed: boolean | null
  video_uri: string | null
  error: string | null
}

export interface InterventionResult {
  intervention_id: string; run_id: string; reached_exit: number; total: number
  delta_vs_current: number; check_ok: boolean; limiting_doors: string[]
}
export interface Recommendation {
  intervention_id: string | null; claimed_reached_exit: number | null; rationale: string; caveats: string[]
}
export interface LedgerEntry {
  call_id: string; kind: 'client_function' | 'sandbox_step'; name: string
  args: Record<string, unknown>; result: Record<string, unknown> | null; executed_at: string
}
export interface Investigation {
  investigation_id: string
  graph_revision: string
  scenario_hash: string
  status: 'completed' | 'failed' | 'timeout' | 'incomplete' | 'cancelled'
  interaction_id: string | null
  environment_id: string | null
  ledger: LedgerEntry[]
  sandbox_runs: number
  results: InterventionResult[]
  recommendation: Recommendation | null
  best: InterventionResult | null
  disagreement: string | null
  hook_denials: number
  receipt: Receipt | null
}

export interface Approval {
  intervention_id: string; investigation_id: string; graph_revision: string
  scenario_hash: string; run_id: string; note_path: string; approved_at: string
}

export interface GhostPoint { t_s: number; x: number; y: number }

export interface Snapshot {
  id: string
  video: PreparedVideo
  anchor: Anchor | null
  sfm: SfmResult | null
  alignment: Alignment | null
  draft_graph: VenueGraph | null
  accepted_graph: VenueGraph | null
  scenario: Scenario
  current_run: FlowRun | null
  current_check: CheckResult | null
  iterations: Iteration[]
  extraction: ExtractionResult | null
  investigations: Investigation[]
  approvals: Approval[]
  jobs: Record<string, JobState>
  ghost_path: GhostPoint[]
  // Derived fields the backend may add (Python `revision`/`hash` are properties,
  // not dumped). When absent, api.ts falls back to the run and the iterations.
  graph_revision?: string | null
  draft_revision?: string | null
  scenario_hash?: string | null
  findings?: Finding[]
  allowed_interventions?: string[]
}

export interface RuleResult {
  rule_id: string; element_id: string; statement: string; threshold_m: number
  measured: Measure | null; status: 'pass' | 'fail' | 'cannot_measure'; reason: string | null; citation: string
}
export interface Requirement {
  id: string; statement: string
  method: 'measured' | 'checker' | 'model_reported' | 'outside_model'
  status: 'pass' | 'fail' | 'cannot_measure' | 'not_run'
  value: string | null; evidence: string
}
export interface Report {
  session_id: string; graph_revision: string; scenario_hash: string; run_id: string
  verdict: 'verified_within_model' | 'failed' | 'incomplete'
  requirements: Requirement[]; rules: RuleResult[]; hand_checks: string[]
  declared_parameters: Record<string, unknown>; provenance: string[]
  /** Optional: the drafted note to security, if the backend includes it. */
  security_note?: string | null
}
