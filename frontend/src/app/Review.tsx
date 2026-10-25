import { useState } from 'react'
import { acceptBlockers, api, ApiError, draftRevision, findingsOf } from '../api'
import type { Finding } from '../apiTypes'
import { ghostFlashes, ghostPath, latestGeometry } from '../twin/ghostWalker'
import type { Door, Evidence, VenueGraph } from '../types'
import { fmtT, Tag, type ScreenProps } from './common'
import { PlanView } from './PlanView'

const STATES = ['open', 'closed', 'locked', 'unknown']
const KINDS = ['door', 'opening', 'exit', 'stair']

function Timeline({ graph, duration, videoTime, selected, onPick }: {
  graph: VenueGraph; duration: number; videoTime: number; selected: string | null
  onPick: (id: string, ev: Evidence) => void
}) {
  const rows: { id: string; label: string; evidence: Evidence[]; door: boolean }[] = [
    ...graph.doors.map((d) => ({ id: d.id, label: `${d.id} ${d.kind}`, evidence: d.evidence, door: true })),
    ...graph.zones.map((z) => ({ id: z.id, label: `${z.id} ${z.name}`, evidence: z.evidence, door: false })),
  ]
  const d = Math.max(duration, 1)
  return (
    <div className="timeline" role="list" aria-label="Evidence timeline">
      {rows.map((r) => (
        <div key={r.id} role="listitem" className={`tl-row${selected === r.id ? ' sel' : ''}`}>
          <span className="tl-label">{r.label}</span>
          <div className="tl-track">
            {r.evidence.map((ev, i) => (
              <button key={i} className={`tl-bar${r.door ? ' door' : ''}`}
                style={{ left: `${(ev.start_s / d) * 100}%`, width: `max(6px, ${((ev.end_s - ev.start_s) / d) * 100}%)` }}
                title={`${r.id} ${fmtT(ev.start_s)}–${fmtT(ev.end_s)}: ${ev.note}`}
                aria-label={`${r.id} evidence from ${fmtT(ev.start_s)}: ${ev.note}`}
                onClick={() => onPick(r.id, ev)} />
            ))}
            <span className="tl-now" style={{ left: `${Math.min(100, (videoTime / d) * 100)}%` }} aria-hidden />
          </div>
        </div>
      ))}
    </div>
  )
}

function DoorEditor({ door, anchorId, onSave, onAnchor, disabled }: {
  door: Door; anchorId: string | null; disabled: boolean
  onSave: (d: Door) => void; onAnchor: (width: number) => void
}) {
  const [state, setState] = useState(door.state)
  const [kind, setKind] = useState(door.kind)
  const [low, setLow] = useState(String(door.clear_width.low_m))
  const [high, setHigh] = useState(String(door.clear_width.high_m))
  const [tape, setTape] = useState('')
  const lo = Number(low), hi = Number(high)
  const valid = lo > 0 && hi >= lo
  const dirty = state !== door.state || kind !== door.kind || lo !== door.clear_width.low_m || hi !== door.clear_width.high_m
  return (
    <div className="editor">
      <h3>{door.id} <span className="muted">{door.a} ↔ {door.b}</span></h3>
      <div className="row">
        <label>State <select value={state} onChange={(e) => setState(e.target.value)}>{STATES.map((s) => <option key={s}>{s}</option>)}</select></label>
        <label>Kind <select value={kind} onChange={(e) => setKind(e.target.value)}>{KINDS.map((s) => <option key={s}>{s}</option>)}</select></label>
      </div>
      <div className="row">
        <label>Width low (m) <input inputMode="decimal" value={low} onChange={(e) => setLow(e.target.value)} /></label>
        <label>Width high (m) <input inputMode="decimal" value={high} onChange={(e) => setHigh(e.target.value)} /></label>
      </div>
      <p className="muted">Width basis: {door.clear_width.basis}</p>
      <button disabled={disabled || !dirty || !valid}
        onClick={() => onSave({ ...door, state, kind, clear_width: { low_m: lo, high_m: hi, basis: door.clear_width.basis } })}>Save door</button>
      <div className="row anchor-row">
        <label>Tape-measured width (m) <input inputMode="decimal" value={tape} onChange={(e) => setTape(e.target.value)} placeholder="0.91" /></label>
        <button disabled={disabled || !(Number(tape) > 0)} onClick={() => onAnchor(Number(tape))}>
          {anchorId === door.id ? 'Update anchor' : 'Use as anchor'}
        </button>
      </div>
    </div>
  )
}

export function Review({ snap, act, pending, seek, videoTime, onAccepted }: ScreenProps & { videoTime: number; onAccepted: () => void }) {
  const graph = snap.draft_graph
  const [selected, setSelected] = useState<string | null>(null)
  const rev = draftRevision(snap)
  // findings from a 422 on Accept apply only to the revision they were returned for
  const [rejectedFor, setRejected] = useState<{ rev: string | null; findings: Finding[] }>({ rev: null, findings: [] })
  const rejected = rejectedFor.rev === rev ? rejectedFor.findings : []
  const findings = [...findingsOf(snap), ...rejected]
  const errorIds = new Set(findings.filter((f) => f.severity === 'error' && f.element_id).map((f) => f.element_id!))
  const blockers = acceptBlockers(snap)

  if (!graph) return <section className="screen"><div className="panel"><p className="muted">No draft twin yet. Build it from the Capture step.</p></div></section>

  const commit = (next: VenueGraph, label: string) => rev && act(label, () => api.putGraph(snap.id, rev, next))
  const door = graph.doors.find((d) => d.id === selected) ?? null
  const geo = latestGeometry(snap)
  const busy = !!pending
  const accept = () => rev && act('Accepting', async () => {
    try { await api.accept(snap.id, rev) } catch (e) {
      if (e instanceof ApiError && e.status === 422) setRejected({ rev, findings: e.findings })
      throw e
    }
  }).then((ok) => ok && onAccepted())

  return (
    <section className="screen review">
      <div className="panel">
        <div className="panel-head">
          <h2>Review the twin <Tag kind="model">Argon proposed</Tag></h2>
          <span className="muted mono">{rev}</span>
        </div>
        <PlanView graph={graph} path={ghostPath(snap)} flashes={geo ? ghostFlashes(geo) : []} hazards={[]} selected={selected}
          errorIds={errorIds} editable={!busy} onSelect={setSelected} onSeek={seek}
          onRectCommit={(id, rect) => commit({ ...graph, zones: graph.zones.map((z) => (z.id === id ? { ...z, rect } : z)) }, `Moving ${id}`)}
          label="Drag a room to move it, drag its corner dot to resize. Click a door to edit it." />
        <Timeline graph={graph} duration={snap.video.duration_s} videoTime={videoTime} selected={selected}
          onPick={(id, ev) => { setSelected(id); seek(ev.start_s) }} />
      </div>
      <div className="panel side">
        {door ? (
          <DoorEditor key={JSON.stringify(door)} door={door} anchorId={graph.anchor?.door_id ?? null} disabled={busy}
            onSave={(d) => commit({ ...graph, doors: graph.doors.map((x) => (x.id === d.id ? d : x)) }, `Saving ${d.id}`)}
            onAnchor={(w) => commit({ ...graph, anchor: { door_id: door.id, measured_width_m: w } }, `Anchoring ${door.id}`)} />
        ) : <p className="muted">Select a door on the plan or the timeline to edit state, kind and width.</p>}
        {graph.anchor && <p>Anchor: {graph.anchor.door_id} = {graph.anchor.measured_width_m.toFixed(3)} m <Tag kind="measured">measured</Tag></p>}
        <h3>Findings</h3>
        {findings.length === 0 ? <p className="muted">No findings.</p> : (
          <ul className="findings">
            {findings.map((f, i) => (
              <li key={i} className={f.severity}>
                <Tag kind={f.severity === 'error' ? 'error' : 'warn'}>{f.severity}</Tag> <code>{f.code}</code>{' '}
                {f.element_id && <button className="link" onClick={() => setSelected(f.element_id)}>{f.element_id}</button>} {f.message}
              </li>
            ))}
          </ul>
        )}
        <div className="actions">
          <button disabled={busy || !rev} onClick={() => rev && act('Refining', () => api.refine(snap.id, rev))}>Refine with Argon</button>
          <button className="primary" disabled={busy || blockers.length > 0} onClick={accept}>Accept</button>
        </div>
        {blockers.length > 0 && <p className="muted">Accept is off: {blockers.join('; ')}.</p>}
      </div>
    </section>
  )
}
