import type { CritiqueRound, DoorCandidate, DraftReceipt, DraftView, Provenance } from '../api/real2sim.ts';
import { MAX_CONTROLLABLE_DOORS } from '../api/real2sim.ts';

/** Pure view helpers for the Real2Sim panel: copy, selection rules and formatting live here so node tests cover them
 *  without rendering React. */

export type Real2SimStage = 'idle' | 'uploading' | 'extracting' | 'checking' | 'critiquing' | 'ready' | 'accepting' | 'accepted' | 'failed';

/** Thought summaries are model text (and may quote the image). They are rendered as plain text; the only markup honoured
 *  is a simple **bold** heading, found by splitting, never by injecting HTML. */
export interface TextSegment { text: string; bold: boolean }
export function thoughtSegments(text: string): TextSegment[] {
  const segments: TextSegment[] = [];
  const pattern = /\*\*([^*]+)\*\*/g;
  let last = 0;
  for (let match = pattern.exec(text); match; match = pattern.exec(text)) {
    if (match.index > last) segments.push({ text: text.slice(last, match.index), bold: false });
    segments.push({ text: match[1], bold: true });
    last = match.index + match[0].length;
  }
  if (last < text.length) segments.push({ text: text.slice(last), bold: false });
  return segments;
}

export interface ProgressStep { key: 'read' | 'check' | 'critique' | 'ready'; label: string; state: 'done' | 'active' | 'pending' }

/** Reading -> Checking -> Fixing (critique) -> Ready. The Fixing step only appears when a critique round ran or is running. */
export function progressSteps(stage: Real2SimStage, hadCritique: boolean): ProgressStep[] {
  const order: Record<Real2SimStage, number> = { idle: -1, uploading: 0, extracting: 0, checking: 1, critiquing: 2, ready: 3, accepting: 3, accepted: 3, failed: -1 };
  const at = order[stage];
  const steps: ProgressStep[] = [
    { key: 'read', label: 'Reading', state: 'pending' },
    { key: 'check', label: 'Checking', state: 'pending' },
    ...(hadCritique || stage === 'critiquing' ? [{ key: 'critique' as const, label: 'Fixing (critique)', state: 'pending' as const }] : []),
    { key: 'ready', label: 'Ready', state: 'pending' },
  ];
  const position = (key: ProgressStep['key']) => key === 'read' ? 0 : key === 'check' ? 1 : key === 'critique' ? 2 : 3;
  const finished = stage === 'ready' || stage === 'accepting' || stage === 'accepted';
  return steps.map(step => {
    const pos = position(step.key);
    const state: ProgressStep['state'] = at < 0 ? 'pending' : finished ? 'done' : pos < at ? 'done' : pos === at ? 'active' : 'pending';
    return { ...step, state };
  });
}

/** Plain-language labels for `accept_blockers` (status:*, compile:*, graph error codes). */
const BLOCKERS: Record<string, string> = {
  'status:extracting': 'Still reading the drawing',
  'status:checking': 'Still checking the building',
  'status:critiquing': 'Still fixing errors',
  'status:failed': 'The reading failed',
  'status:accepted': 'Already accepted',
  'compile:no_exit_survived': 'No exit could be placed from the drawing',
  'compile:empty_drawing': 'Nothing could be built from the drawing',
  room_unreachable: 'A room cannot reach any exit',
  no_exit: 'The building has no exit',
  door_blocked: 'A door is blocked',
};
export function blockerLabel(code: string): string {
  if (BLOCKERS[code]) return BLOCKERS[code];
  const [kind, rest] = code.split(':');
  const words = (rest ?? kind).replace(/_/g, ' ');
  return kind === 'compile' ? `Could not build: ${words}` : kind === 'status' ? `Draft is ${words}` : `Check failed: ${words}`;
}

/** Toggles a controllable door; a 4th choice is refused (the server also rejects it with too_many_controllable_doors). */
export function toggleDoor(selected: readonly string[], key: string, max = MAX_CONTROLLABLE_DOORS): string[] {
  if (selected.includes(key)) return selected.filter(item => item !== key);
  return selected.length >= max ? [...selected] : [...selected, key];
}

/** Keeps only keys that are still candidates (a refresh can change the candidate list) and at most `max`. */
export function reconcileSelection(selected: readonly string[], candidates: readonly DoorCandidate[], max = MAX_CONTROLLABLE_DOORS): string[] {
  const known = new Set(candidates.map(candidate => candidate.key));
  return selected.filter(key => known.has(key)).slice(0, max);
}

export type NumberRead = { ok: true; value: number | undefined } | { ok: false; message: string };

/** Optional numeric field: empty -> omitted. Headcount is an integer 0-5000; width is > 0 and <= 500 metres. */
export function readHeadcount(text: string): NumberRead {
  const trimmed = text.trim();
  if (!trimmed) return { ok: true, value: undefined };
  if (!/^\d{1,4}$/.test(trimmed) || Number(trimmed) > 5000) return { ok: false, message: 'Headcount is a whole number from 0 to 5000' };
  return { ok: true, value: Number(trimmed) };
}
export function readBuildingWidth(text: string): NumberRead {
  const trimmed = text.trim().replace(',', '.');
  if (!trimmed) return { ok: true, value: undefined };
  const value = Number(trimmed);
  if (!/^\d+(\.\d+)?$/.test(trimmed) || !Number.isFinite(value) || value <= 0 || value > 500) return { ok: false, message: 'Building width is metres, more than 0 and up to 500' };
  return { ok: true, value };
}

/** Why Accept is disabled, or null when it may be pressed. Blockers come from the server preview; the local rules cover the form. */
export function acceptDisabledReason(input: { stage: Real2SimStage; blockers: readonly string[]; headcountError?: string; widthError?: string; unreachableResolved?: boolean }): string | null {
  if (input.stage === 'accepting') return 'Accepting…';
  if (input.stage !== 'ready') return 'The draft is not ready yet';
  // Unreachable rooms the operator left out no longer block; the server re-runs every check at Accept.
  const blockers = input.unreachableResolved ? input.blockers.filter(code => code !== 'room_unreachable') : input.blockers;
  if (blockers.length) return blockers.map(blockerLabel).join('. ');
  return input.headcountError || input.widthError || null;
}

export const PROVENANCE_SHORT: Record<Provenance, string> = {
  live: 'Live Gemini 4 Argon',
  synthetic: 'Synthetic saved run',
  saved_run: 'Saved run (recorded)',
};

export interface ReceiptView { provenance: string; fullLabel: string; model: string | null; latency: string | null; tokens: string | null; thinking: string | null; tone: 'live' | 'saved' }

const seconds = (ms: number) => `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)} s`;

/** The receipt chip. Live readings show model, latency, tokens and thinking level; saved runs say so and make no provider claim. */
export function receiptView(view: Pick<DraftView, 'provenance' | 'provenance_label' | 'receipts'>): ReceiptView {
  const live = view.provenance === 'live';
  const receipt: DraftReceipt | undefined = view.receipts.find(item => item.phase === 'extract') ?? view.receipts[0];
  const tokens = receipt?.token_usage?.total_tokens;
  return {
    provenance: PROVENANCE_SHORT[view.provenance], fullLabel: view.provenance_label, tone: live ? 'live' : 'saved',
    model: live ? receipt?.provider_model ?? null : null,
    latency: live && receipt?.latency_ms != null ? seconds(receipt.latency_ms) : null,
    tokens: live && tokens != null ? `${tokens.toLocaleString('en-US')} tokens` : null,
    thinking: live && receipt?.thinking_level ? `${receipt.thinking_level} thinking` : null,
  };
}

/** "round 1: 3 errors → 0". Falls back to the server's own note when the counts are missing. */
export function roundLine(round: CritiqueRound): string {
  const before = round.issues_before.compile_failed ? 'nothing compiled' : `${round.issues_before.errors} error${round.issues_before.errors === 1 ? '' : 's'}`;
  const after = round.issues_after.compile_failed ? 'nothing compiled' : `${round.issues_after.errors}`;
  return `round ${round.round}: ${before} → ${after}${round.accepted ? ' (correction kept)' : ' (correction discarded)'}`;
}

export const countsLine = (counts: { rooms: number; doors: number; exits: number } | null): string | null =>
  counts ? `${counts.rooms} room${counts.rooms === 1 ? '' : 's'} · ${counts.doors} door${counts.doors === 1 ? '' : 's'} · ${counts.exits} exit${counts.exits === 1 ? '' : 's'}` : null;
