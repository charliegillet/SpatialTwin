import { api, approvable, currentRevision, currentRun, currentScenarioHash, investigationsInProgress, localDisagreement, readyInvestigations } from '../api'
import type { Investigation, LedgerEntry } from '../apiTypes'
import type { VenueGraph } from '../types'
import { Tag, type ScreenProps } from './common'
import { fmtT } from './format'

const doorOf = (interventionId: string) => interventionId.replace(/^OPEN:/, '')

function DoorLink({ id, graph, seek }: { id: string; graph: VenueGraph | null; seek: (t: number) => void }) {
  const ev = graph?.doors.find((d) => d.id === id)?.evidence[0]
  if (!ev) return <span>{id}</span>
  return <button className="link" onClick={() => seek(ev.start_s)} title={`Show ${id} in the video (${fmtT(ev.start_s)})`}>{id} ▸ {fmtT(ev.start_s)}</button>
}

function short(v: unknown, n = 160) {
  const s = typeof v === 'string' ? v : JSON.stringify(v)
  return s.length > n ? `${s.slice(0, n)}…` : s
}

function Step({ e }: { e: LedgerEntry }) {
  const sandbox = e.kind === 'sandbox_step'
  const code = typeof e.args.code === 'string' ? e.args.code : null
  return (
    <li className={`ledger-step ${sandbox ? 'sandbox' : 'client'}`}>
      <div className="ledger-head">
        {sandbox ? <Tag kind="model">sandbox, unverified</Tag> : <Tag kind="checked">ran locally</Tag>}
        <code>{e.name}</code>
        <span className="muted mono">{e.executed_at.slice(11, 19)}</span>
      </div>
      {code ? <pre>{code}</pre> : <p className="mono small">{short(e.args)}</p>}
      {e.result && <p className="mono small">→ {short(e.result)}</p>}
    </li>
  )
}

function Case({ inv, props }: { inv: Investigation; props: ScreenProps }) {
  const { snap, act, pending, seek, stale } = props
  const graph = snap.accepted_graph
  const rec = inv.recommendation
  const recResult = rec?.intervention_id ? inv.results.find((r) => r.intervention_id === rec.intervention_id) : undefined
  const best = approvable(inv, snap)
  const approved = snap.approvals.filter((a) => a.investigation_id === inv.investigation_id)
  const rev = currentRevision(snap), sh = currentScenarioHash(snap)
  const run = currentRun(snap)
  // the server's flag, or ours when the claimed and checker figures differ
  const disagreement = inv.disagreement ?? localDisagreement(inv)
  return (
    <div className="case">
      <div className="case-meta">
        <span>Investigation <span className="mono">{inv.investigation_id}</span></span>
        <span className={inv.status === 'completed' ? '' : 'fail'}>status {inv.status}{inv.error ? `: ${inv.error}` : ''}</span>
        <span>{inv.sandbox_runs} sandbox runs, unverified</span>
        <span>{inv.hook_denials} audit hook denials</span>
      </div>
      <h3>Evidence</h3>
      {inv.ledger.length ? <ol className="ledger">{inv.ledger.map((e) => <Step key={e.call_id} e={e} />)}</ol> : <p className="muted">No steps recorded yet.</p>}

      <h3>Figures</h3>
      <div className="figures">
        <div className="figure">
          <Tag kind="model">sandbox figure</Tag>
          <p className="big">{rec?.claimed_reached_exit ?? 'n/a'}</p>
          <p className="muted">Agent claimed{rec?.intervention_id ? ` for ${rec.intervention_id}` : ''}</p>
        </div>
        <div className="figure">
          {recResult?.check_ok ? <Tag kind="checked">checker verified</Tag> : <Tag kind="error">{recResult ? 'check failed' : 'not checked'}</Tag>}
          <p className="big">{recResult ? recResult.reached_exit : 'n/a'}{recResult && ` of ${recResult.total}`}</p>
          <p className="muted">{recResult ? (recResult.check_ok ? 'local solve, check passed' : 'local solve, check failed') : 'not evaluated locally'}</p>
        </div>
      </div>
      {disagreement && <p className="disagree" role="alert">Disagreement: {disagreement}</p>}

      {inv.results.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Change</th><th>Reach a modeled exit</th><th>vs now</th><th>Check</th><th>Limiting doors</th></tr></thead>
            <tbody>
              {inv.results.map((r) => (
                <tr key={r.intervention_id}>
                  <td><DoorLink id={doorOf(r.intervention_id)} graph={graph} seek={seek} /> <span className="muted">{r.intervention_id}</span></td>
                  <td>{r.reached_exit} of {r.total}</td>
                  <td>{r.delta_vs_current > 0 ? '+' : ''}{r.delta_vs_current}</td>
                  <td>{r.check_ok ? 'pass' : 'fail'}</td>
                  <td>{r.limiting_doors.map((d) => <DoorLink key={d} id={d} graph={graph} seek={seek} />)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {rec && (
        <div className="explanation">
          <h3>Agent's explanation</h3>
          <p>{rec.rationale}</p>
          {rec.caveats.length > 0 && <ul>{rec.caveats.map((c, i) => <li key={i}>{c}</li>)}</ul>}
        </div>
      )}

      <div className="approve">
        {inv.best ? (
          <p>{inv.best.check_ok ? 'Best checked change' : 'Best change, but its check failed'}: <strong>{inv.best.intervention_id}</strong>, {inv.best.reached_exit} of {inv.best.total} reach a modeled exit
            {run ? ` (now ${run.reached_exit})` : ''}. Door: <DoorLink id={doorOf(inv.best.intervention_id)} graph={graph} seek={seek} /></p>
        ) : <p>No allowed change improves this case.</p>}
        <button className="primary" disabled={!best || !!pending || !rev || !sh || stale}
          onClick={() => best && rev && sh && act('Approving', () => api.approve(snap.id, {
            expected_revision: rev, expected_scenario: sh, investigation_id: inv.investigation_id, intervention_id: best.intervention_id,
          }))}>Approve {inv.best?.intervention_id ?? ''}</button>
        {approved.map((a) => (
          <p key={a.intervention_id}><Tag kind="approved">you approved</Tag> {a.intervention_id} at {a.approved_at.slice(11, 16)} · note drafted, not sent</p>
        ))}
      </div>
    </div>
  )
}

export function Investigate(props: ScreenProps) {
  const { snap, act, pending } = props
  const ready = readyInvestigations(snap)
  const running = investigationsInProgress(snap)
  const rev = currentRevision(snap), sh = currentScenarioHash(snap)
  const failedJob = Object.values(snap.jobs).find((j) => j.kind === 'investigate' && j.status === 'failed'
    && j.meta.graph_revision === rev && j.meta.scenario_hash === sh)
  const inv = ready.find((i) => i.investigation_id === snap.ready_investigation_id) ?? ready.at(-1)
  return (
    <section className="screen investigate">
      <div className="panel">
        <div className="panel-head">
          <h2>Investigate a fix</h2>
          <span className="muted">Fire on {snap.scenario.hazards.map((h) => h.door_id).join(', ') || 'nothing yet'}</span>
        </div>
        <p className="lede">A managed agent sweeps options in its sandbox; only its shortlist is solved and checked here. Authority stays local: nothing changes until you approve.</p>
        {!snap.accepted_graph ? <p className="muted">Accept the twin in Review first.</p>
          : !rev || !sh ? <p className="fail">Revision unknown: nothing is shown as current until a reload succeeds.</p> : null}
        {running.length > 0 && <p className="muted" role="status">The agent is investigating this exact twin and hazard…</p>}
        {!inv && failedJob && <p className="fail">The last investigation of this case failed: {failedJob.error ?? 'no detail'}</p>}
        {inv ? <Case inv={inv} props={props} /> : (
          <div>
            <p className="muted">No investigation for this exact twin and hazard yet.</p>
            <button disabled={!!pending || !rev || !sh || !snap.accepted_graph || running.length > 0}
              onClick={() => rev && sh && act('Investigating', () => api.investigate(snap.id, rev, sh))}>Investigate this case</button>
          </div>
        )}
      </div>
    </section>
  )
}
