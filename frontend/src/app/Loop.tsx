import { api, draftRevision, frameUrl } from '../api'
import type { Iteration, RenderedView } from '../apiTypes'
import { Tag, type ScreenProps } from './common'
import { fmtT, pct } from './format'

function RenderImg({ r }: { r: RenderedView }) {
  if (!r.url) return <div className="img-missing">render unavailable</div>
  return <img src={r.url} alt={`Twin render at t=${r.t_s}`} loading="lazy" />
}

function Round({ it, n, sessionId, seek }: { it: Iteration; n: number; sessionId: string; seek: (t: number) => void }) {
  const pairs = it.renders.filter((r) => r.kind === 'perspective' && r.t_s != null)
  const g = it.geometry
  const regression = it.rejected.some(([, why]) => why === 'measured_regression') || it.stop_reason === 'measured_regression'
  return (
    <article className={`round${regression ? ' regressed' : ''}`}>
      <header className="round-head">
        <h3>Round {n}</h3>
        <span className="mono muted">{it.graph_revision}</span>
        {it.stop_reason && <span className="stop">stopped: {it.stop_reason.replace(/_/g, ' ')}</span>}
      </header>
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
      <div className="scores">
        <div className="score">
          <Tag kind="measured">measured</Tag>
          {g ? (
            <ul>
              <li><strong>{g.illegal_crossings.length}</strong> illegal crossings</li>
              <li><strong>{pct(g.wall_support)}</strong> wall support</li>
              <li><strong>{pct(g.edge_within_5px)}</strong> edges within 5 px{g.edge_chamfer_px != null && ` (mean ${g.edge_chamfer_px.toFixed(1)} px)`}</li>
            </ul>
          ) : <p className="muted">Geometry not measured for this round's revision (no SfM path).</p>}
          {it.rejected_geometry && (
            <p className="fail small">Reverted candidate measured {it.rejected_geometry.illegal_crossings.length} crossings, {pct(it.rejected_geometry.wall_support)} wall support.</p>
          )}
        </div>
        <div className="score">
          <Tag kind="model">model-reported</Tag>
          <ul><li><strong>{it.discrepancy_count}</strong> discrepancies</li></ul>
        </div>
      </div>
      <div className="ops">
        <p>Applied ops: {it.applied.length ? it.applied.map((i) => `#${i}`).join(', ') : 'none'}</p>
        {it.rejected.length > 0 && (
          <ul className="rejected">
            {it.rejected.map(([i, why]) => (
              <li key={i} className={why === 'measured_regression' ? 'regression' : ''}>
                Rejected op #{i}: {why === 'measured_regression' ? 'measured regression, the whole round was reverted' : why}
              </li>
            ))}
          </ul>
        )}
        {it.findings.length > 0 && <p className="muted">{it.findings.length} findings after this round</p>}
      </div>
    </article>
  )
}

export function Loop({ snap, act, pending, seek }: ScreenProps) {
  const rev = draftRevision(snap)
  return (
    <section className="screen loop">
      <div className="panel">
        <div className="panel-head">
          <h2>Geometry loop</h2>
          <button disabled={!!pending || !rev || !snap.draft_graph} onClick={() => rev && act('Refining', () => api.refine(snap.id, rev))}>Run another round</button>
        </div>
        <p className="lede">Argon compares video frames with twin renders and proposes patches. The walker's own path grades each round: <Tag kind="measured">measured</Tag> rows come from geometry, <Tag kind="model">model-reported</Tag> counts come from Argon.</p>
        {snap.alignment && (
          <p className="muted">Alignment frozen on round 1 · residual {snap.alignment.residual_m.toFixed(2)} m · eye height {snap.alignment.eye_height_m.toFixed(2)} m (declared 1.5 ± 0.1 m)</p>
        )}
        {snap.iterations.length === 0 && <p className="muted">No rounds yet.</p>}
        {snap.iterations.map((it, i) => <Round key={`${i}-${it.index}`} n={i + 1} it={it} sessionId={snap.id} seek={seek} />)}
      </div>
    </section>
  )
}
