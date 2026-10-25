import { api, draftRevision, frameUrl } from '../api'
import type { GeometryScore, Iteration, RenderedView } from '../apiTypes'
import { Tag, type ScreenProps } from './common'
import { fmtT, pct } from './format'
import { critiqueProblem, iterKind, iterationLabels, loopDelta, opRows, orphanRejections } from './loopView'

function RenderImg({ r }: { r: RenderedView }) {
  if (!r.url) return <div className="img-missing">render unavailable</div>
  return <img src={r.url} alt={`Twin render at t=${r.t_s}`} loading="lazy" />
}

function Seek({ t, seek }: { t: number; seek: (t: number) => void }) {
  return <button className="link mono" onClick={() => seek(t)} title="Seek the video here">▸ {fmtT(t)}</button>
}

function Measured({ g, none }: { g: GeometryScore | null; none: string }) {
  return (
    <div className="score">
      <Tag kind="measured">measured</Tag>
      {g ? (
        <ul>
          <li><strong>{g.illegal_crossings.length}</strong> illegal crossings</li>
          <li><strong>{pct(g.wall_support)}</strong> wall support</li>
          <li><strong>{pct(g.edge_within_5px)}</strong> held-out edges within 5 px{g.edge_chamfer_px != null && ` (mean ${g.edge_chamfer_px.toFixed(1)} px)`}</li>
        </ul>
      ) : <p className="muted">{none}</p>}
    </div>
  )
}

function Critique({ it, seek }: { it: Iteration; seek: (t: number) => void }) {
  const c = it.critique
  const rows = opRows(it)
  const orphans = orphanRejections(it)
  const problem = critiqueProblem(it)
  return (
    <div className="ops">
      {problem && <p className="fail" role="alert">{problem}</p>}
      {c && c.discrepancies.length > 0 && (
        <>
          <h4>Discrepancies <Tag kind="model">model-reported</Tag></h4>
          <ul className="discrepancies">
            {c.discrepancies.map((d, i) => (
              <li key={i}><Seek t={d.t_s} seek={seek} /> {d.element_id && <code>{d.element_id}</code>} {d.description}</li>
            ))}
          </ul>
        </>
      )}
      {rows.length > 0 && (
        <>
          <h4>Argon proposed {rows.length} op{rows.length === 1 ? '' : 's'}</h4>
          <div className="table-wrap">
            <table className="op-table">
              <thead><tr><th>#</th><th>Op</th><th>Target</th><th>Cites</th><th>Reason</th><th>Outcome</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.i} className={`op-${r.status.replace(' ', '-')}`}>
                    <td className="mono">{r.i}</td>
                    <td><code>{r.type}</code>{r.detail && <div className="muted small">{r.detail}</div>}</td>
                    <td>{r.target ?? <span className="muted">none</span>}</td>
                    <td><Seek t={r.cite_t_s} seek={seek} /></td>
                    <td>{r.reason}</td>
                    <td>{r.status}{r.why && <div className="small">{r.why}</div>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {!c && <p>Applied ops: {it.applied.length ? it.applied.map((i) => `#${i}`).join(', ') : 'none'}</p>}
      {orphans.length > 0 && (
        <ul className="rejected">
          {orphans.map(([i, why]) => (
            <li key={i} className={why === 'measured_regression' ? 'regression' : ''}>
              Rejected op #{i}: {why === 'measured_regression' ? 'measured regression, the whole round was reverted' : why}
            </li>
          ))}
        </ul>
      )}
      {(c?.dropped_ops?.length ?? 0) > 0 && (
        <>
          <h4>Dropped before patching (did not validate)</h4>
          <ul className="rejected">{c!.dropped_ops!.map(([i, why]) => <li key={i}>Op #{i}: {why}</li>)}</ul>
        </>
      )}
      {it.findings.length > 0 && <p className="muted">{it.findings.length} findings after this round</p>}
    </div>
  )
}

function Row({ it, label, sessionId, seek }: { it: Iteration; label: string; sessionId: string; seek: (t: number) => void }) {
  const kind = iterKind(it)
  const pairs = it.renders.filter((r) => r.kind === 'perspective' && r.t_s != null)
  const regression = it.rejected.some(([, why]) => why === 'measured_regression') || it.stop_reason === 'measured_regression'
  return (
    <article className={`round round-${kind}${regression ? ' regressed' : ''}`}>
      <header className="round-head">
        <h3>{label}</h3>
        {kind === 'baseline' && <span className="muted">the extraction graph, scored before any patch</span>}
        {kind === 'accepted' && <span className="muted">the graph you accepted, rescored at accept</span>}
        <span className="mono muted">{it.graph_revision}</span>
        {it.stop_reason && <span className="stop">stopped: {it.stop_reason.replace(/_/g, ' ')}</span>}
      </header>
      {pairs.length > 0 && (
        <div className="pairs">
          {pairs.map((r) => (
            <figure key={r.t_s} className="pair">
              <button className="pair-imgs" onClick={() => seek(r.t_s!)} title="Seek the video here">
                <img src={frameUrl(sessionId, r.t_s!)} alt={`Video frame at ${fmtT(r.t_s!)}`} loading="lazy" />
                <RenderImg r={r} />
              </button>
              <figcaption>{fmtT(r.t_s!)} · frame | render</figcaption>
            </figure>
          ))}
        </div>
      )}
      <div className="scores">
        <Measured g={it.geometry} none={kind === 'round' ? "Geometry not measured for this round's revision (no SfM path)." : 'Geometry not measured (no SfM path).'} />
        {it.rejected_geometry && (
          <p className="fail small">Reverted candidate measured {it.rejected_geometry.illegal_crossings.length} crossings, {pct(it.rejected_geometry.wall_support)} wall support.</p>
        )}
        {kind === 'round' && (
          <div className="score">
            <Tag kind="model">model-reported</Tag>
            <ul><li><strong>{it.discrepancy_count}</strong> discrepancies</li></ul>
          </div>
        )}
      </div>
      {kind === 'round' && <Critique it={it} seek={seek} />}
    </article>
  )
}

export function Loop({ snap, act, pending, seek }: ScreenProps) {
  const rev = draftRevision(snap)
  const labels = iterationLabels(snap.iterations)
  const delta = loopDelta(snap)
  return (
    <section className="screen loop">
      <div className="panel">
        <div className="panel-head">
          <h2>Geometry loop</h2>
          <button disabled={!!pending || !rev || !snap.draft_graph} onClick={() => rev && act('Refining', () => api.refine(snap.id, rev))}>Run another round</button>
        </div>
        <p className="lede">Argon compares video frames with twin renders and proposes patches. The walker's own path grades each round: <Tag kind="measured">measured</Tag> rows come from geometry, <Tag kind="model">model-reported</Tag> counts come from Argon.</p>
        {snap.alignment && (
          <p className="muted">Alignment fitted on the extraction graph, then frozen · residual {snap.alignment.residual_m.toFixed(2)} m · eye height {snap.alignment.eye_height_m.toFixed(2)} m (declared 1.5 ± 0.1 m)</p>
        )}
        {snap.geometry_unavailable_reason && <p className="fail">Geometry unavailable: {snap.geometry_unavailable_reason}. The loop ran on model-reported counts only.</p>}
        {delta && (
          <p className="delta" aria-live="polite">
            <Tag kind="measured">measured</Tag> Illegal crossings: before the loop <strong>{delta.before.illegal_crossings.length}</strong> → {delta.afterLabel.toLowerCase()} <strong>{delta.after.illegal_crossings.length}</strong>
            {' · '}held-out edges within 5 px: {pct(delta.before.edge_within_5px)} → {pct(delta.after.edge_within_5px)}
          </p>
        )}
        {snap.iterations.length === 0 && <p className="muted">No rounds yet.</p>}
        {snap.iterations.map((it, i) => <Row key={`${i}-${it.index}`} label={labels[i]} it={it} sessionId={snap.id} seek={seek} />)}
      </div>
    </section>
  )
}
