import { useCallback, useEffect, useRef, useState } from 'react';
import { RotateCcw, X } from 'lucide-react';
import type { AiCapabilities, CaptureEvidence, CaptureRequest, GroundingResult, HazardSimulateResponse, HealthStatus, InvestigationMode, InvestigationProgress, InvestigationResult, RunContext, ScenarioSnapshot } from './types';
import { cancelInvestigation, clearBlockage, fetchHealth, fetchInvestigationProgress, fetchScenario, getCapabilities, interpretGrounding, investigateScenario, operatorApproveGate, resetGate, sendCommand, simulateHazard, stopOutputs } from './api/client';
import { ObservationPanel, type BoardView } from './components/ObservationPanel';
import { SpatialViewport } from './components/SpatialViewport';
import { DecisionBar } from './components/DecisionBar';
import { EvidenceDetails } from './components/WorkspaceDetails';
import { EventConsole, type WorkspaceEvent } from './components/EventConsole';
import { AgentPane } from './components/AgentPane';
import { TopBar } from './components/TopBar';
import { StageChips } from './components/StageChips';
import { HeroNumber } from './components/HeroNumber';
import { HazardPalette } from './components/HazardPalette';
import { PresenterMenu } from './components/PresenterMenu';
import { ResetChecklist } from './components/ResetChecklist';
import { WhyStrip } from './components/WhyStrip';
import { heroView, nextResultMemory, type ResultMemory } from './ai/heroView';
import { ANALYSIS_RUNNING, HAZARD_REJECT, forecastBreakdown, forecastLine, heroForecastLine, placementOutcome, SMOKE_DEFAULT, smokeEvents, type HazardTargetId, type HazardTool } from './ai/hazardTools';
import { preflightItems, resetComplete, type ResetFacts, pendingMessage } from './ai/resetFlow';
import './components/JudgeStage.css';
import { TargetReview } from './components/TargetReview';
import { DetailsSheet, type SheetTab } from './components/DetailsSheet';
import { canApplyGrounding, canApproveInvestigation, groundingLabel, investigationLabel, sameContext } from './ai/policy';
import { captureEvidence } from './ai/evidence';
import { createRequestGate } from './ai/requestGate';
import { approvalSuccessMessage, needsOperatorToken, stopSuccessMessage, type OperatorOutcome } from './ai/operator';
import { createWorkflowEpoch, nextNotFoundCount, shouldKeepPolling } from './ai/workflowEpoch';
import { checkedChip, effectiveVideoMode, gateChip, hardwareChip, provenanceChip, uploadLogLine, uploadSourceLabel, videoModeOptions, VIDEO_DEADLINE_SECONDS, type UploadKind, type VideoMode } from './ai/stageView';
import { ScheduleExplorer } from './features/schedule/ScheduleExplorer';
import { ScenarioLab } from './features/scenario-lab/ScenarioLab';
import { HazardPanel } from './features/hazard-exposure/HazardPanel';
import { HazardRunner } from './features/hazard-exposure/HazardRunner';
import type { HazardResultView } from './features/hazard-exposure/hazard';
import { ClipPicker, type GroundingSelection } from './features/grounding-media/ClipPicker';
import { readVideoSize } from './features/grounding-media/clip';
import { ReviewPanel } from './features/proposal-evidence/ReviewPanel';
import { cleanHazardEvents, toHazardView } from './ai/hazardView';
import { TwinWorkspace } from './components/TwinWorkspace';
import { preloadScene3D } from './components/TwinStage';
import { canSwitchMode, DEFAULT_TWIN_MODE, MODE_LOCKED, modeAfterReset } from './twin/modes';
import { useTwin } from './twin/useTwin';
import type { TwinMode } from './twin/types';

type Target = 'portal:P1' | 'portal:P2' | 'boundary:B2';
const targets: { id: Target; title: string }[] = [
  { id: 'portal:P1', title: 'P1 · West passage' },
  { id: 'portal:P2', title: 'P2 · East passage' },
  { id: 'boundary:B2', title: 'B2 · East boundary' },
];

export { sameContext } from './ai/policy';
const failureMessage = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please try again.';

async function fileBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = '';
  for (let index = 0; index < bytes.length; index += 0x8000) binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  return btoa(binary);
}

/** Longest side of an uploaded image sent for analysis; larger photos are scaled down. */
const MAX_UPLOAD_SIDE = 1920;

export function App() {
  const [snapshot, setSnapshot] = useState<ScenarioSnapshot | null>(null);
  const snapshotRef = useRef<ScenarioSnapshot | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [connection, setConnection] = useState<'connecting' | 'connected' | 'reconnecting'>('connecting');
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedTarget, setSelectedTarget] = useState<Target | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [sheetTab, setSheetTab] = useState<SheetTab>('forecast');
  const [presenting, setPresenting] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isMutating, setIsMutating] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [grounding, setGrounding] = useState<GroundingResult | null>(null);
  const [heldCapture, setHeldCapture] = useState<CaptureEvidence | null>(null);
  const proposal = grounding?.proposal ?? null;
  const [appliedCaptureId, setAppliedCaptureId] = useState<string | null>(null);
  const [isGrounding, setIsGrounding] = useState(false);
  const [groundingError, setGroundingError] = useState<string | null>(null);
  const [investigation, setInvestigation] = useState<InvestigationResult | null>(null);
  const [investigationError, setInvestigationError] = useState<string | null>(null);
  const [isInvestigating, setIsInvestigating] = useState(false);
  const [activeInvestigation, setActiveInvestigation] = useState<{ id: string; context: RunContext } | null>(null);
  const [investigationProgress, setInvestigationProgress] = useState<InvestigationProgress | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);
  const [cancellationRequested, setCancellationRequested] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  // The token lives only in memory: no storage; a page reload clears it, Clear and reset keep it.
  const [operatorToken, setOperatorToken] = useState('');
  const [selectedMode, setSelectedMode] = useState<InvestigationMode | null>(null);
  const [lastAi, setLastAi] = useState<'grounding' | 'investigation' | null>(null);
  const [captureOrigin, setCaptureOrigin] = useState<string | null>(null);
  const [videoMode, setVideoMode] = useState<VideoMode>('static');
  const [capabilities, setCapabilities] = useState<AiCapabilities | null>(null);
  const [hazard, setHazard] = useState<{ view: HazardResultView; context: RunContext } | null>(null);
  const [hazardRows, setHazardRows] = useState<{ element_id: string; close_at_s: string }[]>([{ element_id: 'portal:P1', close_at_s: '12' }]);
  const [isSimulating, setIsSimulating] = useState(false);
  const [hazardError, setHazardError] = useState<string | null>(null);
  const [events, setEvents] = useState<WorkspaceEvent[]>([]);
  const [tool, setTool] = useState<HazardTool | null>(null);
  const [smokeSeconds, setSmokeSeconds] = useState(SMOKE_DEFAULT);
  const [smoke, setSmoke] = useState<Partial<Record<HazardTargetId, number>>>({});
  const [smokeForecast, setSmokeForecast] = useState<{ events: { element_id: string; close_at_s: number }[]; count: number; population: number; breakdown: Record<string, number> | null; context: RunContext } | null>(null);
  const [smokePending, setSmokePending] = useState(false);
  const [smokeError, setSmokeError] = useState<string | null>(null);
  const [stageNotice, setStageNotice] = useState<string | null>(null);
  const noticeTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [twinMode, setTwinMode] = useState<TwinMode>(DEFAULT_TWIN_MODE);
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuSlot, setMenuSlot] = useState<HTMLDivElement | null>(null);
  const menuTriggerRef = useRef<HTMLButtonElement | null>(null);
  const [cameraLive, setCameraLive] = useState(false);
  const [boardView, setBoardView] = useState<BoardView>('none');
  const [readSeconds, setReadSeconds] = useState<number | null>(null);
  const [resultMemory, setResultMemory] = useState<ResultMemory>({ current: null, previous: null });
  const [reset, setReset] = useState<{ phase: 'idle' | 'running' | 'waiting' | 'done' | 'error'; message: string | null }>({ phase: 'idle', message: null });
  const eventId = useRef(0);
  // Bumped on every reset. A response that began in an earlier epoch is dropped before it touches state.
  const epoch = useRef(createWorkflowEpoch());
  const [epochKey, setEpochKey] = useState(0);
  const groundingRequest = useRef(0);
  const groundingGate = useRef(createRequestGate());
  const investigationGate = useRef(createRequestGate());
  const investigationRequest = useRef<string | null>(null);
  const healthRequest = useRef(0);
  const hazardGate = useRef(createRequestGate());
  const hazardRequest = useRef(0);
  const hazardAbort = useRef<AbortController | null>(null);
  const telemetryRef = useRef<string | null>(null);
  const reviewRef = useRef<HTMLElement>(null);
  const reviewTriggerRef = useRef<HTMLElement | null>(null);
  const presenterTriggerRef = useRef<HTMLButtonElement | null>(null);

  const addEvent = useCallback((source: WorkspaceEvent['source'], message: string, level: WorkspaceEvent['level'] = 'info') => {
    setEvents(previous => [...previous.slice(-149), { id: ++eventId.current, at: new Date().toISOString(), source, message, level }]);
  }, []);

  const acceptSnapshot = useCallback((next: ScenarioSnapshot, authoritative = false) => {
    const previous = snapshotRef.current;
    const newDeviceBoot = authoritative && previous?.last_hardware_boot_id && next.last_hardware_boot_id
      && previous.last_hardware_boot_id !== next.last_hardware_boot_id;
    // A newer server snapshot may reset revisions after a restart. Delayed older snapshots still lose to later updates.
    const freshServerSnapshot = authoritative && previous && Date.parse(next.timestamp_iso) > Date.parse(previous.timestamp_iso);
    if (!newDeviceBoot && !freshServerSnapshot && previous && next.context.geometry_revision === previous.context.geometry_revision
      && (next.context.scenario_revision < previous.context.scenario_revision || next.context.physical_revision < previous.context.physical_revision)) return;
    snapshotRef.current = next;
    setSnapshot(next);
    if (!previous || next.current_plan?.run_id !== previous.current_plan?.run_id) {
      const plan = next.current_plan;
      addEvent('planner', plan ? `${plan.completed_crossings} modeled crossings · ${plan.remaining_population} remaining · ${plan.horizon_seconds}s horizon. ${plan.validator_report.is_valid ? 'Checker accepted result.' : 'Result needs review.'}` : 'Scenario loaded. Awaiting a result.', plan?.validator_report.is_valid ? 'success' : 'info');
    }
  }, [addEvent]);

  const refreshHealth = useCallback(async () => {
    const request = ++healthRequest.current;
    const next = await fetchHealth();
    if (request === healthRequest.current) setHealth(next);
  }, []);

  const refresh = useCallback(async () => {
    setLoadError(null);
    const [, scenarioResult] = await Promise.allSettled([refreshHealth(), fetchScenario(), getCapabilities().then(setCapabilities, () => setCapabilities(null))]);
    if (scenarioResult.status === 'fulfilled') acceptSnapshot(scenarioResult.value, true);
    else setLoadError('The local backend is unavailable. Start the server, then reconnect.');
  }, [acceptSnapshot, refreshHealth]);

  useEffect(() => {
    void refresh();
    const stream = new EventSource('/api/scenarios/facility-demo/events');
    stream.onopen = () => { setConnection('connected'); setLoadError(null); void refreshHealth().catch(() => { /* Scenario SSE remains the state authority; configuration stays unverified. */ }); };
    stream.onerror = () => setConnection('reconnecting');
    const update = (event: MessageEvent, authoritative = false) => {
      try { acceptSnapshot(JSON.parse(event.data) as ScenarioSnapshot, authoritative); }
      catch { addEvent('system', 'A state update could not be read. Reconnect to refresh the workspace.', 'warning'); }
    };
    stream.addEventListener('snapshot', event => update(event as MessageEvent, true));
    stream.addEventListener('scenario_updated', event => update(event as MessageEvent));
    stream.addEventListener('physical_state_confirmed', event => { update(event as MessageEvent); addEvent('device', 'Endpoint state update received. A new model result was requested.', 'success'); });
    stream.addEventListener('hardware_telemetry', event => {
      try {
        const telemetry = JSON.parse((event as MessageEvent).data);
        if (!['OPEN', 'CLOSED', 'TRANSIT', 'UNKNOWN', 'FAULT'].includes(telemetry.physical_gate_state)) return;
        const current = snapshotRef.current;
        if (!current) return;
        const key = `${telemetry.boot_id}:${telemetry.gate_epoch}:${telemetry.physical_gate_state}`;
        if (telemetryRef.current !== key) { telemetryRef.current = key; addEvent('device', `P3 reported ${String(telemetry.physical_gate_state).toLowerCase()} · epoch ${telemetry.gate_epoch}.`, telemetry.physical_gate_state === 'FAULT' ? 'warning' : 'info'); }
        acceptSnapshot({ ...current, physical_gate_state: telemetry.physical_gate_state, last_hardware_boot_id: telemetry.boot_id, last_gate_epoch: telemetry.gate_epoch });
      } catch { addEvent('device', 'Device telemetry could not be read.', 'warning'); }
    });
    return () => stream.close();
  }, [acceptSnapshot, addEvent, refresh, refreshHealth]);

  useEffect(() => {
    if (!activeInvestigation) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let notFound = 0;
    const poll = async () => {
      try {
        const progress = await fetchInvestigationProgress('facility-demo', activeInvestigation.id, controller.signal);
        if (controller.signal.aborted || investigationRequest.current !== activeInvestigation.id) return;
        setInvestigationProgress(progress);
        if (progress.investigation) setInvestigation(progress.investigation);
        notFound = nextNotFoundCount(progress.status, notFound);
        if (!shouldKeepPolling(progress.status, notFound)) return;
      } catch { if (controller.signal.aborted) return; }
      timer = setTimeout(() => void poll(), 1000);
    };
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [activeInvestigation]);

  useEffect(() => {
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || document.querySelector('dialog[open]')) return;
      if (isEditing) {
        setIsEditing(false); setSelectedTarget(null);
        reviewTriggerRef.current?.focus({ preventScroll: true });
      } else if (presenting) {
        setPresenting(false);
        presenterTriggerRef.current?.focus();
      }
    };
    window.addEventListener('keydown', escape);
    return () => window.removeEventListener('keydown', escape);
  }, [isEditing, presenting]);

  useEffect(() => {
    if (isEditing) {
      reviewRef.current?.querySelector<HTMLSelectElement>('select')?.focus({ preventScroll: true });
    }
  }, [isEditing, selectedTarget]);

  const physicalUncertain = Boolean(snapshot && ['UNKNOWN', 'TRANSIT', 'FAULT'].includes(snapshot.physical_gate_state));
  const plan = snapshot?.current_plan;
  const planCurrent = Boolean(connection === 'connected' && plan?.validator_report.is_valid && sameContext(plan.base_context, snapshot?.context) && !physicalUncertain);
  const proposalCurrent = Boolean(connection === 'connected' && sameContext(proposal?.source_context, snapshot?.context) && !physicalUncertain);
  const hazardCurrent = Boolean(hazard && connection === 'connected' && sameContext(hazard.context, snapshot?.context));
  const investigationCurrent = Boolean(connection === 'connected' && sameContext(investigation?.base_context, snapshot?.context) && !physicalUncertain);
  const blocked = [...(snapshot?.blocked_portals ?? []), ...(snapshot?.blocked_boundaries ?? [])];
  const physical = needsOperatorToken(health?.hardware_mode);
  const targetBlocked = selectedTarget ? blocked.includes(selectedTarget.split(':')[1]) : false;
  const canChange = Boolean(snapshot && connection === 'connected' && !isMutating);
  // Anything that shows plan numbers receives displaySnapshot, which hides a plan that is not current.
  // ScenarioLab and WorkspaceDetails check plan currency themselves, so they receive the raw snapshot.
  const displaySnapshot = snapshot && !planCurrent ? { ...snapshot, current_plan: null } : snapshot;
  const connectedSnapshot = connection === 'connected' ? displaySnapshot : null;

  /** Invalidates every outstanding request and clears workflow state. Late responses compare against the new epoch. */
  const resetWorkflow = () => {
    epoch.current.bump(); setEpochKey(epoch.current.current());
    groundingRequest.current += 1;
    groundingGate.current.invalidate();
    investigationGate.current.invalidate();
    investigationRequest.current = null;
    hazardRequest.current += 1; hazardGate.current.invalidate(); hazardAbort.current?.abort();
    setHazard(null); setHazardError(null); setIsSimulating(false);
    setGrounding(null); setHeldCapture(null); setAppliedCaptureId(null); setInvestigation(null);
    setGroundingError(null); setInvestigationError(null); setIsGrounding(false); setIsInvestigating(false);
    setActiveInvestigation(null); setInvestigationProgress(null); setCancellationRequested(false); setIsCancelling(false);
    // The operator token stays in memory across Clear and reset; only a page reload drops it.
    setIsApproving(false); setLastAi(null); setCaptureOrigin(null);
    setTool(null); setSmoke({}); setSmokeForecast(null); setSmokeError(null); setSmokePending(false); setReadSeconds(null);
  };

  const mutate = async (target?: Target, reset = false, source: 'manual_override' | 'grounding_proposal' = 'manual_override') => {
    const current = snapshotRef.current;
    if (!current || connection !== 'connected' || isMutating) return false;
    setIsMutating(true); setMutationError(null);
    try {
      const [type, id] = (target ?? 'portal:P2').split(':') as ['portal' | 'boundary', 'P1' | 'P2' | 'B2'];
      const alreadyBlocked = type === 'portal' ? current.blocked_portals.includes(id) : current.blocked_boundaries.includes(id);
      const response = !reset && alreadyBlocked && source === 'manual_override'
        ? await clearBlockage('facility-demo', current.context, type, id)
        : await sendCommand('facility-demo', { type: reset ? 'RESET_SCENARIO' : 'APPLY_BLOCKAGE', expected_scenario_revision: current.context.scenario_revision, expected_context: current.context, idempotency_key: crypto.randomUUID(), ...(!reset ? { target_type: type, target_id: id, source, ...(source === 'grounding_proposal' ? { proposal_id: grounding?.proposal_id, reviewed: true } : {}) } : {}) });
      acceptSnapshot(response.snapshot);
      const sourceLabel = source === 'manual_override' ? 'Manual override' : groundingLabel(grounding, { mediaKind: heldCapture?.media_kind });
      addEvent('scenario', reset ? 'Manual reset · scenario blockages cleared. Physical gate position is unchanged.' : `${sourceLabel} · ${id} ${alreadyBlocked && source === 'manual_override' ? 'restored' : 'marked unavailable'} after operator review.`, 'success');
      if (reset) resetWorkflow();
      reviewTriggerRef.current?.focus({ preventScroll: true });
      setSelectedTarget(null); setIsEditing(false);
      return true;
    } catch (error) { setMutationError(failureMessage(error)); addEvent('scenario', failureMessage(error), 'warning'); return false; }
    finally { setIsMutating(false); }
  };

  const capture = async (captureRequest: CaptureRequest, upload?: UploadKind) => {
    if (isGrounding || !snapshotRef.current || connection !== 'connected') return;
    const token = groundingGate.current.start();
    if (token === null) return;
    const request = ++groundingRequest.current;
    const started = epoch.current.current();
    const readStart = performance.now();
    setReadSeconds(null);
    setIsGrounding(true); setGroundingError(null); setGrounding(null); setHeldCapture(captureRequest); setAppliedCaptureId(null);
    setCaptureOrigin(upload ? uploadSourceLabel(upload) : captureRequest.mode === 'fixture' ? 'Fixture' : captureRequest.source_kind === 'annotated_plan' ? 'Demo board image' : 'Camera still');
    addEvent('vision', captureRequest.mode === 'fixture' ? `Reviewing ${captureRequest.fixture_target} fixture. No Gemini call requested.` : upload ? uploadLogLine(upload, captureRequest.thinking_level) : `${captureRequest.source_kind === 'annotated_plan' ? 'Synthetic demo board image' : 'Captured camera still'} sent to Gemini · ${captureRequest.thinking_level} thinking.`);
    try {
      const response = await interpretGrounding('facility-demo', captureRequest);
      if (request !== groundingRequest.current || !epoch.current.isCurrent(started)) return;
      setGrounding(response); setLastAi('grounding'); setReadSeconds((performance.now() - readStart) / 1000);
      if (response.status !== 'completed') setGroundingError(response.errors.join(' ') || `Gemini grounding ${response.status.replace(/_/g, ' ')}. No proposal was accepted.`);
      addEvent('vision', `${groundingLabel(response, { mediaKind: captureRequest.media_kind })} · ${response.proposal?.status ?? response.status} · ${response.proposal?.selected_entity_id ?? 'no target'}.`, response.status === 'completed' && response.proposal?.status === 'matched' ? 'success' : 'warning');
    } catch (error) { if (request === groundingRequest.current && epoch.current.isCurrent(started)) { setGroundingError(failureMessage(error)); addEvent('vision', failureMessage(error), 'warning'); } }
    finally { groundingGate.current.finish(token); if (request === groundingRequest.current && epoch.current.isCurrent(started)) setIsGrounding(false); }
  };
  const runHazard = async () => {
    const current = snapshotRef.current;
    const hazardEvents = cleanHazardEvents(hazardRows);
    if (!current || connection !== 'connected' || hazardEvents.length === 0) return;
    const token = hazardGate.current.start();
    if (token === null) return;
    const request = ++hazardRequest.current;
    const started = epoch.current.current();
    const context = { ...current.context };
    const abort = new AbortController();
    hazardAbort.current = abort;
    setIsSimulating(true); setHazardError(null);
    try {
      const responses: HazardSimulateResponse[] = [];
      for (const alternative_id of ['KEEP_CURRENT', 'OPEN_P3'] as const) responses.push(await simulateHazard({ alternative_id, events: hazardEvents }, abort.signal));
      if (request !== hazardRequest.current || !epoch.current.isCurrent(started) || !hazardGate.current.isCurrent(token)) return;
      setHazard({ view: toHazardView(hazardEvents, responses), context });
      addEvent('analysis', `Hazard forecast · ${hazardEvents.length} closure ${hazardEvents.length === 1 ? 'event' : 'events'} · local solver, no Gemini call.`, responses.every(item => item.is_valid) ? 'success' : 'warning');
    } catch (error) { if (request === hazardRequest.current && epoch.current.isCurrent(started)) { setHazardError(failureMessage(error)); addEvent('analysis', failureMessage(error), 'warning'); } }
    finally { hazardGate.current.finish(token); if (request === hazardRequest.current && epoch.current.isCurrent(started)) setIsSimulating(false); }
  };
  const selectClip = async (selection: GroundingSelection) => {
    const current = snapshotRef.current;
    if (!current || connection !== 'connected' || isGrounding) return;
    const started = epoch.current.current();
    try {
      const base = { capture_id: crypto.randomUUID(), timestamp_iso: new Date().toISOString(), source_context: { ...current.context }, thinking_level: 'low' as const, source_kind: 'tabletop_camera' as const, mode: 'live' as const };
      if (selection.kind === 'video') {
        const [bytes, size] = await Promise.all([fileBase64(selection.file), readVideoSize(selection.file)]);
        if (!epoch.current.isCurrent(started)) return;
        // The real frame size when the browser can read it; the contract default only as a last resort.
        await capture(await captureEvidence({ ...base, dimensions: size ?? [1920, 1080], video_base64: bytes, media_kind: 'video', video_mode: effectiveVideoMode(videoModeOptions(capabilities), videoMode), video_mime: selection.file.type, deadline_seconds: VIDEO_DEADLINE_SECONDS }), 'video');
      } else {
        // Re-encode as JPEG at a bounded size so the declared dimensions always match the pixels sent.
        const bitmap = await createImageBitmap(selection.file);
        if (!epoch.current.isCurrent(started)) { bitmap.close(); return; }
        const scale = Math.min(1, MAX_UPLOAD_SIDE / Math.max(bitmap.width, bitmap.height));
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(bitmap.width * scale)); canvas.height = Math.max(1, Math.round(bitmap.height * scale));
        const drawing = canvas.getContext('2d');
        if (!drawing) { bitmap.close(); throw new Error('This browser could not read the image.'); }
        drawing.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
        bitmap.close();
        const data = canvas.toDataURL('image/jpeg', .92);
        await capture(await captureEvidence({ ...base, dimensions: [canvas.width, canvas.height], image_base64: data.slice(data.indexOf(',') + 1), media_kind: 'image', deadline_seconds: 45 }), 'image');
      }
    } catch (error) { if (epoch.current.isCurrent(started)) setGroundingError(failureMessage(error)); }
  };
  const clearProposal = () => { groundingRequest.current++; groundingGate.current.invalidate(); setGrounding(null); setHeldCapture(null); setAppliedCaptureId(null); setGroundingError(null); setIsGrounding(false); };
  const applyProposal = async () => {
    const target = proposal && `${proposal.selected_entity_type}:${proposal.selected_entity_id}`;
    if (!proposal || !proposalCurrent || !canApplyGrounding(grounding, snapshotRef.current?.context) || !targets.some(item => item.id === target)) return;
    const started = epoch.current.current();
    const request = groundingRequest.current;
    const applied = await mutate(target as Target, false, 'grounding_proposal');
    // A reset or a cleared/replaced proposal while the command was in flight must not repopulate the workspace.
    if (applied && epoch.current.isCurrent(started) && request === groundingRequest.current) { setAppliedCaptureId(proposal.capture_id); startAutoInvestigation(); }
  };
  const investigate = async (mode: InvestigationMode) => {
    if (isInvestigating || !snapshotRef.current || connection !== 'connected') return;
    const token = investigationGate.current.start();
    if (token === null) return;
    const expectedContext = { ...snapshotRef.current.context };
    const investigationId = crypto.randomUUID();
    const started = epoch.current.current();
    investigationRequest.current = investigationId;
    setActiveInvestigation({ id: investigationId, context: expectedContext }); setInvestigationProgress(null); setCancellationRequested(false); setIsCancelling(false);
    setIsInvestigating(true); setInvestigation(null); setInvestigationError(null); addEvent('analysis', `Requested KEEP_CURRENT and OPEN_P3 comparison · ${mode === 'live' ? 'Gemini managed agent' : 'explicit local solver'}.`);
    try {
      const response = await investigateScenario('facility-demo', expectedContext, mode, investigationId);
      if (investigationRequest.current !== investigationId || !epoch.current.isCurrent(started)) return;
      setInvestigation(response.investigation); setLastAi('investigation');
      const checkedCount = response.investigation.candidate_envelopes.filter(candidate => candidate.validator_report.is_valid).length;
      if (response.investigation.status !== 'completed') setInvestigationError(response.investigation.errors?.join(' ') || `Analysis ${response.investigation.status.replace(/_/g, ' ')}. No winning option is available.`);
      addEvent('analysis', `${investigationLabel(response.investigation, { managedModelFallback: capabilities?.managed_model_fallback })} · ${checkedCount} checked alternatives.`, response.investigation.status === 'completed' ? 'success' : 'warning');
    } catch (error) { if (investigationRequest.current === investigationId && epoch.current.isCurrent(started)) { setInvestigationError(failureMessage(error)); addEvent('analysis', failureMessage(error), 'warning'); } }
    finally { investigationGate.current.finish(token); if (investigationRequest.current === investigationId && epoch.current.isCurrent(started)) { setIsInvestigating(false); setActiveInvestigation(null); setIsCancelling(false); } }
  };
  const cancelAnalysis = async () => {
    if (!activeInvestigation || isCancelling || cancellationRequested) return;
    const activeId = activeInvestigation.id;
    const started = epoch.current.current();
    setIsCancelling(true);
    try {
      const response = await cancelInvestigation('facility-demo', activeInvestigation.id, activeInvestigation.context);
      if (investigationRequest.current !== activeId || !epoch.current.isCurrent(started)) return;
      setCancellationRequested(response.status === 'cancellation_requested');
      if (response.investigation) setInvestigation(response.investigation);
      addEvent('analysis', response.status === 'already_finished' ? 'Analysis already finished. Recorded result retained.' : 'Cancellation requested. Waiting for the server and provider receipts.');
    } catch (error) { if (investigationRequest.current === activeId && epoch.current.isCurrent(started)) { setInvestigationError(failureMessage(error)); addEvent('analysis', failureMessage(error), 'warning'); } }
    finally { if (investigationRequest.current === activeId && epoch.current.isCurrent(started)) setIsCancelling(false); }
  };
  const approve = async (): Promise<OperatorOutcome> => {
    const current = snapshotRef.current;
    const candidate = investigation?.candidate_envelopes.find(item => item.alternative_id === 'OPEN_P3');
    if (!current || !investigationCurrent || !canApproveInvestigation(investigation, current.context) || !candidate || isApproving) {
      return { ok: false, message: 'A current checked improvement recommending OPEN_P3 is required before movement.' };
    }
    const started = epoch.current.current();
    setIsApproving(true);
    try {
      const response = await operatorApproveGate(current.context, investigation!.investigation_id, candidate.run_id, physical ? operatorToken.trim() : undefined);
      const message = approvalSuccessMessage(Boolean(response.acknowledged));
      if (epoch.current.isCurrent(started)) addEvent('device', message);
      return { ok: true, message, acknowledged: Boolean(response.acknowledged) };
    } catch (error) {
      if (epoch.current.isCurrent(started)) addEvent('device', failureMessage(error), 'warning');
      return { ok: false, message: failureMessage(error) };
    } finally { if (epoch.current.isCurrent(started)) setIsApproving(false); }
  };
  const stop = async (): Promise<OperatorOutcome> => {
    if (physical && !operatorToken.trim()) return { ok: false, message: 'Enter the operator token to stop.' };
    try {
      await stopOutputs(physical ? operatorToken.trim() : undefined);
      addEvent('device', stopSuccessMessage(), 'success');
      return { ok: true, message: stopSuccessMessage() };
    } catch (error) {
      addEvent('device', failureMessage(error), 'warning');
      return { ok: false, message: failureMessage(error) };
    }
  };
  const selectTarget = (target: Target) => { reviewTriggerRef.current = document.activeElement as HTMLElement | null; setSelectedTarget(target); setIsEditing(true); setMutationError(null); };
  const availabilityMessage = connection !== 'connected'
    ? 'Reconnect to the local backend before using this result.'
    : physicalUncertain ? `P3 is ${snapshot?.physical_gate_state.toLowerCase()}. Wait for a confirmed endpoint.` : undefined;
  const closeEditor = () => {
    setIsEditing(false); setSelectedTarget(null);
    reviewTriggerRef.current?.focus({ preventScroll: true });
  };


  const videoOptions = videoModeOptions(capabilities);
  const apiConfigured = health?.ai?.managed.configured ?? health?.live_api_configured ?? false;
  const mode: InvestigationMode = selectedMode ?? (apiConfigured ? 'live' : 'local');
  const aiResult = lastAi === 'investigation' ? investigation : lastAi === 'grounding' ? grounding : investigation ?? grounding;
  const endpointReported = Boolean(snapshot?.last_hardware_boot_id);
  const stagePlan = planCurrent ? plan : null;
  const localEnabled = health?.ai?.fixtures_enabled ?? false;
  const stageCount = stagePlan ? stagePlan.completed_crossings : null;
  // The delta chip compares with the last different checked count. Derived during render so the chip and digits change together.
  if (stageCount !== null && stageCount !== resultMemory.current) setResultMemory(nextResultMemory(resultMemory, stageCount));
  const hero = heroView({ connected: connection === 'connected', physicalUncertain, planCurrent, completed: plan?.completed_crossings, population: plan?.initial_population, horizon: plan?.horizon_seconds, previous: resultMemory.previous });

  const showNotice = (message: string) => {
    clearTimeout(noticeTimer.current);
    setStageNotice(message);
    noticeTimer.current = setTimeout(() => setStageNotice(null), 4000);
  };
  useEffect(() => () => clearTimeout(noticeTimer.current), []);
  useEffect(() => preloadScene3D(), []);

  // Simulation never touches the v1 investigation: switching only changes what the stage shows, and leaving clears the twin.
  const twin = useTwin({ mode: twinMode, notify: showNotice, log: (message, level = 'info') => addEvent('analysis', message, level) });
  const sim = twinMode !== 'tabletop';
  const [calibrateTick, setCalibrateTick] = useState(0);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const changeTwinMode = (next: TwinMode) => {
    if (!canSwitchMode(isInvestigating)) { showNotice(MODE_LOCKED); return; }
    if (next === twinMode) return;
    setTool(null); setStageNotice(null);
    if (next !== 'camera') setImageFile(null);
    setTwinMode(next);
  };

  /** Live Gemini when configured, otherwise the local solver; the presenter menu choice wins when it is available. */
  const startAutoInvestigation = () => {
    const live = apiConfigured, local = localEnabled;
    const chosen: InvestigationMode | null = mode === 'live' ? (live ? 'live' : local ? 'local' : null) : (local ? 'local' : live ? 'live' : null);
    if (chosen) void investigate(chosen);
  };

  const placeHazard = async (targetId: Target) => {
    if (isInvestigating) { showNotice(ANALYSIS_RUNNING); return; }
    const placement = placementOutcome(targetId);
    if (!placement.ok) { showNotice(placement.message); return; }
    const id = targetId.split(':')[1];
    const closed = blocked.includes(id);
    if (tool === 'fire') {
      if (closed) { showNotice(`${id} is already closed.`); return; }
      if (await mutate(targetId)) { setTool(null); startAutoInvestigation(); }
    } else if (tool === 'smoke') {
      setSmoke(current => ({ ...current, [targetId]: smokeSeconds })); setTool(null);
    } else if (tool === 'clear') {
      if (closed) { if (await mutate(targetId)) setTool(null); }
      else if (smoke[targetId] !== undefined) { setSmoke(current => { const next = { ...current }; delete next[targetId]; return next; }); setTool(null); }
      else showNotice(`Nothing to clear on ${id}.`);
    }
  };
  const onSelectTarget = (target: Target) => {
    if (tool) { void placeHazard(target); return; }
    if (isInvestigating) { showNotice(ANALYSIS_RUNNING); return; }
    selectTarget(target);
  };
  const chooseTool = (next: HazardTool | null) => { setTool(next); if (next) { setIsEditing(false); setSelectedTarget(null); } };

  // Smoke is a forecast: the closure is timed, the real scenario is untouched, and nothing here can be approved.
  const contextHash = snapshot?.context.context_hash ?? '';
  useEffect(() => {
    const hazardEvents = smokeEvents(smoke);
    const current = snapshotRef.current;
    if (!hazardEvents.length || !current || connection !== 'connected') { setSmokeForecast(null); setSmokePending(false); setSmokeError(null); return; }
    const controller = new AbortController();
    const context = { ...current.context };
    setSmokePending(true); setSmokeError(null);
    simulateHazard({ alternative_id: 'KEEP_CURRENT', events: hazardEvents }, controller.signal).then(response => {
      if (controller.signal.aborted) return;
      setSmokePending(false);
      if (!response.is_valid) { setSmokeForecast(null); setSmokeError('The forecast could not be checked.'); return; }
      setSmokeForecast({ events: hazardEvents, count: response.completed_crossings, population: response.completed_crossings + response.remaining_population, breakdown: forecastBreakdown(response.boundary_breakdown), context });
      addEvent('analysis', `Smoke forecast · ${hazardEvents.map(event => `${event.element_id} at ${event.close_at_s} s`).join(', ')} · local solver, no Gemini call.`, 'success');
    }, error => {
      if (controller.signal.aborted) return;
      setSmokePending(false); setSmokeForecast(null); setSmokeError(failureMessage(error));
    });
    return () => controller.abort();
  }, [smoke, contextHash, connection, addEvent]);
  const smokeCurrent = Boolean(smokeForecast && connection === 'connected' && sameContext(smokeForecast.context, snapshot?.context));
  const smokeHazardEvents = smokeEvents(smoke);
  const forecastUi = smokeHazardEvents.length === 0 ? null
    : smokeCurrent && smokeForecast ? { text: forecastLine({ events: smokeForecast.events, forecast: smokeForecast.count, current: stageCount, population: smokeForecast.population }), pending: false }
    : { text: '', pending: smokePending };

  const resetFacts: ResetFacts = { scenarioClear: blocked.length === 0, gateClosedObserved: snapshot?.physical_gate_state === 'CLOSED' && Boolean(snapshot?.last_hardware_boot_id), noRunActive: !isInvestigating && !activeInvestigation && !isSimulating, boardReady: physical ? boardView === 'live' : boardView !== 'none' };
  // While waiting, name exactly what is unmet so the message never contradicts a green item.
  const resetMessage = reset.phase === 'waiting' ? (pendingMessage(resetFacts, physical) ?? reset.message) : reset.message;
  const resetNow = async () => {
    if (reset.phase === 'running' || !snapshotRef.current) return;
    setTwinMode(modeAfterReset()); twin.reset(); setImageFile(null);
    setReset({ phase: 'running', message: 'Cancelling any run…' });
    try {
      if (activeInvestigation) {
        await cancelInvestigation('facility-demo', activeInvestigation.id, activeInvestigation.context).catch(() => undefined);
        for (let attempt = 0; attempt < 16; attempt += 1) {
          const status = await fetchHealth().catch(() => null);
          if (!status?.investigation_running) break;
          await new Promise(resolve => setTimeout(resolve, 500));
        }
      }
      setReset({ phase: 'running', message: 'Clearing hazards and the scenario…' });
      if (!(await mutate(undefined, true))) { setReset({ phase: 'error', message: 'The scenario could not be cleared. Retry.' }); return; }
      if (physical && !operatorToken.trim()) { setReset({ phase: 'error', message: 'Operator token required to close P3.' }); return; }
      setReset({ phase: 'running', message: 'Closing P3…' });
      const response = await resetGate(physical ? operatorToken.trim() : undefined);
      addEvent('device', response.status === 'ALREADY_CLOSED' ? 'P3 already closed. Waiting for the endpoint to confirm.' : 'Close request acknowledged — not arrival. Waiting for the endpoint.', 'info');
      setResultMemory({ current: null, previous: null });
      setReset({ phase: 'waiting', message: 'Waiting for P3 closed to be observed…' });
    } catch (error) {
      const message = failureMessage(error);
      addEvent('device', message, 'warning');
      setReset({ phase: 'error', message });
    }
  };
  useEffect(() => {
    if (reset.phase === 'waiting' && resetComplete(resetFacts, physical)) setReset({ phase: 'done', message: 'Ready for the next judge.' });
  });
  useEffect(() => {
    if (reset.phase === 'done') {
      const timer = setTimeout(() => setReset({ phase: 'idle', message: null }), 8000);
      return () => clearTimeout(timer);
    }
  }, [reset.phase]);

  const receiptAge = capabilities?.last_live_receipt_age_seconds ?? (capabilities?.last_live_receipt_at ? Math.max(0, (Date.now() - Date.parse(capabilities.last_live_receipt_at)) / 1000) : null);
  const preflight = preflightItems({ geminiConfigured: apiConfigured, receiptAgeSeconds: Number.isFinite(receiptAge) ? receiptAge : null, hardwareMode: health?.hardware_mode, gateState: snapshot?.physical_gate_state, endpointReported, physical, tokenHeld: operatorToken.trim().length > 0, cameraLive: physical ? boardView === 'live' : boardView !== 'none' });
  const [clearMessage, setClearMessage] = useState<string | null>(null);
  const clearHazards = async () => {
    if (snapshot?.physical_gate_state === 'OPEN') { setClearMessage('P3 is open \u00b7 use Next judge'); return; }
    setClearMessage(null);
    if (await mutate(undefined, true)) setClearMessage('Hazards cleared.');
  };
  const toggleMenu = () => setMenuOpen(value => !value);
  const uploadPanel = <div className="clip-slot">
    <ClipPicker videoEnabled={videoOptions.length > 0} onSelect={selection => void selectClip(selection)} disabled={isGrounding || connection !== 'connected' || !snapshot} />
    {videoOptions.length > 1 && <label className="clip-mode">Video mode<select aria-label="Video mode" value={videoMode} onChange={event => setVideoMode(event.target.value as VideoMode)}><option value="static">Static frames</option><option value="agentic">Agentic</option></select></label>}
  </div>;
  const openSheet = (tab?: SheetTab) => { if (tab) setSheetTab(tab); setSheetOpen(true); };

  return <div className={`app${presenting ? ' presenting' : ''}`}>
    <a className="skip-link" href="#workspace-main">Skip to workspace</a>
    <TopBar hardware={hardwareChip(health?.hardware_mode)} checked={checkedChip(Boolean(snapshot), planCurrent)} connection={connection} presenting={presenting} presenterRef={presenterTriggerRef} onTogglePresenting={() => setPresenting(value => !value)} onStop={stop} onOpenDetails={() => openSheet()} onToggleMenu={toggleMenu} menuOpen={menuOpen} menuRef={menuTriggerRef} onResetJudge={() => void resetNow()} isResetting={reset.phase === 'running'} canReset={Boolean(snapshot) && connection === 'connected'} />
    <PresenterMenu open={menuOpen} onClose={() => setMenuOpen(false)} triggerRef={menuTriggerRef} boardSlot={setMenuSlot} mode={mode} onModeChange={setSelectedMode} modeLocked={isInvestigating} apiConfigured={apiConfigured} localEnabled={localEnabled} physical={physical} operatorToken={operatorToken} onOperatorToken={setOperatorToken} preflight={preflight} facts={resetFacts} resetMessage={resetMessage} isResetting={reset.phase === 'running'} canReset={Boolean(snapshot) && connection === 'connected'} onReset={() => void resetNow()} onClearHazards={() => void clearHazards()} clearMessage={clearMessage} twinMode={twinMode} onTwinMode={changeTwinMode} twinLocked={isInvestigating} onCalibrate={() => { setMenuOpen(false); setCalibrateTick(value => value + 1); }} imageFile={imageFile} onImageFile={setImageFile} venues={twin.venues} venueId={twin.venueId} onVenue={id => void twin.switchVenue(id)} />
    <main id="workspace-main" className={`main${sim ? ' is-sim' : ''}`} tabIndex={-1}>
      <div className="alerts">
        {loadError && <div className="alert" role="alert"><span>{loadError}</span><button type="button" onClick={() => void refresh()}>Reconnect<RotateCcw size={13} aria-hidden="true" /></button></div>}
        {mutationError && <div className="alert" role="alert"><span>{mutationError}</span><button type="button" onClick={() => setMutationError(null)} aria-label="Dismiss error"><X size={16} aria-hidden="true" /></button></div>}
      </div>
      <StageChips hero={<HeroNumber hero={hero} forecast={smokeCurrent && smokeForecast ? heroForecastLine(smokeForecast.events, smokeForecast.count) : null} />} gate={gateChip(snapshot?.physical_gate_state, endpointReported)} provenance={provenanceChip(aiResult)} blocked={blocked} />
      <SpatialViewport snapshot={displaySnapshot} selectedTarget={selectedTarget} onSelectTarget={onSelectTarget} forecast={smokeCurrent ? smokeForecast?.events : hazardCurrent ? hazard?.view.events : undefined} armedTool={tool} onBackgroundTap={() => showNotice(isInvestigating ? ANALYSIS_RUNNING : HAZARD_REJECT)} smoke={smoke} forecastFlow={smokeCurrent ? smokeForecast?.breakdown : null} />
      <div className="stage-tools">
        <HazardPalette tool={tool} onTool={chooseTool} smokeSeconds={smokeSeconds} onSmokeSeconds={setSmokeSeconds} locked={isInvestigating} notice={stageNotice} forecast={forecastUi} forecastError={smokeError} />
        {isEditing && selectedTarget && <TargetReview reviewRef={reviewRef} targets={targets} target={selectedTarget} blocked={targetBlocked} busy={isMutating} disabled={!canChange} onChange={value => setSelectedTarget(value as Target)} onApply={() => void mutate(selectedTarget)} onClose={closeEditor} />}
        {reset.phase !== 'idle' && <ResetChecklist facts={resetFacts} message={resetMessage} physical={physical} />}
      </div>
      {sim && <TwinWorkspace twin={twin} notice={stageNotice} mode={twinMode} calibrateTick={calibrateTick} imageFile={imageFile} analysisMode={mode} />}
      <ObservationPanel resetKey={epochKey} physical={physical} proposal={proposal} result={grounding} currentContext={snapshot?.context} liveConfigured={health?.ai?.direct.configured ?? health?.live_api_configured ?? false} fixturesEnabled={health?.ai?.fixtures_enabled ?? false} appliedCaptureId={appliedCaptureId} isLoading={isGrounding} isApplying={isMutating} isProposalCurrent={proposalCurrent} availabilityMessage={availabilityMessage} error={groundingError} onCapture={capture} onApply={applyProposal} onClearProposal={clearProposal} isAvailable={connection === 'connected' && Boolean(snapshot)} uploadSlot={uploadPanel} settingsSlot={menuSlot} locked={isInvestigating} onLockedTap={() => showNotice(ANALYSIS_RUNNING)} readSeconds={readSeconds} onCameraLive={setCameraLive} onBoardView={setBoardView} />
      <div className="stage-decision">
        <WhyStrip snapshot={snapshot} isCurrent={connection === 'connected' && planCurrent} closeKey={`${epochKey}:${snapshot?.physical_gate_state}`} />
        <DecisionBar key={`investigation-${epochKey}`} snapshot={connectedSnapshot} investigation={investigation} isLoading={isInvestigating} error={investigationError} isCurrent={investigationCurrent} availabilityMessage={availabilityMessage} onInvestigate={investigate} onCancel={cancelAnalysis} isCancelling={isCancelling} cancellationRequested={cancellationRequested} onApprove={approve} isApproving={isApproving} physical={physical} tokenHeld={operatorToken.trim().length > 0} apiConfigured={apiConfigured} localEnabled={localEnabled} mode={mode} resolvedCount={stageCount} />
      </div>
      <div className="panes">
        <EventConsole events={events} connected={connection === 'connected'} onClear={() => setEvents([])} />
        <AgentPane investigation={investigation} progress={investigationProgress} isLoading={isInvestigating} mode={mode} />
      </div>
    </main>
    <DetailsSheet open={sheetOpen} tab={sheetTab} onTab={setSheetTab} onClose={() => setSheetOpen(false)} panels={{
      forecast: <><HazardRunner rows={hazardRows} onRows={setHazardRows} onRun={() => void runHazard()} canRun={canChange && cleanHazardEvents(hazardRows).length > 0} isSimulating={isSimulating} error={hazardError} /><HazardPanel result={hazard?.view ?? null} isCurrent={hazardCurrent} /></>,
      scenarios: <ScenarioLab snapshot={snapshot} isCurrent={connection === 'connected'} />,
      schedule: <ScheduleExplorer snapshot={displaySnapshot} isCurrent={planCurrent} />,
      review: <ReviewPanel snapshot={connectedSnapshot} isCurrent={planCurrent} investigationId={investigation?.investigation_id ?? null} />,
      evidence: <EvidenceDetails snapshot={snapshot} health={health} grounding={grounding} capture={heldCapture} captureOrigin={captureOrigin} investigation={investigation} planCurrent={planCurrent} />,
      upload: uploadPanel,
    }} />
  </div>;
}
