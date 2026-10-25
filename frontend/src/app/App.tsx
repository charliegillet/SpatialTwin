import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, videoUrl } from '../api'
import { Capture } from './Capture'
import { type Act } from './common'
import { fmtT } from './format'
import { Investigate } from './Investigate'
import { Loop } from './Loop'
import { ReportDrawer } from './ReportDrawer'
import { Review } from './Review'
import { savedRunBadge, sessionStarted } from './sessionView'
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
  const { snap, error, refresh, markMutated, stale, staleBanner } = useSession(id)
  const [chosen, setChosen] = useState<StepId | null>(null)
  const [pending, setPending] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [drawer, setDrawer] = useState(false)
  const closeDrawer = useCallback(() => setDrawer(false), [])
  // I8: the saved-run badge depends on the wall clock; re-read it every 30 s
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(t)
  }, [])
  const savedRun = snap ? savedRunBadge(snap.created_at, now) : null
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
      markMutated()
      await refresh()
      return true
    } catch (e) {
      setNotice(e instanceof ApiError && e.status === 422 && e.findings.length ? 'Rejected: the draft still has error findings.' : errText(e))
      markMutated()
      await refresh()
      return false
    } finally {
      setPending(null)
    }
  }, [refresh, markMutated])

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

  return (
    <div className="app">
      <header className="top">
        <a className="brand" href="#/" onClick={() => setChosen('capture')}>WalkTwin</a>
        {snap && (
          <span className="session-time">
            {savedRun ? <span className="badge-saved">{savedRun}</span> : <span className="muted small">{sessionStarted(snap.created_at)}</span>}
          </span>
        )}
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
      {staleBanner && (
        <div className="notice" role="alert">
          Showing an older copy of this session: Accept, Approve and the checked badge are paused until a reload succeeds.{' '}
          <button className="link" onClick={() => void refresh()}>Reload now</button>
        </div>
      )}

      <main className={`stage step-${step}${id ? ' with-video' : ''}`}>
        <div className="content">
          {step === 'capture' && <Capture snap={snap} act={act} pending={pending} onCreated={created} />}
          {snap && step === 'review' && (
            <Review snap={snap} act={act} pending={pending} seek={seek} stale={stale} videoTime={videoTime} onAccepted={() => setChosen('twin')} />
          )}
          {snap && step === 'loop' && <Loop snap={snap} act={act} pending={pending} seek={seek} stale={stale} />}
          {snap && step === 'twin' && <Twin snap={snap} act={act} pending={pending} seek={seek} stale={stale} videoRef={videoRef} />}
          {snap && step === 'investigate' && <Investigate snap={snap} act={act} pending={pending} seek={seek} stale={stale} />}
        </div>
        {id && (
          <aside className="video-pane">
            <video ref={videoRef} src={snap?.video.url ?? videoUrl(id)} controls playsInline muted preload="metadata"
              onTimeUpdate={(e) => setVideoTime(e.currentTarget.currentTime)} onSeeked={(e) => setVideoTime(e.currentTarget.currentTime)} />
            <p className="muted small">Walk-through video · t = {fmtT(videoTime)}</p>
          </aside>
        )}
      </main>
      {snap && <ReportDrawer snap={snap} open={drawer} onClose={closeDrawer} />}
    </div>
  )
}
