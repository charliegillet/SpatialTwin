import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, videoUrl } from '../api'
import { Capture } from './Capture'
import { fmtT, type Act } from './common'
import { Investigate } from './Investigate'
import { Loop } from './Loop'
import { ReportDrawer } from './ReportDrawer'
import { Review } from './Review'
import { Twin } from './Twin'
import { errText, useSession } from './useSession'

type StepId = 'capture' | 'review' | 'loop' | 'twin' | 'investigate'
const STEPS: { id: StepId; label: string }[] = [
  { id: 'capture', label: 'Capture' },
  { id: 'review', label: 'Review' },
  { id: 'loop', label: 'Loop' },
  { id: 'twin', label: 'Twin' },
  { id: 'investigate', label: 'Investigate' },
]

const sessionFromHash = () => location.hash.match(/^#\/s\/([\w.-]+)/)?.[1] ?? null

export default function App() {
  const [id, setId] = useState<string | null>(sessionFromHash)
  useEffect(() => {
    const on = () => setId(sessionFromHash())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  const { snap, error, refresh } = useSession(id)
  const [chosen, setChosen] = useState<StepId | null>(null)
  const [pending, setPending] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [drawer, setDrawer] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const [videoTime, setVideoTime] = useState(0)

  const auto: StepId = !snap ? 'capture' : snap.accepted_graph ? 'twin' : snap.draft_graph ? 'review' : 'capture'
  const step = chosen ?? auto
  const done: Record<StepId, boolean> = {
    capture: !!snap, review: !!snap?.accepted_graph, loop: (snap?.iterations.length ?? 0) > 0,
    twin: !!snap?.current_run, investigate: (snap?.approvals.length ?? 0) > 0,
  }

  const act: Act = useCallback(async (label, fn) => {
    setPending(label)
    setNotice(null)
    try {
      await fn()
      await refresh()
      return true
    } catch (e) {
      setNotice(e instanceof ApiError && e.status === 422 ? 'Rejected: the draft still has error findings.' : errText(e))
      await refresh()
      return false
    } finally {
      setPending(null)
    }
  }, [refresh])

  const seek = useCallback((t: number) => {
    const v = videoRef.current
    if (!v) return
    v.currentTime = Math.max(0, t)
    v.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [])

  const created = (newId: string) => {
    location.hash = `#/s/${newId}`
    setChosen('capture')
  }
  const props = snap ? { snap, act, pending, seek } : null

  return (
    <div className="app">
      <header className="top">
        <a className="brand" href="#/" onClick={() => setChosen('capture')}>WalkTwin</a>
        <nav className="steps" aria-label="Steps">
          {STEPS.map((s, i) => (
            <button key={s.id} className={`step${step === s.id ? ' current' : ''}${done[s.id] ? ' done' : ''}`}
              aria-current={step === s.id ? 'step' : undefined} disabled={!snap && s.id !== 'capture'} onClick={() => setChosen(s.id)}>
              <span className="step-n">{i + 1}</span> {s.label}
            </button>
          ))}
        </nav>
        <button className="report-btn" disabled={!snap} onClick={() => setDrawer(true)}>Report</button>
      </header>
      {pending && <div className="status" role="status">{pending}…</div>}
      {notice && <div className="notice" role="alert">{notice} <button className="link" onClick={() => setNotice(null)}>dismiss</button></div>}
      {error && <div className="notice" role="alert">Could not load the session: {error}</div>}

      <main className={`stage step-${step}${id ? ' with-video' : ''}`}>
        <div className="content">
          {step === 'capture' && <Capture snap={snap} act={act} pending={pending} onCreated={created} />}
          {props && step === 'review' && <Review {...props} videoTime={videoTime} onAccepted={() => setChosen('twin')} />}
          {props && step === 'loop' && <Loop {...props} />}
          {props && step === 'twin' && <Twin {...props} videoRef={videoRef} />}
          {props && step === 'investigate' && <Investigate {...props} />}
        </div>
        {id && (
          <aside className="video-pane">
            <video ref={videoRef} src={videoUrl(id)} controls playsInline muted preload="metadata"
              onTimeUpdate={(e) => setVideoTime(e.currentTarget.currentTime)} onSeeked={(e) => setVideoTime(e.currentTarget.currentTime)} />
            <p className="muted small">Walk-through video · t = {fmtT(videoTime)}</p>
          </aside>
        )}
      </main>
      {snap && <ReportDrawer snap={snap} open={drawer} onClose={() => setDrawer(false)} />}
    </div>
  )
}
