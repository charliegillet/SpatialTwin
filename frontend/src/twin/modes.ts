import type { TwinMode } from './types.ts';

/** Camera twin (Phase 2). Set to false to hide it from the toggle if its rehearsal fails. */
export const CAMERA_TWIN_ENABLED = true;

export const MODE_LABEL: Record<TwinMode, string> = { tabletop: 'Tabletop', camera: 'Camera twin', sim: 'Simulation' };

export function visibleModes(cameraEnabled = CAMERA_TWIN_ENABLED): TwinMode[] {
  return cameraEnabled ? ['tabletop', 'camera', 'sim'] : ['tabletop', 'sim'];
}

/** Next judge always lands on the tabletop. */
export const modeAfterReset = (): TwinMode => 'tabletop';

export const MODE_LOCKED = 'Analysis running — wait or cancel';

export function canSwitchMode(locked: boolean): boolean {
  return !locked;
}
