import type { DoorPlanResponse, PlanAlternative, PlanDoor, PlanExit } from './types.ts';

export interface TwinHero {
  ready: boolean;
  /** A figure from an earlier hazard set is shown muted while the new one is solved. */
  stale: boolean;
  digits: string;
  label: string;
  tag: string;
  delta: { text: string; tone: 'gain' | 'loss' } | null;
  reason: string | null;
  spoken: string;
  /** The checker rejected the plan: no figure is shown. */
  withheld: boolean;
}

export const MODEL_TAG = 'building-v2 model';
export const modelTag = (venueId: string | null | undefined, venueName?: string | null): string =>
  venueName ? `${venueName} model` : venueId ? `${venueId} model` : MODEL_TAG;
export const NO_CHECKED_PLAN = 'No checked plan \u2014 numbers withheld';

/** False only when the checker said the chosen plan is invalid; partial fixtures without a report count as unknown, not failed. */
export const planChecked = (plan: { chosen?: { validator_report?: { is_valid?: boolean } } } | null | undefined): boolean =>
  plan?.chosen?.validator_report?.is_valid !== false;
const MINUS = '−';

/** Doors the planner opened beyond their default state. */
export function plannerOpened(plan: DoorPlanResponse): string[] {
  return plan.doors.filter(door => door.changed && door.state === 'open' && door.decided_by === 'door_planner').map(door => door.id);
}

const joinIds = (ids: string[]) => ids.length < 3 ? ids.join(' and ') : `${ids.slice(0, -1).join(', ')} and ${ids[ids.length - 1]}`;

/** "+34 by opening D9" against the same hazards with every door at its default; null when nothing changed. */
export function deltaFor(plan: DoorPlanResponse): TwinHero['delta'] {
  if (plan.hazards.length === 0) return null;
  const gain = plan.chosen.completed_crossings - plan.baseline.completed_crossings;
  if (gain === 0) return null;
  const opened = plannerOpened(plan);
  const sign = gain > 0 ? '+' : MINUS;
  const text = gain > 0 && opened.length ? `${sign}${gain} by opening ${joinIds(opened)}` : `${sign}${Math.abs(gain)} vs default doors`;
  return { text, tone: gain > 0 ? 'gain' : 'loss' };
}

/** Modeled crossings, never survival. The population and horizon come from the response. */
export function twinHero(input: { plan: DoorPlanResponse | null; pending: boolean; error?: string | null; venueId?: string | null; venueName?: string | null }): TwinHero {
  const { plan, pending, error } = input;
  if (!plan) {
    const reason = error ?? (pending ? 'Solving…' : 'Waiting for the planner.');
    return { ready: false, stale: false, digits: '—', label: 'reach an exit', tag: modelTag(input.venueId, input.venueName), delta: null, reason, spoken: `No result. ${reason}`, withheld: false };
  }
  // The name is used only while it belongs to the plan's venue; a plan from the previous venue keeps its id.
  const tag = modelTag(plan.venue_id, plan.venue_id === input.venueId ? input.venueName : null);
  if (!planChecked(plan)) return { ready: false, stale: false, digits:'\u2014', label: 'no checked plan', tag, delta: null, reason: NO_CHECKED_PLAN, spoken: NO_CHECKED_PLAN, withheld: true };
  const { completed_crossings: done, initial_population: population, horizon_seconds: horizon } = plan.chosen;
  const label = `of ${population} reach an exit in ${horizon} s`;
  const stale = pending || Boolean(error);
  const delta = stale ? null : deltaFor(plan);
  const reason = error ?? (pending ? 'Re-solving…' : null);
  return { ready: !stale, stale, digits: String(done), label, tag, delta, reason, spoken: `${done} ${label}, ${tag}${delta ? `, ${delta.text}` : ''}`, withheld: false };
}

/** The incident's checked plan when it is not the stateless one: a fallback (a door jammed and the server re-planned with
 *  it stuck closed) or the fail-safe's (gates into a hazard room held closed). */
export interface HeroFallback { valid: boolean; completed: number; population: number; stuck: string[]; held?: string[] }

/** After a jam, or once the fail-safe holds a gate closed, the doors being executed follow that plan, so the headline
 *  follows it and says why it differs. An unchecked plan withholds the number like any unchecked plan. */
export function withFallback(hero: TwinHero, fallback: HeroFallback | null | undefined, primary: DoorPlanResponse | null): TwinHero {
  if (!fallback || !hero.ready || !primary) return hero;
  const held = fallback.held ?? [];
  const stuck = fallback.stuck.length ? joinIds(fallback.stuck) : held.length ? null : 'a door';
  if (!fallback.valid) return { ...hero, ready: false, digits: '\u2014', label: 'no checked plan', delta: null, reason: NO_CHECKED_PLAN, spoken: NO_CHECKED_PLAN, withheld: true };
  const loss = primary.chosen.completed_crossings - fallback.completed;
  const label = `of ${fallback.population} reach an exit in ${primary.chosen.horizon_seconds} s`;
  const why = [stuck ? `${stuck} stuck` : null, held.length ? `${joinIds(held)} held closed` : null].filter(Boolean).join(' · ');
  const delta = { text: `${stuck ? 'fallback' : 'fail-safe'} · ${why}${loss > 0 ? ` · ${MINUS}${loss} vs the plan` : ''}`, tone: 'loss' as const };
  return { ...hero, digits: String(fallback.completed), label, delta, spoken: `${fallback.completed} ${label}, ${hero.tag}, ${delta.text}` };
}

export const twinChips = (plan: DoorPlanResponse | null, fixtureVenue: boolean): string[] =>
  [plan ? 'Local solver' : null, plan ? 'Hypothetical' : null, fixtureVenue ? 'Fixture venue' : null].filter((item): item is string => Boolean(item));

// --- Door plan rows -----------------------------------------------------------------------------------------

export interface DoorRow { id: string; verb: string; reason: string; tone: 'open' | 'closed' | 'locked'; }

export function doorVerb(door: PlanDoor): { verb: string; tone: DoorRow['tone'] } {
  if (door.locked) return { verb: 'locked', tone: 'locked' };
  if (door.state === 'closed') return { verb: door.entry_denied_into.length ? 'closed to entry' : 'closed', tone: 'closed' };
  if (!door.changed && door.entry_denied_into.length) return { verb: 'stays open \u00b7 no entry', tone: 'locked' };
  return { verb: door.changed ? 'opened' : 'open', tone: 'open' };
}

/** Only doors the plan touched: changed, locked, or closed to entry. */
export function doorRows(plan: DoorPlanResponse): DoorRow[] {
  return plan.doors
    .filter(door => door.changed || door.locked || door.entry_denied_into.length > 0)
    .map(door => ({ id: door.id, ...doorVerb(door), reason: door.reason }));
}

export interface DoorGroup { ids: string[]; verb: string; reason: string; tone: DoorRow['tone']; }

/** Doors that share a verb and a reason read as one line ("D1 D5 D6 closed to entry"). */
export function groupDoorRows(rows: DoorRow[]): DoorGroup[] {
  const groups: DoorGroup[] = [];
  for (const row of rows) {
    const same = groups.find(group => group.verb === row.verb && group.reason === row.reason);
    if (same) same.ids.push(row.id); else groups.push({ ids: [row.id], verb: row.verb, reason: row.reason, tone: row.tone });
  }
  return groups;
}

/** "+29" from a backend reason like "opened: +29 modeled crossings"; null when the reason carries none. */
export const gainFrom = (reason: string): string | null => reason.match(/[+\u2212-]\d+/)?.[0] ?? null;

export const unsafeExits = (plan: DoorPlanResponse): PlanExit[] => plan.exits.filter(exit => !exit.safe);

export interface AlternativeRow { rank: number; doors: string; crossings: number; valid: boolean; chosen: boolean; }
export const FAILED_CHECK = 'failed check';

/** Door states of an alternative, compact: "D4 open · D9 open". Doors at default are left out. */
export function alternativeLabel(states: PlanAlternative['door_states']): string {
  const entries = Object.entries(states);
  return entries.length ? entries.map(([id, state]) => `${id} ${state}`).join(' · ') : 'defaults';
}

export function alternativeRows(plan: DoorPlanResponse, limit = 6): AlternativeRow[] {
  return [...plan.alternatives].sort((a, b) => a.rank - b.rank).slice(0, limit)
    .map(item => ({ rank: item.rank, doors: alternativeLabel(item.door_states), crossings: item.completed_crossings, valid: item.is_valid, chosen: item.run_id === plan.chosen.run_id }));
}

/** One activity line per accepted plan: hazards, chosen doors, crossings, time. */
export function planLogLine(plan: DoorPlanResponse, zoneNames: Record<string, string>, ms: number): string {
  const hazards = plan.hazards.length ? plan.hazards.map(item => `${item.type} ${zoneNames[item.zone_id] ?? item.zone_id}`).join(', ') : 'no hazards';
  const byVerb = new Map<string, string[]>();
  for (const row of doorRows(plan)) byVerb.set(row.verb, [...(byVerb.get(row.verb) ?? []), row.id]);
  const doors = [...byVerb].map(([verb, ids]) => `${ids.join(' ')} ${verb}`).join(', ') || 'doors at default';
  return `${hazards} → ${doors} → ${plan.chosen.completed_crossings} of ${plan.chosen.initial_population} · ${ms} ms · local solver, no Gemini call`;
}
