export type Point = [number, number];
export interface PlumePuff { dx: number; dy: number; rx: number; ry: number; opacity: number; }

/** A static stack of soft ellipses rising from the target. Index 0 is the dense coral core at the base. */
export function plumePuffs(count = 5, height = 110): PlumePuff[] {
  const steps = Math.max(2, Math.min(6, Math.round(count)));
  return Array.from({ length: steps }, (_, index) => {
    const t = index / (steps - 1);
    const rx = 20 + t * 22;
    return { dx: 0 + (index % 2 ? 1 : -1) * t * 6, dy: 0 - t * height, rx, ry: rx * .72, opacity: Math.round((.7 - t * .55) * 100) / 100 };
  });
}

/** Chevron vertices (wing, tip, wing) for an arrow pointing along `direction`, with the tip at `tip`. */
export function chevronPoints(tip: Point, direction: Point, length: number, spread: number): [Point, Point, Point] {
  const size = Math.hypot(direction[0], direction[1]) || 1;
  const d: Point = [direction[0] / size, direction[1] / size];
  const n: Point = [-d[1], d[0]];
  const base: Point = [tip[0] - d[0] * length, tip[1] - d[1] * length];
  return [[base[0] + n[0] * spread, base[1] + n[1] * spread], tip, [base[0] - n[0] * spread, base[1] - n[1] * spread]];
}

export type ExitArrowState = 'flow' | 'blocked' | 'none';

/** One arrow per boundary: outward when checked flow exists, a marker when the boundary is blocked, nothing otherwise. */
export function exitArrows(input: { checked: boolean; breakdown?: Record<string, number> | null; blockedBoundaries?: readonly string[] | null }): { id: 'B1' | 'B2'; state: ExitArrowState }[] {
  return (['B1', 'B2'] as const).map(id => {
    if (input.blockedBoundaries?.includes(id)) return { id, state: 'blocked' as const };
    return { id, state: input.checked && (input.breakdown?.[id] ?? 0) > 0 ? 'flow' as const : 'none' as const };
  });
}

/** A solid arrow from `tail` to `tip`: a shaft of width `shaft` and a head `head` wide and `headLength` long. */
export function arrowPolygon(tail: Point, tip: Point, shaft: number, head: number, headLength: number): Point[] {
  const dx = tip[0] - tail[0];
  const dy = tip[1] - tail[1];
  const size = Math.hypot(dx, dy) || 1;
  const d: Point = [dx / size, dy / size];
  const n: Point = [-d[1], d[0]];
  const neck: Point = [tip[0] - d[0] * Math.min(headLength, size), tip[1] - d[1] * Math.min(headLength, size)];
  const at = (base: Point, offset: number): Point => [base[0] + n[0] * offset, base[1] + n[1] * offset];
  return [at(tail, shaft / 2), at(neck, shaft / 2), at(neck, head / 2), tip, at(neck, -head / 2), at(neck, -shaft / 2), at(tail, -shaft / 2)];
}
