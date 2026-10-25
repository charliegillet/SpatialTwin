import { useState } from 'react';
import type { DraftView, GraphIssue } from '../api/real2sim.ts';
import { roundLine } from '../twin/real2simView.ts';

type EvidenceView = 'overlay' | 'topdown';

/** The proof the operator reviews before accepting: the source with the compiled building drawn back on it, the plan
 *  alone, what Argon could not read, what the checker dropped or repaired, and every graph-check issue. All text from
 *  the server or the model is rendered as text nodes. */
export function Real2SimEvidence({ view, overlaySrc, topdownSrc }: { view: DraftView; overlaySrc: string | null; topdownSrc: string | null }) {
  const [shown, setShown] = useState<EvidenceView>('overlay');
  const [broken, setBroken] = useState<Record<string, boolean>>({});
  const src = shown === 'overlay' ? overlaySrc : topdownSrc;
  const issues = view.checks?.issues ?? [];
  const errors = view.checks?.errors ?? 0;
  const warnings = view.checks?.warnings ?? 0;
  return <div className="r2s-evidence">
    {(overlaySrc || topdownSrc) && <div className="r2s-figure">
      <div className="r2s-toggle" role="group" aria-label="Evidence image">
        <button type="button" className="btn btn-quiet" aria-pressed={shown === 'overlay'} disabled={!overlaySrc} onClick={() => setShown('overlay')}>Overlay on source</button>
        <button type="button" className="btn btn-quiet" aria-pressed={shown === 'topdown'} disabled={!topdownSrc} onClick={() => setShown('topdown')}>Top-down plan</button>
      </div>
      {src && !broken[src]
        ? <img className="r2s-image" src={src} onError={() => setBroken(prev => ({ ...prev, [src]: true }))}
            alt={shown === 'overlay' ? 'The source drawing with the compiled rooms, doors and exits drawn on top' : 'Top-down plan of the compiled building'} />
        : <p className="twin-quiet">This image is not available.</p>}
    </div>}
    <p className="r2s-checks" role="status">
      {view.checks ? `Local checks: ${errors} error${errors === 1 ? '' : 's'}, ${warnings} warning${warnings === 1 ? '' : 's'}` : 'Local checks did not run.'}
      {view.checks?.compile_error ? ` · could not build: ${view.checks.compile_error.replace(/_/g, ' ')}` : ''}
    </p>
    {view.rounds.length > 0 && <ul className="r2s-rounds" aria-label="Critique rounds">{view.rounds.map(round => <li key={round.round}>{roundLine(round)}</li>)}</ul>}
    {view.critique_note && <p className="twin-quiet">{view.critique_note}</p>}
    {issues.length > 0 && <ul className="r2s-issues" aria-label="Check issues">{issues.map((issue, index) => <IssueRow key={index} issue={issue} />)}</ul>}
    <TextList title="Argon could not read" items={view.unreadable} tone="muted" />
    <TextList title="Dropped" items={view.dropped} tone="drop" hint="Elements the checker removed because they did not hold up." />
    <TextList title="Repaired" items={view.repaired} tone="muted" hint="Harmless fixes applied while reading." />
  </div>;
}

function IssueRow({ issue }: { issue: GraphIssue }) {
  return <li className={`is-${issue.severity}`}>
    <span className="r2s-sev">{issue.severity}</span>{issue.message}
    {issue.element_ids.length > 0 && <small> {issue.element_ids.join(', ')}</small>}
  </li>;
}

function TextList({ title, items, tone, hint }: { title: string; items: string[]; tone: 'muted' | 'drop'; hint?: string }) {
  if (items.length === 0) return null;
  return <details className={`r2s-textlist is-${tone}`}>
    <summary>{title} <span className="r2s-count">{items.length}</span></summary>
    {hint && <p className="twin-quiet">{hint}</p>}
    <ul className="r2s-list">{items.map((item, index) => <li key={index}>{item}</li>)}</ul>
  </details>;
}
