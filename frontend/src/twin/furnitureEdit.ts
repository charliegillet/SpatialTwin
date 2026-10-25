import { pointInPolygon } from './geometry.ts';
import type { Point2, VenueFurniture, VenueV2 } from './types.ts';

/** Pure helpers for the optional furniture editor on a draft (looks only: nothing here touches zones, doors or exits).
 *  The working copy keeps ids F1..; the server renumbers them when it stores the edit. */

export const FURNITURE_KINDS = ['sofa', 'chair', 'table', 'desk', 'bed', 'shelf', 'plant', 'bin', 'stool'] as const;
export type FurnitureKind = typeof FURNITURE_KINDS[number];
export const MAX_PIECES = 60;

/** Typical sizes (width, depth, height in metres) for a newly added piece. */
const SIZES: Record<FurnitureKind, [number, number, number]> = {
  sofa: [2.0, 0.9, 0.8], chair: [0.5, 0.5, 0.9], table: [1.2, 0.8, 0.75], desk: [1.4, 0.7, 0.75], bed: [2.0, 1.6, 0.5],
  shelf: [1.0, 0.4, 1.8], plant: [0.5, 0.5, 1.2], bin: [0.4, 0.4, 0.6], stool: [0.4, 0.4, 0.7],
};
const LABELS: Record<FurnitureKind, string> = {
  sofa: 'Sofa', chair: 'Chair', table: 'Table', desk: 'Desk', bed: 'Bed', shelf: 'Shelf', plant: 'Plant', bin: 'Bin', stool: 'Stool',
};

export const pieceId = (piece: VenueFurniture, index: number) => piece.id ?? `F${index + 1}`;

/** The working copy with stable ids. */
export function furnitureOf(venue: VenueV2): VenueFurniture[] {
  return (venue.appearance?.furniture ?? []).map((piece, index) => ({ ...piece, id: pieceId(piece, index) }));
}

/** The venue drawn with the working copy (zones, doors and exits are the same objects). */
export function withFurniture(venue: VenueV2, furniture: VenueFurniture[]): VenueV2 {
  return { ...venue, appearance: { zones: venue.appearance?.zones ?? {}, furniture, features: venue.appearance?.features ?? [] } };
}

function centroid(polygon: Point2[]): Point2 {
  const xs = polygon.map(p => p[0]);
  const ys = polygon.map(p => p[1]);
  return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
}

const round2 = (value: number) => Math.round(value * 100) / 100;

function nextId(furniture: VenueFurniture[]): string {
  const used = furniture.map(piece => Number(/^F(\d+)$/.exec(piece.id ?? '')?.[1] ?? 0));
  return `F${Math.max(0, ...used) + 1}`;
}

/** A new piece of `kind` in the middle of `zoneId`; unchanged when the room is unknown or the list is full. */
export function addPiece(venue: VenueV2, furniture: VenueFurniture[], zoneId: string, kind: FurnitureKind): { furniture: VenueFurniture[]; id: string | null } {
  const zone = venue.zones.find(z => z.id === zoneId);
  if (!zone || furniture.length >= MAX_PIECES) return { furniture, id: null };
  const [width, depth, height] = SIZES[kind];
  const [x, y] = centroid(zone.polygon);
  const id = nextId(furniture);
  return { furniture: [...furniture, { id, zone: zoneId, label: LABELS[kind], category: kind, position: [round2(x), round2(y)], width, depth, height, yaw_deg: 0, color: '' }], id };
}

/** Moves a piece (kept inside the building); it joins whichever room it lands in. */
export function movePiece(venue: VenueV2, furniture: VenueFurniture[], id: string, position: Point2): VenueFurniture[] {
  const x = round2(Math.min(Math.max(position[0], 0), venue.extent[0]));
  const y = round2(Math.min(Math.max(position[1], 0), venue.extent[1]));
  const zone = venue.zones.find(z => pointInPolygon(x, y, z.polygon))?.id;
  return furniture.map(piece => piece.id === id ? { ...piece, position: [x, y], zone: zone ?? piece.zone } : piece);
}

/** Field edits from the form; sizes are clamped to what the server accepts. */
export function updatePiece(furniture: VenueFurniture[], id: string, patch: Partial<Omit<VenueFurniture, 'id' | 'zone' | 'position'>>): VenueFurniture[] {
  const clamp = (value: number | undefined, max: number) => value === undefined || !Number.isFinite(value) ? undefined : Math.min(Math.max(value, 0.05), max);
  return furniture.map(piece => {
    if (piece.id !== id) return piece;
    const next = { ...piece, ...patch };
    next.width = clamp(patch.width, 10) ?? piece.width;
    next.depth = clamp(patch.depth, 10) ?? piece.depth;
    next.height = clamp(patch.height, 4) ?? piece.height;
    if (patch.yaw_deg !== undefined && Number.isFinite(patch.yaw_deg)) next.yaw_deg = ((((patch.yaw_deg + 180) % 360) + 360) % 360) - 180;
    next.label = (next.label ?? '').slice(0, 40) || piece.label;
    next.category = (next.category ?? '').slice(0, 24) || 'furniture';
    return next;
  });
}

export const removePiece = (furniture: VenueFurniture[], id: string): VenueFurniture[] => furniture.filter(piece => piece.id !== id);

/** What the server stores: ids dropped (it renumbers), numbers rounded. */
export const furniturePayload = (furniture: VenueFurniture[]): VenueFurniture[] =>
  furniture.map(({ id: _id, ...piece }) => ({ ...piece, position: [round2(piece.position[0]), round2(piece.position[1])], width: round2(piece.width), depth: round2(piece.depth), height: round2(piece.height), yaw_deg: Math.round(piece.yaw_deg * 10) / 10 }));
