import type { InvestigationResult, ProviderProgress } from '../types';
import { allowlistedTools, progressDescription } from '../ai/evidence';

function compactResult(result: Record<string, unknown> | null | undefined): string {
  if (!result) return 'No completed tool result';
  const omit = new Set(['timeline', 'zone_occupancy', 'zones', 'portals', 'boundaries']);
  const json = JSON.stringify(result, (key, value) => omit.has(key) ? undefined : value, 2);
  return json.length > 8000 ? `${json.slice(0, 8000)}\n… Full result available in evidence export.` : json;
}

export function ProviderProgressList({ events, pending = false, pendingMessage = 'Request submitted. Waiting for a receipt.' }: { events: ProviderProgress[]; pending?: boolean; pendingMessage?: string }) {
  if (!events.length) return pending ? <p className="investigation-progress-note" role="status">{pendingMessage}</p> : null;
  return <ol className="investigation-progress-list" aria-label="Recorded investigation progress" aria-live={pending ? 'polite' : 'off'} aria-relevant="additions">{events.slice(-8).map((event, index) => <li key={`${Math.max(0, events.length - 8) + index}-${event.phase}-${event.elapsed_ms}`}><span>{Number.isFinite(event.elapsed_ms) ? `${(event.elapsed_ms! / 1000).toFixed(1)}s` : 'Receipt'}</span><div>{progressDescription(event)}</div></li>)}</ol>;
}

export function InvestigationEvidence({ investigation }: { investigation: InvestigationResult | null }) {
  if (!investigation) return null;
  return <details className="investigation-evidence"><summary>Review evidence <small>{investigation.tool_ledger.length} recorded calls</small></summary><div className="investigation-evidence-content">
    {investigation.agent_explanation && <section className="investigation-evidence-section"><h4>{investigation.provenance === 'local' ? 'Local comparison summary' : 'Gemini explanation'}</h4><p>{investigation.agent_explanation.slice(0, 6000)}</p></section>}
    <section className="investigation-evidence-section"><h4>Read-only tool evidence · {investigation.tool_ledger.length} {investigation.tool_ledger.length === 1 ? 'call' : 'calls'}</h4>{investigation.tool_ledger.length ? <ol className="investigation-tool-list">{investigation.tool_ledger.map((entry, index) => <li key={`${entry.call_id}-${index}`}><div><strong>{allowlistedTools.has(entry.function_name) ? entry.function_name : 'Rejected tool request'}</strong><span>{entry.status} · {Math.round(entry.execution_time_ms)} ms</span></div><small>Call {entry.call_id}</small>{entry.error && <p className="details-warning">{entry.error}</p>}{allowlistedTools.has(entry.function_name) && <div className="investigation-tool-detail"><strong>Arguments and checked result</strong><pre>{JSON.stringify(entry.arguments, null, 2)}</pre><pre>{compactResult(entry.result)}</pre></div>}</li>)}</ol> : <p>No local tool execution was recorded.</p>}</section>
    {!!investigation.provider_progress?.length && <section className="investigation-evidence-section"><h4>Provider lifecycle receipts</h4><ProviderProgressList events={investigation.provider_progress} /></section>}
  </div></details>;
}
