import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { BUILTIN_VENUE_ID, fetchVenue, fetchVenueList, postDoorPlan, putActiveVenue, VENUE_CHANGED } from '../api/twin.ts';
import { ApiError } from '../api/client.ts';
import { SMOKE_DEFAULT, stepSmokeSeconds } from '../ai/hazardTools.ts';
import { modeAfterReset } from './modes.ts';
import { addCameraHazards, clearHazards, emptyPlacement, placeHazard, removeHazard, setSmokeSeconds, toHazardInputs, undoPlacement, zoneDropPoint, type PlacementState } from './placement.ts';
import { TOO_MANY_HAZARDS } from './placement.ts';
import { createTwinFlow, idleFlow, type FlowState } from './twinFlow.ts';
import { planLogLine } from './twinHero.ts';
import type { DoorPlanResponse, HazardType, PlacedHazard, TwinMode, VenueSummary, VenueV2 } from './types.ts';

export const PICK_FIRST = 'Pick a hazard first';

interface Options {
  mode: TwinMode;
  notify: (message: string) => void;
  log: (message: string, level?: 'info' | 'success' | 'warning') => void;
}

/** Simulation-mode state: the active venue, placed hazards, the debounced door plan. Everything resets on leaving the mode or switching venue. */
export function useTwin({ mode, notify, log }: Options) {
  const active = mode !== 'tabletop';
  // The camera twin calibrates against the printed building-v2 sheet, so it always plans on building-v2.
  const cameraOnly = mode === 'camera';
  const [activeVenue, setActiveVenue] = useState<{ venue_id: string; revision: number }>({ venue_id: BUILTIN_VENUE_ID, revision: 0 });
  const [venues, setVenues] = useState<VenueSummary[]>([]);
  const venueId = cameraOnly ? BUILTIN_VENUE_ID : activeVenue.venue_id;
  const venueIdRef = useRef(venueId);
  venueIdRef.current = venueId;
  const [venue, setVenue] = useState<VenueV2 | null>(null);
  const [fixtureVenue, setFixtureVenue] = useState(false);
  const [placement, setPlacement] = useState<PlacementState>(emptyPlacement);
  const [armed, setArmed] = useState<HazardType | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [smokeSeconds, setSmokeSecondsState] = useState(SMOKE_DEFAULT);
  const [flow, setFlow] = useState<FlowState<DoorPlanResponse>>(idleFlow);
  const logRef = useRef(log);
  logRef.current = log;
  const venueRef = useRef<VenueV2 | null>(null);
  venueRef.current = venue;

  const flowRef = useRef<ReturnType<typeof createTwinFlow<DoorPlanResponse>> | null>(null);
  if (!flowRef.current) {
    flowRef.current = createTwinFlow<DoorPlanResponse>({
      fetchPlan: async (hazards, signal) => {
        try {
          return await postDoorPlan(venueIdRef.current, hazards, signal, venueRef.current?.geometry_revision);
        } catch (error) {
          // The server's venue moved on (another judge accepted a new reading): redraw from the server.
          if (error instanceof ApiError && error.detail === VENUE_CHANGED) setVenue(null);
          throw error;
        }
      },
      onState: setFlow,
      onPlan: (plan, _hazards, ms) => {
        const names = Object.fromEntries((venueRef.current?.zones ?? []).map(zone => [zone.id, zone.name]));
        logRef.current(planLogLine(plan, names, ms), plan.chosen.validator_report.is_valid ? 'success' : 'warning');
      },
      describeError: error => error instanceof Error ? error.message : 'The door plan could not be calculated.',
    });
  }
  const planner = flowRef.current;

  // The active venue pointer and the list, read whenever the twin opens; an unreachable backend keeps building-v2.
  const [listTick, setListTick] = useState(0);
  const refreshVenues = useCallback(() => setListTick(value => value + 1), []);
  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    fetchVenueList(controller.signal).then(
      list => {
        setVenues(list.venues); setActiveVenue(list.active);
        // Same id, new geometry (a re-accepted reading): drop the drawn copy so it is fetched again.
        const listed = list.venues.find(item => item.venue_id === venueRef.current?.venue_id);
        if (listed && venueRef.current && listed.geometry_revision !== venueRef.current.geometry_revision) setVenue(null);
      },
      () => { /* the venue fetch below reports an unreachable backend */ },
    );
    return () => controller.abort();
  }, [active, listTick]);

  /** Moves the shared active-venue pointer (incident state, approvals and phone signs follow it) under
   *  compare-and-set. The screen only ever shows the venue the server confirms, so they cannot drift apart. */
  // App passes a new notify function on every render; read it through a ref so switchVenue only changes when the
  // pointer does, and effects that call it are not restarted by unrelated renders.
  const notifyRef = useRef(notify);
  notifyRef.current = notify;
  const switchVenue = useCallback(async (nextId: string) => {
    if (nextId === activeVenue.venue_id) return true;
    try {
      setActiveVenue(await putActiveVenue(nextId, activeVenue.revision));
      return true;
    } catch (error) {
      notifyRef.current(error instanceof ApiError && error.message ? error.message : 'The venue could not be switched');
      refreshVenues();
      return false;
    }
  }, [activeVenue, refreshVenues]);
  const switchVenueRef = useRef(switchVenue);
  switchVenueRef.current = switchVenue;

  // Venue: fetched when the twin opens or the venue changes; the bundled fixture covers an unreachable backend.
  // switchVenue is read through its ref: a pointer refresh must not abort and restart a fetch already in flight.
  useEffect(() => {
    if (!active || venue?.venue_id === venueId) return;
    const controller = new AbortController();
    fetchVenue(venueId, controller.signal).then(
      loaded => { setVenue(loaded); setFixtureVenue(false); },
      async () => {
        if (controller.signal.aborted) return;
        if (venueId !== BUILTIN_VENUE_ID) {
          // Point everyone back at building-v2 on the server too, not just this screen.
          logRef.current(`Venue ${venueId} could not be loaded. Switching to building-v2.`, 'warning');
          void switchVenueRef.current(BUILTIN_VENUE_ID);
          return;
        }
        const bundled = (await import('./fixtures/building-v2.json')).default as unknown as VenueV2;
        if (controller.signal.aborted) return;
        setVenue(bundled); setFixtureVenue(true);
        logRef.current('Backend venue unavailable. Using the bundled fixture venue.', 'warning');
      },
    );
    return () => controller.abort();
  }, [active, venue, venueId]);

  // The camera twin plans on building-v2 (its printed sheet), so the shared pointer follows it there.
  useEffect(() => {
    if (cameraOnly && activeVenue.venue_id !== BUILTIN_VENUE_ID) void switchVenueRef.current(BUILTIN_VENUE_ID);
  }, [cameraOnly, activeVenue.venue_id]);

  // Every change to the hazards (or a smoke time) re-plans; the first plan for a visit skips the debounce.
  const planned = useRef(false);
  useEffect(() => {
    if (!active || !venue || venue.venue_id !== venueId) return;
    planner.request(toHazardInputs(placement.hazards), { immediate: !planned.current });
    planned.current = true;
  }, [active, venue, venueId, placement.hazards, planner]);

  const reset = useCallback(() => {
    planner.reset();
    planned.current = false;
    setPlacement(emptyPlacement()); setArmed(null); setSelectedId(null); setSmokeSecondsState(SMOKE_DEFAULT);
  }, [planner]);
  // Any mode or venue change starts clean: hazards, selection and the plan are forgotten.
  useEffect(() => { reset(); }, [mode, venueId, venue?.geometry_revision, reset]);
  useEffect(() => () => planner.reset(), [planner]);

  const place = useCallback((point: { x: number; y: number }, type: HazardType | null = armed) => {
    if (!venue) return;
    if (!type) { notify(PICK_FIRST); return; }
    const result = placeHazard(placement, venue, type, point, smokeSeconds);
    if (!result.ok) { notify(result.message); return; }
    setPlacement(result.state); setSelectedId(result.hazard.id); setArmed(null);
  }, [armed, notify, placement, smokeSeconds, venue]);

  const placeInZone = useCallback((zoneId: string) => {
    const point = venue && zoneDropPoint(venue, zoneId);
    if (point) place(point);
  }, [place, venue]);

  const addCamera = useCallback((incoming: PlacedHazard[]) => {
    const result = addCameraHazards(placement, incoming);
    if (result.skipped > 0) notify(TOO_MANY_HAZARDS);
    if (result.added > 0) { setPlacement(result.state); setSelectedId(incoming[0]?.id ?? null); }
    return result.added;
  }, [notify, placement]);

  const remove = useCallback((id: string) => {
    setPlacement(current => removeHazard(current, id));
    setSelectedId(current => current === id ? null : current);
  }, []);

  const stepSmoke = useCallback((direction: 1 | -1) => {
    const next = stepSmokeSeconds(smokeSeconds, direction);
    setSmokeSecondsState(next);
    const selected = placement.hazards.find(item => item.id === selectedId);
    if (selected?.type === 'SMOKE') setPlacement(current => setSmokeSeconds(current, selected.id, next));
  }, [placement.hazards, selectedId, smokeSeconds]);

  // Esc disarms or deselects; Delete/Backspace removes the selected hazard (not while typing).
  useEffect(() => {
    if (!active) return;
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && /^(INPUT|SELECT|TEXTAREA)$/.test(target.tagName)) return;
      if (event.key === 'Escape' && (armed || selectedId) && !document.querySelector('dialog[open]')) { setArmed(null); setSelectedId(null); }
      else if ((event.key === 'Delete' || event.key === 'Backspace') && selectedId) { event.preventDefault(); remove(selectedId); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [active, armed, selectedId, remove]);

  // A venue from before a switch is never shown while the next one loads.
  const current = venue?.venue_id === venueId ? venue : null;
  return useMemo(() => ({
    active, venue: current, venueId, venues, activeRevision: activeVenue.revision, switchVenue, refreshVenues,
    fixtureVenue, flow, placement, hazards: placement.hazards as PlacedHazard[], armed, selectedId, smokeSeconds,
    setArmed, setSelectedId, place, placeInZone, addCamera, remove, stepSmoke, reset,
    undo: () => setPlacement(undoPlacement), clear: () => { setPlacement(clearHazards); setSelectedId(null); },
    canUndo: placement.history.length > 0,
    leave: modeAfterReset,
  }), [active, current, venueId, venues, activeVenue.revision, switchVenue, refreshVenues, fixtureVenue, flow, placement, armed, selectedId, smokeSeconds, place, placeInZone, addCamera, remove, stepSmoke, reset]);
}

export type TwinController = ReturnType<typeof useTwin>;
