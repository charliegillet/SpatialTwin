import type { CaptureEvidence, CaptureRequest, ProviderProgress } from '../types.ts';

export const allowlistedTools = new Set(['get_reviewed_scenario', 'evaluate_allowed_alternative', 'get_checked_comparison']);

export async function captureEvidence(capture: CaptureRequest): Promise<CaptureEvidence> {
  if (!capture.image_base64) return { ...capture };
  const bytes = Uint8Array.from(atob(capture.image_base64), character => character.charCodeAt(0));
  const hash = await crypto.subtle.digest('SHA-256', bytes);
  return { ...capture, image_sha256: Array.from(new Uint8Array(hash), value => value.toString(16).padStart(2, '0')).join('') };
}

/** Show lifecycle receipts and tool names, never provider thought content. */
export function progressDescription(event: ProviderProgress): string {
  const status = typeof event.status === 'string' ? event.status.replace(/_/g, ' ') : '';
  if (event.phase === 'provider_request') return 'Request sent to Gemini';
  if (event.phase === 'provider_response') return `Gemini response${status ? ` · ${status}` : ''}`;
  if (event.phase === 'provider_cancel_response') return `Cancellation response${status ? ` · ${status}` : ''}`;
  if (event.phase === 'local_tool_complete') return allowlistedTools.has(String(event.function_name)) ? `Read-only tool completed · ${event.function_name}` : 'Read-only tool update';
  return 'Investigation lifecycle update';
}
