// Evacuation playback model: discrete timeline frames only (no interpolation, no invented positions).
import type { DoorPlanResponse, TimelineFrameV2, VenueV2 } from './types.ts';

export const PLAYBACK_CAPTION = 'Modeled occupancy · not positions';
/** Autoplay sweeps the whole timeline in about this long. */
export const AUTOPLAY_MS = 6000;

export function frames(plan: DoorPlanResponse | null): TimelineFrameV2[] {
  return plan?.chosen?.timeline ?? [];
}

export function lastIndex(plan: DoorPlanResponse | null): number {
  return Math.max(0, frames(plan).length - 1);
}

export function clampIndex(plan: DoorPlanResponse | null, index: number): number {
  const last = lastIndex(plan);
  if (!Number.isFinite(index)) return 0;
  return Math.min(last, Math.max(0, Math.round(index)));
}

/** Scrubber position (0..last) to the frame's time in seconds. */
export function timeForIndex(plan: DoorPlanResponse | null, index: number): number {
  const list = frames(plan);
  return list.length ? list[clampIndex(plan, index)].time_seconds : 0;
}

/** Latest frame whose time is at or before t (discrete: never between frames). */
export function indexForTime(plan: DoorPlanResponse | null, seconds: number): number {
  const list = frames(plan);
  let found = 0;
  for (let i = 0; i < list.length; i++) if (list[i].time_seconds <= seconds) found = i;
  return found;
}

/** Delay between autoplay frames. */
export function stepDelayMs(plan: DoorPlanResponse | null): number {
  return AUTOPLAY_MS / Math.max(1, lastIndex(plan));
}

/** 0..1 fill strength: count against the room's reference (initial or peak, at least 1). */
export function intensity(count: number, reference: number): number {
  if (!Number.isFinite(count) || count <= 0) return 0;
  return Math.min(1, count / Math.max(1, reference));
}

function lookup(map: Record<string, number> | undefined, id: string): number {
  if (!map) return 0;
  return map[id] ?? map[id.toLowerCase()] ?? 0;
}

export interface PlaybackZone { id: string; name: string; count: number; intensity: number; label: string }
export interface PlaybackExit { id: string; count: number; label: string }
export interface PlaybackView {
  index: number;
  last: number;
  time: number;
  timeLabel: string;
  atEnd: boolean;
  zones: PlaybackZone[];
  exits: PlaybackExit[];
  transit: string | null;
  completed: number;
}

export function playbackView(venue: VenueV2, plan: DoorPlanResponse | null, requested: number): PlaybackView | null {
  const list = frames(plan);
  if (!plan || list.length === 0) return null;
  const index = clampIndex(plan, requested);
  const frame = list[index];
  const zones = venue.zones.map((zone) => {
    const peak = Math.max(zone.initial_occupants, ...list.map((f) => lookup(f.occupancy, zone.id)));
    const count = lookup(frame.occupancy, zone.id);
    return { id: zone.id, name: zone.name, count, intensity: intensity(count, peak), label: `${zone.name} ${count}` };
  });
  const exits = venue.exits.map((exit) => {
    const count = lookup(frame.exits_cumulative, exit.id);
    return { id: exit.id, count, label: `${exit.id} · ${count}` };
  });
  return {
    index,
    last: list.length - 1,
    time: frame.time_seconds,
    timeLabel: `t = ${frame.time_seconds} s`,
    atEnd: index === list.length - 1,
    zones,
    exits,
    transit: frame.in_transit > 0 ? `${frame.in_transit} between rooms` : null,
    completed: frame.total_completed,
  };
}
