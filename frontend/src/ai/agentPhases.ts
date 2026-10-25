import type { ProviderProgress, ToolCallLedgerEntry } from '../types.ts';
import { allowlistedTools } from './evidence.ts';

export interface Phase { label: string; atMs: number; }

function labelFor(event: ProviderProgress): string | null {
  const status = typeof event.status === 'string' ? event.status : '';
  if (event.phase === 'provider_request') return 'submitted';
  if (event.phase === 'local_tool_complete') return 'checked locally';
  if (event.phase === 'provider_cancel_response') return 'cancelled';
  if (event.phase !== 'provider_response') return null;
  if (status === 'completed') return 'finished';
  if (status === 'requires_action') return 'tool requested';
  if (['failed', 'cancelled', 'incomplete', 'timed_out'].includes(status)) return status.replace(/_/g, ' ');
  return 'running';
}

/** Polling receipts collapse into one entry per phase, the first time each phase was reached. */
export function collapsePhases(events: readonly ProviderProgress[]): Phase[] {
  const phases: Phase[] = [];
  for (const event of events) {
    const label = labelFor(event);
    if (!label || phases.some(phase => phase.label === label)) continue;
    phases.push({ label, atMs: typeof event.elapsed_ms === 'number' && Number.isFinite(event.elapsed_ms) ? event.elapsed_ms : 0 });
  }
  return phases;
}

const seconds = (ms: number) => `${Math.round(ms / 1000)} s`;

/** "submitted 0 s · running 15 s · tool requested 32 s · checked locally 14 ms · finished 51 s" */
export function phaseLine(events: readonly ProviderProgress[], ledger: readonly ToolCallLedgerEntry[]): string {
  const localMs = ledger.filter(entry => entry.status === 'executed').reduce((sum, entry) => sum + (Number.isFinite(entry.execution_time_ms) ? entry.execution_time_ms : 0), 0);
  return collapsePhases(events).map(phase => phase.label === 'checked locally' && ledger.length ? `${phase.label} ${Math.max(1, Math.round(localMs))} ms` : `${phase.label} ${seconds(phase.atMs)}`).join(' · ');
}

function argsSummary(args: Record<string, unknown> | undefined): string {
  if (!args) return '';
  const parts: string[] = [];
  for (const [key, value] of Object.entries(args)) {
    if (Array.isArray(value)) parts.push(`${key}: ${value.length}`);
    else if (value !== null && typeof value === 'object') parts.push(key);
    else parts.push(`${value}`);
    if (parts.length === 2) break;
  }
  return parts.join(', ').slice(0, 48);
}

export function toolLine(entry: ToolCallLedgerEntry): string {
  const known = allowlistedTools.has(entry.function_name);
  const name = known ? entry.function_name : 'rejected tool request';
  const args = known ? argsSummary(entry.arguments) : '';
  return `${name}${args ? ` (${args})` : ''} · ${Math.round(entry.execution_time_ms)} ms${entry.status === 'executed' ? '' : ` · ${entry.status}`}`;
}

export function shortInteractionId(id: string | null | undefined): string | null {
  if (!id) return null;
  return id.length > 12 ? `${id.slice(0, 8)}…` : id;
}

export const MAX_AGENT_LINES = 8;

/** At most eight lines per run: one phase line, tool calls, one id line. */
export function agentLines(input: { events: readonly ProviderProgress[]; ledger: readonly ToolCallLedgerEntry[]; interactionId?: string | null }): { phases: string; tools: string[]; id: string | null } {
  const id = shortInteractionId(input.interactionId);
  const room = MAX_AGENT_LINES - 1 - (id ? 1 : 0);
  const all = input.ledger.map(toolLine);
  const tools = all.length > room ? [...all.slice(0, room - 1), `+${all.length - room + 1} more calls`] : all;
  return { phases: phaseLine(input.events, input.ledger), tools, id };
}
