import { useState } from 'react'
import { api, draftRevision } from '../api'
import type { Snapshot, VideoMode } from '../apiTypes'
import { ghostPath } from '../twin/ghostWalker'
import { Jobs, Tag, type Act } from './common'
import { PlanView } from './PlanView'

const MODES: { id: VideoMode; label: string }[] = [
  { id: 'static_hifps', label: 'Static, 3 fps high-res' },
  { id: 'static', label: 'Static, 1 fps' },
  { id: 'agentic', label: 'Agentic video' },
]

interface Props {
  snap: Snapshot | null
  act: Act
  pending: string | null
  onCreated: (id: string) => void
}

export function Capture({ snap, act, pending, onCreated }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [hint, setHint] = useState('')
  const [width, setWidth] = useState('')
  const [mode, setMode] = useState<VideoMode>('static_hifps')

  const upload = () => file && act('Uploading video', async () => {
    const w = Number(width)
    onCreated(await api.createSession(file, hint.trim() || undefined, w > 0 ? w : undefined))
  })

  const path = snap ? ghostPath(snap) : []
  const sfmJob = snap?.jobs.sfm
  const ex = snap?.extraction
  return (
    <section className="screen capture">
      <div className="panel">
        <h2>Film the walk-through</h2>
        <p className="lede">Walk slowly, pause about 2 s facing each door, keep people out of frame.</p>
        <label className="file-drop">
          <input type="file" accept="video/*" capture="environment" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <span>{file ? `${file.name} · ${(file.size / 1e6).toFixed(1)} MB` : 'Record or choose a video'}</span>
        </label>
        <details className="anchor">
          <summary>Optional anchor: one tape-measured door</summary>
          <p>You can also pick the door later in Review.</p>
          <div className="row">
            <label>Which door <input value={hint} onChange={(e) => setHint(e.target.value)} placeholder="e.g. front door at 0:12" maxLength={120} /></label>
            <label>Clear width (m) <input inputMode="decimal" value={width} onChange={(e) => setWidth(e.target.value)} placeholder="0.91" /></label>
          </div>
        </details>
        <button className="primary" disabled={!file || !!pending} onClick={upload}>
          {pending === 'Uploading video' ? 'Uploading…' : 'Upload and start'}
        </button>
        <p className="hint">On a phone, open <code>http://&lt;laptop-ip&gt;:8000</code> on the same network.
          No shared Wi-Fi? Use a personal hotspot, or AirDrop/USB the file to the laptop and upload it here.</p>
      </div>

      {snap && (
        <div className="panel">
          <h2>Session {snap.id}</h2>
          <p>{snap.video.duration_s.toFixed(0)} s video, {snap.video.width}×{snap.video.height}</p>
          <Jobs snap={snap} />
          {snap.sfm?.status === 'failed' && <p className="fail">SfM failed: {snap.sfm.error ?? 'no model'}. The loop will run on model-reported counts only.</p>}
          {path.length > 1 ? (
            <PlanView graph={snap.draft_graph} path={path} label={`Your walked path (SfM, ${path.length} camera positions${snap.sfm ? `, ${Math.round(snap.sfm.registered_fraction * 100)}% of frames registered` : ''})`} />
          ) : sfmJob && sfmJob.status !== 'done' && sfmJob.status !== 'failed' ? (
            <p className="muted">Reconstructing your walked path…</p>
          ) : null}
          {ex && ex.status !== 'completed' && <p className="fail">Argon extraction {ex.status}{ex.error ? `: ${ex.error}` : ''}</p>}
          {ex?.mode === 'agentic' && ex.agentic_observed === false && <p className="warn">Agentic mode requested but not observed (0 processing calls).</p>}
          <div className="row">
            <label>Video mode
              <select value={mode} onChange={(e) => setMode(e.target.value as VideoMode)}>
                {MODES.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
              </select>
            </label>
            <button className="primary" disabled={!!pending || snap.jobs.extract?.status === 'running' || snap.jobs.extract?.status === 'queued'}
              onClick={() => act('Extracting', () => api.extract(snap.id, mode))}>
              {snap.draft_graph ? 'Extract again with Argon' : 'Build the twin with Argon'}
            </button>
          </div>
          {snap.draft_graph && <p><Tag kind="model">Argon proposed</Tag> {snap.draft_graph.zones.length} zones, {snap.draft_graph.doors.length} doors{draftRevision(snap) ? ` · ${draftRevision(snap)}` : ''}</p>}
        </div>
      )}
    </section>
  )
}
