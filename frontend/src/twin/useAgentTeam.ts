import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { cancelAgentTeam, fetchAgentTeam, followUpAgentTeam, isParentFinishing, parseTraceEvent, startAgentTeam, traceUrl } from '../api/agentTeam.ts';
import {
  askAvailability, createTeamRunner, createTraceConnection, followUpSuggestions, followUpUnavailable, hazardsKeyOf, idleRun, isActive, normalizeScenario, withRetry,
  type EventSourceLike,
} from './agentTeamFlow.ts';
import { TRACE_EVENT_NAMES, type TeamMode, type TeamRun } from './agentTeamTypes.ts';
import type { DoorPlanResponse, HazardInput, TwinMode } from './types.ts';

interface Options {
  venueId: string;
  /** Hazards currently placed, as sent to the planner. */
  hazards: HazardInput[];
  plan: DoorPlanResponse | null;
  pending: boolean;
  /** Simulation or Camera twin; a change drops the run. */
  mode: TwinMode;
  /** The presenter menu's Analysis mode (live Gemini or local solver). */
  analysisMode: TeamMode;
  /** Start the team by itself once the planner has a checked plan for the current hazards. */
  auto?: boolean;
}

/** A judge dropping several hazards in a row starts one run, not one per drop. */
export const AUTO_START_MS = 2500;

const BAD_SCENARIO = 'Try "What if D3 jams?" or a scenario like stuck_closed:D3.';

/** Builds a runner whose I/O is the real API and a real EventSource; `venue()` is read lazily because a venue switch drops the run before the next call. */
function makeRunner(venue: () => string, onRun: (run: TeamRun) => void) {
  return createTeamRunner({
    poll: (id, signal) => fetchAgentTeam(venue(), id, signal),
    cancel: id => cancelAgentTeam(venue(), id),
    onRun,
    openConnection: ({ traceUrl: path, lastSeq, onEvent, onPolled, onStatus, poll }) => createTraceConnection({
      makeSource: after => new EventSource(traceUrl(path, after)) as unknown as EventSourceLike,
      poll, lastSeq, parse: parseTraceEvent, eventTypes: TRACE_EVENT_NAMES, onEvent, onPolled, onStatus,
    }),
  });
}

/** Ask-the-agent-team state for Simulation. A new hazard set, a venue or mode switch, Next judge (unmount) or Cancel drops the run and its follow-up. */
export function useAgentTeam({ venueId, hazards, plan, pending, mode, analysisMode, auto = false }: Options) {
  const [run, setRun] = useState<TeamRun>(idleRun);
  const [follow, setFollow] = useState<TeamRun>(idleRun);
  const [followError, setFollowError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const venueRef = useRef(venueId);
  venueRef.current = venueId;
  const hazardsRef = useRef(hazards);
  hazardsRef.current = hazards;
  const runRef = useRef(run);
  runRef.current = run;

  const mainRef = useRef<ReturnType<typeof makeRunner> | null>(null);
  const followRef = useRef<ReturnType<typeof makeRunner> | null>(null);
  if (!mainRef.current) mainRef.current = makeRunner(() => venueRef.current, setRun);
  if (!followRef.current) followRef.current = makeRunner(() => venueRef.current, setFollow);
  const main = mainRef.current;
  const side = followRef.current;

  const key = hazardsKeyOf(hazards);
  const dropAll = useCallback(() => { main.reset(); side.reset(); setFollowError(null); }, [main, side]);
  useEffect(() => { dropAll(); }, [dropAll, key, mode, venueId]);
  useEffect(() => dropAll, [dropAll]);

  // The countdown and elapsed labels need a clock only while something is running.
  const anyActive = isActive(run) || isActive(follow);
  useEffect(() => {
    if (!anyActive) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [anyActive]);

  const unavailable = askAvailability({ hazardCount: hazards.length, planReady: Boolean(plan), pending, active: isActive(run) || isActive(follow) });
  const ask = useCallback(() => {
    if (unavailable) return;
    side.reset();
    setFollowError(null);
    void main.begin({
      mode: analysisMode, hazardsKey: hazardsKeyOf(hazardsRef.current), lanes: ['strategist', 'robustness'],
      start: signal => startAgentTeam(venueRef.current, hazardsRef.current, analysisMode, { signal }),
    });
  }, [analysisMode, main, side, unavailable]);

  const cancel = useCallback(() => { main.cancel(); side.cancel(); }, [main, side]);

  // Auto start: only from idle (a new hazard set drops the old run to idle and the server supersedes it), so a finished,
  // failed or cancelled run is never restarted by itself; the next hazard change starts the next one.
  const autoReady = auto && !unavailable && run.status === 'idle';
  useEffect(() => {
    if (!autoReady) return;
    const timer = setTimeout(ask, AUTO_START_MS);
    return () => clearTimeout(timer);
  }, [autoReady, ask, key]);

  const suggestions = useMemo(() => followUpSuggestions(run), [run]);
  const followUnavailableReason = followUpUnavailable(run) ?? (isActive(follow) ? 'The follow-up is working' : null);

  /** "What if D3 jams?" continues in the same sandbox on the server; this only sends the canonical scenario. */
  const askFollowUp = useCallback((text: string) => {
    const parent = runRef.current;
    if (followUpUnavailable(parent) || !parent.teamId) return;
    const scenario = normalizeScenario(text);
    if (!scenario) { setFollowError(BAD_SCENARIO); return; }
    setFollowError(null);
    const runMode = parent.mode ?? analysisMode;
    const parentId = parent.teamId;
    void side.begin({
      mode: runMode, hazardsKey: parent.hazardsKey, lanes: ['followup'], scenario, parentId,
      start: (signal, notify) => withRetry(() => followUpAgentTeam(venueRef.current, parentId, scenario, runMode, signal), {
        shouldRetry: isParentFinishing, onWait: attempt => notify(`The earlier agent is still wrapping up. Retrying (${attempt})…`),
      }),
    });
  }, [analysisMode, side]);

  const cancelFollowUp = useCallback(() => side.cancel(), [side]);
  return useMemo(() => ({
    run, follow, now, analysisMode, auto, unavailable, followUnavailable: followUnavailableReason, suggestions, followError,
    ask, cancel, askFollowUp, cancelFollowUp,
  }), [run, follow, now, analysisMode, auto, unavailable, followUnavailableReason, suggestions, followError, ask, cancel, askFollowUp, cancelFollowUp]);
}

export type AgentTeamController = ReturnType<typeof useAgentTeam>;
