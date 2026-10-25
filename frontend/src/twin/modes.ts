import type { TwinMode } from './types.ts';

/** Camera twin (Phase 2). Set to false to hide it from the toggle if its rehearsal fails. */
export const CAMERA_TWIN_ENABLED = true;

export const MODE_LABEL: Record<TwinMode, string> = { build: 'Build', tabletop: 'Tabletop', camera: 'Camera twin', sim: 'Simulation' };

/** Without the tabletop hardware the demo opens on Act 1 (Build: read a floor plan); Tabletop stays available, last. */
export const DEFAULT_TWIN_MODE: TwinMode = 'build';

export function visibleModes(cameraEnabled = CAMERA_TWIN_ENABLED): TwinMode[] {
  return cameraEnabled ? ['build', 'sim', 'camera', 'tabletop'] : ['build', 'sim', 'tabletop'];
}

/** Next judge always lands on the default mode. */
export const modeAfterReset = (): TwinMode => DEFAULT_TWIN_MODE;

export const MODE_LOCKED = 'Analysis running — wait or cancel';

export function canSwitchMode(locked: boolean): boolean {
  return !locked;
}
