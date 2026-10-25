import type { InvestigationResult, ProviderProgress } from '../types';
import { allowlistedTools, progressDescription } from '../ai/evidence';

function compactResult(result: Record<string, unknown> | null | undefined): string {
  if (!result) return 'No completed tool result';
  const omit = new Set(['timeline', 'zone_occupancy', 'zones', 'portals', 'boundaries']);
  const json = JSON.stringify(result, (key, value) => omit.has(key) ? undefined : value, 2);
  return json.length > 8000 ? `${json.slice(0, 8000)}\n… Full result available in evidence export.` : json;
}

export function ProviderProgressList({ events, pending = false }: { events: ProviderProgress[]; pending?: boolean }) {
  if (!events.length) return pending ? <p className="investigation-progress-note" role="status">Request submitted. Waiting for a provider receipt.</p> : null;
  return <ol className="investigation-progress-list" aria-label="Recorded investigation progress" aria-live={pending ? 'polite' : 'off'}>{events.slice(-8).map((event, index) => <li key={`${index}-${event.phase}-${event.elapsed_ms}`}><span>{Number.isFinite(event.elapsed_ms) ? `${(event.elapsed_ms! / 1000).toFixed(1)}s` : 'Receipt'}</span><div>{progressDescription(event)}</div></li>)}</ol>;
}

export function InvestigationEvidence({ investigation }: { investigation: InvestigationResult | null }) {
  if (!investigation) return null;
  return <div className="investigation-evidence">
    {investigation.agent_explanation && <details className="investigation-evidence-section"><summary>{investigation.provenance === 'local' ? 'Local comparison summary' : 'Gemini explanation'}</summary><p>{investigation.agent_explanation.slice(0, 6000)}</p></details>}
    <details className="investigation-evidence-section"><summary>Read-only tool evidence · {investigation.tool_ledger.length} calls</summary>{investigation.tool_ledger.length ? <ol className="investigation-tool-list">{investigation.tool_ledger.map((entry, index) => <li key={`${entry.call_id}-${index}`}><div><strong>{allowlistedTools.has(entry.function_name) ? entry.function_name : 'Rejected tool request'}</strong><span>{entry.status} · {Math.round(entry.execution_time_ms)} ms</span></div><small>Call {entry.call_id}</small>{entry.error && <p className="details-warning">{entry.error}</p>}{allowlistedTools.has(entry.function_name) && <details><summary>Arguments and checked result</summary><pre>{JSON.stringify(entry.arguments, null, 2)}</pre><pre>{compactResult(entry.result)}</pre></details>}</li>)}</ol> : <p>No local tool execution was recorded.</p>}</details>
    {!!investigation.provider_progress?.length && <details className="investigation-evidence-section"><summary>Provider lifecycle receipts</summary><ProviderProgressList events={investigation.provider_progress} /></details>}
  </div>;
}
