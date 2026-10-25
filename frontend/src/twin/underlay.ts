// Map underlay: the accepted venue's source photo under the 3D model, in venue metres. Pure: no three.js, no React.
// GET /api/venues/{venue_id}/underlay (backend/app/venues/underlay.py) places the image by the compiler's own map;
// this module checks the answer, crops the photo to the building and computes the texture coordinates.
import type { Point2, VenueV2 } from './types.ts';

/** The built-in venue is authored: it has no photo, so it is never asked for one. */
export const NO_PHOTO_VENUES: ReadonlySet<string> = new Set(['building-v2']);

/** Opacity the photo starts at (0..1), and the steps the control offers. */
export const DEFAULT_UNDERLAY_OPACITY = 0.6;

export interface Underlay {
  venueId: string;
  /** The geometry the photo was placed against: drawn only under exactly this geometry. */
  geometryRevision: string;
  imageUrl: string;
  /** Image TL, TR, BR, BL in venue metres (x east, y north). */
  corners: [Point2, Point2, Point2, Point2];
  widthPx: number;
  heightPx: number;
  provenanceLabel: string;
}

export type UnderlayAnswer = { available: true; underlay: Underlay } | { available: false; reason: string };

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const isPoint = (value: unknown): value is Point2 => Array.isArray(value) && value.length === 2 && value.every(finite);

/** Anything malformed is "not available": a photo that cannot be placed exactly is not drawn at all. */
export function parseUnderlay(raw: unknown, venueId: string): UnderlayAnswer {
  if (!isRecord(raw) || raw.venue_id !== venueId) return { available: false, reason: 'invalid_response' };
  if (raw.available !== true) return { available: false, reason: typeof raw.reason === 'string' ? raw.reason : 'unavailable' };
  const corners = raw.corners_m;
  const { image_url: url, geometry_revision: revision, width_px: w, height_px: h, provenance_label: label } = raw;
  if (!Array.isArray(corners) || corners.length !== 4 || !corners.every(isPoint)) return { available: false, reason: 'invalid_response' };
  const [tl, tr, br, bl] = corners as Point2[];
  // The compiler's map is an axis-aligned scale and shift: anything else is not what the server promises.
  const axisAligned = tl[1] === tr[1] && bl[1] === br[1] && tl[0] === bl[0] && tr[0] === br[0] && tr[0] > tl[0] && tl[1] > bl[1];
  // Same origin only: the route the backend names for this venue, never an arbitrary URL.
  const prefix = `/api/venues/${encodeURIComponent(venueId)}/underlay`;
  const urlOk = typeof url === 'string' && url.startsWith(prefix) && !url.includes('//');
  if (!axisAligned || !urlOk || typeof revision !== 'string' || !finite(w) || !finite(h) || w <= 0 || h <= 0
    || typeof label !== 'string' || !label.trim()) return { available: false, reason: 'invalid_response' };
  return {
    available: true,
    underlay: { venueId, geometryRevision: revision, imageUrl: url, corners: [tl, tr, br, bl], widthPx: w, heightPx: h, provenanceLabel: label },
  };
}

/** True only when the photo was placed against the very geometry on screen (a re-read or replaced venue is not). */
export function underlayMatches(underlay: Underlay | null, venue: Pick<VenueV2, 'venue_id' | 'geometry_revision'>): underlay is Underlay {
  return underlay !== null && underlay.venueId === venue.venue_id && underlay.geometryRevision === venue.geometry_revision;
}

export interface UnderlayPlacement {
  /** The cropped rectangle drawn on the floor, venue metres: x0 < x1 (west to east), y0 < y1 (south to north). */
  x0: number; y0: number; x1: number; y1: number;
  /** Texture coordinates at the crop's corners (three.js flipY: v = 0 at the image's bottom edge). */
  u0: number; v0: number; u1: number; v1: number;
  /** Width of the soft edge as a fraction of the crop's width and height. */
  featherU: number; featherV: number;
}

/** Margin of photo kept around the building: enough to show the drawing's surroundings, not the whole poster. */
export function underlayMargin(extent: Point2): number {
  return Math.min(8, Math.max(3, 0.1 * Math.max(extent[0], extent[1])));
}

/** The photo cropped to the building plus a margin (and to the image itself), with its texture coordinates. */
export function underlayPlacement(underlay: Underlay, extent: Point2, margin = underlayMargin(extent)): UnderlayPlacement | null {
  const [tl, tr, , bl] = underlay.corners;
  const x0 = Math.max(tl[0], -margin);
  const x1 = Math.min(tr[0], extent[0] + margin);
  const y0 = Math.max(bl[1], -margin);
  const y1 = Math.min(tl[1], extent[1] + margin);
  if (!(x1 - x0 > 0.5 && y1 - y0 > 0.5)) return null;
  const u = (x: number) => (x - tl[0]) / (tr[0] - tl[0]);
  const v = (y: number) => (y - bl[1]) / (tl[1] - bl[1]);
  const feather = Math.min(2.5, margin * 0.6);
  return {
    x0, y0, x1, y1, u0: u(x0), v0: v(y0), u1: u(x1), v1: v(y1),
    featherU: Math.min(0.45, feather / (x1 - x0)), featherV: Math.min(0.45, feather / (y1 - y0)),
  };
}

/** An alpha ramp (size x size, one byte per texel, row 0 = south edge) fading the crop's edges to nothing. */
export function featherMask(size: number, featherU: number, featherV: number): Uint8Array {
  const out = new Uint8Array(size * size);
  const ramp = (t: number, f: number) => (f <= 0 ? 1 : Math.min(1, Math.max(0, Math.min(t, 1 - t) / f)));
  for (let row = 0; row < size; row++) {
    const t = (row + 0.5) / size;
    for (let col = 0; col < size; col++) {
      const s = (col + 0.5) / size;
      const a = ramp(s, featherU) * ramp(t, featherV);
      out[row * size + col] = Math.round(255 * a * a * (3 - 2 * a)); // smoothstep
    }
  }
  return out;
}

/** How opaque the room floors are drawn over the photo: with the photo up, the drawing is the floor, and the plate is
 * only a wash that keeps rooms darker than the paper around the building (never fully transparent). */
export function floorOpacity(underlayOpacity: number): number {
  return Math.max(0.15, 1 - 1.1 * Math.min(1, Math.max(0, underlayOpacity)));
}
