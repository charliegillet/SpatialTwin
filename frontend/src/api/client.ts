import {
  GroundingProposalV1,
  HealthStatus,
  InvestigationResult,
  ScenarioSnapshot,
} from '../types';

const API_BASE = '';

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
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Command failed');
  }
  return res.json();
}

export async function interpretGrounding(
  scenarioId: string,
  options: {
    imageBase64?: string;
    forceTarget?: string;
    targetOverride?: string;
  }
): Promise<{ proposal: GroundingProposalV1; provenance: string; is_live_api: boolean }> {
  const res = await fetch(`${API_BASE}/api/scenarios/${scenarioId}/grounding`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_base64: options.imageBase64,
      force_target: options.forceTarget,
      target_override: options.targetOverride,
    }),
  });
  if (!res.ok) throw new Error('Grounding perception request failed');
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
  if (!res.ok) throw new Error('Managed investigation request failed');
  return res.json();
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
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Operator approval command failed');
  }
  return res.json();
}
