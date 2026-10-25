// Scene colours. Plan palette: canvas #070908, safe green, hazard red, pending amber; hazard kinds below.
// The building itself is drawn like an architect's cutaway model: pale walls with bright caps on a dark floor plate, so
// rooms read at a glance and the state colours (green, red, amber) stay the only saturated things on screen.
import type { DoorKind, DoorLamp, HazardType, ZoneStatus } from '../twin/types.ts';
import type { FloorKind } from '../twin/sceneModel.ts';

export const PALETTE = {
  canvas: '#070908',
  floor: '#111614',
  grid: '#1b2421',
  wall: '#b9c3bd',
  wallOuter: '#cfd7d2',
  wallTop: '#eef3ef',
  jamb: '#56645e',
  text: '#f2f5f1',
  muted: '#a3b1a9',
  safe: '#5cf28a',
  safeDeep: '#1d7a45',
  hazard: '#ff4d4f',
  pending: '#ffb454',
  lampOff: '#3a4540',
  slowed: '#6f8fb0',
} as const;

/** Floor plate per inferred room kind (lit albedo, so a little lighter than it renders): circulation a shade lighter,
 * stair cores cooler, service darker. Empty rooms must still read as floor, not as holes in the plan. */
export const FLOOR_COLOR: Record<FloorKind, string> = {
  room: '#252b28',
  circulation: '#2c3430',
  stair: '#262e38',
  service: '#1f2422',
};

/** Door leaves by kind. Fire and smoke doors are the red-brown of a rated door; motorized gates are steel. */
export const LEAF_COLOR: Record<DoorKind, string> = {
  fire_door: '#9c4632',
  smoke_door: '#8a5a3c',
  room_door: '#a48764',
  servo_door: '#6f8794',
  roller_door: '#7b858a',
  opening: '#a48764',
};

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
