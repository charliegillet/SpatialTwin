import { useEffect, useId, useRef, useState } from 'react';
import { ArrowRight, CheckCheck, FlaskConical } from 'lucide-react';
import type { RunContext, ScenarioLabResult, ScenarioSnapshot } from '../../types';
import { fetchScenarioLab } from '../../api/client';
import { sameContext } from '../../ai/policy';
import { createRequestGate } from '../../ai/requestGate';
import { canRunScenarioLab, labCases, predictionOutcome, reviewScenarioLab } from './policy';
import type { JudgePrediction, ReserveBasis } from './policy';
import './ScenarioLab.css';

interface ScenarioLabProps {
  snapshot: ScenarioSnapshot | null;
  isCurrent: boolean;
}

interface SavedLab {
  result: ScenarioLabResult;
  prediction: JudgePrediction | null;
  context: RunContext;
  basis: ReserveBasis;
}

export function ScenarioLab({ snapshot, isCurrent }: ScenarioLabProps) {
  const uid = useId();
  const [basis, setBasis] = useState<ReserveBasis>('reported');
  const [prediction, setPrediction] = useState<JudgePrediction | null>(null);
  const [saved, setSaved] = useState<SavedLab | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const gate = useRef(createRequestGate());
  const controller = useRef<AbortController | null>(null);
  const latest = useRef({ context: snapshot?.context, isCurrent, basis });
  latest.current = { context: snapshot?.context, isCurrent, basis };
  const contextKey = JSON.stringify(snapshot?.context ?? null);
  useEffect(() => {
    gate.current.invalidate();
    controller.current?.abort();
    setPending(false);
    setError(null);
    return () => { gate.current.invalidate(); controller.current?.abort(); };
  }, [contextKey, isCurrent, basis]);

  async function runCases() {
    if (!snapshot || !isCurrent || !canRunScenarioLab(snapshot.current_plan, snapshot.context)) return;
    const token = gate.current.start();
    if (token === null) return;
    const context = { ...snapshot.context };
    const requestedBasis = basis;
    const requestedPrediction = prediction;
    const abort = new AbortController();
    controller.current = abort;
    setPending(true);
    setError(null);
    setSaved(null);
    try {
      const result = await fetchScenarioLab(context, requestedBasis, abort.signal);
      if (gate.current.isCurrent(token) && latest.current.isCurrent && sameContext(context, latest.current.context)
        && requestedBasis === latest.current.basis) setSaved({ result, prediction: requestedPrediction, context, basis: requestedBasis });
    } catch (cause) {
      if (gate.current.isCurrent(token) && !abort.signal.aborted) setError(cause instanceof Error ? cause.message : 'The cases could not be calculated. Try again.');
    } finally {
      if (gate.current.isCurrent(token)) { setPending(false); gate.current.finish(token); }
    }
  }

  const review = reviewScenarioLab(saved?.result, snapshot?.context, basis, snapshot?.current_plan, snapshot?.physical_gate_state === 'OPEN');
  const stale = Boolean(saved && (!isCurrent || !sameContext(saved.context, snapshot?.context) || saved.basis !== basis));
  const ready = Boolean(saved && !stale && review.valid);
  const canRun = Boolean(snapshot && isCurrent && canRunScenarioLab(snapshot.current_plan, snapshot.context));
  const message = pending ? 'Calculating eight local alternatives. This does not change the board.'
    : stale ? 'Saved cases are stale. Run again on the current context and reserve basis; earlier metrics are hidden.'
      : error ? error : saved && !review.valid ? 'Comparison unavailable. The complete batch could not be verified. Run again.'
        : ready ? predictionOutcome(saved!.prediction, review) : !canRun ? 'Waiting for a connected, current checked board result.'
          : 'Choose a reserve basis and run four independent cases. No scenario change or Gemini call is made.';

  return <section id="scenario-lab" tabIndex={-1} className="scenario-lab" aria-labelledby={`${uid}-title`}>
    <header className="scenario-lab-header"><div><h2 id={`${uid}-title`}><FlaskConical size={18} aria-hidden="true" />Scenario lab</h2><p>Compare the baseline with three closure cases.</p></div><span className="scenario-lab-source">Hypothetical · local solver</span></header>
    <div className="scenario-lab-controls">
      <label htmlFor={`${uid}-basis`}><span>Reserve basis</span><select id={`${uid}-basis`} value={basis} onChange={event => setBasis(event.target.value as ReserveBasis)} disabled={pending}><option value="reported">Reported P3 state</option><option value="closed_benchmark">Closed reserve benchmark</option></select></label>
      <label htmlFor={`${uid}-prediction`}><span>Your prediction <small>optional</small></span><select id={`${uid}-prediction`} value={prediction ?? ''} onChange={event => setPrediction((event.target.value || null) as JudgePrediction | null)} disabled={pending} aria-describedby={`${uid}-prediction-help`}><option value="">Which blocked case benefits most?</option><option value="p1_blocked">P1 blocked</option><option value="p2_blocked">P2 blocked</option><option value="b2_blocked">B2 blocked</option></select></label>
    </div>
    <p className="scenario-lab-basis" id={`${uid}-prediction-help`}>{basis === 'closed_benchmark' ? 'Hypothesis: P3 starts closed in every case, regardless of the reported position.' : `Each case starts with P3 in its reported state${snapshot ? ` (${snapshot.physical_gate_state.toLowerCase()})` : ''}.`}{basis === 'reported' && snapshot?.physical_gate_state === 'OPEN' ? ' It is already open; opening it again may add no benefit.' : ''} All cases retain the same population, horizon and boundary quotas.</p>
    <p className={`scenario-lab-status${stale || error || (saved && !review.valid) ? ' scenario-lab-status-warning' : ''}`} role="status" aria-live="polite">{ready && <CheckCheck size={16} aria-hidden="true" />}{message}</p>
    {saved && !stale && !review.valid && <ul className="scenario-lab-errors">{review.reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ul>}
    <table className="scenario-lab-table"><caption>{ready ? `${review.parameters!.population} synthetic occupants · ${review.parameters!.horizon}s horizon · ${review.parameters!.timestep}s timestep. Completed modeled-boundary crossings.` : 'Four hypothetical cases. Completed-crossing counts appear only after the entire batch is checked.'}</caption><thead><tr><th scope="col">Case</th><th scope="col">Keep</th><th scope="col">Open P3</th><th scope="col">Gain</th></tr></thead><tbody>{labCases.map(spec => {
      const row = ready ? review.rows.find(item => item.id === spec.id) : null;
      return <tr key={spec.id}><th scope="row"><span>{spec.title}</span><small>{row ? row.reason : pending ? 'Calculation pending' : stale ? 'Stale result hidden' : saved ? 'Comparison unavailable' : 'Not run'}</small></th><td>{row ? row.keep : <span className="scenario-lab-unavailable"><span aria-hidden="true">—</span><span className="scenario-lab-sr-only">Unavailable</span></span>}</td><td>{row ? row.open : <span className="scenario-lab-unavailable"><span aria-hidden="true">—</span><span className="scenario-lab-sr-only">Unavailable</span></span>}</td><td className={row && row.gain! > 0 ? 'scenario-lab-gain' : row && row.gain! < 0 ? 'scenario-lab-loss' : ''}>{row ? row.gain! > 0 ? `+${row.gain}` : row.gain : <span className="scenario-lab-unavailable"><span aria-hidden="true">—</span><span className="scenario-lab-sr-only">Unavailable</span></span>}</td></tr>;
    })}</tbody></table>
    {ready && <details className="scenario-lab-receipt"><summary>Checked run receipts</summary><p>Local hypothetical calculations · generated {new Date(saved!.result.generated_at_iso).toLocaleString()}. These runs cannot approve a movement.</p><dl>{review.rows.map(row => <div key={row.id}><dt>{row.title}</dt><dd>Keep: {row.runIds![0]}<br />Open P3: {row.runIds![1]}</dd></div>)}</dl><p>Context: {saved!.context.context_hash}</p></details>}
    <footer className="scenario-lab-footer"><p>P3 is an internal connection to B2. It adds no boundary capacity.</p><button type="button" onClick={() => void runCases()} disabled={!canRun} aria-disabled={pending || !canRun} aria-busy={pending} aria-describedby={`${uid}-prediction-help`}>{pending ? 'Calculating cases…' : saved ? 'Run cases again' : 'Run four cases'}{!pending && <ArrowRight size={16} aria-hidden="true" />}</button></footer>
  </section>;
}
