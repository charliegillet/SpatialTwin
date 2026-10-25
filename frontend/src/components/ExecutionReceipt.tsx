import type { GroundingResult, InvestigationResult } from '../types';

/** Configuration is deliberately absent: this receipt describes one actual result. */
export function ExecutionReceipt({ result, label }: { result: GroundingResult | InvestigationResult | null; label: string }) {
  if (!result) return null;
  const usage = Object.entries(result.token_usage ?? {}).filter(([, value]) => Number.isFinite(value));
  return <details className="execution-receipt">
    <summary><span>{label}</span><small>{result.status.replace(/_/g, ' ')} · View receipt</small></summary>
    <dl>
      <div><dt>Source</dt><dd>{result.provenance ?? 'unverified'}</dd></div>
      <div><dt>Status</dt><dd>{result.status}</dd></div>
      {'last_provider_status' in result && result.last_provider_status && <div><dt>Last provider status</dt><dd>{result.last_provider_status}</dd></div>}
      {'replayed' in result && result.replayed && <div><dt>Delivery</dt><dd>Replayed saved run · no new provider request</dd></div>}
      {result.provider_model && <div><dt>Model</dt><dd>{result.provider_model}</dd></div>}
      {result.provider_interaction_id && <div><dt>Interaction</dt><dd>{result.provider_interaction_id}</dd></div>}
      {'provider_environment_id' in result && result.provider_environment_id && <div><dt>Environment</dt><dd>{result.provider_environment_id}</dd></div>}
      {'proposal_id' in result && result.proposal_id && <div><dt>Review record</dt><dd>{result.proposal_id}</dd></div>}
      {result.sdk_version && <div><dt>SDK</dt><dd>{result.sdk_version}</dd></div>}
      {Number.isFinite(result.latency_ms) && <div><dt>Elapsed</dt><dd>{Math.round(result.latency_ms!)} ms</dd></div>}
      {usage.map(([key, value]) => <div key={key}><dt>{key.replace(/_/g, ' ')}</dt><dd>{value}</dd></div>)}
    </dl>
    {!usage.length && <p>{result.provenance === 'fixture' || result.provenance === 'local' ? 'No provider tokens used.' : 'Provider token usage was not returned.'}</p>}
    {result.errors?.length ? <ul className="execution-receipt-errors">{result.errors.map((error, index) => <li key={`${index}-${error}`}>{error}</li>)}</ul> : null}
  </details>;
}
