import type { CalibrationRequest, CardCandidate, CardRejection, ConfirmResponse, CornerId, HazardReadResponse, PlacedHazard, VenueV2 } from './types.ts';

// --- Corner clicks -----------------------------------------------------------------------------------------

/** The presenter clicks the printed corner markers in this order. */
export const CORNER_ORDER: readonly CornerId[] = ['TL', 'TR', 'BR', 'BL'];
export type ImageSize = [number, number];
export interface CornerState { points: [number, number][]; }

export const emptyCorners = (): CornerState => ({ points: [] });
export const nextCorner = (state: CornerState): CornerId | null => CORNER_ORDER[state.points.length] ?? null;
export const cornersComplete = (state: CornerState) => state.points.length === CORNER_ORDER.length;

/** Image-pixel point; a click outside the still or a fifth click is ignored. */
export function addCorner(state: CornerState, point: [number, number], size: ImageSize): CornerState {
  const [x, y] = point;
  if (cornersComplete(state) || !Number.isFinite(x) || !Number.isFinite(y) || x < 0 || y < 0 || x > size[0] || y > size[1]) return state;
  return { points: [...state.points, [Math.round(x), Math.round(y)]] };
}
export const undoCorner = (state: CornerState): CornerState => ({ points: state.points.slice(0, -1) });
export const resetCorners = emptyCorners;

/** Converts a click on the displayed still into image pixels. */
export function clickToImagePoint(click: { x: number; y: number }, rect: { left: number; top: number; width: number; height: number }, size: ImageSize): [number, number] {
  return [((click.x - rect.left) / rect.width) * size[0], ((click.y - rect.top) / rect.height) * size[1]];
}

export function toCalibrationRequest(state: CornerState, size: ImageSize): CalibrationRequest | null {
  if (!cornersComplete(state)) return null;
  const corners_px = Object.fromEntries(CORNER_ORDER.map((id, index) => [id, state.points[index]])) as CalibrationRequest['corners_px'];
  return { corners_px, image_size: size };
}

// --- Calibration storage (per camera and resolution) ----------------------------------------------------

export interface StoredCalibration { calibration_id: string; image_size: ImageSize; reprojection_error_m: number; }
type Store = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> | null | undefined;

export const calibrationKey = (deviceId: string | null | undefined, size: ImageSize) => `spatialtwin.sheetCalibration:${deviceId || 'default'}:${size[0]}x${size[1]}`;

export function loadCalibration(store: Store, key: string): StoredCalibration | null {
  try {
    const raw = store?.getItem(key);
    if (!raw) return null;
    const value = JSON.parse(raw);
    const ok = typeof value?.calibration_id === 'string' && Array.isArray(value.image_size) && value.image_size.length === 2 && Number.isFinite(value.reprojection_error_m);
    return ok ? value as StoredCalibration : null;
  } catch { return null; }
}
export function saveCalibration(store: Store, key: string, value: StoredCalibration): void {
  try { store?.setItem(key, JSON.stringify(value)); } catch { /* The calibration only lasts for this page. */ }
}
export function clearCalibration(store: Store, key: string): void {
  try { store?.removeItem(key); } catch { /* Nothing stored to clear. */ }
}
/** The backend no longer knows this calibration (restart) or the resolution moved: forget it and ask again. */
export const isStaleCalibration = (error: unknown): boolean => {
  const failure = error as { status?: number; detail?: string } | null;
  return failure?.status === 422 && (failure.detail === 'unknown_calibration' || failure.detail === 'calibration_image_size_mismatch');
};
/** Four corners always fit a homography exactly, so a reprojection error would say nothing; the line names the corners instead. */
export const calibratedLine = () => 'Calibrated · 4 corners';

/** The frame a read or calibration uses: the selected source decides, never whichever has data. */
export function selectFrame<T>(source: FrameSource, live: T | null, image: T | null): T | null {
  return source === 'image' ? image : live;
}

// --- Read result -> chips ---------------------------------------------------------------------------------

export const REJECTED_COPY: Record<CardRejection, string> = {
  no_calibration: 'Calibrate the sheet first',
  outside_building: 'Card is outside the plan',
  crosses_building_edge: 'Card crosses the plan edge',
};

export const READ_ERROR_COPY: Record<string, string> = {
  configuration_missing: 'Gemini is not configured on this laptop',
  provider_timeout: 'Gemini took too long. Read again.',
  provider_rate_limited: 'Gemini is busy. Wait a moment, then read again.',
  stale_capture: 'The still is out of date. Read again.',
  camera_read_busy: 'A read is already running',
  unknown_calibration: 'Calibration expired. Calibrate the sheet again.',
  calibration_image_size_mismatch: 'The camera resolution changed. Calibrate the sheet again.',
  unknown_read: 'That read expired. Read the board again.',
  missing_corner: 'Click all four corners',
  corner_outside_image: 'A corner is outside the image',
  corners_out_of_order: 'Click the corners in order: TL, TR, BR, BL',
  corners_too_close: 'Corners too close together. Click the four printed markers.',
  degenerate_calibration: 'Those corners do not form the sheet. Try again.',
};

export function errorCopy(code: string): string {
  if (code.startsWith('candidate_not_usable')) return 'That card cannot be used';
  return READ_ERROR_COPY[code] ?? 'The camera read did not complete';
}

const STATUS_COPY: Record<HazardReadResponse['status'], string> = {
  completed: '',
  failed: 'The read failed. Read again.',
  timed_out: 'Gemini took too long. Read again.',
  unavailable: 'Gemini is not available',
  cancelled: 'The read was cancelled',
};

/** One short line for a read that did not complete; null when it did. */
export function readFailure(read: Pick<HazardReadResponse, 'status' | 'errors'>): string | null {
  if (read.status === 'completed') return null;
  const first = read.errors.find(code => code in READ_ERROR_COPY);
  return first ? READ_ERROR_COPY[first] : STATUS_COPY[read.status];
}

/** Badge text for the confirmed camera cards: the plan's per-hazard provenance, else the confirm response's. */
export function cameraCardsLabel(hazards: readonly { source: string }[], plan: { hazards: readonly { source: string; camera_provenance?: 'live' | 'fixture' | null }[] } | null, seed: 'live' | 'fixture' | null): string | null {
  if (!hazards.some(item => item.source === 'camera')) return null;
  const seen = new Set((plan?.hazards ?? []).filter(item => item.source === 'camera' && item.camera_provenance).map(item => item.camera_provenance));
  if (seen.size === 0 && seed) seen.add(seed);
  const name = seen.size === 0 ? null : seen.size > 1 ? 'Fixture and live cards' : seen.has('live') ? 'Live Gemini card' : 'Fixture card';
  return name ? `Camera cards confirmed · ${name}` : 'Camera cards confirmed';
}

export const PROVENANCE_LABEL: Record<HazardReadResponse['provenance'], string> = { live: 'Live Gemini', fixture: 'Fixture', unavailable: 'Unavailable' };
export const seconds = (ms: number) => `${Math.max(0, Math.round(ms / 1000))} s`;

export interface ChipView {
  id: string;
  label: string;
  tone: 'ok' | 'warn' | 'muted';
  usable: boolean;
  confirmed: boolean;
  /** "Check card" with its reason, or the rejection copy. */
  note: string | null;
  /** Percent of the still, for the box overlay. */
  box: { left: number; top: number; width: number; height: number };
}

const pct = (value: number) => Math.min(100, Math.max(0, value / 10));

export type FrameSource = 'camera' | 'image';
export const SOURCE_LABEL: Record<FrameSource, string> = { camera: 'Live camera', image: 'Uploaded image' };

export function chipView(candidate: CardCandidate, read: Pick<HazardReadResponse, 'provenance' | 'latency_ms'>, venue: Pick<VenueV2, 'zones'> | null, confirmedIds: ReadonlySet<string> = new Set(), source: FrameSource = 'camera'): ChipView {
  const [ymin, xmin, ymax, xmax] = candidate.box_2d;
  const zone = candidate.zone_id ? venue?.zones.find(item => item.id === candidate.zone_id)?.name ?? candidate.zone_id : 'off plan';
  const low = candidate.confidence === 'low';
  const rejected = candidate.rejected_reason ? REJECTED_COPY[candidate.rejected_reason] : null;
  return {
    id: candidate.candidate_id,
    label: `${candidate.type} · ${zone} · ${PROVENANCE_LABEL[read.provenance]} · ${seconds(read.latency_ms)}${source === 'image' ? ` · ${SOURCE_LABEL.image}` : ''}`,
    tone: !candidate.usable ? 'muted' : low ? 'warn' : 'ok',
    usable: candidate.usable && !candidate.rejected_reason,
    confirmed: candidate.confirmed || confirmedIds.has(candidate.candidate_id),
    note: rejected ?? (low ? `Check card${candidate.low_confidence_reason ? ` · ${candidate.low_confidence_reason}` : ''}` : null),
    box: { left: pct(xmin), top: pct(ymin), width: pct(xmax - xmin), height: pct(ymax - ymin) },
  };
}

export const usableIds = (read: Pick<HazardReadResponse, 'candidates'>, confirmedIds: ReadonlySet<string> = new Set()): string[] =>
  read.candidates.filter(item => item.usable && !item.rejected_reason && !item.confirmed && !confirmedIds.has(item.candidate_id)).map(item => item.candidate_id);

/** The confirmed hazards, unchanged: id, type, position, zone and proposal_id all come straight from the backend. */
export function confirmedToPlaced(response: ConfirmResponse): PlacedHazard[] {
  return response.hazards.map(item => ({
    id: item.id,
    type: item.type,
    x: item.position.x,
    y: item.position.y,
    zone_id: item.zone_id,
    untenable_s: item.untenable_s ?? null,
    source: 'camera' as const,
    proposal_id: item.proposal_id,
  }));
}

/** Hex SHA-256 of base64 JPEG bytes, as the read endpoint expects. */
export async function sha256Base64(base64: string): Promise<string> {
  const bytes = Uint8Array.from(atob(base64), character => character.charCodeAt(0));
  const hash = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(hash), value => value.toString(16).padStart(2, '0')).join('');
}
