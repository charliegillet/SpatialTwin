// Non-component helpers shared by the screens.
import { useMemo } from 'react'

export const fmtT = (t: number) => {
  const m = Math.floor(t / 60), s = Math.floor(t % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}
export const pct = (v: number | null | undefined) => (v == null ? 'n/a' : `${Math.round(v * 100)}%`)


/** Keep the same object identity until `key` changes, so polling doesn't rebuild the 3D scene. */
export function useStable<T>(value: T, key: string): T {
  // eslint-disable-next-line react-hooks/exhaustive-deps -- identity follows the key on purpose
  return useMemo(() => value, [key])
}
