import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchVenue, postDoorPlan } from '../api/twin.ts';
import { SMOKE_DEFAULT, stepSmokeSeconds } from '../ai/hazardTools.ts';
import { modeAfterReset } from './modes.ts';
import { addCameraHazards, clearHazards, emptyPlacement, placeHazard, removeHazard, setSmokeSeconds, toHazardInputs, undoPlacement, zoneDropPoint, type PlacementState } from './placement.ts';
import { TOO_MANY_HAZARDS } from './placement.ts';
import { createTwinFlow, idleFlow, type FlowState } from './twinFlow.ts';
import { planLogLine } from './twinHero.ts';
import type { DoorPlanResponse, HazardType, PlacedHazard, TwinMode, VenueV2 } from './types.ts';

export const PICK_FIRST = 'Pick a hazard first';

interface Options {
  mode: TwinMode;
  notify: (message: string) => void;
  log: (message: string, level?: 'info' | 'success' | 'warning') => void;
}

/** Simulation-mode state: venue, placed hazards, the debounced door plan. Everything resets on leaving the mode. */
export function useTwin({ mode, notify, log }: Options) {
  const active = mode !== 'tabletop';
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
      fetchPlan: postDoorPlan,
      onState: setFlow,
      onPlan: (plan, _hazards, ms) => {
        const names = Object.fromEntries((venueRef.current?.zones ?? []).map(zone => [zone.id, zone.name]));
        logRef.current(planLogLine(plan, names, ms), plan.chosen.validator_report.is_valid ? 'success' : 'warning');
      },
      describeError: error => error instanceof Error ? error.message : 'The door plan could not be calculated.',
    });
  }
  const planner = flowRef.current;

  // Venue: fetched once when Simulation first opens; the bundled fixture covers an unreachable backend.
  useEffect(() => {
    if (!active || venue) return;
    const controller = new AbortController();
    fetchVenue(controller.signal).then(
      loaded => { setVenue(loaded); setFixtureVenue(false); },
      async () => {
        if (controller.signal.aborted) return;
        const bundled = (await import('./fixtures/building-v2.json')).default as unknown as VenueV2;
        if (controller.signal.aborted) return;
        setVenue(bundled); setFixtureVenue(true);
        logRef.current('Backend venue unavailable. Using the bundled fixture venue.', 'warning');
      },
    );
    return () => controller.abort();
  }, [active, venue]);

  // Every change to the hazards (or a smoke time) re-plans; the first plan for a visit skips the debounce.
  const planned = useRef(false);
  useEffect(() => {
    if (!active || !venue) return;
    planner.request(toHazardInputs(placement.hazards), { immediate: !planned.current });
    planned.current = true;
  }, [active, venue, placement.hazards, planner]);

  const reset = useCallback(() => {
    planner.reset();
    planned.current = false;
    setPlacement(emptyPlacement()); setArmed(null); setSelectedId(null); setSmokeSecondsState(SMOKE_DEFAULT);
  }, [planner]);
  // Any mode change starts clean: hazards, selection and the plan are forgotten.
  useEffect(() => { reset(); }, [mode, reset]);
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

  return useMemo(() => ({
    active, venue, fixtureVenue, flow, placement, hazards: placement.hazards as PlacedHazard[], armed, selectedId, smokeSeconds,
    setArmed, setSelectedId, place, placeInZone, addCamera, remove, stepSmoke, reset,
    undo: () => setPlacement(undoPlacement), clear: () => { setPlacement(clearHazards); setSelectedId(null); },
    canUndo: placement.history.length > 0,
    leave: modeAfterReset,
  }), [active, venue, fixtureVenue, flow, placement, armed, selectedId, smokeSeconds, place, placeInZone, addCamera, remove, stepSmoke, reset]);
}

export type TwinController = ReturnType<typeof useTwin>;
