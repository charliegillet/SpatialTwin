import { useMemo, type ReactNode } from 'react'
import type { JobState, Snapshot } from '../apiTypes'

export type Act = (label: string, fn: () => Promise<unknown>) => Promise<boolean>
export interface ScreenProps {
  snap: Snapshot
  act: Act
  pending: string | null
  seek: (t: number) => void
}

export const fmtT = (t: number) => {
  const m = Math.floor(t / 60), s = Math.floor(t % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}
export const pct = (v: number | null | undefined) => (v == null ? 'n/a' : `${Math.round(v * 100)}%`)

export function Tag({ kind, children }: { kind: 'measured' | 'model' | 'checked' | 'declared' | 'approved' | 'warn' | 'error'; children: ReactNode }) {
  return <span className={`tag tag-${kind}`}>{children}</span>
}

export function JobLine({ name, job }: { name: string; job: JobState }) {
  return (
    <li className={`job job-${job.status}`}>
      <span className="job-dot" aria-hidden />
      <strong>{name}</strong> <span>{job.status}</span>
      {job.error && <span className="job-error">: {job.error}</span>}
    </li>
  )
}

export function Jobs({ snap }: { snap: Snapshot }) {
  const entries = Object.entries(snap.jobs)
  if (!entries.length) return null
  return <ul className="jobs" aria-label="Background jobs">{entries.map(([k, j]) => <JobLine key={k} name={k} job={j} />)}</ul>
}

/** Keep the same object identity until `key` changes, so polling doesn't rebuild the 3D scene. */
export function useStable<T>(value: T, key: string): T {
  // eslint-disable-next-line react-hooks/exhaustive-deps -- identity follows the key on purpose
  return useMemo(() => value, [key])
}
