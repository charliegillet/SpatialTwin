import { planChecked } from './twinHero.ts';
import type { DoorPlanResponse, LightCode } from './types.ts';

export interface LightMeaning { label: string; tone: 'safe' | 'quiet' | 'hazard' | 'pending' | 'idle' | 'off'; flashing: boolean; }

/** Legend for the 24-character px string of building-v2 (on screen only). */
export const LIGHT_CODES: Record<LightCode, LightMeaning> = {
  F: { label: 'Safe exit', tone: 'safe', flashing: true },
  g: { label: 'Safe · no modeled flow', tone: 'quiet', flashing: false },
  X: { label: 'Exit unsafe', tone: 'hazard', flashing: false },
  S: { label: 'Held red', tone: 'hazard', flashing: false },
  O: { label: 'Door open', tone: 'safe', flashing: false },
  B: { label: 'Door closed', tone: 'idle', flashing: false },
  L: { label: 'Door locked', tone: 'pending', flashing: false },
  '0': { label: 'Off', tone: 'off', flashing: false },
};

export const LIGHTS_TITLE = 'Exit signs · model output';
export const PIXEL_COUNT = 24;

export interface LightPixel { index: number; code: string; known: boolean; meaning: LightMeaning; flashing: boolean; }
export interface LightGroup { id: string; pixels: LightPixel[]; }

const UNKNOWN: LightMeaning = { label: 'Unknown code', tone: 'off', flashing: false };

/** Groups the px string by led_map element (E1–E4, D4), in strip order. Under reduced motion nothing flashes. */
export function lightsView(plan: (Pick<DoorPlanResponse, 'lights'> & { chosen?: { validator_report?: { is_valid?: boolean } } }) | null, ledMap: Record<string, [number, number]>, reducedMotion = false): LightGroup[] {
  const px = planChecked(plan) ? plan?.lights.px : undefined;
  if (!px || px.length !== PIXEL_COUNT) return [];
  return Object.entries(ledMap)
    .sort((a, b) => a[1][0] - b[1][0])
    .map(([id, [first, last]]) => ({
      id,
      pixels: Array.from({ length: Math.max(0, last - first + 1) }, (_, offset) => {
        const index = first + offset;
        const code = px[index] ?? '0';
        const known = code in LIGHT_CODES;
        const meaning = known ? LIGHT_CODES[code as LightCode] : UNKNOWN;
        return { index, code, known, meaning, flashing: meaning.flashing && !reducedMotion };
      }),
    }));
}

/** Legend entries for the codes actually on screen, in a stable order. */
export function legendFor(groups: LightGroup[]): { code: string; meaning: LightMeaning }[] {
  const seen = new Set(groups.flatMap(group => group.pixels.map(pixel => pixel.code)));
  return (Object.keys(LIGHT_CODES) as LightCode[]).filter(code => seen.has(code) && code !== '0').map(code => ({ code, meaning: LIGHT_CODES[code] }));
}
