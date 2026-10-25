export type OperatorAction = 'approve' | 'stop';

/** Result of an operator call as shown to the user; never thrown. */
export interface OperatorOutcome { ok: boolean; message: string; acknowledged?: boolean; }

/** Physical boards need an operator token; the simulator does not. */
export function needsOperatorToken(hardwareMode: string | null | undefined): boolean {
  return hardwareMode === 'physical_serial';
}

/** Only short, plain reason text from the server is shown; anything else is dropped. */
function reasonText(raw: string): string {
  const reason = raw.replace(/_/g, ' ').trim();
  return /^[\w .,:;()/-]{1,80}$/.test(reason) ? reason : '';
}

/** Plain-words outcome for a failed operator call. `detail` is the backend's string detail, if any. */
export function operatorErrorMessage(action: OperatorAction, status: number, detail: string): string {
  if (status === 403) {
    if (detail === 'operator_token_not_configured') return 'No operator token is configured on the server.';
    if (detail === 'operator_token_rejected') return 'Operator token rejected.';
    if (detail === 'operator_config_invalid') return 'Server operator configuration is invalid.';
    return 'Operator token not accepted.';
  }
  if (status === 502) {
    const [, rest = ''] = detail.split(/:(.*)/s);
    const reason = reasonText(rest);
    const suffix = reason ? ` (${reason})` : '';
    if (detail.startsWith('stop_not_acknowledged')) return `Stop not acknowledged${suffix}. Outputs may still be active.`;
    if (detail.startsWith('device_not_acknowledged')) return `Device did not acknowledge${suffix}. Nothing recorded; retry.`;
    return 'Device unreachable. Nothing recorded; retry.';
  }
  if (status === 409) return action === 'approve'
    ? 'Approval already recorded or stale. Compare again.'
    : 'Stop conflicts with the device state.';
  return '';
}

/** Rate limit and similar investigation failures; empty means "use the generic message". */
export function investigationErrorMessage(status: number): string {
  if (status === 429) return 'Too many analyses running. Retry shortly.';
  return '';
}

export function approvalSuccessMessage(acknowledged: boolean): string {
  return acknowledged
    ? 'Acknowledged — not arrival. Waiting for endpoint evidence.'
    : 'Accepted. Waiting for endpoint evidence.';
}

export function stopSuccessMessage(): string {
  return 'Stop acknowledged — not proof the gate stopped.';
}
