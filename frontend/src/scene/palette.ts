// Scene colours. Plan palette: canvas #070908, safe green, hazard red, pending amber; hazard kinds below.
import type { DoorLamp, HazardType, ZoneStatus } from '../twin/types.ts';

export const PALETTE = {
  canvas: '#070908',
  floor: '#0b0e0d',
  grid: '#17201c',
  wall: '#1c2422',
  wallTop: '#2f3a36',
  text: '#f2f5f1',
  muted: '#a3b1a9',
  safe: '#5cf28a',
  safeDeep: '#1d7a45',
  hazard: '#ff4d4f',
  pending: '#ffb454',
  lampOff: '#3a4540',
  slowed: '#6f8fb0',
} as const;

export const HAZARD_COLOR: Record<HazardType, string> = {
  FIRE: '#ff5a36',
  SMOKE: '#8f9995',
  GAS: '#d9e84a',
  CHEMICAL: '#b56cff',
  WATER: '#3fa9ff',
};
export const FIRE_HOT = '#ffb020';

export const LAMP_COLOR: Record<DoorLamp, string> = {
  green: PALETTE.safe,
  red: PALETTE.hazard,
  red_static: PALETTE.hazard,
  off: PALETTE.lampOff,
};

export const ZONE_TINT: Record<ZoneStatus, { color: string; opacity: number }> = {
  passable: { color: PALETTE.safe, opacity: 0 },
  slowed: { color: PALETTE.slowed, opacity: 0.12 },
  no_entry: { color: PALETTE.hazard, opacity: 0.18 },
};
