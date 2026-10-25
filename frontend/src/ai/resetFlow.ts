export interface ResetFacts {
  scenarioClear: boolean;
  gateClosedObserved: boolean;
  noRunActive: boolean;
  /** A live camera, or the labelled demo board / fixture when no camera is available. */
  boardReady: boolean;
}
export interface ChecklistItem { id: keyof ResetFacts; label: string; ok: boolean; }

/** Physical hardware needs the live camera; the simulator only needs some board view. */
export function resetChecklist(facts: ResetFacts, physical = false): ChecklistItem[] {
  return [
    { id: 'scenarioClear', label: 'Scenario clear', ok: facts.scenarioClear },
    { id: 'gateClosedObserved', label: 'P3 closed · observed', ok: facts.gateClosedObserved },
    { id: 'noRunActive', label: 'No run active', ok: facts.noRunActive },
    { id: 'boardReady', label: physical ? 'Camera live' : 'Board view ready', ok: facts.boardReady },
  ];
}

export const resetComplete = (facts: ResetFacts, physical = false) => resetChecklist(facts, physical).every(item => item.ok);

/** Names exactly what is still unmet, so the message can never contradict a green item. */
export function pendingMessage(facts: ResetFacts, physical = false): string | null {
  const unmet = resetChecklist(facts, physical).filter(item => !item.ok).map(item => item.label);
  return unmet.length ? `Waiting for: ${unmet.join(', ')}` : null;
}

/** Plain words for a failed reset-gate call. */
export function resetGateError(status: number, detail: string): string {
  if (status === 409 && detail === 'investigation_running') return 'An analysis is still running. Cancel it, then reset.';
  if (status === 403) return 'Operator token not accepted.';
  if (status === 502) {
    const reason = detail.split(':')[1]?.replace(/_/g, ' ').trim();
    return `P3 did not acknowledge the close request${reason && /^[\w .,-]{1,60}$/.test(reason) ? ` (${reason})` : ''}. Retry.`;
  }
  return '';
}

export interface PreflightInput {
  geminiConfigured: boolean;
  /** Seconds since the last completed live receipt, or null/undefined when the server does not report it. */
  receiptAgeSeconds?: number | null;
  hardwareMode: string | null | undefined;
  gateState: string | undefined;
  endpointReported: boolean;
  physical: boolean;
  tokenHeld: boolean;
  cameraLive: boolean;
}
export interface PreflightItem { id: string; label: string; detail: string; ok: boolean; }

const MAX_RECEIPT_AGE_SECONDS = 24 * 3600;

export function ageText(seconds: number): string {
  if (seconds < 90) return `${Math.max(0, Math.round(seconds))} s ago`;
  if (seconds < 5400) return `${Math.round(seconds / 60)} min ago`;
  return `${Math.round(seconds / 3600)} h ago`;
}

export function preflightItems(input: PreflightInput): PreflightItem[] {
  const age = input.receiptAgeSeconds;
  const ageKnown = typeof age === 'number' && Number.isFinite(age);
  return [
    { id: 'gemini', label: 'Gemini', ok: input.geminiConfigured && ageKnown && (age as number) <= MAX_RECEIPT_AGE_SECONDS,
      detail: !input.geminiConfigured ? 'Not configured' : ageKnown ? `Configured · last live receipt ${ageText(age as number)}` : 'Configured · receipt age not reported' },
    { id: 'hardware', label: 'Hardware', ok: input.hardwareMode === 'simulator' || input.hardwareMode === 'physical_serial',
      detail: input.hardwareMode === 'physical_serial' ? 'Physical board' : input.hardwareMode === 'simulator' ? 'Simulator' : 'No board' },
    { id: 'p3', label: 'P3', ok: input.gateState === 'CLOSED' && input.endpointReported,
      detail: input.gateState === 'CLOSED' ? (input.endpointReported ? 'Closed · observed' : 'Closed · not yet observed') : `${(input.gateState ?? 'unknown').toLowerCase()}` },
    { id: 'token', label: 'Operator token', ok: !input.physical || input.tokenHeld,
      detail: !input.physical ? 'Not needed' : input.tokenHeld ? 'Held in memory' : 'Missing' },
    { id: 'camera', label: input.physical ? 'Camera' : 'Board view', ok: input.cameraLive, detail: input.cameraLive ? (input.physical ? 'Live' : 'Ready') : input.physical ? 'Not live' : 'Not ready' },
  ];
}
