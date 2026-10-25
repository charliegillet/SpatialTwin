import { useEffect, useId, useRef, useState } from 'react';
import { ArrowDownToLine, ListChecks, RotateCcw, ShieldCheck } from 'lucide-react';
import type { RunContext, ScenarioSnapshot } from '../../types';
import { sameContext } from '../../ai/policy';
import { createRequestGate } from '../../ai/requestGate';
import { buildReviewHtml, escalationLabel, fetchReview, nextStepCopy, reviewJson, reviewPayload, statusLabel, verdictLabel } from './review';
import type { WatchRecord } from './review';
import './ReviewPanel.css';

interface ReviewPanelProps {
  snapshot: ScenarioSnapshot | null;
  isCurrent: boolean;
  investigationId?: string | null;
}

interface SavedReview { payload: unknown; context: RunContext; runId: string; investigationId: string | null; }

function download(filename: string, type: string, body: string) {
  const url = URL.createObjectURL(new Blob([body], { type }));
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = filename; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function ReviewPanel({ snapshot, isCurrent, investigationId = null }: ReviewPanelProps) {
  const uid = useId();
  const [saved, setSaved] = useState<SavedReview | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const gate = useRef(createRequestGate());
  const controller = useRef<AbortController | null>(null);
  const runId = snapshot?.current_plan?.run_id ?? null;
  const latest = useRef({ context: snapshot?.context, runId, isCurrent, investigationId });
  // Refs are written after commit, never during render. This effect precedes the review effect below.
  useEffect(() => { latest.current = { context: snapshot?.context, runId, isCurrent, investigationId }; });
  const reviewKey = JSON.stringify([snapshot?.context.context_hash ?? null, runId, isCurrent, investigationId]);

  async function runReview() {
    if (!snapshot || !runId || !isCurrent) return;
    const token = gate.current.start();
    if (token === null) return;
    const context = { ...snapshot.context };
    const requested = { runId, investigationId };
    const abort = new AbortController();
    controller.current = abort;
    setPending(true);
    setError(null);
    try {
      const payload = await fetchReview(context, requested.investigationId, abort.signal);
      if (gate.current.isCurrent(token) && latest.current.isCurrent && sameContext(context, latest.current.context)
        && latest.current.runId === requested.runId) setSaved({ payload, context, ...requested });
    } catch (cause) {
      if (gate.current.isCurrent(token) && !abort.signal.aborted) setError(cause instanceof Error ? cause.message : 'The review could not finish. Try again.');
    } finally {
      if (gate.current.isCurrent(token)) { setPending(false); gate.current.finish(token); }
    }
  }

  useEffect(() => {
    // Watchers re-read each newly accepted run. A context change cancels older work.
    gate.current.invalidate();
    controller.current?.abort();
    setPending(false);
    setError(null);
    void runReview();
    return () => { gate.current.invalidate(); controller.current?.abort(); };
  }, [reviewKey]);

  const stale = Boolean(saved && (!isCurrent || !sameContext(saved.context, snapshot?.context) || saved.runId !== runId));
  const view = saved && !stale ? reviewPayload(saved.payload, snapshot, isCurrent) : null;
  const ready = view?.available ? view.payload : null;
  const message = pending ? 'Watchers are reading the accepted checked run. Nothing is sent or changed.'
    : error ? error : stale ? 'Saved watch records are stale and hidden. Review the current run.'
      : view && !view.available ? view.message : ready ? `${ready.watch.watchers.length} watchers · ${escalationLabel(ready.watch.escalation)}.`
        : !isCurrent ? 'Waiting for a connected, current checked result.' : 'No review yet.';
  const records = new Map((ready?.watch.records ?? []).map(item => [item.record_id, item] as [string, WatchRecord]));
  const measured = ready?.verification.requirements.filter(item => item.status !== 'cannot_measure') ?? [];
  const outside = ready?.verification.requirements.filter(item => item.status === 'cannot_measure') ?? [];
  const checkedCount = measured.filter(item => item.status !== 'not_run').length;
  const notRunCount = measured.length - checkedCount;
  const revision = snapshot?.context.scenario_revision ?? 'unknown';

  return <section id="zone-watch" tabIndex={-1} className="review-panel" aria-labelledby={`${uid}-title`} aria-busy={pending}>
    <header className="review-header"><div><h2 id={`${uid}-title`}><ListChecks size={18} aria-hidden="true" />Zone watch &amp; verification</h2><p>Independent watchers read the accepted checked run. The report lists what was measured and what this model cannot measure.</p></div><span className="review-source">Local · checked run · no Gemini call</span></header>
    <p className={`review-status${error || stale || (view && !view.available) ? ' review-status-warning' : ''}`} role="status" aria-live="polite">{message}</p>
    {ready && <>
      <div className={`review-escalation is-${ready.watch.escalation}`}>
        <strong>{escalationLabel(ready.watch.escalation)}</strong>
        <p>{nextStepCopy(ready.watch.next_step)}</p>
        <small>{ready.escalation_record ? `Record ${ready.escalation_record.record_id} · ` : ''}{ready.watch.notice}</small>
      </div>
      <ul className="review-watchers" aria-label="Watchers">{ready.watch.watchers.map(watcher => <li key={watcher.watcher_id} className={`is-${watcher.severity}`}>
        <header><span>{watcher.label}</span><small>{watcher.severity}</small></header>
        {watcher.record_ids.map(id => <p key={id}>{records.get(id)?.summary}</p>)}
      </li>)}</ul>
      <div className="review-verdict"><ShieldCheck size={16} aria-hidden="true" /><span>{verdictLabel(ready.verification.verdict)}</span><small>{ready.verification.summary.passed} pass · {ready.verification.summary.failed} fail · {ready.verification.summary.checker_attested} checker · {ready.verification.summary.not_run} not run</small></div>
      <details className="review-requirements"><summary>{checkedCount} requirements checked{notRunCount ? ` · ${notRunCount} not run` : ''}{ready.verification.summary.failed ? ` · ${ready.verification.summary.failed} failed` : ''}</summary>
        <table className="review-table"><caption>Each measured value is re-read from run {ready.run_id} and the reviewed venue spec.</caption><thead><tr><th scope="col">Requirement</th><th scope="col">Measured</th><th scope="col">Status</th></tr></thead><tbody>{measured.map(item => <tr key={item.requirement_id} className={`is-${item.status}`}><th scope="row"><span>{item.statement}</span>{item.expected && <small>Expected {item.expected}</small>}</th><td>{item.measured ?? '—'}</td><td>{statusLabel[item.status]}</td></tr>)}</tbody></table>
      </details>
      <h3 className="review-outside-title">Outside the model</h3>
      <ul className="review-outside">{outside.map(item => <li key={item.requirement_id}><strong>{item.statement}</strong><span>{item.measured}</span></li>)}</ul>
    </>}
    <footer className="review-footer"><p>{ready?.verification.scope_note ?? 'Counts describe modeled crossings of synthetic occupants, not people.'}</p><div>
      <button type="button" className="review-secondary" onClick={() => void runReview()} disabled={!isCurrent || !runId || pending}><RotateCcw size={14} aria-hidden="true" />Review again</button>
      <button type="button" className="review-secondary" disabled={!ready} onClick={() => ready && download(`spatialtwin-review-r${revision}.json`, 'application/json', reviewJson(ready))}><ArrowDownToLine size={14} aria-hidden="true" />Export review JSON</button>
      <button type="button" className="review-primary" disabled={!ready} onClick={() => ready && download(`spatialtwin-verification-r${revision}.html`, 'text/html;charset=utf-8', buildReviewHtml(ready))}><ArrowDownToLine size={14} aria-hidden="true" />Printable report</button>
    </div></footer>
  </section>;
}
