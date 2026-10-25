import type { AiCapabilities, GateObservedState } from '../types.ts';

export type ChipTone = 'ok' | 'warn' | 'info' | 'muted';
export interface Chip { label: string; tone: ChipTone; }

/** Gate chip: what the endpoint reported, never what was requested. */
export function gateChip(state: GateObservedState | string | undefined, endpointReported: boolean): Chip {
  switch (state) {
    case 'CLOSED': return { label: 'P3 closed', tone: 'muted' };
    case 'OPEN': return endpointReported ? { label: 'P3 open · observed', tone: 'ok' } : { label: 'P3 open · unconfirmed', tone: 'warn' };
    case 'TRANSIT': return { label: 'P3 moving', tone: 'warn' };
    case 'FAULT': return { label: 'P3 fault', tone: 'warn' };
    default: return { label: 'P3 unknown', tone: 'warn' };
  }
}

export function checkedChip(hasSnapshot: boolean, planCurrent: boolean): Chip {
  if (!hasSnapshot) return { label: 'Connecting', tone: 'muted' };
  return planCurrent ? { label: 'Checked', tone: 'ok' } : { label: 'Unverified', tone: 'warn' };
}

export function hardwareChip(mode: string | null | undefined): Chip {
  if (mode === 'simulator') return { label: 'Simulator', tone: 'info' };
  if (mode === 'physical_serial') return { label: 'Board connected', tone: 'ok' };
  return { label: 'No board', tone: 'muted' };
}

export function crossingChip(plan: { completed_crossings: number; initial_population: number; horizon_seconds: number } | null | undefined): string | null {
  return plan ? `${plan.completed_crossings} / ${plan.initial_population} crossed · ${plan.horizon_seconds} s` : null;
}

interface AiResult { status: string; provenance?: string; provider_interaction_id?: string | null; }

/** Provenance of the latest AI result. A live result without a provider receipt is not shown as live. */
export function provenanceChip(result: AiResult | null | undefined): Chip | null {
  if (!result) return null;
  if (result.status !== 'completed') return { label: 'Unavailable', tone: 'warn' };
  if (result.provenance === 'live' && result.provider_interaction_id) return { label: 'Live Gemini', tone: 'ok' };
  if (result.provenance === 'fixture') return { label: 'Fixture', tone: 'info' };
  if (result.provenance === 'local') return { label: 'Local solver', tone: 'info' };
  return { label: 'Unavailable', tone: 'warn' };
}

/** Checked gain of opening P3, in the decision bar's words. */
export function gainText(gain: number | null): string {
  if (gain === null || !Number.isFinite(gain)) return '';
  if (gain === 0) return 'No gain';
  return `${gain > 0 ? '+' : '−'}${Math.abs(gain)} crossings`;
}

export type UploadKind = 'image' | 'video';

/** Uploaded files are not camera stills; the label and log line say so. */
export function uploadSourceLabel(kind: UploadKind): string {
  return `Uploaded ${kind === 'video' ? 'clip' : 'image'}`;
}

export function uploadLogLine(kind: UploadKind, thinking: string): string {
  return `${uploadSourceLabel(kind)} sent for analysis · ${thinking} thinking.`;
}

export type VideoMode = 'static' | 'agentic';

/** Both modes enabled: the operator chooses (static first). Otherwise the single enabled mode is used. */
export function videoModeOptions(capabilities: Pick<AiCapabilities, 'video_static' | 'video_agentic'> | null | undefined): VideoMode[] {
  const modes: VideoMode[] = [];
  if (capabilities?.video_static) modes.push('static');
  if (capabilities?.video_agentic) modes.push('agentic');
  return modes;
}

export function effectiveVideoMode(options: readonly VideoMode[], chosen: VideoMode): VideoMode {
  if (options.length === 1) return options[0];
  return options.includes(chosen) ? chosen : 'static';
}

/** Longest video deadline the API accepts. */
export const VIDEO_DEADLINE_SECONDS = 60;
