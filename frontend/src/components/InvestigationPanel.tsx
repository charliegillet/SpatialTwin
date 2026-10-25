import React, { useId, useState } from 'react';
import { ArrowDown, ArrowRight, Check, CheckCheck, Circle, Cpu, GitBranch, LoaderCircle, OctagonX, Play, Radio, RotateCcw, ShieldCheck, Unplug } from 'lucide-react';
import type { EvaluationEnvelope, InvestigationMode, InvestigationProgress, InvestigationResult, ScenarioSnapshot } from '../types';
import { canApproveInvestigation, canCompareInvestigation, investigationLabel, sameContext } from '../ai/policy';
import type { OperatorOutcome } from '../ai/operator';
import { InvestigationEvidence, ProviderProgressList } from './InvestigationEvidence';
import './InvestigationPanel.css';

export interface InvestigationPanelProps {
  snapshot: ScenarioSnapshot | null;
  investigation: InvestigationResult | null;
  progress: InvestigationProgress | null;
  isLoading: boolean;
  error: string | null;
  isCurrent: boolean;
  availabilityMessage?: string;
  onInvestigate: (mode: InvestigationMode) => Promise<void>;
  onCancel: () => Promise<void>;
  isCancelling: boolean;
  cancellationRequested: boolean;
  onApprove: (operatorToken?: string) => Promise<OperatorOutcome>;
  onStop: (operatorToken?: string) => Promise<OperatorOutcome>;
  isApproving: boolean;
  hardwareMode: string;
  /** Physical serial hardware: commands need an operator token. */
  physical: boolean;
  apiConfigured: boolean;
  localEnabled: boolean;
  view?: 'analysis' | 'device';
  onViewChange?: (view: 'analysis' | 'device') => void;
}

function RouteDiagram() {
  return (
    <div className="investigation-diagram" role="img" aria-label="Schematic: P3 reconnects the event zone to the existing B2 boundary">
      <svg viewBox="0 0 340 106" role="img" aria-hidden="true">
        <path className="investigation-route-muted" d="M68 53H114V23H260" />
        <path className="investigation-route-active" d="M68 53H111V83H222V53H260" />
        <rect x="22" y="35" width="64" height="36" rx="5" className="investigation-diagram-zone" />
        <text x="54" y="57" textAnchor="middle" className="investigation-svg-label">EVENT</text>
        <rect x="143" y="70" width="43" height="26" rx="4" className="investigation-diagram-gate" />
        <text x="164.5" y="87" textAnchor="middle" className="investigation-svg-gate-label">P3</text>
        <rect x="260" y="10" width="52" height="26" rx="4" className="investigation-diagram-zone" />
        <text x="286" y="27" textAnchor="middle" className="investigation-svg-label">B1</text>
        <rect x="260" y="40" width="52" height="26" rx="4" className="investigation-diagram-zone" />
        <text x="286" y="57" textAnchor="middle" className="investigation-svg-label">B2</text>
        <circle cx="111" cy="53" r="3" className="investigation-route-node" />
        <path d="m248 49 5 4-5 4" className="investigation-route-arrow" />
      </svg>
      <span className="investigation-diagram-caption">ONE INTERNAL CONNECTION. SAME BOUNDARY CAPACITY.</span>
    </div>
  );
}

function ComparisonRow({ candidate, alternative }: { candidate: EvaluationEnvelope; alternative?: boolean }) {
  const progress = candidate.initial_population > 0
    ? Math.min(100, candidate.completed_crossings / candidate.initial_population * 100) : 0;
  return (
    <div className={`investigation-comparison-row${alternative ? ' investigation-comparison-row-alternative' : ''}`}>
      <div className="investigation-comparison-label">
        <span>{alternative ? 'Open reserve · P3' : 'Keep current layout'}</span>
        <span className="investigation-comparison-count">{candidate.completed_crossings}<small> / {candidate.initial_population}</small></span>
      </div>
      <div className="investigation-bar" aria-hidden="true"><span style={{ width: `${progress}%` }} /></div>
      <div className="investigation-comparison-meta">
        <span>{candidate.remaining_population} remaining</span>
        <span>{candidate.horizon_seconds}s horizon</span>
      </div>
    </div>
  );
}

export function InvestigationPanel({ snapshot, investigation, progress, isLoading, error, isCurrent, availabilityMessage, onInvestigate, onCancel, isCancelling, cancellationRequested, onApprove, onStop, isApproving, hardwareMode, physical, apiConfigured, localEnabled, view, onViewChange }: InvestigationPanelProps) {
  const id = useId();
  const [localTab, setLocalTab] = useState<'analysis' | 'device'>('analysis');
  const tab = view ?? localTab;
  const setTab = (next: 'analysis' | 'device') => { if (view === undefined) setLocalTab(next); onViewChange?.(next); };
  const [selectedMode, setMode] = useState<InvestigationMode | null>(null);
  const mode = selectedMode ?? (apiConfigured ? 'live' : 'local');
  const [localError, setLocalError] = useState<string | null>(null);
  const [approval, setApproval] = useState<{ context: string; acknowledged: boolean } | null>(null);
  const [requestInFlight, setRequestInFlight] = useState(false);
  // The token lives only in this component's state: no storage, cleared when the workflow resets (the parent re-keys this panel).
  const [operatorToken, setOperatorToken] = useState('');
  const [stopping, setStopping] = useState(false);
  const [stopOutcome, setStopOutcome] = useState<OperatorOutcome | null>(null);
  const currentContext = snapshot?.context;
  const investigationCurrent = Boolean(isCurrent && currentContext && investigation && sameContext(investigation.base_context, currentContext));
  const baseline = investigation?.candidate_envelopes.find(candidate => candidate.alternative_id === 'KEEP_CURRENT');
  const reserve = investigation?.candidate_envelopes.find(candidate => candidate.alternative_id === 'OPEN_P3');
  const comparisonReady = investigationCurrent && canCompareInvestigation(investigation, currentContext);
  const gain = comparisonReady && baseline && reserve ? reserve.completed_crossings - baseline.completed_crossings : null;
  const contextKey = currentContext ? `${currentContext.context_hash ?? currentContext.geometry_revision}:${currentContext.scenario_revision}:${currentContext.physical_revision}:${currentContext.parameters_revision}:${currentContext.solver_version}` : null;
  const requestSubmitted = Boolean(contextKey && approval?.context === contextKey);
  const tokenReady = !physical || operatorToken.trim().length > 0;
  const gateState = snapshot?.physical_gate_state ?? 'UNKNOWN';
  const endpointReported = Boolean(snapshot?.last_hardware_boot_id);
  const observedOpen = endpointReported && gateState === 'OPEN';
  // Gating stays keyed to the current context. For display, an acknowledged request whose movement was
  // then observed still counts: opening the gate is what changed the context.
  const requestRecorded = requestSubmitted || Boolean(approval?.acknowledged && observedOpen);
  const busy = isApproving || requestInFlight;
  const improvementApproved = investigationCurrent && canApproveInvestigation(investigation, currentContext);
  const canApprove = Boolean(improvementApproved && snapshot && !isLoading && !busy && gateState === 'CLOSED' && !requestSubmitted && tokenReady);
  const executedCalls = investigation?.tool_ledger.filter(entry => entry.status === 'executed').length ?? 0;
  const visibleError = error || localError;
  const modeAvailable = mode === 'live' ? apiConfigured : localEnabled;
  const simulator = hardwareMode.toLowerCase() === 'simulator';
  const unavailableReason = availabilityMessage ?? 'The scenario has changed. Run a fresh comparison.';

  const changeTabWithKey = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 'analysis' : event.key === 'End' ? 'device' : tab === 'analysis' ? 'device' : 'analysis';
    setTab(next);
    document.getElementById(`${id}-${next}-tab`)?.focus();
  };

  const runAnalysis = async () => {
    if (isLoading || !snapshot || !modeAvailable) return;
    setLocalError(null);
    try { await onInvestigate(mode); }
    catch (failure) { setLocalError(failure instanceof Error ? failure.message : 'Analysis could not be completed. Try again.'); }
  };

  const approve = async () => {
    if (!canApprove) return;
    setLocalError(null);
    setRequestInFlight(true);
    try {
      const outcome = await onApprove(physical ? operatorToken.trim() : undefined);
      if (outcome.ok && contextKey) setApproval({ context: contextKey, acknowledged: Boolean(outcome.acknowledged) });
      else if (!outcome.ok) setLocalError(outcome.message);
    } catch (failure) {
      setLocalError(failure instanceof Error ? failure.message : 'The opening request was not accepted.');
    } finally { setRequestInFlight(false); }
  };

  const stop = async () => {
    if (stopping) return;
    if (physical && !operatorToken.trim()) { setStopOutcome({ ok: false, message: 'Enter the operator token to send a stop command.' }); return; }
    setStopping(true); setStopOutcome(null);
    try { setStopOutcome(await onStop(physical ? operatorToken.trim() : undefined)); }
    catch (failure) { setStopOutcome({ ok: false, message: failure instanceof Error ? failure.message : 'The stop command was not confirmed.' }); }
    finally { setStopping(false); }
  };

  return (
    <section id="intervention-workspace" tabIndex={-1} className="investigation-panel" aria-labelledby={`${id}-title`}>
      <header className="investigation-header">
        <div className="investigation-title"><span className="investigation-phase-number" aria-hidden="true">03</span><div><h2 id={`${id}-title`}>Compare</h2><p>One internal connection. Two checked possibilities.</p></div></div>
        <span className="investigation-provider-label" data-confirmed={investigation?.status === 'completed' && (investigation.provenance === 'local' || Boolean(investigation.provenance === 'live' && investigation.provider_interaction_id))}><span />{investigationLabel(investigation)}</span>
      </header>
      <div className="investigation-tabs" role="tablist" aria-label="Intervention views">
        <button type="button" role="tab" id={`${id}-analysis-tab`} aria-selected={tab === 'analysis'} aria-controls={`${id}-analysis`} tabIndex={tab === 'analysis' ? 0 : -1} onClick={() => setTab('analysis')} onKeyDown={changeTabWithKey}><GitBranch size={15}  aria-hidden="true" />Analysis</button>
        <button type="button" role="tab" id={`${id}-device-tab`} aria-selected={tab === 'device'} aria-controls={`${id}-device`} tabIndex={tab === 'device' ? 0 : -1} onClick={() => setTab('device')} onKeyDown={changeTabWithKey}><Cpu size={15}  aria-hidden="true" />{simulator ? 'Simulator' : 'Device'}<span className={`investigation-tab-dot${endpointReported ? ' investigation-tab-dot-connected' : ''}`} /></button>
        <span className="investigation-context-label">{currentContext ? `SCN ${String(currentContext.scenario_revision).padStart(2, '0')}` : 'NO CONTEXT'}</span>
      </div>
      <div className="operator-strip" role="group" aria-label="Operator controls">
        {physical && <label className="operator-token"><span>Operator token</span><input type="password" autoComplete="off" spellCheck={false} value={operatorToken} onChange={event => setOperatorToken(event.target.value)} placeholder="Required for physical hardware" /></label>}
        <button type="button" className="operator-stop" onClick={() => { void stop(); }} disabled={stopping}>{stopping ? <LoaderCircle size={14} className="investigation-spin" aria-hidden="true" /> : <OctagonX size={14} aria-hidden="true" />}<span>{stopping ? 'Sending stop…' : 'Stop outputs'}</span></button>
        <p className="operator-note">{physical ? 'Sends a stop command to the board. A device acknowledgement is not proof the gate stopped; check the reported position.' : 'Simulator mode: no token needed. Stops simulated outputs only.'}</p>
        {stopOutcome && <p className={`operator-result${stopOutcome.ok ? '' : ' is-error'}`} role={stopOutcome.ok ? 'status' : 'alert'}>{stopOutcome.message}</p>}
      </div>

        <div id={`${id}-analysis`} role="tabpanel" aria-labelledby={`${id}-analysis-tab`} className="investigation-body" hidden={tab !== 'analysis'}>
          <div className="investigation-mode-switch" role="group" aria-label="Analysis execution mode"><button type="button" aria-pressed={mode === 'live'} disabled={isLoading} onClick={() => setMode('live')}>Live Gemini</button><button type="button" aria-pressed={mode === 'local'} disabled={isLoading} onClick={() => setMode('local')}>Local solver</button></div>
          {investigation && !investigationCurrent && <p className="investigation-history-note">{unavailableReason} Earlier receipts remain available below.</p>}
          {comparisonReady && baseline && reserve ? (
            <>
              <div className="investigation-result-heading"><h3>{gain === 0 ? 'Same capacity. Another route.' : gain !== null && gain > 0 ? 'A connection with an impact.' : 'The current layout performs better.'}</h3><span className="investigation-check-label"><ShieldCheck size={15}  aria-hidden="true" />Checked</span></div>
              <div className="investigation-comparison"><ComparisonRow candidate={baseline} /><ComparisonRow candidate={reserve} alternative /></div>
              <div className="investigation-outcome"><span className={`investigation-outcome-value${gain !== null && gain < 0 ? ' investigation-outcome-negative' : ''}`}>{gain !== null && gain > 0 ? '+' : ''}{gain}<ArrowRight size={17}  aria-hidden="true" /></span><p>{gain === 0 ? 'No additional modeled boundary crossings. P3 still feeds the existing B2 boundary.' : 'Modeled boundary crossings compared with the current layout. This is a prediction, awaiting physical observation.'}</p></div>
            </>
          ) : (
            <div className="investigation-empty">
              <RouteDiagram />
              <div className="investigation-empty-copy"><h3>{isLoading ? 'Evaluating the alternatives.' : investigation && !investigationCurrent ? 'Review a fresh comparison.' : investigation?.status === 'cancelled' ? 'Analysis cancelled.' : investigation?.status === 'timed_out' ? 'The model took too long.' : investigation ? 'The comparison is incomplete.' : 'Find the better connection.'}</h3><p>{isLoading ? 'Real tool results will appear as they are returned. Every occupant stays accounted for.' : investigation && !investigationCurrent ? unavailableReason : investigation ? 'A winning option needs two valid results with the same population and horizon. Retry when you are ready.' : 'Compare the current layout with an open reserve connection. Both runs start with the same population and horizon.'}</p></div>
            </div>
          )}
          <div className={`investigation-run-footer${comparisonReady ? ' investigation-result-footer' : ''}`}>
            <span hidden={!comparisonReady}><CheckCheck size={13} aria-hidden="true" />{executedCalls} tool {executedCalls === 1 ? 'call' : 'calls'} recorded</span>
            <button type="button" className={comparisonReady ? 'investigation-rerun' : 'investigation-primary'} onClick={() => { void runAnalysis(); }} disabled={!snapshot || !modeAvailable} aria-disabled={isLoading || !snapshot || !modeAvailable} aria-busy={isLoading}>
              {isLoading ? <LoaderCircle size={15} className="investigation-spin" aria-hidden="true" /> : comparisonReady ? <RotateCcw size={14} aria-hidden="true" /> : <Play size={14} fill="currentColor" aria-hidden="true" />}
              <span>{isLoading ? 'Analysis in progress' : comparisonReady ? mode === 'live' ? 'Run Gemini' : 'Run local' : mode === 'live' ? 'Run Gemini analysis' : 'Compare with local solver'}</span>
              {!comparisonReady && !isLoading && <ArrowRight size={15} aria-hidden="true" />}
            </button>
          </div>
          <div className="investigation-source-note"><span className="investigation-source-dot" />{mode === 'local' ? localEnabled ? 'Explicit local numerical computation · no Gemini call' : 'Local demo mode disabled by the server' : apiConfigured ? 'Gemini configured · up to 60s · completed response required' : 'Gemini unavailable · server credentials are not configured'}</div>
          <InvestigationEvidence investigation={investigation} />
        </div>
        <div id={`${id}-device`} role="tabpanel" aria-labelledby={`${id}-device-tab`} className="investigation-body investigation-device-body" hidden={tab !== 'device'}>
          <div className="investigation-device-summary"><div className="investigation-device-icon"><Cpu size={24} strokeWidth={1.5}  aria-hidden="true" /></div><div><h3>{endpointReported ? `P3 reported ${gateState.toLowerCase()}` : 'Awaiting P3 endpoint evidence'}</h3><span className="investigation-device-mode">{hardwareMode ? `${hardwareMode} mode` : 'Connection mode unavailable'}</span></div></div>
          <ol className="investigation-device-ledger">
            <li><span className={`investigation-step-icon${requestRecorded ? ' investigation-step-icon-done' : ''}`}>{requestRecorded ? <Check size={12}  aria-hidden="true" /> : <Circle size={8}  aria-hidden="true" />}</span><div><strong>Operator request</strong><span>{busy ? 'Submitting opening request…' : requestRecorded ? approval?.acknowledged ? 'Backend recorded the request for its reviewed context' : 'Backend accepted the request for its reviewed context' : observedOpen ? 'No request recorded in this browser session' : 'Opening requires your approval'}</span></div></li>
            <li><span className="investigation-step-icon"><Radio size={12}  aria-hidden="true" /></span><div><strong>Device acknowledgement</strong><span>{requestRecorded ? approval?.acknowledged ? 'Device acknowledged the command. An acknowledgement is not arrival.' : 'No device acknowledgement was reported' : 'No acknowledgement yet'}</span></div></li>
            <li><span className={`investigation-step-icon${observedOpen ? ' investigation-step-icon-done' : ''}`}>{endpointReported ? <Check size={12}  aria-hidden="true" /> : <Unplug size={12}  aria-hidden="true" />}</span><div><strong>Endpoint observation</strong><span>{endpointReported ? `Snapshot reports ${gateState.toLowerCase()} · epoch ${snapshot?.last_gate_epoch ?? 'unknown'}` : 'No endpoint receipt in the current snapshot'}</span></div></li>
          </ol>
          <button type="button" className="investigation-primary investigation-approval" disabled={!canApprove} onClick={() => { void approve(); }}>{busy ? <LoaderCircle size={14} className="investigation-spin"  aria-hidden="true" /> : <ArrowDown size={14}  aria-hidden="true" />}<span>{busy ? 'Submitting request' : observedOpen ? 'Open endpoint reported' : requestSubmitted ? 'Request sent · awaiting observation' : 'Approve opening P3'}</span>{!busy && !observedOpen && !requestSubmitted && <ArrowRight size={15}  aria-hidden="true" />}</button>
          <p className="investigation-device-note">{observedOpen ? `${simulator ? 'Simulated' : 'Reported'} open endpoint received. The workspace result uses the new physical revision; the earlier comparison remains historical evidence.` : !comparisonReady ? availabilityMessage ?? 'Complete a current, checked comparison before approval.' : !improvementApproved ? 'No checked improvement recommends opening P3. Keep the current layout.' : !tokenReady ? 'Enter the operator token to approve movement of physical hardware.' : simulator ? 'This requests a simulated movement. No physical hardware is connected.' : 'Approval requests movement. Only endpoint evidence can establish the resulting position.'}</p>
        </div>
      {isLoading && <div className="investigation-live-progress"><ProviderProgressList events={progress?.provider_progress ?? []} pending pendingMessage={mode === 'local' ? 'Local solver running. Waiting for checked results.' : 'Request submitted. Waiting for a Gemini receipt.'} /><button type="button" className="investigation-cancel" onClick={() => void onCancel()} disabled={isCancelling || cancellationRequested}>{isCancelling ? 'Requesting cancellation…' : cancellationRequested ? 'Cancellation requested · awaiting receipt' : 'Cancel analysis'}</button></div>}
      {visibleError && <div className="investigation-error" role="alert">{visibleError}</div>}
    </section>
  );
}
