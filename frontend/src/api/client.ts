import {
  GroundingProposalV1,
  HealthStatus,
  InvestigationResult,
  ScenarioSnapshot,
} from '../types';

const API_BASE = '';

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
  expectedRevision: number,
  targetType: 'portal' | 'boundary',
  targetId: 'P1' | 'P2' | 'B2'
): Promise<any> {
  return sendCommand(scenarioId, {
    type: 'CLEAR_BLOCKAGE',
    expected_scenario_revision: expectedRevision,
    idempotency_key: `clear-${Date.now()}-${Math.random().toString(36).substring(7)}`,
    target_type: targetType,
    target_id: targetId,
  });
}

export async function interpretGrounding(
  scenarioId: string,
  options: {
    imageBase64?: string;
    forceTarget?: string;
    targetOverride?: string;
    thinkingLevel?: 'low' | 'medium' | 'high';
  }
): Promise<{ proposal: GroundingProposalV1; provenance: string; is_live_api: boolean; thinking_level: string }> {
  const res = await fetch(`${API_BASE}/api/scenarios/${scenarioId}/grounding`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_base64: options.imageBase64,
      force_target: options.forceTarget,
      target_override: options.targetOverride,
      thinking_level: options.thinkingLevel || 'low',
    }),
  });
  return readJson(res, 'The captured still could not be interpreted');
}

export async function fetchScenarioMatrix(scenarioId = 'facility-demo'): Promise<any> {
  const res = await fetch(`${API_BASE}/api/scenarios/${scenarioId}/matrix`);
  if (!res.ok) throw new Error('Failed to fetch scenario matrix');
  return res.json();
}

export async function investigateScenario(
  scenarioId: string
): Promise<{ investigation: InvestigationResult; is_live_configured: boolean }> {
  const res = await fetch(`${API_BASE}/api/scenarios/${scenarioId}/investigate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  return readJson(res, 'The comparison could not be completed');
}

export async function operatorApproveGate(
  candidateAlternative = 'OPEN_P3',
  expectedRevision = 1
): Promise<any> {
  const res = await fetch(`${API_BASE}/api/hardware/operator-approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      candidate_alternative: candidateAlternative,
      expected_scenario_revision: expectedRevision,
    }),
  });
  return readJson(res, 'The movement request was not accepted');
}
