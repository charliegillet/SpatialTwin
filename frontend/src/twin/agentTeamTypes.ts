import type { DoorStateMap } from './types.ts';

/** Wire and state types for the managed-agent team (docs/plans/contracts/agent-team.md). Kept out of twin/types.ts, which the lead owns. */
export type TeamLane = 'strategist' | 'robustness' | 'followup';
export const TEAM_LANES: readonly TeamLane[] = ['strategist', 'robustness', 'followup'];
export type TeamMode = 'live' | 'local';
export type LaneStatus = 'running' | 'completed' | 'failed' | 'incomplete' | 'cancelled' | 'timed_out';

export interface ClaimCheck {
  index?: number;
  scenario: string;
  applies_to: 'recommended' | 'fallback';
  claimed_completed_crossings: number | null;
  claimed_candidate_hash?: string | null;
  local_completed_crossings: number | null;
  local_candidate_hash?: string | null;
  local_is_valid?: boolean | null;
  reproduced: boolean;
  reason: string | null;
  /** `sandbox` when the claimed number appeared in this run's code output; otherwise the agent's own statement. */
  provenance?: 'sandbox' | 'agent';
}

export interface LaneVerification {
  verified: number;
  total: number;
  /** `sandbox`: numbers the agent computed in its sandbox; `agent`: numbers it claimed in its submission; `local`: the checker's own self-check (not agent evidence). */
  source: 'agent' | 'sandbox' | 'local';
  mismatches: ClaimCheck[];
  checks?: ClaimCheck[];
  /** Reproduced claims whose number came from sandbox output. */
  sandbox_matched?: number;
}

export interface CostEstimate { usd: number; input_tokens: number; cached_tokens?: number; output_tokens: number; basis?: string }

export interface LaneView {
  investigation_id: string;
  lane: TeamLane;
  status: LaneStatus;
  provenance?: 'live' | 'local' | 'unavailable';
  label?: string;
  recommended_door_states?: DoorStateMap | null;
  fallback_if_jammed?: DoorStateMap | null;
  recommended_ties_checked_best?: boolean | null;
  agrees_with_checker?: boolean;
  agreement_note?: string;
  explanation?: string;
  robustness_headline?: string;
  verification?: LaneVerification | null;
  token_usage?: Record<string, number>;
  token_budget?: number;
  cost_estimate?: CostEstimate | null;
  deadline_at_ms?: number;
  latency_ms?: number;
  errors?: string[];
  scenario?: string | null;
  sandbox?: { available?: boolean; network?: string; mount?: string } | null;
  fallback_for?: { investigation_id?: string; status?: string; errors?: string[] } | null;
  fallback?: LaneView | null;
  effective?: 'live' | 'local' | 'local_fallback' | 'none';
}

export interface LaneDeadline { investigation_id: string; deadline_seconds: number; deadline_at_ms: number }

export interface TeamStart {
  investigation_id: string;
  deadline_at_ms: number;
  lanes: Partial<Record<TeamLane, LaneDeadline>>;
  trace_url: string;
  parent_investigation_id?: string | null;
  scenario?: string | null;
}

export interface TeamProgress {
  investigation_id: string;
  status: string;
  team_status: 'running' | 'finished' | 'cancelled';
  deadline_at_ms: number | null;
  /** A lane that is still running is only a stub (`status: 'running'`), so `LaneView` fields are optional there. */
  lanes: Partial<Record<TeamLane, LaneView>>;
  trace_url: string | null;
  parent_investigation_id: string | null;
}

export type TraceEventName = 'deadline' | 'lane' | 'status' | 'delta' | 'step' | 'tool' | 'verification' | 'usage' | 'retry' | 'stream' | 'fallback' | 'result' | 'done';
export const TRACE_EVENT_NAMES: readonly TraceEventName[] = ['deadline', 'lane', 'status', 'delta', 'step', 'tool', 'verification', 'usage', 'retry', 'stream', 'fallback', 'result', 'done'];

/** Every frame carries `{seq, event, lane, elapsed_ms}`; the event-specific fields stay in `data` and are read defensively by the flow. */
export interface TraceEvent {
  seq: number;
  event: TraceEventName;
  lane: TeamLane | null;
  elapsed_ms: number;
  data: Record<string, unknown>;
}

export type TraceKind = 'code' | 'result' | 'output' | 'call' | 'tool' | 'status' | 'note' | 'error';
export interface TraceLine {
  /** Stable key so a delta-built line is replaced by its durable `step` frame instead of duplicated. */
  key: string;
  kind: TraceKind;
  atMs: number;
  /** Function name for calls and tools. */
  name?: string;
  text: string;
  isError?: boolean;
  /** True while the line is built from live deltas and not yet confirmed by a durable step frame. */
  partial?: boolean;
}

export type RunStatus = 'idle' | 'starting' | 'running' | 'done' | 'failed' | 'cancelled';
export type LanePhase = 'waiting' | 'running' | 'plan_ready' | 'completed' | 'failed' | 'cancelled' | 'timed_out' | 'incomplete';
export type TraceConnection = 'idle' | 'connecting' | 'live' | 'polling' | 'offline' | 'closed';

export interface LiveUsage { token_usage: Record<string, number>; token_budget: number | null; cost_estimate: CostEstimate | null }

export interface LaneState {
  lane: TeamLane;
  phase: LanePhase;
  investigationId: string | null;
  deadlineMs: number | null;
  /** Local epoch ms when the lane started, for the elapsed display. */
  startedAt: number | null;
  trace: TraceLine[];
  /** Lines dropped from the front of the bounded list. */
  droppedLines: number;
  statesChecked: number | null;
  view: LaneView | null;
  /** The labelled local result that replaced a failed live lane. */
  fallbackView: LaneView | null;
  /** Why the live lane failed; stays visible next to the fallback. */
  fallbackReason: { status: string; errors: string[] } | null;
  verification: LaneVerification | null;
  usage: LiveUsage | null;
}

export interface TeamRun {
  status: RunStatus;
  mode: TeamMode | null;
  teamId: string | null;
  hazardsKey: string;
  /** Local epoch ms at Ask; countdown anchor when the server's clock disagrees with ours. */
  startedAt: number | null;
  deadlineMs: number | null;
  lanes: Partial<Record<TeamLane, LaneState>>;
  order: TeamLane[];
  lastSeq: number;
  connection: TraceConnection;
  error: string | null;
  /** A non-error line while a start is retried (follow-up 409 parent_finishing). */
  notice: string | null;
  scenario: string | null;
  parentId: string | null;
}
