import type { DoorPlanResponse } from './types.ts';

export const ANNOUNCE_LABEL = 'Simulated announcement';
export const SPEECH_UNAVAILABLE = 'Speech is not available in this browser';

/** The plan's announcement, trimmed; empty means there is nothing to announce (no hazard). */
export const announcementText = (plan: (Pick<DoorPlanResponse, 'announcement'> & { chosen?: { validator_report?: { is_valid?: boolean } } }) | null | undefined): string =>
  plan?.chosen?.validator_report?.is_valid === false ? '' : plan?.announcement?.trim() ?? '';

const PLANNED = /Door (\S+) between (.+?) is to be opened\./g;

/** The plan says a door "is to be opened"; it "is open" only once its endpoint switch says so, and "is opening" while it
 *  moves. A door that never opened keeps the planned wording: the announcement never runs ahead of the device. */
export function confirmedAnnouncement(text: string, gates: ReadonlyArray<{ id: string; observed: string | null; moving: boolean; warn: boolean }>): string {
  return text.replace(PLANNED, (sentence, id: string, between: string) => {
    const gate = gates.find(item => item.id === id);
    if (!gate || gate.warn) return sentence;
    if (gate.observed === 'open' && !gate.moving) return `Door ${id} between ${between} is open.`;
    return gate.moving ? `Door ${id} between ${between} is opening.` : sentence;
  });
}

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

// ---- the fail-safe's voice ---------------------------------------------------------------------------------------

export interface VoicePlayer { play(blob: Blob): Promise<void>; stop(): void }

/** Plays one clip at a time; `play` resolves once playback starts and rejects when the browser blocks it. */
export function createAudioPlayer(make: (url: string) => { play(): Promise<void>; pause(): void } = url => new Audio(url),
  urls: { create(blob: Blob): string; revoke(url: string): void } = { create: blob => URL.createObjectURL(blob), revoke: url => URL.revokeObjectURL(url) }): VoicePlayer {
  let current: { audio: { pause(): void }; url: string } | null = null;
  const stop = () => {
    if (!current) return;
    try { current.audio.pause(); } catch { /* already stopped */ }
    urls.revoke(current.url);
    current = null;
  };
  return {
    async play(blob) {
      stop();
      const url = urls.create(blob);
      const audio = make(url);
      current = { audio, url };
      await audio.play();
    },
    stop,
  };
}

export type VoiceOutcome = { by: 'gemini'; model: string | null } | { by: 'browser' | 'none'; reason: string | null };

/** The fail-safe speaks once: its Gemini TTS clip when it was armed with that voice, otherwise (or when the clip cannot
 *  be fetched or played) the browser's voice. The outcome says which, so the screen can label it. */
export async function announceFailsafe(options: {
  voice: 'gemini' | 'browser'; text: string; player: VoicePlayer | null;
  fetchVoice: () => Promise<{ blob: Blob; model: string | null }>; speakBrowser: (text: string) => boolean;
}): Promise<VoiceOutcome> {
  let reason: string | null = null;
  if (options.voice === 'gemini') {
    if (!options.player) reason = 'audio_unavailable';
    else {
      try {
        const { blob, model } = await options.fetchVoice();
        await options.player.play(blob);
        return { by: 'gemini', model };
      } catch (error) {
        const code = (error as { code?: unknown } | null)?.code;
        reason = typeof code === 'string' && code ? code : error instanceof DOMException ? error.name : 'playback_failed';
      }
    }
  }
  return { by: options.speakBrowser(options.text) ? 'browser' : 'none', reason };
}

export function voiceNote(outcome: VoiceOutcome): string {
  if (outcome.by === 'gemini') return `Fail-safe voice · Gemini TTS${outcome.model ? ` (${outcome.model})` : ''}`;
  if (outcome.by === 'browser') return `Fail-safe voice · browser speech${outcome.reason ? ` (Gemini TTS: ${outcome.reason.replace(/_/g, ' ')})` : ''}`;
  return 'The fail-safe could not speak: the browser blocked audio. Click the page once, then press Announce.';
}
