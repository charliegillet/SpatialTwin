import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import {
  approveIncidentPlan, clearIncidentFault, fetchIncident, fetchIncidentDoorPlan, INCIDENT_EVENTS_URL, injectIncidentFault, postIncidentHazards, resetIncident,
  type GateFault, type IncidentApproval, type IncidentEvent, type IncidentState,
} from '../api/incident.ts';
import {
  addApprovalIfNew, applyIncidentState, approveAvailability, createHazardSync, createIncidentConnection, createStaleGuard, doorVisuals, fallbackBanner, gateViews, hazardsInSync,
  initialIncidentState, latestApproval, reduceIncidentEvent, type ConnectionStatus, type EventSourceLike, type IncidentFlowState,
} from './incidentFlow.ts';
import type { DoorPlanResponse, HazardInput } from './types.ts';

type Action =
  | { kind: 'event'; event: IncidentEvent; now: number }
  | { kind: 'state'; incident: IncidentState; now: number }
  | { kind: 'approval'; approval: IncidentApproval }
  | { kind: 'status'; status: ConnectionStatus };

function reducer(state: IncidentFlowState, action: Action): IncidentFlowState {
  if (action.kind === 'event') return reduceIncidentEvent(state, action.event, action.now);
  if (action.kind === 'state') return applyIncidentState(state, action.incident, action.now);
  if (action.kind === 'approval') return addApprovalIfNew(state, action.approval);
  return state.connection === action.status ? state : { ...state, connection: action.status };
}

const message = (error: unknown, fallback: string) => error instanceof Error && error.message ? error.message : fallback;

/** The virtual door controller for one venue: live state from SSE (polling as a fallback), the twin's hazards synced to the server's
 *  planner, and the judge's actions. Mount it once; hand `view` to IncidentPanel and `doors` to the 3D door leaves. */
export function useIncident(venueId: string, hazards: HazardInput[], options: { enabled?: boolean } = {}) {
  const enabled = options.enabled ?? true;
  const [flow, dispatch] = useReducer(reducer, undefined, initialIncidentState);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<'approve' | 'jam' | 'clear' | 'reset' | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const flowRef = useRef(flow);
  flowRef.current = flow;
  const guard = useRef(createStaleGuard()).current;
  const syncRef = useRef<ReturnType<typeof createHazardSync> | null>(null);
  const hazardsRef = useRef(hazards);
  hazardsRef.current = hazards;
  const [executed, setExecuted] = useState<{ revision: number; plan: DoorPlanResponse } | null>(null);

  const accept = useCallback((incident: IncidentState, token: number) => {
    if (guard.isCurrent(token)) dispatch({ kind: 'state', incident, now: Date.now() });
  }, [guard]);

  // One connection per hook; a venue switch is handled by the hazard post, not by reconnecting.
  useEffect(() => {
    if (!enabled) return;
    const connection = createIncidentConnection({
      makeSource: url => new EventSource(url.startsWith(INCIDENT_EVENTS_URL) ? url : INCIDENT_EVENTS_URL) as unknown as EventSourceLike,
      poll: () => fetchIncident(), lastSeq: () => flowRef.current.lastSeq,
      onEvent: event => dispatch({ kind: 'event', event, now: Date.now() }),
      onPolled: incident => dispatch({ kind: 'state', incident, now: Date.now() }),
      onStatus: status => dispatch({ kind: 'status', status }),
    });
    connection.start();
    return () => connection.stop();
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;
    const sync = createHazardSync({
      post: (venue, revision, items) => postIncidentHazards(venue, revision, items),
      read: () => fetchIncident(), revision: () => flowRef.current.incident?.plan_revision ?? null,
      onState: incident => dispatch({ kind: 'state', incident, now: Date.now() }), onError: setError,
    });
    syncRef.current = sync;
    return () => { sync.dispose(); syncRef.current = null; };
  }, [enabled]);

  useEffect(() => { if (enabled) syncRef.current?.update(venueId, hazards); }, [enabled, venueId, hazards]);

  // A rejected send (approval in progress) is retried as soon as the doors stop moving.
  const inProgress = flow.incident?.approval_in_progress ?? false;
  useEffect(() => { if (!inProgress) syncRef.current?.kick(); }, [inProgress]);

  // Elapsed-since-command needs a clock only while a gate is in transit.
  const anyMoving = Object.keys(flow.movingSince).length > 0;
  useEffect(() => {
    if (!anyMoving) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(timer);
  }, [anyMoving]);

  // Run an action against the server; on the polling fallback also re-read, since no event will announce the result.
  const act = useCallback(async (kind: NonNullable<typeof busy>, work: (token: number) => Promise<void>) => {
    const token = guard.begin();
    setBusy(kind);
    setError(null);
    try {
      await work(token);
      if (flowRef.current.connection !== 'live') accept(await fetchIncident(), guard.begin());
    } catch (cause) {
      setError(message(cause, 'The door controller did not answer'));
      // A stale or in-progress answer means our view is behind: read it again so the next click quotes the new plan.
      try { accept(await fetchIncident(), guard.begin()); } catch { /* the connection status already says it is down */ }
    } finally { setBusy(null); }
  }, [accept, guard]);

  const plan = flow.incident?.plan ?? null;

  // After a jam the doors follow a fallback the stateless planner never saw: fetch its full plan (routes, lamps, door
  // reasons) so the twin draws what is executed. Keyed by plan revision; a newer revision drops an older answer.
  const fallbackRevision = plan?.label === 'fallback' ? plan.plan_revision : null;
  const incidentVenue = flow.incident?.venue_id ?? null;
  useEffect(() => {
    if (!enabled || fallbackRevision === null || !incidentVenue) return;
    const controller = new AbortController();
    fetchIncidentDoorPlan(incidentVenue, controller.signal).then(answer => {
      if (answer.plan_revision === fallbackRevision && answer.door_plan) setExecuted({ revision: answer.plan_revision, plan: answer.door_plan });
    }).catch(() => { /* the panel still shows the fallback summary; the twin keeps the proposed plan, labelled */ });
    return () => controller.abort();
  }, [enabled, fallbackRevision, incidentVenue]);
  const inSync = flow.incident ? hazardsInSync(flow.incident.hazards, hazards) : false;
  const fallbackPlan = executed && fallbackRevision === executed.revision && inSync ? executed.plan : null;

  const approve = useCallback(() => {
    const current = flowRef.current.incident;
    if (!current?.plan || !approveAvailability(current, hazardsRef.current).allowed) return Promise.resolve();
    const quoted = current.plan;
    return act('approve', async () => {
      const approval = await approveIncidentPlan(quoted);
      dispatch({ kind: 'approval', approval });
    });
  }, [act]);
  const jam = useCallback((gateId: string, fault: GateFault = 'stall') => act('jam', async () => { await injectIncidentFault(gateId, fault); }), [act]);
  const clearFault = useCallback((gateId?: string) => act('clear', async () => { await clearIncidentFault(gateId); }), [act]);
  const reset = useCallback(() => act('reset', async () => {
    // Anything in flight from before the reset must not land after it.
    guard.invalidate();
    const token = guard.begin();
    accept(await resetIncident(), token);
    syncRef.current?.resend();
  }), [accept, act, guard]);

  const view = useMemo(() => ({
    incident: flow.incident, plan, gates: gateViews(flow.incident, flow.movingSince, now), availability: approveAvailability(flow.incident, hazards),
    banner: fallbackBanner(flow.incident), approval: latestApproval(flow.incident), connection: flow.connection,
    heartbeat: flow.incident?.controller.heartbeat ?? 'ok', label: flow.incident?.controller.label ?? 'Simulated device: no hardware is connected',
  }), [flow.incident, flow.movingSince, flow.connection, plan, now, hazards]);
  const doors = useMemo(() => doorVisuals(flow.incident, flow.movingSince), [flow.incident, flow.movingSince]);

  return { state: view, doors, fallbackPlan, console: flow.log, approve, jam, clearFault, reset, busy, error, dismissError: () => setError(null) };
}

export type IncidentController = ReturnType<typeof useIncident>;
