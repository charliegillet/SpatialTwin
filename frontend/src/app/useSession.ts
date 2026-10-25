import { useCallback, useEffect, useRef, useState } from 'react'
import { api, runningJobs } from '../api'
import type { Snapshot } from '../apiTypes'

export const errText = (e: unknown) => (e instanceof Error ? e.message : String(e))

/** Loads the session snapshot; polls once a second while any job is queued or running, idle otherwise. */
export function useSession(id: string | null) {
  const [snap, setSnap] = useState<Snapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const issued = useRef(0)
  const applied = useRef(0)

  const refresh = useCallback(async () => {
    if (!id) return
    const my = ++issued.current
    try {
      const s = await api.snapshot(id)
      if (my < applied.current) return // an older response arriving late: drop it
      applied.current = my
      setSnap(s)
      setError(null)
    } catch (e) {
      if (my >= applied.current) setError(errText(e))
    }
  }, [id])

  useEffect(() => {
    setSnap(null)
    setError(null)
    void refresh()
  }, [refresh])

  const busy = snap ? runningJobs(snap).length > 0 : false
  useEffect(() => {
    if (!busy) return
    const t = setInterval(() => void refresh(), 1000)
    return () => clearInterval(t)
  }, [busy, refresh])

  return { snap, error, refresh, busy }
}
