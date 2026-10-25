import { useCallback, useEffect, useRef, useState } from 'react'
import { api, runningJobs, snapshotIsStale, type Freshness } from '../api'
import type { Snapshot } from '../apiTypes'

export const errText = (e: unknown) => (e instanceof Error ? e.message : String(e))

/**
 * Loads the session snapshot; polls once a second while any job is queued or running, idle
 * otherwise. `stale` is true when a reload failed or a mutation returned after the last
 * successful reload: the UI then pauses Accept/Approve and the "checked" badge.
 */
export function useSession(id: string | null) {
  const [snap, setSnap] = useState<Snapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [fresh, setFresh] = useState<Freshness>({ okAt: 0, errorAt: 0, mutatedAt: 0 })
  const seq = useRef(0)
  const applied = useRef(0)

  const refresh = useCallback(async () => {
    if (!id) return
    const my = ++seq.current
    try {
      const s = await api.snapshot(id)
      if (my < applied.current) return // an older response arriving late: drop it
      applied.current = my
      setSnap(s)
      setError(null)
      setFresh((f) => ({ ...f, okAt: Math.max(f.okAt, my) }))
    } catch (e) {
      if (my < applied.current) return
      setError(errText(e))
      setFresh((f) => ({ ...f, errorAt: Math.max(f.errorAt, my) }))
    }
  }, [id])

  /** Call when a mutation returns, before refreshing. */
  const markMutated = useCallback(() => {
    const my = ++seq.current
    setFresh((f) => ({ ...f, mutatedAt: Math.max(f.mutatedAt, my) }))
  }, [])

  useEffect(() => {
    let live = true
    applied.current = seq.current
    queueMicrotask(() => {
      if (!live) return
      setSnap(null)
      setError(null)
      void refresh()
    })
    return () => { live = false }
  }, [refresh])

  const busy = snap ? runningJobs(snap).length > 0 : false
  useEffect(() => {
    if (!busy) return
    const t = setInterval(() => void refresh(), 1000)
    return () => clearInterval(t)
  }, [busy, refresh])

  return { snap, error, refresh, markMutated, busy, stale: !!snap && snapshotIsStale(fresh) }
}
