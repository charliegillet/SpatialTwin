import { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, ArrowRight, Box, Check, CircleHelp, ClipboardCheck, Cpu, Expand, FileJson, FlaskConical, Layers2, LayoutDashboard, LoaderCircle, Radio, RotateCcw, X } from 'lucide-react';
import type { CaptureEvidence, CaptureRequest, GroundingResult, HealthStatus, InvestigationMode, InvestigationProgress, InvestigationResult, RunContext, ScenarioSnapshot } from './types';
import { cancelInvestigation, clearBlockage, fetchHealth, fetchInvestigationProgress, fetchScenario, interpretGrounding, investigateScenario, operatorApproveGate, sendCommand } from './api/client';
import { ObservationPanel } from './components/ObservationPanel';
import { SpatialViewport } from './components/SpatialViewport';
import { InvestigationPanel } from './components/InvestigationPanel';
import { WorkspaceDetails } from './components/WorkspaceDetails';
import { EventConsole, type WorkspaceEvent } from './components/EventConsole';
import { canApplyGrounding, canApproveInvestigation, groundingLabel, investigationLabel, sameContext } from './ai/policy';
import { createRequestGate } from './ai/requestGate';
import { ScheduleExplorer } from './features/schedule/ScheduleExplorer';
import { ScenarioLab } from './features/scenario-lab/ScenarioLab';

type Target = 'portal:P1' | 'portal:P2' | 'boundary:B2';
type Details = 'evidence' | 'devices' | 'guide' | null;
const targets: { id: Target; title: string; description: string }[] = [
  { id: 'portal:P1', title: 'P1 · West passage', description: 'Connects the event hall to the west corridor.' },
  { id: 'portal:P2', title: 'P2 · East passage', description: 'Connects the event hall to the east corridor.' },
  { id: 'boundary:B2', title: 'B2 · East boundary', description: 'The finite-capacity boundary beyond the east corridor.' },
];

export { sameContext } from './ai/policy';
const failureMessage = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please try again.';

function BrandMark({ small = false }: { small?: boolean }) {
  return <svg width={small ? 24 : 30} height={small ? 26 : 32} viewBox="0 0 30 32" fill="none" aria-hidden="true"><path d="m15 2 12 7v14l-12 7L3 23V9L15 2Z" stroke="currentColor" strokeWidth="1.2" /><path d="m3 9 12 7 12-7M15 16v14M9 5.5l12 7V26.5M3 16l12 7 12-7" stroke="currentColor" strokeWidth="1.2" /></svg>;
}

export function App() {
  const [snapshot, setSnapshot] = useState<ScenarioSnapshot | null>(null);
  const snapshotRef = useRef<ScenarioSnapshot | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [connection, setConnection] = useState<'connecting' | 'connected' | 'reconnecting'>('connecting');
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedTarget, setSelectedTarget] = useState<Target | null>(null);
  const [details, setDetails] = useState<Details>(null);
  const [presenting, setPresenting] = useState(false);
  const [interventionView, setInterventionView] = useState<'analysis' | 'device'>('analysis');
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
  const [events, setEvents] = useState<WorkspaceEvent[]>([]);
  const eventId = useRef(0);
  const groundingRequest = useRef(0);
  const groundingGate = useRef(createRequestGate());
  const investigationGate = useRef(createRequestGate());
  const investigationRequest = useRef<string | null>(null);
  const healthRequest = useRef(0);
  const telemetryRef = useRef<string | null>(null);
  const spatialRef = useRef<HTMLDivElement>(null);
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
    const [, scenarioResult] = await Promise.allSettled([refreshHealth(), fetchScenario()]);
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
    const poll = async () => {
      try {
        const progress = await fetchInvestigationProgress('facility-demo', activeInvestigation.id, controller.signal);
        if (controller.signal.aborted || investigationRequest.current !== activeInvestigation.id) return;
        setInvestigationProgress(progress);
        if (progress.investigation) setInvestigation(progress.investigation);
        if (!['running', 'not_found'].includes(progress.status)) return;
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
      reviewRef.current?.scrollIntoView({ block: 'nearest', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
      reviewRef.current?.querySelector<HTMLSelectElement>('select')?.focus({ preventScroll: true });
    }
  }, [isEditing, selectedTarget]);

  const physicalUncertain = Boolean(snapshot && ['UNKNOWN', 'TRANSIT', 'FAULT'].includes(snapshot.physical_gate_state));
  const plan = snapshot?.current_plan;
  const planCurrent = Boolean(connection === 'connected' && plan?.validator_report.is_valid && sameContext(plan.base_context, snapshot?.context) && !physicalUncertain);
  const proposalCurrent = Boolean(connection === 'connected' && sameContext(proposal?.source_context, snapshot?.context) && !physicalUncertain);
  const investigationCurrent = Boolean(connection === 'connected' && sameContext(investigation?.base_context, snapshot?.context) && !physicalUncertain);
  const blocked = [...(snapshot?.blocked_portals ?? []), ...(snapshot?.blocked_boundaries ?? [])];
  const targetSpec = targets.find(target => target.id === selectedTarget);
  const targetBlocked = selectedTarget ? blocked.includes(selectedTarget.split(':')[1]) : false;
  const canChange = Boolean(snapshot && connection === 'connected' && !isMutating);
  const displaySnapshot = snapshot && !planCurrent ? { ...snapshot, current_plan: null } : snapshot;

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
      const sourceLabel = source === 'manual_override' ? 'Manual override' : groundingLabel(grounding);
      addEvent('scenario', reset ? 'Manual reset · scenario blockages cleared. Physical gate position is unchanged.' : `${sourceLabel} · ${id} ${alreadyBlocked && source === 'manual_override' ? 'restored' : 'marked unavailable'} after operator review.`, 'success');
      if (reset) {
        groundingRequest.current += 1;
        groundingGate.current.invalidate();
        investigationGate.current.invalidate();
        investigationRequest.current = null;
        setGrounding(null); setHeldCapture(null); setAppliedCaptureId(null); setInvestigation(null);
        setGroundingError(null); setInvestigationError(null); setIsGrounding(false); setIsInvestigating(false);
        setActiveInvestigation(null); setInvestigationProgress(null); setCancellationRequested(false); setIsCancelling(false);
      }
      reviewTriggerRef.current?.focus({ preventScroll: true });
      setSelectedTarget(null); setIsEditing(false);
      return true;
    } catch (error) { setMutationError(failureMessage(error)); addEvent('scenario', failureMessage(error), 'warning'); return false; }
    finally { setIsMutating(false); }
  };

  const capture = async (captureRequest: CaptureRequest) => {
    if (isGrounding || !snapshotRef.current || connection !== 'connected') return;
    const token = groundingGate.current.start();
    if (token === null) return;
    const request = ++groundingRequest.current;
    setIsGrounding(true); setGroundingError(null); setGrounding(null); setHeldCapture(captureRequest); setAppliedCaptureId(null);
    addEvent('vision', captureRequest.mode === 'fixture' ? `Reviewing ${captureRequest.fixture_target} fixture. No Gemini call requested.` : `${captureRequest.source_kind === 'annotated_plan' ? 'Synthetic demo board image' : 'Captured camera still'} sent to Gemini · ${captureRequest.thinking_level} thinking.`);
    try {
      const response = await interpretGrounding('facility-demo', captureRequest);
      if (request !== groundingRequest.current) return;
      setGrounding(response);
      if (response.status !== 'completed') setGroundingError(response.errors.join(' ') || `Gemini grounding ${response.status.replace(/_/g, ' ')}. No proposal was accepted.`);
      addEvent('vision', `${groundingLabel(response)} · ${response.proposal?.status ?? response.status} · ${response.proposal?.selected_entity_id ?? 'no target'}.`, response.status === 'completed' && response.proposal?.status === 'matched' ? 'success' : 'warning');
    } catch (error) { if (request === groundingRequest.current) { setGroundingError(failureMessage(error)); addEvent('vision', failureMessage(error), 'warning'); } }
    finally { groundingGate.current.finish(token); if (request === groundingRequest.current) setIsGrounding(false); }
  };
  const clearProposal = () => { groundingRequest.current++; groundingGate.current.invalidate(); setGrounding(null); setHeldCapture(null); setAppliedCaptureId(null); setGroundingError(null); setIsGrounding(false); };
  const applyProposal = async () => {
    const target = proposal && `${proposal.selected_entity_type}:${proposal.selected_entity_id}`;
    if (!proposal || !proposalCurrent || !canApplyGrounding(grounding, snapshotRef.current?.context) || !targets.some(item => item.id === target)) return;
    if (await mutate(target as Target, false, 'grounding_proposal')) setAppliedCaptureId(proposal.capture_id);
  };
  const investigate = async (mode: InvestigationMode) => {
    if (isInvestigating || !snapshotRef.current || connection !== 'connected') return;
    const token = investigationGate.current.start();
    if (token === null) return;
    const expectedContext = { ...snapshotRef.current.context };
    const investigationId = crypto.randomUUID();
    investigationRequest.current = investigationId;
    setActiveInvestigation({ id: investigationId, context: expectedContext }); setInvestigationProgress(null); setCancellationRequested(false); setIsCancelling(false);
    setIsInvestigating(true); setInvestigation(null); setInvestigationError(null); addEvent('analysis', `Requested KEEP_CURRENT and OPEN_P3 comparison · ${mode === 'live' ? 'Gemini managed agent' : 'explicit local solver'}.`);
    try {
      const response = await investigateScenario('facility-demo', expectedContext, mode, investigationId);
      if (investigationRequest.current !== investigationId) return;
      setInvestigation(response.investigation);
      const checkedCount = response.investigation.candidate_envelopes.filter(candidate => candidate.validator_report.is_valid).length;
      if (response.investigation.status !== 'completed') setInvestigationError(response.investigation.errors?.join(' ') || `Analysis ${response.investigation.status.replace(/_/g, ' ')}. No winning option is available.`);
      addEvent('analysis', `${investigationLabel(response.investigation)} · ${checkedCount} checked alternatives.`, response.investigation.status === 'completed' ? 'success' : 'warning');
    } catch (error) { if (investigationRequest.current === investigationId) { setInvestigationError(failureMessage(error)); addEvent('analysis', failureMessage(error), 'warning'); } }
    finally { investigationGate.current.finish(token); if (investigationRequest.current === investigationId) { setIsInvestigating(false); setActiveInvestigation(null); setIsCancelling(false); } }
  };
  const cancelAnalysis = async () => {
    if (!activeInvestigation || isCancelling || cancellationRequested) return;
    const activeId = activeInvestigation.id;
    setIsCancelling(true);
    try {
      const response = await cancelInvestigation('facility-demo', activeInvestigation.id, activeInvestigation.context);
      if (investigationRequest.current !== activeId) return;
      setCancellationRequested(response.status === 'cancellation_requested');
      if (response.investigation) setInvestigation(response.investigation);
      addEvent('analysis', response.status === 'already_finished' ? 'Analysis already finished. Recorded result retained.' : 'Cancellation requested. Waiting for the server and provider receipts.');
    } catch (error) { if (investigationRequest.current === activeId) { setInvestigationError(failureMessage(error)); addEvent('analysis', failureMessage(error), 'warning'); } }
    finally { if (investigationRequest.current === activeId) setIsCancelling(false); }
  };
  const approve = async () => {
    const current = snapshotRef.current;
    const candidate = investigation?.candidate_envelopes.find(item => item.alternative_id === 'OPEN_P3');
    if (!current || !investigationCurrent || !canApproveInvestigation(investigation, current.context) || !candidate || isApproving) throw new Error('A current checked improvement recommending OPEN_P3 is required before movement.');
    setIsApproving(true);
    try { await operatorApproveGate(current.context, investigation!.investigation_id, candidate.run_id); addEvent('device', 'Backend accepted the P3 opening request. Waiting for endpoint evidence.'); }
    catch (error) { addEvent('device', failureMessage(error), 'warning'); throw error; }
    finally { setIsApproving(false); }
  };
  const selectTarget = (target: Target) => { reviewTriggerRef.current = document.activeElement as HTMLElement | null; setSelectedTarget(target); setIsEditing(true); setMutationError(null); };
  const inspectModel = () => spatialRef.current?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'center' });

  const availabilityMessage = connection !== 'connected'
    ? 'Reconnect to the local backend before using this result.'
    : physicalUncertain ? `P3 is ${snapshot?.physical_gate_state.toLowerCase()}. Wait for a confirmed endpoint.` : undefined;
  const focusSection = (id: string) => requestAnimationFrame(() => {
    const element = document.getElementById(id);
    element?.scrollIntoView({ block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
    element?.focus({ preventScroll: true });
  });
  const closeEditor = () => {
    setIsEditing(false); setSelectedTarget(null);
    reviewTriggerRef.current?.focus({ preventScroll: true });
  };

  return <div className={`workspace-app${presenting ? ' workspace-presenting' : ''}`}>
    <a className="skip-link" href="#workspace-main">Skip to workspace</a>
    <aside className="workspace-rail" aria-label="Workspace navigation">
      <a className="rail-brand" href="#workspace-main" aria-label="SpatialTwin workspace"><BrandMark small /><span>SpatialTwin<span className="wordmark-dot" /></span></a>
      <div className="rail-workspace-label">WORKSPACE</div>
      <nav>
        <button className={!details ? 'is-active' : ''} onClick={() => { setDetails(null); window.scrollTo({ top: 0, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' }); }} aria-label="Overview"><LayoutDashboard size={18} strokeWidth={1.7} /><span>Overview</span></button>
        <button onClick={inspectModel} aria-label="Spatial model"><Layers2 size={18} strokeWidth={1.7} /><span>Spatial model</span></button>
        <button onClick={() => focusSection('scenario-lab')} aria-label="Scenarios in the scenario lab"><FlaskConical size={18} strokeWidth={1.7} /><span>Scenarios</span></button>
        <button className={details === 'evidence' ? 'is-active' : ''} onClick={() => setDetails('evidence')} aria-label="Evidence and run details"><ClipboardCheck size={18} strokeWidth={1.7} /><span>Evidence</span></button>
        <button className={details === 'devices' ? 'is-active' : ''} onClick={() => setDetails('devices')} aria-label="Devices and connection details"><Cpu size={18} strokeWidth={1.7} /><span>Devices</span></button>
      </nav>
      <div className="rail-scope"><span className="status-dot" /><div>Tabletop 01<small>Illustrative model</small></div></div>
      <div className="rail-bottom"><button onClick={() => setDetails('guide')} aria-label="Workspace guide"><CircleHelp size={18} /><span>Workspace guide</span></button><div className="operator-profile"><span className="operator-avatar">OP</span><span>Local operator<small>Review before applying</small></span></div></div>
    </aside>
    <div className="workspace-content">
      <header className="workspace-topbar">
        <a className="workspace-wordmark" href="#workspace-main">SpatialTwin<span className="wordmark-dot" /></a>
        <div className="workspace-breadcrumb"><span>Workspace</span><span>/</span><strong>Tabletop 01</strong></div>
        <div className="workspace-connection" role="status"><span className={connection === 'connected' ? 'status-dot' : 'status-dot status-dot-waiting'} />{connection === 'connected' ? 'Backend connected' : connection === 'connecting' ? 'Connecting…' : 'Reconnecting…'}</div>
        <button className="topbar-evidence" onClick={() => setDetails('evidence')}><FileJson size={15} /><span>Evidence</span></button>
      </header>
      <main id="workspace-main" className="workspace-main" tabIndex={-1}>
        <div className="workspace-heading">
          <div><h1>Spatial control room<span className="title-period">.</span></h1><p className="workspace-subtitle">Observe a change. Review its impact. Confirm the result.</p></div>
          <div className="workspace-heading-actions"><button className="button-secondary" onClick={() => void mutate(undefined, true)} disabled={!canChange} aria-label={`${isMutating ? 'Updating…' : 'Clear blockages'}. P3 position stays unchanged.`} title="Clear model blockages. P3 position stays unchanged."><RotateCcw size={14} /><span>{isMutating ? 'Updating…' : 'Clear blockages'}</span></button><button ref={presenterTriggerRef} className={`button-presenter${presenting ? ' is-active' : ''}`} onClick={() => setPresenting(!presenting)} aria-pressed={presenting}><Expand size={15} /><span>{presenting ? 'Exit presenter' : 'Present'}</span></button></div>
        </div>
        <div className="workspace-scope"><span><Box size={13} />Illustrative tabletop · synthetic population</span><span>Clear blockages preserves P3’s reported position.</span></div>
        {loadError && <div className="workspace-alert" role="alert"><Radio size={17} /><span>{loadError}</span><button onClick={() => void refresh()}>Reconnect<RotateCcw size={13} /></button></div>}
        {mutationError && <div className="workspace-alert" role="alert"><span>{mutationError}</span><button onClick={() => setMutationError(null)} aria-label="Dismiss error"><X size={16} /></button></div>}
        <section className="workspace-metrics" aria-label="Current modeled result" aria-busy={Boolean(snapshot && !planCurrent)}>
          <div className="metric-primary"><div className="metric-label"><span>Modeled crossings</span><span className={`result-tag${planCurrent ? ' is-valid' : ''}`}>{planCurrent ? <Check size={12} /> : <Activity size={12} />}{planCurrent ? 'Checked' : snapshot ? 'Pending' : 'Connecting'}</span></div><div className="metric-value">{planCurrent ? plan?.completed_crossings : '—'}<span>/ {plan?.initial_population ?? '—'}</span><small>in {plan?.horizon_seconds ?? '—'}s</small></div></div>
          <div><div className="metric-label">Remaining population</div><div className="metric-value">{planCurrent ? plan?.remaining_population : '—'}<small>synthetic occupants</small></div><span className="metric-caption">{planCurrent ? 'Every occupant accounted for' : 'Awaiting a current checked result'}</span></div>
          <div><div className="metric-label">Scenario</div><div className={`metric-state${blocked.length ? ' has-blockage' : ''}`}><span className={`status-dot${blocked.length ? ' status-dot-warning' : ''}`} />{!snapshot ? 'Awaiting scenario' : blocked.length ? `${blocked.length} ${blocked.length === 1 ? 'target' : 'targets'} blocked` : 'Baseline layout'}</div><button className="metric-link" onClick={event => { reviewTriggerRef.current = event.currentTarget; if (isEditing) closeEditor(); else { setIsEditing(true); if (!selectedTarget) setSelectedTarget('portal:P2'); } }} disabled={!snapshot}>{isEditing ? 'Close editor' : 'Edit scenario'}<ArrowRight size={12} /></button></div>
          <div><div className="metric-label">Hardware</div><div className="metric-state"><Cpu size={16} />{health?.hardware_mode === 'simulator' ? 'Simulator' : health?.hardware_mode === 'physical_serial' ? 'Serial bridge' : 'Not connected'}</div><button className="metric-link" onClick={() => setDetails('devices')}>P3 · {snapshot?.physical_gate_state.toLowerCase() ?? 'unknown'}<ArrowRight size={12} /></button></div>
        </section>
        <nav className="workflow-guide" aria-label="Workflow">
          <button onClick={() => focusSection('observation-workspace')}><span>01</span><div><strong>Observe</strong><small>Choose an input</small></div><ArrowRight size={14} /></button>
          <button onClick={() => focusSection('observation-review')}><span>02</span><div><strong>Review</strong><small>Apply a proposed change</small></div><ArrowRight size={14} /></button>
          <button onClick={() => { setInterventionView('analysis'); focusSection('intervention-workspace'); }}><span>03</span><div><strong>Compare</strong><small>Check the alternatives</small></div><ArrowRight size={14} /></button>
          <button onClick={() => { setInterventionView('device'); focusSection('intervention-workspace'); }}><span>04</span><div><strong>Confirm</strong><small>Review endpoint evidence</small></div><ArrowRight size={14} /></button>
        </nav>
        {isEditing && selectedTarget && <section ref={reviewRef} className="scenario-review" aria-label="Review scenario change"><div className="scenario-review-symbol"><Layers2 size={20} /></div><div className="scenario-review-copy"><h2>{targetSpec?.title}</h2><p>{targetSpec?.description} {targetBlocked ? 'Restore its availability in the model.' : 'Mark it unavailable in the model.'}</p><span>Manual scenario change · review before applying</span></div><div className="scenario-review-actions"><label>Target<select aria-label="Scenario target" value={selectedTarget} onChange={event => setSelectedTarget(event.target.value as Target)}>{targets.map(target => <option key={target.id} value={target.id}>{target.title}</option>)}</select></label><button className="button-primary" disabled={!canChange} onClick={() => void mutate(selectedTarget)}>{isMutating ? <LoaderCircle size={15} className="spin" /> : <Check size={15} />}{targetBlocked ? 'Restore target' : 'Apply blockage'}</button></div><button className="icon-button" aria-label="Cancel scenario change" onClick={closeEditor}><X size={18} /></button></section>}
        <div className="workspace-hero">
          <ObservationPanel proposal={proposal} result={grounding} currentContext={snapshot?.context} liveConfigured={health?.ai?.direct.configured ?? health?.live_api_configured ?? false} fixturesEnabled={health?.ai?.fixtures_enabled ?? false} appliedCaptureId={appliedCaptureId} isLoading={isGrounding} isApplying={isMutating} isProposalCurrent={proposalCurrent} availabilityMessage={availabilityMessage} error={groundingError} onCapture={capture} onApply={applyProposal} onClearProposal={clearProposal} isAvailable={connection === 'connected' && Boolean(snapshot)} />
          <div ref={spatialRef} className="workspace-spatial"><SpatialViewport snapshot={displaySnapshot} selectedTarget={selectedTarget} onSelectTarget={selectTarget} onInspectPlan={() => focusSection('schedule-explorer')} /></div>
        </div>
        <div className="workspace-analysis">
          <InvestigationPanel view={interventionView} onViewChange={setInterventionView} snapshot={connection === 'connected' ? displaySnapshot : null} investigation={investigation} progress={investigationProgress} isLoading={isInvestigating} error={investigationError} isCurrent={investigationCurrent} availabilityMessage={availabilityMessage} onInvestigate={investigate} onCancel={cancelAnalysis} isCancelling={isCancelling} cancellationRequested={cancellationRequested} onApprove={approve} isApproving={isApproving} hardwareMode={health?.hardware_mode === 'simulator' ? 'Simulator' : health?.hardware_mode === 'physical_serial' ? 'Serial' : ''} apiConfigured={health?.ai?.managed.configured ?? health?.live_api_configured ?? false} localEnabled={health?.ai?.fixtures_enabled ?? false} />
          <EventConsole events={events} connected={connection === 'connected'} onClear={() => setEvents([])} />
        </div>
        <div className="workspace-exploration">
          <ScheduleExplorer snapshot={displaySnapshot} isCurrent={planCurrent} />
          <ScenarioLab snapshot={snapshot} isCurrent={connection === 'connected'} />
        </div>
        <footer className="workspace-footer"><span>Illustrative geometry. Every result has a source.</span><button onClick={() => setDetails('guide')}>Workspace guide</button><div><span>{snapshot ? `Scenario ${snapshot.context.scenario_revision} · physical ${snapshot.context.physical_revision}` : 'Awaiting context'}</span><button onClick={() => setDetails('evidence')}>Inspect evidence<ArrowRight size={13} /></button></div></footer>
      </main>
    </div>
    <WorkspaceDetails view={details} onClose={() => setDetails(null)} snapshot={snapshot} health={health} grounding={grounding} capture={heldCapture} investigation={investigation} planCurrent={planCurrent} />
  </div>;
}
