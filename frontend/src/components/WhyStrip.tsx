import { useEffect, useId, useRef, useState } from 'react';
import { HelpCircle } from 'lucide-react';
import type { RunContext, ScenarioLabResult, ScenarioSnapshot } from '../types';
import { fetchScenarioLab } from '../api/client';
import { sameContext } from '../ai/policy';
import { createRequestGate } from '../ai/requestGate';
import { canRunScenarioLab, reviewScenarioLab } from '../features/scenario-lab/policy';

interface Props { snapshot: ScenarioSnapshot | null; isCurrent: boolean; /** The card closes whenever this changes (an approval finished, or a reset). */ closeKey?: string; }

/** Four local cases with keep versus open P3. Read-only: it never changes the scenario. */
export function WhyStrip({ snapshot, isCurrent, closeKey }: Props) {
  const uid = useId();
  const [open, setOpen] = useState(false);
  const [saved, setSaved] = useState<{ result: ScenarioLabResult; context: RunContext } | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const gate = useRef(createRequestGate());
  const controller = useRef<AbortController | null>(null);
  useEffect(() => { setOpen(false); }, [closeKey]);
  const contextKey = JSON.stringify(snapshot?.context ?? null);
  useEffect(() => { gate.current.invalidate(); controller.current?.abort(); setPending(false); setError(null); }, [contextKey, isCurrent]);
  useEffect(() => () => { gate.current.invalidate(); controller.current?.abort(); }, []);
  const canRun = Boolean(snapshot && isCurrent && canRunScenarioLab(snapshot.current_plan, snapshot.context));
  const fresh = Boolean(saved && sameContext(saved.context, snapshot?.context));

  const run = async () => {
    if (!snapshot || !canRun) return;
    const token = gate.current.start();
    if (token === null) return;
    const context = { ...snapshot.context };
    const abort = new AbortController();
    controller.current = abort;
    setPending(true); setError(null);
    try {
      const result = await fetchScenarioLab(context, 'closed_benchmark', abort.signal);
      if (gate.current.isCurrent(token)) setSaved({ result, context });
    } catch (cause) {
      if (gate.current.isCurrent(token) && !abort.signal.aborted) setError(cause instanceof Error ? cause.message : 'The cases could not be calculated.');
    } finally { if (gate.current.isCurrent(token)) { setPending(false); gate.current.finish(token); } }
  };
  const toggle = () => { const next = !open; setOpen(next); if (next && !fresh && !pending) void run(); };
  const review = fresh ? reviewScenarioLab(saved?.result, snapshot?.context, 'closed_benchmark', snapshot?.current_plan, false) : null;
  const rows = review?.valid ? review.rows : null;

  return <div className="why">
    <button type="button" className="btn btn-quiet" aria-expanded={open} aria-controls={`${uid}-why`} onClick={toggle} disabled={!canRun && !open}><HelpCircle size={13} aria-hidden="true" />Why?</button>
    {open && <div id={`${uid}-why`} className="why-card">
      <p className="why-source">Local solver · no Gemini call · P3 closed in every case</p>
      {rows ? <table><thead><tr><th scope="col">Case</th><th scope="col">Keep</th><th scope="col">Open P3</th><th scope="col">Gain</th></tr></thead>
        <tbody>{rows.map(row => <tr key={row.id}><th scope="row">{row.title}</th><td>{row.keep}</td><td>{row.open}</td><td className={row.gain! > 0 ? 'is-gain' : ''}>{row.gain! > 0 ? `+${row.gain}` : row.gain}</td></tr>)}</tbody></table>
        : <p className="why-status" role="status">{pending ? 'Calculating four cases…' : error ?? (fresh ? 'The comparison could not be verified.' : 'Waiting for a checked result.')}</p>}
    </div>}
  </div>;
}
