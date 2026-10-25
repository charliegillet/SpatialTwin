// Mirrors the Python contracts exactly (snake_case, as in the JSON).
export interface Evidence {
  start_s: number
  end_s: number
  note: string
}

export interface Measure {
  low_m: number
  high_m: number
  basis: string
}

export interface Zone {
  id: string
  name: string
  /** [x, y, w, h] in meters, axis-aligned */
  rect: [number, number, number, number]
  occupants: number
  furniture_seen: boolean
  evidence: Evidence[]
}

export interface Door {
  id: string
  a: string
  /** Zone id, or "OUTSIDE" */
  b: string
  kind: string
  state: string
  clear_width: Measure
  position: [number, number]
  evidence: Evidence[]
}

export interface Keyframe {
  t_s: number
  zone_id: string
  x: number
  y: number
  heading_deg: number
}

export interface Anchor {
  door_id: string
  measured_width_m: number
}

export interface VenueGraph {
  schema_version: string
  video_sha256: string
  anchor: Anchor | null
  zones: Zone[]
  doors: Door[]
  keyframes: Keyframe[]
}
