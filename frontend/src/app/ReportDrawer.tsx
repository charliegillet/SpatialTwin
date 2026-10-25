import { useEffect, useState } from 'react'
import { api, currentRevision, isCurrent, reportHtmlUrl } from '../api'
import type { Report, Requirement, Snapshot } from '../apiTypes'
import { Tag } from './common'
import { errText } from './useSession'

const METHOD: Record<Requirement['method'], string> = {
  measured: 'measured', checker: 'checker verified', model_reported: 'model-reported', outside_model: 'outside the model',
}
const STATUS: Record<string, string> = { pass: 'pass', fail: 'fail', cannot_measure: 'cannot measure', not_run: 'not run' }
const VERDICT: Record<Report['verdict'], string> = {
  verified_within_model: 'Verified within the model', failed: 'Failed', incomplete: 'Incomplete',
}

type Loaded<T> = { key: string; value: T | null; error: string | null }

export function ReportDrawer({ snap, open, onClose }: { snap: Snapshot; open: boolean; onClose: () => void }) {
  const key = `${currentRevision(snap)}|${snap.current_run?.run_id}|${snap.approvals.length}`
  const [rep, setRep] = useState<Loaded<Report> | null>(null)
  const [note, setNote] = useState<Loaded<string> | null>(null)
  useEffect(() => {
    if (!open) return
    let live = true
    api.report(snap.id).then(
      (r) => live && setRep({ key, value: r, error: null }),
      (e) => live && setRep({ key, value: null, error: errText(e) }))
    const last = snap.approvals.length - 1
    if (last >= 0) {
      api.note(snap.id, last).then(
        (t) => live && setNote({ key, value: t, error: null }),
        (e) => live && setNote({ key, value: null, error: errText(e) }))
    }
    return () => { live = false }
  }, [open, snap.id, key, snap.approvals.length])
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  const report = rep?.key === key ? rep.value : null
  const error = rep?.key === key ? rep.error : null
  const noteText = note?.key === key ? note.value : null
  const noteError = note?.key === key ? note.error : null
  if (!open) return null
  const current = report && isCurrent(report, snap) ? report : null
  const ada = current?.rules ?? []
  return (
    <aside className="drawer" role="dialog" aria-label="Report">
      <div className="drawer-head">
        <h2>Report</h2>
        <button onClick={onClose} aria-label="Close report">Close</button>
      </div>
      {error && <p className="fail">Report unavailable: {error}</p>}
      {!report && !error && <p className="muted">Loading the report…</p>}
      {report && !current && <p className="muted">That report is not for the current revision and scenario, so it is hidden.</p>}
      {current && (
        <>
          <p className="verdict">{VERDICT[current.verdict]} <span className="muted mono">{current.graph_revision} · {current.scenario_hash}</span></p>
          <a className="button" href={reportHtmlUrl(snap.id)} target="_blank" rel="noreferrer">Open HTML export</a>
          <h3>Requirements</h3>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Requirement</th><th>Method</th><th>Status</th><th>Value</th></tr></thead>
              <tbody>
                {current.requirements.map((r) => (
                  <tr key={r.id} className={`st-${r.status}`}>
                    <td>{r.statement}<div className="muted small">{r.evidence}</div></td>
                    <td>{METHOD[r.method]}</td><td>{STATUS[r.status]}</td><td>{r.value ?? ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h3>ADA checks</h3>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Rule</th><th>Element</th><th>Result</th><th>Citation</th></tr></thead>
              <tbody>
                {ada.map((r, i) => (
                  <tr key={i} className={`st-${r.status}`}>
                    <td>{r.rule_id}<div className="muted small">{r.statement}</div></td>
                    <td>{r.element_id}</td>
                    <td>{r.status === 'pass' ? `meets ${r.rule_id.replace('ADA-', 'ADA §')} within measured range` : STATUS[r.status]}{r.reason ? `: ${r.reason}` : ''}
                      {r.measured && <div className="muted small">{r.measured.low_m.toFixed(2)}–{r.measured.high_m.toFixed(2)} m ({r.measured.basis}) vs {r.threshold_m} m</div>}</td>
                    <td className="small">{r.citation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h3>Check by hand</h3>
          <ul className="todo">{current.hand_checks.map((h, i) => <li key={i}><input type="checkbox" aria-label={h} /> {h}</li>)}</ul>
          <h3>Declared parameters <Tag kind="declared">declared</Tag></h3>
          <p className="mono small">{Object.entries(current.declared_parameters).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(' · ')}</p>
          <h3>Provenance</h3>
          <ul className="small">{current.provenance.map((p, i) => <li key={i}>{p}</li>)}</ul>
        </>
      )}
      <h3>Note to security</h3>
      <div className="note">
        <p className="note-head"><strong>DRAFT — not sent</strong></p>
        {snap.approvals.length === 0 ? <p className="muted">Drafted after you approve a change. Nothing is sent.</p>
          : noteText != null ? <pre>{noteText}</pre>
            : noteError ? <p className="fail">Could not load the note: {noteError}</p>
              : <p className="muted">Loading the note…</p>}
      </div>
    </aside>
  )
}
