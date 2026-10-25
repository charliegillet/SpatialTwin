import type { DoorPlanResponse } from './types.ts';

export const ANNOUNCE_LABEL = 'Simulated announcement';
export const SPEECH_UNAVAILABLE = 'Speech is not available in this browser';

/** The plan's announcement, trimmed; empty means there is nothing to announce (no hazard). */
export const announcementText = (plan: (Pick<DoorPlanResponse, 'announcement'> & { chosen?: { validator_report?: { is_valid?: boolean } } }) | null | undefined): string =>
  plan?.chosen?.validator_report?.is_valid === false ? '' : plan?.announcement?.trim() ?? '';

interface Synth { speak(utterance: unknown): void; cancel(): void; }
type UtteranceCtor = new (text: string) => { lang?: string };

export const speechAvailable = (synth: Synth | undefined | null, ctor: UtteranceCtor | undefined | null): boolean =>
  Boolean(synth && ctor && typeof synth.speak === 'function' && typeof synth.cancel === 'function');

/** Cancels anything in progress, then speaks. Returns false when speech is unavailable or the text is empty. Never called automatically. */
export function speak(synth: Synth | undefined | null, ctor: UtteranceCtor | undefined | null, text: string): boolean {
  if (!text || !synth || !ctor || !speechAvailable(synth, ctor)) return false;
  synth.cancel();
  const utterance = new ctor(text);
  utterance.lang = 'en-GB';
  synth.speak(utterance);
  return true;
}

export function stopSpeaking(synth: Synth | undefined | null): void {
  try { synth?.cancel(); } catch { /* Nothing was speaking. */ }
}
