/**
 * Pure view logic for the phone exit sign and the phone hazard proposer (no DOM, no network: node-testable).
 *
 * The server (backend/app/signs) sends the lamp of the incident's latest checked plan; this file decides what a
 * phone shows for it. Safety rules: nothing without a checker-valid plan is drawn as a lamp, a stale or lost
 * connection never keeps showing a green arrow, and an expired link says so instead of freezing on old data.
 */

export type ExitLamp = 'green_flash' | 'green' | 'red_x' | 'red_static';
export type SignStatus = 'normal' | 'incident' | 'unchecked' | 'inactive';
export type HazardType = 'FIRE' | 'SMOKE' | 'GAS' | 'CHEMICAL' | 'WATER';

export interface SignExit { exit_id: string; name: string; lamp: ExitLamp | null; routed: number | null; }
export interface SignHazard { type: HazardType; room: string; }
export interface SignState {
  simulated: true;
  venue_id: string;
  venue_name: string;
  status: SignStatus;
  plan_revision: number | null;
  plan_label: 'primary' | 'fallback' | null;
  exits: SignExit[];
  hazards: SignHazard[];
  count_label: string;
  expires_at: string | null;
  server_time: string;
}

export type Connection = 'connecting' | 'live' | 'reconnecting' | 'expired';
export type SignKind = 'go' | 'go_flash' | 'unsafe' | 'locked' | 'unchecked' | 'inactive' | 'stale' | 'expired' | 'connecting' | 'missing';
export type Tone = 'green' | 'red' | 'amber' | 'grey';
export type Glyph = 'exit' | 'cross' | 'no_entry' | 'question' | 'offline';

export interface SignDisplay {
  kind: SignKind;
  tone: Tone;
  glyph: Glyph;
  flashing: boolean;
  headline: string;
  exitLabel: string;
  detail: string;
  footnote: string;
  /** What a screen reader hears when the sign changes. */
  announce: string;
}

/** No event (sign or heartbeat, every ~10 s) for this long means the sign is not being updated. */
export const STALE_AFTER_MS = 25_000;
export const SIMULATED_NOTE = 'Simulated sign · model output, not a certified exit sign';

export const HAZARD_LABELS: Record<HazardType, string> = {
  FIRE: 'Fire', SMOKE: 'Smoke', GAS: 'Gas', CHEMICAL: 'Chemical', WATER: 'Water',
};
const LAMPS: readonly string[] = ['green_flash', 'green', 'red_x', 'red_static'];
const STATUSES: readonly string[] = ['normal', 'incident', 'unchecked', 'inactive'];

export const routedLabel = (count: number) => `${count} modeled crossing${count === 1 ? '' : 's'}`;
export const exitLabel = (exit: Pick<SignExit, 'exit_id' | 'name'>) => `${exit.exit_id} · ${exit.name}`;

export function hazardSummary(hazards: readonly SignHazard[], max = 2): string {
  if (!hazards.length) return '';
  const shown = hazards.slice(0, max).map(item => `${HAZARD_LABELS[item.type] ?? item.type} · ${item.room}`).join(', ');
  return hazards.length > max ? `${shown} +${hazards.length - max}` : shown;
}

/** A defensive parse of the public sign payload; anything off-contract becomes null rather than a wrong sign. */
export function parseSignState(raw: unknown): SignState | null {
  if (!raw || typeof raw !== 'object') return null;
  const value = raw as Record<string, unknown>;
  if (typeof value.venue_id !== 'string' || typeof value.status !== 'string' || !STATUSES.includes(value.status)
    || !Array.isArray(value.exits) || !Array.isArray(value.hazards)) return null;
  const exits: SignExit[] = [];
  for (const item of value.exits) {
    if (!item || typeof item !== 'object') return null;
    const exit = item as Record<string, unknown>;
    if (typeof exit.exit_id !== 'string' || typeof exit.name !== 'string') return null;
    const lamp = typeof exit.lamp === 'string' && LAMPS.includes(exit.lamp) ? exit.lamp as ExitLamp : null;
    if (exit.lamp != null && lamp === null) return null;
    exits.push({ exit_id: exit.exit_id, name: exit.name, lamp, routed: typeof exit.routed === 'number' ? exit.routed : null });
  }
  const hazards = (value.hazards as unknown[]).filter((item): item is SignHazard =>
    !!item && typeof item === 'object' && typeof (item as SignHazard).type === 'string' && typeof (item as SignHazard).room === 'string');
  return {
    simulated: true,
    venue_id: value.venue_id,
    venue_name: typeof value.venue_name === 'string' ? value.venue_name : value.venue_id,
    status: value.status as SignStatus,
    plan_revision: typeof value.plan_revision === 'number' ? value.plan_revision : null,
    plan_label: value.plan_label === 'fallback' ? 'fallback' : value.plan_label === 'primary' ? 'primary' : null,
    exits,
    hazards,
    count_label: typeof value.count_label === 'string' ? value.count_label : 'modeled crossings',
    expires_at: typeof value.expires_at === 'string' ? value.expires_at : null,
    server_time: typeof value.server_time === 'string' ? value.server_time : '',
  };
}

const plain = (kind: SignKind, tone: Tone, glyph: Glyph, headline: string, detail: string, label = ''): SignDisplay =>
  ({ kind, tone, glyph, flashing: false, headline, exitLabel: label, detail, footnote: SIMULATED_NOTE, announce: `${headline}. ${detail}` });

/** One exit's face, given a fresh, checked state. */
export function exitDisplay(state: SignState, exit: SignExit, reducedMotion = false): SignDisplay {
  const label = exitLabel(exit);
  const footnote = state.plan_label === 'fallback' ? `${SIMULATED_NOTE} · fallback plan` : SIMULATED_NOTE;
  const face = (kind: SignKind, tone: Tone, glyph: Glyph, headline: string, detail: string, flashing = false): SignDisplay =>
    ({ kind, tone, glyph, flashing: flashing && !reducedMotion, headline, exitLabel: label, detail, footnote, announce: `${label}: ${headline}. ${detail}` });
  if (state.status === 'inactive') return { ...plain('inactive', 'grey', 'offline', 'SIGN IDLE', 'This building is not on the presenter screen', label), footnote };
  if (state.status === 'unchecked') return { ...plain('unchecked', 'amber', 'question', 'NO CHECKED PLAN', 'Follow staff instructions', label), footnote };
  const hazards = hazardSummary(state.hazards);
  switch (exit.lamp) {
    case 'red_x': return face('unsafe', 'red', 'cross', 'DO NOT USE', hazards ? `Hazard: ${hazards}` : 'Exit unsafe in the model');
    case 'red_static': return face('locked', 'red', 'no_entry', 'LOCKED · GAS', 'Do not open this exit');
    case 'green_flash':
      // People are routed through this exit; it only flashes during an incident (a calm building shows a steady sign).
      if (state.status === 'incident') {
        const routed = exit.routed != null ? `${routedLabel(exit.routed)} routed here` : 'Routed here';
        return face('go_flash', 'green', 'exit', 'EXIT', reducedMotion ? `Use this exit · ${routed}` : routed, true);
      }
      return face('go', 'green', 'exit', 'EXIT', 'No incident');
    case 'green': return face('go', 'green', 'exit', 'EXIT', state.status === 'incident' ? 'Safe · no modeled flow' : 'No incident');
    default: return face('go', 'green', 'exit', 'EXIT', 'No incident');
  }
}

export interface SignInput {
  state: SignState | null;
  exitId: string | null;
  connection: Connection;
  lastMessageAt: number | null;
  now: number;
  reducedMotion?: boolean;
}

export function isStale(input: Pick<SignInput, 'lastMessageAt' | 'now'>): boolean {
  return input.lastMessageAt !== null && input.now - input.lastMessageAt > STALE_AFTER_MS;
}

/** The whole page for a single-exit sign (or the first exit of a one-exit venue). */
export function signDisplay(input: SignInput): SignDisplay {
  if (input.connection === 'expired') return plain('expired', 'grey', 'offline', 'LINK EXPIRED', 'Scan the new QR code on the presenter screen');
  if (input.state === null) return plain('connecting', 'grey', 'offline', 'CONNECTING', 'Waiting for the presenter laptop');
  const exit = input.exitId !== null
    ? input.state.exits.find(item => item.exit_id === input.exitId)
    : input.state.exits.length === 1 ? input.state.exits[0] : undefined;
  if (!exit) return plain('missing', 'grey', 'question', 'UNKNOWN EXIT', `${input.exitId ?? 'No exit'} is not in ${input.state.venue_name}`);
  if (isStale(input)) return plain('stale', 'grey', 'offline', 'NOT UPDATING', 'Connection lost · follow staff instructions', exitLabel(exit));
  return exitDisplay(input.state, exit, input.reducedMotion);
}

/** Every exit of the venue, for an all-exits link or a loopback overview tab. */
export function overviewDisplays(input: SignInput): SignDisplay[] {
  if (input.state === null || input.connection === 'expired') return [signDisplay(input)];
  if (isStale(input)) return input.state.exits.map(exit => plain('stale', 'grey', 'offline', 'NOT UPDATING', 'Connection lost', exitLabel(exit)));
  return input.state.exits.map(exit => exitDisplay(input.state as SignState, exit, input.reducedMotion));
}

/** The connection chip under the sign: only shown when something is wrong. */
export function connectionNote(connection: Connection, lastMessageAt: number | null, now: number): string | null {
  if (connection === 'reconnecting') {
    if (lastMessageAt === null) return 'Reconnecting…';
    return `Reconnecting… last update ${Math.max(0, Math.round((now - lastMessageAt) / 1000))} s ago`;
  }
  return null;
}

// -- hazard proposals -----------------------------------------------------------------------------------------

export type ProposalStatus = 'pending' | 'confirmed' | 'rejected' | 'expired';
export interface Spot { x: number; y: number; }
export interface ProposalPublic { proposal_id: string; type: HazardType; room: string; position: Spot | null; status: ProposalStatus; created_at: string; decided_at: string | null; }
export interface Room { id: string; name: string; }
export type Pt = [number, number];
export interface PlanRoom { id: string; name: string; polygon: Pt[]; }
export interface PlanDoor { id: string; position: Pt; width: number; }
export interface PlanExit { id: string; name: string; position: Pt; kind: 'door' | 'stair' | 'window'; }
export interface Plan { extent: Pt; rooms: PlanRoom[]; doors: PlanDoor[]; exits: PlanExit[]; }
export interface ProposerState {
  simulated: true; venue_id: string; venue_name: string; active: boolean; rooms: Room[]; plan: Plan; hazard_types: HazardType[];
  mine: ProposalPublic[]; limits: { min_interval_seconds: number; max_pending_per_phone: number }; expires_at: string; server_time: string;
}

export const PROPOSAL_STATUS_LABELS: Record<ProposalStatus, string> = {
  pending: 'Waiting for the operator',
  confirmed: 'Confirmed by the operator',
  rejected: 'Rejected by the operator',
  expired: 'Expired before a decision',
};

/** Phone-readable copy for the proposal endpoint's error codes. */
export function proposeErrorMessage(status: number, code: string | null, retryAfter: number | null): string {
  if (status === 403 || status === 410) return 'This link has expired. Scan the new QR code on the presenter screen.';
  if (code === 'rate_limited') return retryAfter ? `Please wait ${retryAfter} s before sending another proposal.` : 'Please wait a moment before sending another proposal.';
  if (code === 'too_many_pending') return 'You already have proposals waiting. Wait for the operator to decide.';
  if (code === 'proposal_queue_full') return 'The operator has too many proposals waiting. Try again shortly.';
  if (code === 'venue_not_active') return 'This building is not on the presenter screen right now.';
  if (code === 'unknown_room') return 'That room is not in this building.';
  if (code === 'outside_building' || code === 'zone_mismatch') return 'That spot is outside the building. Tap inside a room.';
  return 'The proposal could not be sent. Try again.';
}

/** A spot (a tapped pin) is all a proposal needs; the server resolves the room and may still refuse it. */
/** A spot (a tapped pin) is all a proposal needs; the server resolves the room and may still refuse it. */
export function canSend(type: HazardType | null, spot: unknown, busy: boolean, active: boolean): boolean {
  return type !== null && spot !== null && spot !== undefined && !busy && active;
}

export const HAZARD_INFO: Record<HazardType, { label: string; colour: string; meaning: string }> = {
  FIRE: { label: 'Fire', colour: '#ef6a4c', meaning: 'No entry. Exits next to it are blocked.' },
  SMOKE: { label: 'Smoke', colour: '#9aa5a8', meaning: 'Slows people, then becomes untenable.' },
  GAS: { label: 'Gas', colour: '#e8c547', meaning: 'Nothing is switched nearby. Doors are locked.' },
  CHEMICAL: { label: 'Chemical', colour: '#b28cf0', meaning: 'No entry. Exits next to it are blocked.' },
  WATER: { label: 'Water', colour: '#5aa9e6', meaning: 'Slows people crossing it.' },
};

export const MAP_PAD_M = 1.5;

/** Even-odd ray cast in metres (edge points are the server's call; it is stricter and may still refuse). */
export function pointInPolygon(x: number, y: number, polygon: readonly Pt[]): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [xi, yi] = polygon[i];
    const [xj, yj] = polygon[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

export function roomAt(plan: Plan, x: number, y: number): PlanRoom | null {
  return plan.rooms.find(room => pointInPolygon(x, y, room.polygon)) ?? null;
}

/** The SVG viewBox in metres (y grows downward on screen) and the aspect ratio the element must have. */
export function mapViewBox(plan: Plan): { box: string; aspect: number } {
  const w = plan.extent[0] + 2 * MAP_PAD_M;
  const h = plan.extent[1] + 2 * MAP_PAD_M;
  return { box: `${-MAP_PAD_M} ${-MAP_PAD_M} ${w} ${h}`, aspect: w / h };
}

/** Client pixels inside the map element -> venue metres (the element's box has the viewBox's aspect ratio). */
export function tapToMetres(plan: Plan, rect: { left: number; top: number; width: number; height: number }, clientX: number, clientY: number): Spot {
  const w = plan.extent[0] + 2 * MAP_PAD_M;
  const h = plan.extent[1] + 2 * MAP_PAD_M;
  return {
    x: Math.round(((clientX - rect.left) / rect.width * w - MAP_PAD_M) * 100) / 100,
    y: Math.round(((clientY - rect.top) / rect.height * h - MAP_PAD_M) * 100) / 100,
  };
}

/** Which way the wall under a door runs, so the door is drawn as a gap in it. */
export function doorAxis(plan: Plan, position: Pt): 'vertical' | 'horizontal' {
  const [x, y] = position;
  for (const room of plan.rooms) {
    for (let i = 0; i < room.polygon.length; i++) {
      const [ax, ay] = room.polygon[i];
      const [bx, by] = room.polygon[(i + 1) % room.polygon.length];
      if (ax === bx && Math.abs(x - ax) < 1e-6 && y >= Math.min(ay, by) - 1e-6 && y <= Math.max(ay, by) + 1e-6) return 'vertical';
    }
  }
  return 'horizontal';
}

export function parsePlan(raw: unknown): Plan | null {
  const plan = raw as Plan | null;
  const pair = (value: unknown) => Array.isArray(value) && value.length === 2 && value.every(n => typeof n === 'number' && Number.isFinite(n));
  if (!plan || !pair(plan.extent) || !Array.isArray(plan.rooms) || !Array.isArray(plan.doors) || !Array.isArray(plan.exits)) return null;
  if (!plan.rooms.every(r => typeof r.id === 'string' && Array.isArray(r.polygon) && r.polygon.length >= 3 && r.polygon.every(pair))) return null;
  if (!plan.doors.every(d => pair(d.position)) || !plan.exits.every(x => pair(x.position))) return null;
  return plan;
}

/** A point inside the room for its name: the middle of the widest span over a few horizontal scanlines (L-shapes safe). */
export function labelPoint(polygon: readonly Pt[]): Pt {
  const ys = polygon.map(p => p[1]);
  const xsAll = polygon.map(p => p[0]);
  const lo = Math.min(...ys);
  const hi = Math.max(...ys);
  let best: Pt = [(Math.min(...xsAll) + Math.max(...xsAll)) / 2, (lo + hi) / 2];
  let bestWidth = -1;
  for (const fraction of [0.5, 0.35, 0.65, 0.2, 0.8]) {
    const y = lo + (hi - lo) * fraction;
    const xs: number[] = [];
    for (let i = 0; i < polygon.length; i++) {
      const [x0, y0] = polygon[i];
      const [x1, y1] = polygon[(i + 1) % polygon.length];
      if ((y0 > y) !== (y1 > y)) xs.push(x0 + ((y - y0) * (x1 - x0)) / (y1 - y0));
    }
    xs.sort((a, b) => a - b);
    for (let i = 0; i + 1 < xs.length; i += 2) {
      if (xs[i + 1] - xs[i] > bestWidth) { bestWidth = xs[i + 1] - xs[i]; best = [(xs[i] + xs[i + 1]) / 2, y]; }
    }
  }
  return best;
}

/** Split a room name over at most two lines so it fits a narrow room. */
export function nameLines(name: string): string[] {
  const words = name.trim().split(/\s+/);
  const cut = (line: string) => (line.length > 14 ? `${line.slice(0, 13)}…` : line);
  if (name.length <= 9 || words.length < 2) return [cut(name)];
  const gap = (at: number) => Math.abs(words.slice(0, at).join(' ').length - words.slice(at).join(' ').length);
  let split = 1;
  for (let i = 2; i < words.length; i++) if (gap(i) < gap(split)) split = i;
  return [cut(words.slice(0, split).join(' ')), cut(words.slice(split).join(' '))];
}
