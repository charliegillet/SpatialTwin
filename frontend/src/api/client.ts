import type {
  CaptureRequest,
  CommandResponse,
  GroundingResult,
  HealthStatus,
  InvestigationResult,
  ScenarioSnapshot,
  RunContext,
  InvestigationMode,
  InvestigationProgress,
  OperatorApproveResponse,
  ReserveBasis,
  ScenarioLabResult,
  AiCapabilities,
  HazardSimulateRequest,
  HazardSimulateResponse,
  StopResponse,
} from '../types.ts';
import { investigationErrorMessage, operatorErrorMessage, type OperatorAction } from '../ai/operator.ts';

const API_BASE = '';

/** A failed backend call. `detail` is the backend's string detail, `code` its structured detail code if any. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  constructor(message: string, status: number, detail = '') {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST';
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  timeoutMs?: number;
  fallback: string;
  /** Maps a failed response to a user message; an empty string falls back to server detail then the generic text. */
  describe?: (status: number, detail: string, code: string) => string;
}

/** `text` is a string detail; `code` is the code of a structured {detail: {code}} body. */
async function errorDetail(res: Response): Promise<{ text: string; code: string }> {
  if (!res.headers.get('content-type')?.includes('application/json')) return { text: '', code: '' };
  try {
    const detail = (await res.json())?.detail;
    return { text: typeof detail === 'string' ? detail : '', code: typeof detail?.code === 'string' ? detail.code : '' };
  } catch { return { text: '', code: '' }; /* The status still explains an unreadable error response. */ }
}

/** The one place that sets the timeout, serialises the body and turns failures into ApiError. */
export async function requestJson<T>(path: string, { method = 'GET', body, headers, signal, timeoutMs, fallback, describe }: RequestOptions): Promise<T> {
  const signals = [signal, timeoutMs ? AbortSignal.timeout(timeoutMs) : undefined].filter((item): item is AbortSignal => Boolean(item));
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: body === undefined ? headers : { 'Content-Type': 'application/json', ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: signals.length > 1 ? AbortSignal.any(signals) : signals[0],
  });
  if (res.ok) return res.json() as Promise<T>;
  const { text, code } = await errorDetail(res);
  throw new ApiError(describe?.(res.status, text, code) || text || `${fallback} (${res.status}). Please try again.`, res.status, text || code);
}

export const fetchScenarioLab = (context: RunContext, reserveBasis: ReserveBasis, signal?: AbortSignal) =>
  requestJson<ScenarioLabResult>('/api/scenarios/facility-demo/lab', { method: 'POST', body: { expected_context: context, reserve_basis: reserveBasis }, signal, timeoutMs: 30_000, fallback: 'Scenario lab could not finish' });

export const fetchHealth = () => requestJson<HealthStatus>('/health', { fallback: 'Health check failed' });

export const fetchScenario = (scenarioId = 'facility-demo') =>
  requestJson<ScenarioSnapshot>(`/api/scenarios/${scenarioId}`, { fallback: 'Failed to fetch scenario snapshot' });

export type CommandPayload = Record<string, unknown>;

export const sendCommand = (scenarioId: string, payload: CommandPayload) =>
  requestJson<CommandResponse>(`/api/scenarios/${scenarioId}/commands`, { method: 'POST', body: payload, fallback: 'The scenario change could not be applied' });

export function clearBlockage(
  scenarioId: string,
  expectedContext: RunContext,
  targetType: 'portal' | 'boundary',
  targetId: 'P1' | 'P2' | 'B2',
): Promise<CommandResponse> {
  return sendCommand(scenarioId, {
    type: 'CLEAR_BLOCKAGE',
    expected_scenario_revision: expectedContext.scenario_revision,
    expected_context: expectedContext,
    idempotency_key: crypto.randomUUID(),
    source: 'manual_override',
    target_type: targetType,
    target_id: targetId,
  });
}

export const interpretGrounding = (scenarioId: string, capture: CaptureRequest) =>
  requestJson<GroundingResult>(`/api/scenarios/${scenarioId}/grounding`, { method: 'POST', body: capture, timeoutMs: 65_000, fallback: 'The captured still could not be interpreted' });

export const investigateScenario = (scenarioId: string, expectedContext: RunContext, mode: InvestigationMode, investigationId: string) =>
  requestJson<{ investigation: InvestigationResult; is_live_configured: boolean }>(`/api/scenarios/${scenarioId}/investigate`, {
    method: 'POST', body: { mode, expected_context: expectedContext, deadline_seconds: 60, investigation_id: investigationId },
    timeoutMs: 65_000, fallback: 'The comparison could not be completed', describe: investigationErrorMessage,
  });

export async function fetchInvestigationProgress(scenarioId: string, investigationId: string, signal?: AbortSignal): Promise<InvestigationProgress> {
  try {
    return await requestJson<InvestigationProgress>(`/api/scenarios/${scenarioId}/investigations/${encodeURIComponent(investigationId)}/progress`, { signal, fallback: 'Analysis progress could not be loaded' });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return { investigation_id: investigationId, status: 'not_found', provider_progress: [] };
    throw error;
  }
}

export const cancelInvestigation = (scenarioId: string, investigationId: string, expectedContext: RunContext) =>
  requestJson<{ status: 'cancellation_requested' | 'already_finished'; investigation?: InvestigationResult }>(`/api/scenarios/${scenarioId}/investigations/${encodeURIComponent(investigationId)}/cancel`, {
    method: 'POST', body: { expected_context: expectedContext }, timeoutMs: 10_000, fallback: 'The cancellation request could not be confirmed',
  });

const operatorHeaders = (token?: string): Record<string, string> | undefined => token ? { 'X-Operator-Token': token } : undefined;
const describeOperator = (action: OperatorAction) => (status: number, detail: string) => operatorErrorMessage(action, status, detail);

export const operatorApproveGate = (expectedContext: RunContext, investigationId: string, candidateRunId: string, operatorToken?: string) =>
  requestJson<OperatorApproveResponse>('/api/hardware/operator-approve', {
    method: 'POST', headers: operatorHeaders(operatorToken),
    body: {
      candidate_alternative: 'OPEN_P3',
      expected_scenario_revision: expectedContext.scenario_revision,
      expected_context: expectedContext,
      investigation_id: investigationId,
      candidate_run_id: candidateRunId,
      idempotency_key: crypto.randomUUID(),
    },
    fallback: 'The movement request was not accepted', describe: describeOperator('approve'),
  });

export const stopOutputs = (operatorToken?: string) =>
  requestJson<StopResponse>('/api/hardware/stop', {
    method: 'POST', headers: operatorHeaders(operatorToken), body: {}, timeoutMs: 15_000,
    fallback: 'The stop command was not confirmed', describe: describeOperator('stop'),
  });

export const getCapabilities = (signal?: AbortSignal) =>
  requestJson<AiCapabilities>('/api/ai/capabilities', { signal, timeoutMs: 10_000, fallback: 'AI capabilities could not be read' });

/** 422 bodies carry {detail: {code}}; the code is surfaced, never free text from the server. */
export const simulateHazard = (body: HazardSimulateRequest, signal?: AbortSignal) =>
  requestJson<HazardSimulateResponse>('/api/hazard/simulate', {
    method: 'POST', body, signal, timeoutMs: 30_000, fallback: 'The hazard simulation could not finish',
    describe: (status, _text, code) => status === 422 ? `The hazard schedule was rejected (${(code || 'invalid_request').replace(/_/g, ' ')}).` : '',
  });
