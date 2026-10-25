// Tiny runtime shape checker: every API response is validated before render.
export class ApiShapeError extends Error {
  path: string
  constructor(path: string, expected: string) {
    super(`bad API response at ${path || '<root>'}: expected ${expected}`)
    this.name = 'ApiShapeError'
    this.path = path
  }
}

export type Check = (v: unknown, path: string) => void

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)

export const str: Check = (v, p) => { if (typeof v !== 'string') throw new ApiShapeError(p, 'string') }
export const num: Check = (v, p) => { if (typeof v !== 'number' || !Number.isFinite(v)) throw new ApiShapeError(p, 'number') }
export const int: Check = (v, p) => { if (!Number.isInteger(v)) throw new ApiShapeError(p, 'integer') }
export const bool: Check = (v, p) => { if (typeof v !== 'boolean') throw new ApiShapeError(p, 'boolean') }
export const any: Check = () => {}

export const lit = (...vals: string[]): Check => (v, p) => {
  if (typeof v !== 'string' || !vals.includes(v)) throw new ApiShapeError(p, vals.join('|'))
}
export const nullable = (c: Check): Check => (v, p) => { if (v !== null) c(v, p) }
export const arr = (c: Check): Check => (v, p) => {
  if (!Array.isArray(v)) throw new ApiShapeError(p, 'array')
  v.forEach((x, i) => c(x, `${p}[${i}]`))
}
export const tuple = (...cs: Check[]): Check => (v, p) => {
  if (!Array.isArray(v) || v.length !== cs.length) throw new ApiShapeError(p, `tuple of ${cs.length}`)
  cs.forEach((c, i) => c(v[i], `${p}[${i}]`))
}
export const rec = (c: Check): Check => (v, p) => {
  if (!isObj(v)) throw new ApiShapeError(p, 'object')
  for (const [k, x] of Object.entries(v)) c(x, `${p}.${k}`)
}
const OPT = Symbol('optional')
type Field = Check & { [OPT]?: true }
/** Field may be missing or undefined; when present it must match. */
export const opt = (c: Check): Field => Object.assign((v: unknown, p: string) => { if (v !== undefined) c(v, p) }, { [OPT]: true as const })
export const obj = (fields: Record<string, Field>): Check => (v, p) => {
  if (!isObj(v)) throw new ApiShapeError(p, 'object')
  for (const [k, c] of Object.entries(fields)) {
    if (!(k in v) && !c[OPT]) throw new ApiShapeError(`${p}.${k}`, 'field')
    c(v[k], `${p}.${k}`)
  }
}

export function validate<T>(c: Check, v: unknown, root = ''): T {
  c(v, root)
  return v as T
}
