import type { TwinMode } from './types.ts';

/** Camera twin (Phase 2). Set to false to hide it from the toggle if its rehearsal fails. */
export const CAMERA_TWIN_ENABLED = true;

export const MODE_LABEL: Record<TwinMode, string> = { tabletop: 'Tabletop', camera: 'Camera twin', sim: 'Simulation' };

/** Without the tabletop hardware the demo opens on the building twin; Tabletop stays available, listed last. */
export const DEFAULT_TWIN_MODE: TwinMode = 'sim';

export function visibleModes(cameraEnabled = CAMERA_TWIN_ENABLED): TwinMode[] {
  return cameraEnabled ? ['sim', 'camera', 'tabletop'] : ['sim', 'tabletop'];
}

/** Next judge always lands on the default mode. */
export const modeAfterReset = (): TwinMode => DEFAULT_TWIN_MODE;

export const MODE_LOCKED = 'Analysis running — wait or cancel';

export function canSwitchMode(locked: boolean): boolean {
  return !locked;
}
