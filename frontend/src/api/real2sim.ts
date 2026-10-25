import { ApiError, requestJson } from './client.ts';

/** Client for the Real2Sim draft API (docs/plans/contracts/real2sim-api.md). Argon proposes, the local compiler and
 *  graph checks decide, an operator accepts: nothing here changes the active venue except `acceptDraft`. */

export const REAL2SIM_BASE = '/api/real2sim';
export const DRAFT_ID_PATTERN = /^r2s-[0-9a-f]{24}$/;
/** The server refuses sources over 8 MiB decoded; the client downscales before that and caps the long side. */
export const MAX_SOURCE_BYTES = 8 * 1024 * 1024;
export const MAX_LONG_SIDE_PX = 4096;
export const MAX_CONTROLLABLE_DOORS = 3;

export type DraftStatus = 'extracting' | 'checking' | 'critiquing' | 'ready' | 'failed' | 'accepted';
export type Provenance = 'live' | 'synthetic' | 'saved_run';
export type SourceKind = 'photo' | 'sketch' | 'pdf';
export type SourceMime = 'image/jpeg' | 'image/png' | 'application/pdf';
export type ThinkingLevel = 'low' | 'medium' | 'high';

export interface GraphIssue { code: string; severity: 'error' | 'warning'; message: string; element_ids: string[] }
export interface DraftCounts { rooms: number; doors: number; exits: number }
export interface DraftChecks { issues: GraphIssue[]; errors: number; warnings: number; compile_error: string | null; geometry_revision: string | null }
export interface DraftThought { phase: string; index?: number; text: string; recorded: boolean }
export interface CritiqueRound {
  round: number; accepted: boolean; note: string;
  issues_before: { errors: number; warnings: number; compile_failed: boolean };
  issues_after: { errors: number; warnings: number; compile_failed: boolean };
}
export interface DraftReceipt {
  phase: string; status: string; provenance: string; provider_model: string | null; thinking_level: string | null;
  latency_ms: number | null; first_output_ms: number | null; token_usage: { total_tokens?: number } | null; streamed: boolean;
}
export interface DoorCandidate { key: string; between: string[]; room_names: string[]; symbol: string; confidence: number | null; venue_door_id: string | null }

export interface DraftView {
  draft_id: string; revision: number; status: DraftStatus; mode: 'live' | 'fixture'; name: string | null;
  provenance: Provenance; provenance_label: string;
  unreadable: string[]; dropped: string[]; repaired: string[];
  checks: DraftChecks | null; rounds: CritiqueRound[]; critique_note: string | null;
  thoughts: DraftThought[]; receipts: DraftReceipt[]; errors: string[];
  draft: Record<string, unknown> | null;
  overlay_available: boolean; topdown_available: boolean;
  controllable_door_candidates: DoorCandidate[]; max_controllable_doors: number; accept_blockers: string[];
  accepted: { venue_id: string } | null;
}

export interface SavedRun {
  fixture_id: string; title: string; source_kind: SourceKind; provenance: Provenance; provenance_label: string;
  counts: DraftCounts | null; note: string;
}
export interface SavedRuns { fixtures_enabled: boolean; saved: SavedRun[] }
export interface CreateDraftResponse { draft_id: string; revision: number; status: DraftStatus }

export type CreateDraftRequest =
  | { mode: 'live'; image_base64: string; mime_type: SourceMime; source_kind: SourceKind; name?: string; thinking_level?: ThinkingLevel }
  | { mode: 'fixture'; fixture_id: string; name?: string };

export interface AcceptRequest {
  expected_revision: number; controllable_doors: string[]; headcount?: number; building_width_m?: number; make_active: boolean;
}
export interface AcceptResponse {
  venue_id: string; venue_revision: number; draft_revision: number; active_revision: number | null;
  geometry_revision: string; provenance: Provenance; warnings: GraphIssue[]; defaults: string[];
}

/** One parsed SSE event. `name` is the SSE event name; terminal events are `done` and `error`. */
export type DraftEvent =
  | { name: 'status'; status: DraftStatus; phase: string; revision: number; provenance: Provenance | null }
  | { name: 'thought'; thought: DraftThought }
  | { name: 'draft'; phase: string; counts: DraftCounts | null; unreadable: string[]; dropped: string[]; repaired: string[] }
  | { name: 'checks'; checks: DraftChecks }
  | { name: 'round'; round: CritiqueRound }
  | { name: 'done'; revision: number; errors: number; warnings: number }
  | { name: 'error'; code: string; revision: number | null };

// --- judge-readable error copy ---------------------------------------------------------------------------------

export const REAL2SIM_ERRORS: Record<string, string> = {
  real2sim_busy: 'Another reading is running. Wait for it to finish, then try again.',
  configuration_missing: 'Gemini is not configured on this server. Use a saved run instead.',
  fixtures_disabled: 'Saved runs are switched off on this server.',
  unknown_fixture: 'That saved run is not available any more.',
  source_too_large: 'That file is over 8 MB. Use a smaller photo.',
  unsupported_mime_type: 'Use a JPEG or PNG photo, or a PDF.',
  source_required: 'Choose a photo or PDF first.',
  invalid_source_encoding: 'The file could not be read. Try another one.',
  source_mime_mismatch: 'The file type does not match its contents. Try another file.',
  source_kind_mismatch: 'Pick the matching kind: photo or sketch for images, PDF for a PDF.',
  invalid_source_image: 'That image could not be opened. Try another one.',
  invalid_source_dimensions: 'That image is too large (max 8192 px a side). Use a smaller photo.',
  invalid_fixture_id: 'That saved run is not available.',
  invalid_fixture: 'That saved run is damaged and cannot be used.',
  runtime_storage_unavailable: 'The server cannot store drafts right now.',
  draft_id_conflict: 'Please try again.',
  unknown_draft: 'That draft is no longer available. Start over.',
  draft_not_ready: 'The draft is not ready to accept.',
  stale_draft_revision: 'The draft changed while you were reviewing it. It was refreshed; check your choices and accept again.',
  draft_closed: 'That draft was already accepted or closed. Start over.',
  too_many_controllable_doors: 'Choose at most 3 controllable doors.',
  duplicate_controllable_door: 'A door was chosen twice.',
  unknown_controllable_door: 'One of the chosen doors is not in this draft. Refresh and choose again.',
  invalid_venue_id: 'That venue id is not valid.',
  graph_check_errors: 'The building checks still report errors, so it cannot be accepted. Review the issues shown.',
  compile_failed: 'No usable building could be built from this drawing.',
  compiler_failure: 'The building could not be built from this drawing.',
};

/** Codes that arrive as the final `error` event / `errors[-1]` of a failed draft (provider and pipeline faults). */
export const PIPELINE_ERRORS: Record<string, string> = {
  provider_timeout: 'Gemini took too long to read the drawing. Try again, or use a saved run.',
  provider_rate_limited: 'Gemini is rate limited right now. Wait a moment and try again.',
  provider_access_denied: 'Gemini refused the request (access denied). Check the server key, or use a saved run.',
  provider_unavailable: 'Gemini is unavailable right now. Try again, or use a saved run.',
  provider_request_rejected: 'Gemini rejected this file. Try a clearer or smaller image.',
  provider_stream_error: 'The Gemini stream broke. Try again.',
  provider_stream_incomplete: 'The Gemini reading stopped early. Try again.',
  provider_failure: 'Gemini failed to read the drawing. Try again, or use a saved run.',
  provider_model_mismatch: 'The server did not get a Gemini 4 Argon reading, so it was discarded.',
  provider_receipt_missing: 'The reading came without a provider receipt, so it was discarded.',
  provider_status_not_completed: 'Gemini did not finish the reading. Try again.',
  unexpected_provider_step: 'Gemini returned an unexpected step, so the reading was discarded.',
  invalid_provider_output: 'Gemini returned a reading the checker could not parse. Try again.',
  draft_not_an_object: 'Gemini returned a reading the checker could not parse. Try again.',
  no_room_survived: 'No room could be read from this drawing. Try a clearer photo.',
  no_exit_survived: 'No exit could be read from this drawing. Try a clearer photo.',
  empty_drawing: 'Nothing could be read from this drawing. Try a clearer photo.',
  pipeline_interrupted: 'The server restarted while reading. Start over.',
  local_processing_failure: 'The server could not process this file. Try another one.',
};

export function real2simErrorMessage(status: number, code: string): string {
  if (code && REAL2SIM_ERRORS[code]) return REAL2SIM_ERRORS[code];
  if (code && PIPELINE_ERRORS[code]) return PIPELINE_ERRORS[code];
  if (status === 413) return REAL2SIM_ERRORS.source_too_large;
  if (status === 415) return REAL2SIM_ERRORS.unsupported_mime_type;
  if (status === 429) return REAL2SIM_ERRORS.real2sim_busy;
  if (status === 409) return REAL2SIM_ERRORS.stale_draft_revision;
  if (status === 404) return REAL2SIM_ERRORS.unknown_draft;
  if (status === 503) return 'The server could not do that right now. Try again, or use a saved run.';
  return '';
}

/** Copy for a failed draft's last error code (never free server text). */
export const pipelineErrorMessage = (code: string): string =>
  PIPELINE_ERRORS[code] ?? REAL2SIM_ERRORS[code] ?? 'The drawing could not be turned into a building. Try again, or use a saved run.';

// --- parsers ---------------------------------------------------------------------------------------------------

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const bad = (what: string): never => { throw new ApiError(`The server returned an unexpected ${what}.`, 502, 'invalid_response'); };
const STATUSES: readonly string[] = ['extracting', 'checking', 'critiquing', 'ready', 'failed', 'accepted'];
const PROVENANCES: readonly string[] = ['live', 'synthetic', 'saved_run'];
const KINDS: readonly string[] = ['photo', 'sketch', 'pdf'];
const isInt = (value: unknown): value is number => typeof value === 'number' && Number.isInteger(value);
const num = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;
const str = (value: unknown): string | null => typeof value === 'string' ? value : null;
const strings = (value: unknown, what: string): string[] => {
  if (!Array.isArray(value) || !value.every(item => typeof item === 'string')) return bad(what);
  return value as string[];
};

function parseIssue(raw: unknown): GraphIssue {
  if (!isRecord(raw) || typeof raw.code !== 'string' || typeof raw.message !== 'string' || (raw.severity !== 'error' && raw.severity !== 'warning')) return bad('check issue');
  return { code: raw.code, severity: raw.severity, message: raw.message, element_ids: Array.isArray(raw.element_ids) ? raw.element_ids.filter((id): id is string => typeof id === 'string') : [] };
}

export function parseChecks(raw: unknown): DraftChecks {
  if (!isRecord(raw) || !Array.isArray(raw.issues) || !isInt(raw.errors) || !isInt(raw.warnings)) return bad('check result');
  return { issues: raw.issues.map(parseIssue), errors: raw.errors, warnings: raw.warnings, compile_error: str(raw.compile_error), geometry_revision: str(raw.geometry_revision) };
}

function parseTally(raw: unknown): CritiqueRound['issues_before'] {
  if (!isRecord(raw) || !isInt(raw.errors) || !isInt(raw.warnings)) return bad('critique round');
  return { errors: raw.errors, warnings: raw.warnings, compile_failed: raw.compile_failed === true };
}

export function parseRound(raw: unknown): CritiqueRound {
  if (!isRecord(raw) || !isInt(raw.round) || typeof raw.note !== 'string') return bad('critique round');
  return { round: raw.round, accepted: raw.accepted === true, note: raw.note, issues_before: parseTally(raw.issues_before), issues_after: parseTally(raw.issues_after) };
}

function parseThought(raw: unknown): DraftThought {
  if (!isRecord(raw) || typeof raw.text !== 'string') return bad('thought');
  return { phase: str(raw.phase) ?? 'extract', index: isInt(raw.index) ? raw.index : undefined, text: raw.text, recorded: raw.recorded === true };
}

function parseReceipt(raw: unknown): DraftReceipt {
  if (!isRecord(raw)) return bad('receipt');
  const usage = isRecord(raw.token_usage) ? { total_tokens: num(raw.token_usage.total_tokens) ?? undefined } : null;
  return {
    phase: str(raw.phase) ?? '', status: str(raw.status) ?? '', provenance: str(raw.provenance) ?? '', provider_model: str(raw.provider_model),
    thinking_level: str(raw.thinking_level), latency_ms: num(raw.latency_ms), first_output_ms: num(raw.first_output_ms), token_usage: usage, streamed: raw.streamed === true,
  };
}

function parseCandidate(raw: unknown): DoorCandidate {
  if (!isRecord(raw) || typeof raw.key !== 'string') return bad('door candidate');
  return {
    key: raw.key, between: Array.isArray(raw.between) ? raw.between.filter((v): v is string => typeof v === 'string') : [],
    room_names: Array.isArray(raw.room_names) ? raw.room_names.filter((v): v is string => typeof v === 'string') : [],
    symbol: str(raw.symbol) ?? '', confidence: num(raw.confidence), venue_door_id: str(raw.venue_door_id),
  };
}

export function parseDraftView(raw: unknown): DraftView {
  if (!isRecord(raw) || typeof raw.draft_id !== 'string' || !DRAFT_ID_PATTERN.test(raw.draft_id) || !isInt(raw.revision)) return bad('draft');
  if (typeof raw.status !== 'string' || !STATUSES.includes(raw.status)) return bad('draft status');
  if (typeof raw.provenance !== 'string' || !PROVENANCES.includes(raw.provenance) || typeof raw.provenance_label !== 'string') return bad('draft provenance');
  for (const key of ['thoughts', 'receipts', 'rounds', 'controllable_door_candidates'] as const) if (!Array.isArray(raw[key])) bad(key);
  const accepted = isRecord(raw.accepted) && typeof raw.accepted.venue_id === 'string' ? { venue_id: raw.accepted.venue_id } : null;
  return {
    draft_id: raw.draft_id, revision: raw.revision, status: raw.status as DraftStatus, mode: raw.mode === 'fixture' ? 'fixture' : 'live', name: str(raw.name),
    provenance: raw.provenance as Provenance, provenance_label: raw.provenance_label,
    unreadable: strings(raw.unreadable, 'unreadable list'), dropped: strings(raw.dropped, 'dropped list'), repaired: strings(raw.repaired, 'repaired list'),
    checks: raw.checks == null ? null : parseChecks(raw.checks),
    rounds: (raw.rounds as unknown[]).map(parseRound), critique_note: str(raw.critique_note),
    thoughts: (raw.thoughts as unknown[]).map(parseThought), receipts: (raw.receipts as unknown[]).map(parseReceipt),
    errors: strings(raw.errors, 'error list'), draft: isRecord(raw.draft) ? raw.draft : null,
    overlay_available: raw.overlay_available === true, topdown_available: raw.topdown_available === true,
    controllable_door_candidates: (raw.controllable_door_candidates as unknown[]).map(parseCandidate),
    max_controllable_doors: isInt(raw.max_controllable_doors) ? raw.max_controllable_doors : MAX_CONTROLLABLE_DOORS,
    accept_blockers: strings(raw.accept_blockers, 'blocker list'), accepted,
  };
}

export function parseCreateResponse(raw: unknown): CreateDraftResponse {
  if (!isRecord(raw) || typeof raw.draft_id !== 'string' || !DRAFT_ID_PATTERN.test(raw.draft_id) || !isInt(raw.revision) || typeof raw.status !== 'string' || !STATUSES.includes(raw.status)) return bad('draft');
  return { draft_id: raw.draft_id, revision: raw.revision, status: raw.status as DraftStatus };
}

function parseSavedRun(raw: unknown): SavedRun {
  if (!isRecord(raw) || typeof raw.fixture_id !== 'string' || typeof raw.title !== 'string' || typeof raw.provenance_label !== 'string') return bad('saved run');
  if (typeof raw.source_kind !== 'string' || !KINDS.includes(raw.source_kind) || typeof raw.provenance !== 'string' || !PROVENANCES.includes(raw.provenance)) return bad('saved run');
  const c = raw.counts;
  const counts = isRecord(c) && isInt(c.rooms) && isInt(c.doors) && isInt(c.exits) ? { rooms: c.rooms, doors: c.doors, exits: c.exits } : null;
  return { fixture_id: raw.fixture_id, title: raw.title, source_kind: raw.source_kind as SourceKind, provenance: raw.provenance as Provenance, provenance_label: raw.provenance_label, counts, note: str(raw.note) ?? '' };
}

export function parseSavedRuns(raw: unknown): SavedRuns {
  if (!isRecord(raw) || typeof raw.fixtures_enabled !== 'boolean' || !Array.isArray(raw.saved)) return bad('saved runs list');
  return { fixtures_enabled: raw.fixtures_enabled, saved: raw.saved.map(parseSavedRun) };
}

export function parseAcceptResponse(raw: unknown): AcceptResponse {
  if (!isRecord(raw) || typeof raw.venue_id !== 'string' || !isInt(raw.venue_revision) || !isInt(raw.draft_revision) || typeof raw.geometry_revision !== 'string') return bad('accept result');
  if (typeof raw.provenance !== 'string' || !PROVENANCES.includes(raw.provenance)) return bad('accept result');
  return {
    venue_id: raw.venue_id, venue_revision: raw.venue_revision, draft_revision: raw.draft_revision, active_revision: isInt(raw.active_revision) ? raw.active_revision : null,
    geometry_revision: raw.geometry_revision, provenance: raw.provenance as Provenance,
    warnings: Array.isArray(raw.warnings) ? raw.warnings.map(parseIssue) : [], defaults: Array.isArray(raw.defaults) ? raw.defaults.filter((v): v is string => typeof v === 'string') : [],
  };
}

function parseCounts(raw: unknown): DraftCounts | null {
  return isRecord(raw) && isInt(raw.rooms) && isInt(raw.doors) && isInt(raw.exits) ? { rooms: raw.rooms, doors: raw.doors, exits: raw.exits } : null;
}

/** Parses one SSE message. Unknown event names and malformed bodies return null (skipped, never fatal): a bad event
 *  must not break the stream, and the final view is always re-fetched at `done`. */
export function parseDraftEvent(name: string, data: string): DraftEvent | null {
  let body: unknown;
  try { body = JSON.parse(data); } catch { return null; }
  if (!isRecord(body)) return null;
  try {
    switch (name) {
      case 'status':
        if (typeof body.status !== 'string' || !STATUSES.includes(body.status) || !isInt(body.revision)) return null;
        return { name, status: body.status as DraftStatus, phase: str(body.phase) ?? '', revision: body.revision, provenance: typeof body.provenance === 'string' && PROVENANCES.includes(body.provenance) ? body.provenance as Provenance : null };
      case 'thought':
        return typeof body.text === 'string' ? { name, thought: parseThought(body) } : null;
      case 'draft':
        return { name, phase: str(body.phase) ?? '', counts: parseCounts(body.counts), unreadable: strings(body.unreadable ?? [], 'unreadable'), dropped: strings(body.dropped ?? [], 'dropped'), repaired: strings(body.repaired ?? [], 'repaired') };
      case 'checks':
        return { name, checks: parseChecks(body) };
      case 'round':
        return { name, round: parseRound(body) };
      case 'done':
        return isInt(body.revision) ? { name, revision: body.revision, errors: isInt(body.errors) ? body.errors : 0, warnings: isInt(body.warnings) ? body.warnings : 0 } : null;
      case 'error':
        return { name, code: str(body.code) ?? 'unknown', revision: isInt(body.revision) ? body.revision : null };
      default:
        return null;
    }
  } catch { return null; }
}

// --- requests --------------------------------------------------------------------------------------------------

const draftPath = (draftId: string) => `${REAL2SIM_BASE}/drafts/${encodeURIComponent(draftId)}`;
const describe = (status: number, _detail: string, code: string) => real2simErrorMessage(status, code);

export const createDraft = async (body: CreateDraftRequest, signal?: AbortSignal): Promise<CreateDraftResponse> =>
  parseCreateResponse(await requestJson<unknown>(`${REAL2SIM_BASE}/drafts`, { method: 'POST', body, signal, timeoutMs: 60_000, fallback: 'The drawing could not be sent', describe }));

export const fetchDraft = async (draftId: string, signal?: AbortSignal): Promise<DraftView> =>
  parseDraftView(await requestJson<unknown>(draftPath(draftId), { signal, timeoutMs: 15_000, fallback: 'The draft could not be loaded', describe }));

export const fetchSavedRuns = async (signal?: AbortSignal): Promise<SavedRuns> =>
  parseSavedRuns(await requestJson<unknown>(`${REAL2SIM_BASE}/saved`, { signal, timeoutMs: 10_000, fallback: 'Saved runs could not be listed', describe }));

export const acceptDraft = async (draftId: string, body: AcceptRequest, signal?: AbortSignal): Promise<AcceptResponse> =>
  parseAcceptResponse(await requestJson<unknown>(`${draftPath(draftId)}/accept`, { method: 'POST', body, signal, timeoutMs: 30_000, fallback: 'The building could not be accepted', describe }));

/** `rev` busts the browser cache after a critique round redraws the overlay (the server also sends no-store). */
export const overlayUrl = (draftId: string, revision: number) => `${draftPath(draftId)}/overlay.png?rev=${revision}`;
export const topdownUrl = (draftId: string, revision: number) => `${draftPath(draftId)}/topdown.png?rev=${revision}`;
export const eventsUrl = (draftId: string) => `${draftPath(draftId)}/events`;

// --- file preparation ------------------------------------------------------------------------------------------

/** Base64 without blowing the stack: String.fromCharCode.apply on a whole 8 MB array throws RangeError. The chunk is
 *  a multiple of 3 bytes so the per-chunk base64 pieces concatenate into one valid string with no mid-stream padding. */
export const BASE64_CHUNK = 3 * 8192;
export function bytesToBase64(bytes: Uint8Array): string {
  const parts: string[] = [];
  for (let offset = 0; offset < bytes.length; offset += BASE64_CHUNK) {
    parts.push(btoa(String.fromCharCode.apply(null, bytes.subarray(offset, offset + BASE64_CHUNK) as unknown as number[])));
  }
  return parts.join('');
}

export async function fileToBase64(file: Blob): Promise<string> {
  return bytesToBase64(new Uint8Array(await file.arrayBuffer()));
}

/** Resolves the mime to send: the browser's type, else the extension (some phones leave `type` empty). */
export function sourceMime(name: string, type: string): SourceMime | null {
  if (type === 'image/jpeg' || type === 'image/png' || type === 'application/pdf') return type;
  const ext = name.toLowerCase().split('.').pop();
  if (ext === 'jpg' || ext === 'jpeg') return 'image/jpeg';
  if (ext === 'png') return 'image/png';
  if (ext === 'pdf') return 'application/pdf';
  return null;
}

/** pdf <=> application/pdf; for an image the operator's photo/sketch choice stands. */
export const effectiveKind = (mime: SourceMime, chosen: SourceKind): SourceKind => mime === 'application/pdf' ? 'pdf' : chosen === 'pdf' ? 'photo' : chosen;

/** Scale that brings the long side to `max`, never upscaling. */
export function fitSize(width: number, height: number, max = MAX_LONG_SIDE_PX): { width: number; height: number; scale: number } {
  const scale = Math.min(1, max / Math.max(width, height));
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)), scale };
}

export interface PreparedSource { image_base64: string; mime_type: SourceMime; source_kind: SourceKind; downscaled: boolean }

/** Reads the picked file for upload. Client-side downscale (documented behaviour): an image whose long side exceeds
 *  4096 px, or whose size is near the server's 8 MiB cap, is redrawn on a canvas and re-encoded as JPEG (quality
 *  steps 0.9 -> 0.6, then a smaller size) so a 12 MP phone photo uploads quickly. 4096 px keeps wall labels legible
 *  at Argon's "high" image resolution. PDFs and small images are sent untouched. A canvas redraw applies EXIF
 *  rotation itself (imageOrientation "from-image") and drops the tag, so it never stacks with the server's rotation. */
export async function prepareSource(file: File, chosenKind: SourceKind): Promise<PreparedSource> {
  const mime = sourceMime(file.name, file.type);
  if (!mime) throw new ApiError(REAL2SIM_ERRORS.unsupported_mime_type, 415, 'unsupported_mime_type');
  const kind = effectiveKind(mime, chosenKind);
  if (mime === 'application/pdf') {
    if (file.size > MAX_SOURCE_BYTES) throw new ApiError(REAL2SIM_ERRORS.source_too_large, 413, 'source_too_large');
    return { image_base64: await fileToBase64(file), mime_type: mime, source_kind: kind, downscaled: false };
  }
  const bitmap = typeof createImageBitmap === 'function' ? await createImageBitmap(file, { imageOrientation: 'from-image' }).catch(() => null) : null;
  const oversized = bitmap ? Math.max(bitmap.width, bitmap.height) > MAX_LONG_SIDE_PX : false;
  if (!bitmap || (!oversized && file.size <= MAX_SOURCE_BYTES * 0.9)) {
    bitmap?.close();
    if (file.size > MAX_SOURCE_BYTES) throw new ApiError(REAL2SIM_ERRORS.source_too_large, 413, 'source_too_large');
    return { image_base64: await fileToBase64(file), mime_type: mime, source_kind: kind, downscaled: false };
  }
  try {
    let side = MAX_LONG_SIDE_PX;
    for (const quality of [0.9, 0.75, 0.6, 0.6]) {
      const size = fitSize(bitmap.width, bitmap.height, side);
      const canvas = document.createElement('canvas');
      canvas.width = size.width; canvas.height = size.height;
      const context = canvas.getContext('2d');
      if (!context) break;
      context.drawImage(bitmap, 0, 0, size.width, size.height);
      const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/jpeg', quality));
      if (blob && blob.size <= MAX_SOURCE_BYTES * 0.9) return { image_base64: await fileToBase64(blob), mime_type: 'image/jpeg', source_kind: kind, downscaled: true };
      side = Math.round(side * 0.75);
    }
  } finally { bitmap.close(); }
  throw new ApiError(REAL2SIM_ERRORS.source_too_large, 413, 'source_too_large');
}
