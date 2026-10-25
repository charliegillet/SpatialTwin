import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { cancelDoorInvestigation, doorAgentErrorMessage, fetchDoorInvestigation, isDoorAgentDone, startDoorInvestigation } from '../api/twin.ts';
import { askAvailability, createDoorAgentFlow, hazardKey, idleAgent, type DoorAgentState } from './doorAgent.ts';
import type { DoorAgentMode, DoorPlanResponse, HazardInput, TwinMode } from './types.ts';

interface Options {
  /** Hazards currently placed, as sent to the planner. */
  hazards: HazardInput[];
  plan: DoorPlanResponse | null;
  pending: boolean;
  /** Simulation or Camera twin; a change drops the run. */
  mode: TwinMode;
  /** The presenter menu's Analysis mode. */
  analysisMode: DoorAgentMode;
  /** The venue the plan is for; a switch drops the run. */
  venueId: string;
}

/** Ask-the-agent state for Simulation. A new hazard set, a mode switch, Next judge (unmount) or Cancel drops the run. */
export function useDoorAgent({ hazards, plan, pending, mode, analysisMode, venueId }: Options) {
  const [state, setState] = useState<DoorAgentState>(idleAgent);
  // A run is dropped on every venue switch, so the venue never changes between its start and its last poll.
  const venueRef = useRef(venueId);
  venueRef.current = venueId;
  const flowRef = useRef<ReturnType<typeof createDoorAgentFlow> | null>(null);
  if (!flowRef.current) {
    flowRef.current = createDoorAgentFlow({
      start: (items, runMode, signal) => startDoorInvestigation(venueRef.current, items, runMode, signal),
      poll: (id, signal) => fetchDoorInvestigation(venueRef.current, id, signal),
      cancel: id => cancelDoorInvestigation(venueRef.current, id),
      onState: setState, isDone: isDoorAgentDone, describeFailure: doorAgentErrorMessage,
    });
  }
  const flow = flowRef.current;
  const key = hazardKey(hazards);
  const hazardsRef = useRef(hazards);
  hazardsRef.current = hazards;

  useEffect(() => { flow.reset(); }, [flow, key, mode, venueId]);
  useEffect(() => () => flow.reset(), [flow]);

  const running = state.status === 'running';
  const unavailable = askAvailability({ hazardCount: hazards.length, planReady: Boolean(plan), pending, running });
  const ask = useCallback(() => { if (!unavailable) flow.ask(hazardsRef.current, analysisMode); }, [analysisMode, flow, unavailable]);
  return useMemo(() => ({ state, analysisMode, unavailable, ask, cancel: flow.cancel }), [state, analysisMode, unavailable, ask, flow]);
}

export type DoorAgentController = ReturnType<typeof useDoorAgent>;
