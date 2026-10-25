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
    if (detail === 'operator_token_not_configured') return 'This server has no operator token configured, so commands to physical hardware are disabled.';
    if (detail === 'operator_token_rejected') return 'The operator token was rejected. Check it and try again.';
    if (detail === 'operator_config_invalid') return 'The server operator configuration is invalid. Ask the administrator to fix it before sending commands.';
    return 'The operator token was not accepted.';
  }
  if (status === 502) {
    const [, rest = ''] = detail.split(/:(.*)/s);
    const reason = reasonText(rest);
    const suffix = reason ? ` (${reason})` : '';
    if (detail.startsWith('stop_not_acknowledged')) return `The device did not acknowledge the stop${suffix}. Treat outputs as still active and try again.`;
    if (detail.startsWith('device_not_acknowledged')) return `Device did not acknowledge${suffix}. Nothing was recorded; you can retry.`;
    return 'The device could not be reached. Nothing was recorded; you can retry.';
  }
  if (status === 409) return action === 'approve'
    ? 'This approval was already recorded or its evidence is no longer valid. Run a fresh comparison.'
    : 'The stop request conflicts with the current device state.';
  return '';
}

/** Rate limit and similar investigation failures; empty means "use the generic message". */
export function investigationErrorMessage(status: number): string {
  if (status === 429) return 'Too many analyses are already running. Wait for one to finish, then try again.';
  return '';
}

export function approvalSuccessMessage(acknowledged: boolean): string {
  return acknowledged
    ? 'Device acknowledged the P3 opening request. Acknowledgement is not arrival; wait for endpoint evidence.'
    : 'Backend accepted the P3 opening request. Waiting for endpoint evidence.';
}

export function stopSuccessMessage(): string {
  return 'Device acknowledged the stop command. Acknowledgement is not proof the gate stopped; check the reported position.';
}
