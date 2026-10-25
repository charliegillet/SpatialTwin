import { describe, expect, it } from 'vitest'

// Copy rules (global constraints): these words never appear in shipped UI source.
const BANNED = /\b(safe|safely|safety|compliant|compliance|survive|survives|survived|evacuated)\b/i
const sources = import.meta.glob(['../**/*.ts', '../**/*.tsx', '../**/*.css', '!../**/*.test.ts'], {
  query: '?raw', import: 'default', eager: true,
}) as Record<string, string>

describe('copy rules', () => {
  it('scans the app sources', () => {
    expect(Object.keys(sources).some((p) => p.endsWith('App.tsx'))).toBe(true)
  })
  it('never uses banned words', () => {
    const hits = Object.entries(sources).filter(([, s]) => BANNED.test(s)).map(([p, s]) => `${p}: ${s.match(BANNED)![0]}`)
    expect(hits).toEqual([])
  })
})
