import type {
  CaptureRequest,
  GroundingResult,
  HealthStatus,
  InvestigationResult,
  ScenarioSnapshot,
  RunContext,
  InvestigationMode,
  InvestigationProgress,
  ReserveBasis,
  ScenarioLabResult,
  AiCapabilities,
  HazardSimulateRequest,
  HazardSimulateResponse,
} from '../types.ts';

const API_BASE = '';

export async function fetchScenarioLab(context: RunContext, reserveBasis: ReserveBasis, signal?: AbortSignal): Promise<ScenarioLabResult> {
  const response = await fetch(`${API_BASE}/api/scenarios/facility-demo/lab`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ expected_context: context, reserve_basis: reserveBasis }),
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(30_000)]) : AbortSignal.timeout(30_000),
  });
  return readJson(response, 'Scenario lab could not finish');
}

async function readJson(res: Response, fallback: string) {
  if (res.ok) return res.json();
  let detail = '';
  if (res.headers.get('content-type')?.includes('application/json')) {
    try { const body = await res.json(); detail = typeof body.detail === 'string' ? body.detail : ''; }
    catch { /* The status below still explains an unreadable error response. */ }
  }
  throw new Error(detail || `${fallback} (${res.status}). Please try again.`);
}

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

export async function fetchScenario(scenarioId = 'facility-demo'): Promise<ScenarioSnapshot> {
  const res = await fetch(`${API_BASE}/api/scenarios/${scenarioId}`);
  if (!res.ok) throw new Error('Failed to fetch scenario snapshot');
  return res.json();
}

export async function sendCommand(
  scenarioId: string,
  payload: Record<string, any>
): Promise<any> {
  const res = await fetch(`${API_BASE}/api/scenarios/${scenarioId}/commands`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return readJson(res, 'The scenario change could not be applied');
}

export async function clearBlockage(
  scenarioId: string,
  expectedContext: RunContext,
  targetType: 'portal' | 'boundary',
  targetId: 'P1' | 'P2' | 'B2'
): Promise<any> {
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

export async function interpretGrounding(
  scenarioId: string,
  capture: CaptureRequest,
): Promise<GroundingResult> {
  const res = await fetch(`${API_BASE}/api/scenarios/${scenarioId}/grounding`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(capture),
    signal: AbortSignal.timeout(65_000),
  });
  return readJson(res, 'The captured still could not be interpreted');
}

export async function fetchScenarioMatrix(scenarioId = 'facility-demo'): Promise<any> {
  const res = await fetch(`${API_BASE}/api/scenarios/${scenarioId}/matrix`);
  if (!res.ok) throw new Error('Failed to fetch scenario matrix');
  return res.json();
}

export async function investigateScenario(
  scenarioId: string,
  expectedContext: RunContext,
  mode: InvestigationMode,
  investigationId: string,
): Promise<{ investigation: InvestigationResult; is_live_configured: boolean }> {
  const res = await fetch(`${API_BASE}/api/scenarios/${scenarioId}/investigate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode, expected_context: expectedContext, deadline_seconds: 60, investigation_id: investigationId }),
    signal: AbortSignal.timeout(65_000),
  });
  return readJson(res, 'The comparison could not be completed');
}

export async function fetchInvestigationProgress(scenarioId: string, investigationId: string, signal?: AbortSignal): Promise<InvestigationProgress> {
  const res = await fetch(`${API_BASE}/api/scenarios/${scenarioId}/investigations/${encodeURIComponent(investigationId)}/progress`, { signal });
  if (res.status === 404) return { investigation_id: investigationId, status: 'not_found', provider_progress: [] };
  return readJson(res, 'Analysis progress could not be loaded');
}

export async function cancelInvestigation(scenarioId: string, investigationId: string, expectedContext: RunContext): Promise<{ status: 'cancellation_requested' | 'already_finished'; investigation?: InvestigationResult }> {
  const res = await fetch(`${API_BASE}/api/scenarios/${scenarioId}/investigations/${encodeURIComponent(investigationId)}/cancel`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ expected_context: expectedContext }), signal: AbortSignal.timeout(10_000),
  });
  return readJson(res, 'The cancellation request could not be confirmed');
}

export async function operatorApproveGate(
  expectedContext: RunContext,
  investigationId: string,
  candidateRunId: string,
): Promise<any> {
  const res = await fetch(`${API_BASE}/api/hardware/operator-approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      candidate_alternative: 'OPEN_P3',
      expected_scenario_revision: expectedContext.scenario_revision,
      expected_context: expectedContext,
      investigation_id: investigationId,
      candidate_run_id: candidateRunId,
      idempotency_key: crypto.randomUUID(),
    }),
  });
  return readJson(res, 'The movement request was not accepted');
}

export async function getCapabilities(signal?: AbortSignal): Promise<AiCapabilities> {
  const res = await fetch(`${API_BASE}/api/ai/capabilities`, {
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(10_000)]) : AbortSignal.timeout(10_000),
  });
  return readJson(res, 'AI capabilities could not be read');
}

/** 422 bodies carry {detail: {code}}; the code is surfaced, never free text from the server. */
export async function simulateHazard(body: HazardSimulateRequest, signal?: AbortSignal): Promise<HazardSimulateResponse> {
  const res = await fetch(`${API_BASE}/api/hazard/simulate`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(30_000)]) : AbortSignal.timeout(30_000),
  });
  if (res.status === 422) {
    let code = 'invalid_request';
    try { const detail = (await res.json())?.detail; if (typeof detail?.code === 'string') code = detail.code; } catch { /* keep the generic code */ }
    throw new Error(`The hazard schedule was rejected (${code.replace(/_/g, ' ')}).`);
  }
  return readJson(res, 'The hazard simulation could not finish');
}
