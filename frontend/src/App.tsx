import { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, ArrowRight, Box, Check, ChevronDown, CircleHelp, ClipboardCheck, Cpu, Expand, FileJson, Focus, Layers2, LayoutDashboard, LoaderCircle, Radio, RotateCcw, X } from 'lucide-react';
import type { GroundingProposalV1, HealthStatus, InvestigationResult, RunContext, ScenarioSnapshot } from './types';
import { clearBlockage, fetchHealth, fetchScenario, interpretGrounding, investigateScenario, operatorApproveGate, sendCommand } from './api/client';
import { ObservationPanel } from './components/ObservationPanel';
import { SpatialViewport } from './components/SpatialViewport';
import { InvestigationPanel } from './components/InvestigationPanel';
import { WorkspaceDetails } from './components/WorkspaceDetails';
import { EventConsole, type WorkspaceEvent } from './components/EventConsole';

type Target = 'portal:P1' | 'portal:P2' | 'boundary:B2';
type Details = 'evidence' | 'devices' | 'guide' | null;
const targets: { id: Target; title: string; description: string }[] = [
  { id: 'portal:P1', title: 'P1 · West passage', description: 'Connects the event hall to the west corridor.' },
  { id: 'portal:P2', title: 'P2 · East passage', description: 'Connects the event hall to the east corridor.' },
  { id: 'boundary:B2', title: 'B2 · East boundary', description: 'The finite-capacity boundary beyond the east corridor.' },
];

export function sameContext(a: RunContext | undefined, b: RunContext | undefined) {
  return Boolean(a && b && a.geometry_revision === b.geometry_revision && a.scenario_revision === b.scenario_revision
    && a.physical_revision === b.physical_revision && a.parameters_revision === b.parameters_revision
    && a.solver_version === b.solver_version && (!a.context_hash || !b.context_hash || a.context_hash === b.context_hash));
}
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
  const [isEditing, setIsEditing] = useState(false);
  const [isMutating, setIsMutating] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [proposal, setProposal] = useState<GroundingProposalV1 | null>(null);
  const [provenance, setProvenance] = useState<string | null>(null);
  const [appliedCaptureId, setAppliedCaptureId] = useState<string | null>(null);
  const [isGrounding, setIsGrounding] = useState(false);
  const [groundingError, setGroundingError] = useState<string | null>(null);
  const [investigation, setInvestigation] = useState<InvestigationResult | null>(null);
  const [investigationError, setInvestigationError] = useState<string | null>(null);
  const [isInvestigating, setIsInvestigating] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [events, setEvents] = useState<WorkspaceEvent[]>([]);
  const eventId = useRef(0);
  const groundingRequest = useRef(0);
  const telemetryRef = useRef<string | null>(null);
  const spatialRef = useRef<HTMLDivElement>(null);
  const reviewRef = useRef<HTMLElement>(null);

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

  const refresh = useCallback(async () => {
    setLoadError(null);
    const [healthResult, scenarioResult] = await Promise.allSettled([fetchHealth(), fetchScenario()]);
    if (healthResult.status === 'fulfilled') setHealth(healthResult.value);
    if (scenarioResult.status === 'fulfilled') acceptSnapshot(scenarioResult.value, true);
    else setLoadError('The local backend is unavailable. Start the server, then reconnect.');
  }, [acceptSnapshot]);

  useEffect(() => {
    void refresh();
    const stream = new EventSource('/api/scenarios/facility-demo/events');
    stream.onopen = () => { setConnection('connected'); setLoadError(null); };
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
  }, [acceptSnapshot, addEvent, refresh]);

  useEffect(() => {
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { setPresenting(false); setIsEditing(false); setSelectedTarget(null); } };
    window.addEventListener('keydown', escape);
    return () => window.removeEventListener('keydown', escape);
  }, []);

  useEffect(() => {
    if (isEditing) reviewRef.current?.scrollIntoView({ block: 'nearest', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
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
        ? await clearBlockage('facility-demo', current.context.scenario_revision, type, id)
        : await sendCommand('facility-demo', { type: reset ? 'RESET_SCENARIO' : 'APPLY_BLOCKAGE', expected_scenario_revision: current.context.scenario_revision, idempotency_key: crypto.randomUUID(), ...(!reset ? { target_type: type, target_id: id, source } : {}) });
      acceptSnapshot(response.snapshot);
      addEvent('scenario', reset ? 'Scenario blockages cleared. Physical gate position is unchanged.' : `${id} ${alreadyBlocked && source === 'manual_override' ? 'restored' : 'marked unavailable'} after operator review.`, 'success');
      if (reset) { setProposal(null); setAppliedCaptureId(null); setInvestigation(null); }
      setSelectedTarget(null); setIsEditing(false);
      return true;
    } catch (error) { setMutationError(failureMessage(error)); addEvent('scenario', failureMessage(error), 'warning'); return false; }
    finally { setIsMutating(false); }
  };

  const capture = async (imageBase64?: string, fixtureTarget?: 'P1' | 'P2' | 'B2') => {
    if (isGrounding || !snapshotRef.current || connection !== 'connected') return;
    const request = ++groundingRequest.current;
    setIsGrounding(true); setGroundingError(null); setProposal(null); setProvenance(null); setAppliedCaptureId(null);
    addEvent('vision', fixtureTarget ? `Reviewing ${fixtureTarget} fixture. No camera inference requested.` : 'Captured still sent for a grounding proposal.');
    try {
      const response = await interpretGrounding('facility-demo', { imageBase64, forceTarget: fixtureTarget });
      if (request !== groundingRequest.current) return;
      setProposal(response.proposal); setProvenance(response.provenance);
      addEvent('vision', `${response.proposal.status} · ${response.proposal.selected_entity_id ?? 'no target'} · source: ${response.provenance}.`, response.proposal.status === 'matched' ? 'success' : 'warning');
    } catch (error) { if (request === groundingRequest.current) { setGroundingError(failureMessage(error)); addEvent('vision', failureMessage(error), 'warning'); } }
    finally { if (request === groundingRequest.current) setIsGrounding(false); }
  };
  const clearProposal = () => { groundingRequest.current++; setProposal(null); setProvenance(null); setAppliedCaptureId(null); setGroundingError(null); setIsGrounding(false); };
  const applyProposal = async () => {
    const target = proposal && `${proposal.selected_entity_type}:${proposal.selected_entity_id}`;
    if (!proposalCurrent || proposal?.status !== 'matched' || !targets.some(item => item.id === target)) return;
    if (await mutate(target as Target, false, 'grounding_proposal')) setAppliedCaptureId(proposal.capture_id);
  };
  const investigate = async () => {
    if (isInvestigating || !snapshotRef.current || connection !== 'connected') return;
    setIsInvestigating(true); setInvestigationError(null); addEvent('analysis', 'Requested a comparison of KEEP_CURRENT and OPEN_P3.');
    try {
      const response = await investigateScenario('facility-demo');
      setInvestigation(response.investigation);
      const checkedCount = response.investigation.candidate_envelopes.filter(candidate => candidate.validator_report.is_valid).length;
      addEvent('analysis', `Comparison ${response.investigation.status} · ${checkedCount} checked alternatives. Provider execution is unverified.`, response.investigation.status === 'completed' ? 'success' : 'warning');
    } catch (error) { setInvestigationError(failureMessage(error)); addEvent('analysis', failureMessage(error), 'warning'); }
    finally { setIsInvestigating(false); }
  };
  const approve = async () => {
    const current = snapshotRef.current;
    const candidate = investigation?.candidate_envelopes.find(item => item.alternative_id === 'OPEN_P3');
    if (!current || !investigationCurrent || investigation?.status !== 'completed' || !candidate?.validator_report.is_valid || !sameContext(candidate.base_context, current.context) || isApproving) throw new Error('Run a current, checked comparison before requesting movement.');
    setIsApproving(true);
    try { await operatorApproveGate('OPEN_P3', current.context.scenario_revision); addEvent('device', 'Backend accepted the P3 opening request. Waiting for endpoint evidence.'); }
    catch (error) { addEvent('device', failureMessage(error), 'warning'); throw error; }
    finally { setIsApproving(false); }
  };
  const selectTarget = (target: Target) => { setSelectedTarget(target); setIsEditing(true); setMutationError(null); };
  const inspectModel = () => spatialRef.current?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'center' });

  return <div className={`workspace-app${presenting ? ' workspace-presenting' : ''}`}>
    <a className="skip-link" href="#workspace-main">Skip to workspace</a>
    <aside className="workspace-rail" aria-label="Workspace navigation">
      <a className="rail-brand" href="#workspace-main" aria-label="SpatialTwin workspace"><BrandMark small /></a><div className="rail-divider" />
      <nav>
        <button className={!details ? 'is-active' : ''} onClick={() => { setDetails(null); window.scrollTo({ top: 0, behavior: 'smooth' }); }} aria-label="Overview" title="Overview"><LayoutDashboard size={19} strokeWidth={1.6} /><span>Overview</span></button>
        <button onClick={inspectModel} aria-label="Spatial model" title="Spatial model"><Layers2 size={19} strokeWidth={1.6} /><span>Model</span></button>
        <button className={details === 'evidence' ? 'is-active' : ''} onClick={() => setDetails('evidence')} aria-label="Evidence and run details" title="Evidence"><ClipboardCheck size={19} strokeWidth={1.6} /><span>Evidence</span></button>
        <button className={details === 'devices' ? 'is-active' : ''} onClick={() => setDetails('devices')} aria-label="Device details" title="Devices"><Cpu size={19} strokeWidth={1.6} /><span>Devices</span></button>
      </nav>
      <div className="rail-bottom"><button onClick={() => setDetails('guide')} aria-label="Workspace guide" title="Workspace guide"><CircleHelp size={19} strokeWidth={1.6} /></button><span className="operator-avatar" title="Local operator">OP</span></div>
    </aside>
    <div className="workspace-content">
      <header className="workspace-topbar"><a className="workspace-wordmark" href="#workspace-main">SpatialTwin<span className="wordmark-dot" /></a><span className="topbar-divider" /><div className="workspace-breadcrumb">Workspace<ChevronDown size={12} /><span>/</span><strong>Tabletop 01</strong></div><div className="workspace-connection"><span className={connection === 'connected' ? 'status-dot' : 'status-dot status-dot-waiting'} />{connection === 'connected' ? 'Local backend connected' : connection === 'connecting' ? 'Connecting' : 'Reconnecting'}<span className="connection-short">SSE</span></div><button className="topbar-evidence" onClick={() => setDetails('evidence')}><FileJson size={14} /><span>Evidence</span><ArrowRight size={12} /></button></header>
      <main id="workspace-main" className="workspace-main">
        <div className="workspace-heading"><div><p className="eyebrow"><span />PHYSICAL + DIGITAL / ONE SHARED CONTEXT</p><h1>Spatial control room<span className="title-period">.</span></h1><p className="workspace-subtitle">See the change. Understand the consequence.</p></div><div className="workspace-heading-actions"><span className="session-chip"><Box size={13} />Illustrative tabletop</span><button className="button-secondary" onClick={() => void mutate(undefined, true)} disabled={!canChange}><RotateCcw size={13} /><span>{isMutating ? 'Updating…' : 'Reset scenario'}</span></button><button className={`button-presenter${presenting ? ' is-active' : ''}`} onClick={() => setPresenting(!presenting)} aria-pressed={presenting}><Expand size={14} /><span>{presenting ? 'Exit presenter' : 'Present'}</span></button></div></div>
        {loadError && <div className="workspace-alert" role="alert"><Radio size={16} /><span>{loadError}</span><button onClick={() => void refresh()}>Reconnect<RotateCcw size={12} /></button></div>}
        {mutationError && <div className="workspace-alert" role="alert"><span>{mutationError}</span><button onClick={() => setMutationError(null)} aria-label="Dismiss error"><X size={15} /></button></div>}
        <section className="workspace-metrics" aria-label="Current modeled result">
          <div className="metric-primary"><div className="metric-label"><span>Modeled crossings</span><span className={`result-tag${planCurrent ? ' is-valid' : ''}`}>{planCurrent ? <Check size={10} /> : <Activity size={10} />}{planCurrent ? 'Checked' : snapshot ? 'Pending' : 'Connecting'}</span></div><div className="metric-value">{planCurrent ? plan?.completed_crossings : '—'}<span>/ {plan?.initial_population ?? '—'}</span><small>within {plan?.horizon_seconds ?? '—'}s</small></div><div className="metric-track"><span style={{ width: planCurrent && plan && plan.initial_population > 0 ? `${plan.completed_crossings / plan.initial_population * 100}%` : '0%' }} /></div></div>
          <div><div className="metric-label">Remaining population<Focus size={13} /></div><div className="metric-value">{planCurrent ? plan?.remaining_population : '—'}<small>synthetic occupants</small></div><span className="metric-caption">{planCurrent ? "All occupants remain accounted for" : "Awaiting a current checked result"}</span></div>
          <div><div className="metric-label">Scenario state<Layers2 size={13} /></div><div className={`metric-state${blocked.length ? ' has-blockage' : ''}`}><span className={`status-dot${blocked.length ? ' status-dot-warning' : ''}`} />{!snapshot ? 'Awaiting scenario' : blocked.length ? `${blocked.length} ${blocked.length === 1 ? 'target' : 'targets'} blocked` : 'Baseline layout'}</div><button className="metric-link" onClick={() => { setIsEditing(!isEditing); if (!selectedTarget) setSelectedTarget('portal:P2'); }} disabled={!snapshot}>{isEditing ? 'Close scenario editor' : 'Edit scenario'}<ArrowRight size={11} /></button></div>
          <div><div className="metric-label">Physical connection<Cpu size={13} /></div><div className="metric-state"><span className="simulator-dot" />{health?.hardware_mode === 'simulator' ? 'Simulator' : health?.hardware_mode === 'physical_serial' ? 'Serial bridge' : 'Not connected'}</div><button className="metric-link" onClick={() => setDetails('devices')}>P3 reported {snapshot?.physical_gate_state.toLowerCase() ?? 'unknown'}<ArrowRight size={11} /></button></div>
        </section>
        {isEditing && selectedTarget && <section ref={reviewRef} className="scenario-review" aria-label="Review scenario change"><div className="scenario-review-symbol"><Layers2 size={19} /></div><div className="scenario-review-copy"><span className="eyebrow">HYPOTHETICAL SCENARIO / REVIEW CHANGE</span><h2>{targetSpec?.title}</h2><p>{targetSpec?.description} {targetBlocked ? 'Restore its availability in the model.' : 'Mark it unavailable in the model.'}</p></div><select aria-label="Scenario target" value={selectedTarget} onChange={event => setSelectedTarget(event.target.value as Target)}>{targets.map(target => <option key={target.id} value={target.id}>{target.title}</option>)}</select><button className="button-primary" disabled={!canChange} onClick={() => void mutate(selectedTarget)}>{isMutating ? <LoaderCircle size={14} className="spin" /> : <Check size={14} />}{targetBlocked ? 'Restore target' : 'Apply blockage'}</button><button className="icon-button" aria-label="Cancel scenario change" onClick={() => { setIsEditing(false); setSelectedTarget(null); }}><X size={16} /></button></section>}
        <div className="workspace-section-heading"><h2>Observe & understand</h2><span><span className="status-dot" />{connection === 'connected' ? 'Current scenario' : 'Waiting for connection'}<i />SCN {snapshot ? String(snapshot.context.scenario_revision).padStart(2, '0') : '—'}</span></div>
        <div className="workspace-hero"><ObservationPanel proposal={proposal} provenance={provenance} appliedCaptureId={appliedCaptureId} isLoading={isGrounding} isApplying={isMutating} isProposalCurrent={proposalCurrent} error={groundingError} onCapture={capture} onApply={applyProposal} onClearProposal={clearProposal} isAvailable={connection === 'connected' && Boolean(snapshot)} /><div ref={spatialRef} className="workspace-spatial"><SpatialViewport snapshot={displaySnapshot} selectedTarget={selectedTarget} onSelectTarget={selectTarget} /></div></div>
        <div className="workspace-analysis"><EventConsole events={events} connected={connection === 'connected'} onClear={() => setEvents([])} /><InvestigationPanel snapshot={connection === 'connected' ? displaySnapshot : null} investigation={investigation} isLoading={isInvestigating} error={investigationError} isCurrent={investigationCurrent} onInvestigate={investigate} onApprove={approve} isApproving={isApproving} hardwareMode={health?.hardware_mode === 'simulator' ? 'Simulator' : health?.hardware_mode === 'physical_serial' ? 'Serial' : ''} apiConfigured={health?.live_api_configured ?? false} /></div>
        <footer className="workspace-footer"><span><BrandMark small />A model of possibilities. Every result has a source.</span><div><span>{snapshot ? `SCENARIO R${snapshot.context.scenario_revision} / PHYSICAL R${snapshot.context.physical_revision}` : 'AWAITING CONTEXT'}</span><button onClick={() => setDetails('evidence')}>Inspect evidence<ArrowRight size={12} /></button></div></footer>
      </main>
    </div>
    <WorkspaceDetails view={details} onClose={() => setDetails(null)} snapshot={snapshot} health={health} proposal={proposal} provenance={provenance} investigation={investigation} planCurrent={planCurrent} />
  </div>;
}
