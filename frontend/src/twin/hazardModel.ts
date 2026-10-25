import type { HazardType } from './types.ts';

export interface HazardInfo {
  label: string;
  /** Kind colour; matches the scene palette. */
  color: string;
  /** Default time until the zone is untenable, from the declared building-v2 model. */
  untenable_s: number | null;
}

export const HAZARD_ORDER: readonly HazardType[] = ['FIRE', 'SMOKE', 'GAS', 'CHEMICAL', 'WATER'];

export const HAZARD_INFO: Record<HazardType, HazardInfo> = {
  FIRE: { label: 'Fire', color: '#ff5a36', untenable_s: 6 },
  SMOKE: { label: 'Smoke', color: '#8f9995', untenable_s: 12 },
  GAS: { label: 'Gas', color: '#d9e84a', untenable_s: 10 },
  CHEMICAL: { label: 'Chemical', color: '#b56cff', untenable_s: 10 },
  WATER: { label: 'Water', color: '#3fa9ff', untenable_s: null },
};

/**
 * One honest line per type: what the declared model does, nothing more.
 * Gas never says a door moves; water never says a door changes.
 */
export function hazardHint(type: HazardType, untenableS?: number | null): string {
  const t = untenableS ?? HAZARD_INFO[type].untenable_s;
  switch (type) {
    case 'FIRE': return `No entry · fire doors close to entry · people inside leave until ${t} s`;
    case 'SMOKE': return `Half speed · no entry · untenable at ${t} s`;
    case 'GAS': return 'No entry · nothing near it is switched or moved · responders vent to the outside';
    case 'CHEMICAL': return `No entry · doors close to confine · people inside leave until ${t} s`;
    case 'WATER': return 'Passable at half speed · no door changes';
  }
}

export const hazardLabel = (type: HazardType) => HAZARD_INFO[type].label;
