import React, { useId, useState } from 'react';
import { ArrowDown, ArrowRight, Check, CheckCheck, Circle, Cpu, GitBranch, LoaderCircle, Play, Radio, RotateCcw, ShieldCheck, Unplug } from 'lucide-react';
import type { EvaluationEnvelope, InvestigationMode, InvestigationProgress, InvestigationResult, ScenarioSnapshot } from '../types';
import { canApproveInvestigation, canCompareInvestigation, investigationLabel, sameContext } from '../ai/policy';
import { ExecutionReceipt } from './ExecutionReceipt';
import { InvestigationEvidence, ProviderProgressList } from './InvestigationEvidence';
import './InvestigationPanel.css';

export interface InvestigationPanelProps {
  snapshot: ScenarioSnapshot | null;
  investigation: InvestigationResult | null;
  progress: InvestigationProgress | null;
  isLoading: boolean;
  error: string | null;
  isCurrent: boolean;
  onInvestigate: (mode: InvestigationMode) => Promise<void>;
  onCancel: () => Promise<void>;
  isCancelling: boolean;
  cancellationRequested: boolean;
  onApprove: () => Promise<void>;
  isApproving: boolean;
  hardwareMode: string;
  apiConfigured: boolean;
  localEnabled: boolean;
}

function RouteDiagram() {
  return (
    <div className="investigation-diagram" aria-label="Schematic: P3 reconnects the event zone to the existing B2 boundary">
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

export function InvestigationPanel({ snapshot, investigation, progress, isLoading, error, isCurrent, onInvestigate, onCancel, isCancelling, cancellationRequested, onApprove, isApproving, hardwareMode, apiConfigured, localEnabled }: InvestigationPanelProps) {
  const id = useId();
  const [tab, setTab] = useState<'analysis' | 'device'>('analysis');
  const [mode, setMode] = useState<InvestigationMode>('local');
  const [localError, setLocalError] = useState<string | null>(null);
  const [requestedContext, setRequestedContext] = useState<string | null>(null);
  const [requestInFlight, setRequestInFlight] = useState(false);
  const currentContext = snapshot?.context;
  const investigationCurrent = Boolean(isCurrent && currentContext && investigation && sameContext(investigation.base_context, currentContext));
  const baseline = investigation?.candidate_envelopes.find(candidate => candidate.alternative_id === 'KEEP_CURRENT');
  const reserve = investigation?.candidate_envelopes.find(candidate => candidate.alternative_id === 'OPEN_P3');
  const comparisonReady = investigationCurrent && canCompareInvestigation(investigation, currentContext);
  const gain = comparisonReady && baseline && reserve ? reserve.completed_crossings - baseline.completed_crossings : null;
  const contextKey = currentContext ? `${currentContext.context_hash ?? currentContext.geometry_revision}:${currentContext.scenario_revision}:${currentContext.physical_revision}:${currentContext.parameters_revision}:${currentContext.solver_version}` : null;
  const requestSubmitted = Boolean(contextKey && requestedContext === contextKey);
  const requestRecorded = requestedContext !== null;
  const gateState = snapshot?.physical_gate_state ?? 'UNKNOWN';
  const endpointReported = Boolean(snapshot?.last_hardware_boot_id);
  const observedOpen = endpointReported && gateState === 'OPEN';
  const busy = isApproving || requestInFlight;
  const improvementApproved = investigationCurrent && canApproveInvestigation(investigation, currentContext);
  const canApprove = Boolean(improvementApproved && snapshot && !isLoading && !busy && gateState === 'CLOSED' && !requestSubmitted);
  const executedCalls = investigation?.tool_ledger.filter(entry => entry.status === 'executed').length ?? 0;
  const visibleError = error || localError;
  const modeAvailable = mode === 'live' ? apiConfigured : localEnabled;

  const runAnalysis = async () => {
    setLocalError(null);
    try { await onInvestigate(mode); }
    catch (failure) { setLocalError(failure instanceof Error ? failure.message : 'Analysis could not be completed. Try again.'); }
  };

  const approve = async () => {
    if (!canApprove) return;
    setLocalError(null);
    setRequestInFlight(true);
    try {
      await onApprove();
      setRequestedContext(contextKey);
    } catch (failure) {
      setLocalError(failure instanceof Error ? failure.message : 'The opening request was not accepted.');
    } finally { setRequestInFlight(false); }
  };

  return (
    <section className="investigation-panel" aria-labelledby={`${id}-title`}>
      <header className="investigation-header">
        <div className="investigation-title"><GitBranch size={15} strokeWidth={1.6} /><h2 id={`${id}-title`}>Intervention analysis</h2></div>
        <span className="investigation-provider-label"><span />{investigationLabel(investigation)}</span>
      </header>
      <div className="investigation-tabs" role="tablist" aria-label="Intervention views">
        <button type="button" role="tab" id={`${id}-analysis-tab`} aria-selected={tab === 'analysis'} aria-controls={`${id}-analysis`} tabIndex={tab === 'analysis' ? 0 : -1} onClick={() => setTab('analysis')} onKeyDown={event => { if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { setTab('device'); document.getElementById(`${id}-device-tab`)?.focus(); } }}><GitBranch size={13} />Analysis</button>
        <button type="button" role="tab" id={`${id}-device-tab`} aria-selected={tab === 'device'} aria-controls={`${id}-device`} tabIndex={tab === 'device' ? 0 : -1} onClick={() => setTab('device')} onKeyDown={event => { if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { setTab('analysis'); document.getElementById(`${id}-analysis-tab`)?.focus(); } }}><Cpu size={13} />Device<span className={`investigation-tab-dot${endpointReported ? ' investigation-tab-dot-connected' : ''}`} /></button>
        <span className="investigation-context-label">{currentContext ? `SCN ${String(currentContext.scenario_revision).padStart(2, '0')}` : 'NO CONTEXT'}</span>
      </div>

      {tab === 'analysis' ? (
        <div id={`${id}-analysis`} role="tabpanel" aria-labelledby={`${id}-analysis-tab`} className="investigation-body">
          <div className="investigation-mode-switch" aria-label="Analysis execution mode"><button type="button" aria-pressed={mode === 'local'} disabled={isLoading} onClick={() => setMode('local')}>Local solver</button><button type="button" aria-pressed={mode === 'live'} disabled={isLoading} onClick={() => setMode('live')}>Live Gemini</button></div>
          {comparisonReady && baseline && reserve ? (
            <>
              <div className="investigation-result-heading"><div><span className="investigation-eyebrow">CHECKED MODEL COMPARISON</span><h3>{gain === 0 ? 'Same capacity. Another route.' : gain !== null && gain > 0 ? 'A connection with an impact.' : 'The current layout performs better.'}</h3></div><span className="investigation-check-label"><ShieldCheck size={13} />Checked</span></div>
              <div className="investigation-comparison"><ComparisonRow candidate={baseline} /><ComparisonRow candidate={reserve} alternative /></div>
              <div className="investigation-outcome"><span className={`investigation-outcome-value${gain !== null && gain < 0 ? ' investigation-outcome-negative' : ''}`}>{gain !== null && gain > 0 ? '+' : ''}{gain}<ArrowRight size={17} /></span><p>{gain === 0 ? 'No additional modeled boundary crossings. P3 still feeds the existing B2 boundary.' : 'Modeled boundary crossings compared with the current layout. This is a prediction, awaiting physical observation.'}</p></div>
              <div className="investigation-result-footer"><span><CheckCheck size={13} />{executedCalls} tool {executedCalls === 1 ? 'call' : 'calls'} recorded</span><button type="button" onClick={() => { void runAnalysis(); }} disabled={isLoading || !snapshot || !modeAvailable}><RotateCcw size={12} />{isLoading ? 'Running…' : mode === 'live' ? 'Run Gemini' : 'Run local'}</button></div>
            </>
          ) : (
            <div className="investigation-empty">
              <RouteDiagram />
              <div className="investigation-empty-copy"><h3>{isLoading ? 'Evaluating the alternatives.' : investigation && !investigationCurrent ? 'The scenario has changed.' : investigation ? 'The comparison is incomplete.' : 'Find the better connection.'}</h3><p>{isLoading ? 'Waiting for checked numerical results for the current scenario.' : investigation && !investigationCurrent ? 'Run a fresh comparison before using this intervention.' : investigation ? 'Both alternatives need valid results under the same population and horizon.' : 'Compare the current layout with an open reserve connection. Every occupant stays accounted for.'}</p></div>
              <button type="button" className="investigation-primary" onClick={() => { void runAnalysis(); }} disabled={isLoading || !snapshot || !modeAvailable}>{isLoading ? <LoaderCircle size={14} className="investigation-spin" /> : <Play size={13} fill="currentColor" />}<span>{isLoading ? 'Analysis in progress' : mode === 'live' ? 'Run Gemini analysis' : 'Compare with local solver'}</span>{!isLoading && <ArrowRight size={15} />}</button>
            </div>
          )}
          <div className="investigation-source-note"><span className="investigation-source-dot" />{mode === 'local' ? localEnabled ? 'Explicit local numerical computation · no Gemini call' : 'Local demo mode disabled by the server' : apiConfigured ? 'Gemini configured · up to 60s · completed response required' : 'Gemini unavailable · server credentials are not configured'}</div>
          {isLoading && <div className="investigation-live-progress"><ProviderProgressList events={progress?.provider_progress ?? []} pending /><button type="button" className="investigation-cancel" onClick={() => void onCancel()} disabled={isCancelling || cancellationRequested}>{isCancelling ? 'Requesting cancellation…' : cancellationRequested ? 'Cancellation requested · awaiting receipt' : 'Cancel analysis'}</button></div>}
          <InvestigationEvidence investigation={investigation} />
          <ExecutionReceipt result={investigation} label={investigationLabel(investigation)} />
        </div>
      ) : (
        <div id={`${id}-device`} role="tabpanel" aria-labelledby={`${id}-device-tab`} className="investigation-body investigation-device-body">
          <div className="investigation-device-summary"><div className="investigation-device-icon"><Cpu size={24} strokeWidth={1.2} /></div><div><span className="investigation-eyebrow">RESERVE CONNECTOR · P3</span><h3>{endpointReported ? `Reported ${gateState.toLowerCase()}` : 'Awaiting endpoint evidence'}</h3><span className="investigation-device-mode">{hardwareMode ? `${hardwareMode} mode` : 'Connection mode unavailable'}</span></div></div>
          <ol className="investigation-device-ledger">
            <li><span className={`investigation-step-icon${requestRecorded ? ' investigation-step-icon-done' : ''}`}>{requestRecorded ? <Check size={12} /> : <Circle size={8} />}</span><div><strong>Operator request</strong><span>{busy ? 'Submitting opening request…' : requestRecorded ? 'Backend request accepted for its reviewed context' : observedOpen ? 'No request recorded in this browser session' : 'Opening requires your approval'}</span></div></li>
            <li><span className="investigation-step-icon"><Radio size={12} /></span><div><strong>Device acknowledgement</strong><span>No device ACK receipt is exposed here</span></div></li>
            <li><span className={`investigation-step-icon${observedOpen ? ' investigation-step-icon-done' : ''}`}>{endpointReported ? <Check size={12} /> : <Unplug size={12} />}</span><div><strong>Endpoint observation</strong><span>{endpointReported ? `Snapshot reports ${gateState.toLowerCase()} · epoch ${snapshot?.last_gate_epoch ?? 'unknown'}` : 'No endpoint receipt in the current snapshot'}</span></div></li>
          </ol>
          <button type="button" className="investigation-primary investigation-approval" disabled={!canApprove} onClick={() => { void approve(); }}>{busy ? <LoaderCircle size={14} className="investigation-spin" /> : <ArrowDown size={14} />}<span>{busy ? 'Submitting request' : observedOpen ? 'Open endpoint reported' : requestSubmitted ? 'Request sent · awaiting observation' : 'Approve opening P3'}</span>{!busy && !observedOpen && !requestSubmitted && <ArrowRight size={15} />}</button>
          <p className="investigation-device-note">{observedOpen ? `${hardwareMode === 'simulator' ? 'Simulated' : 'Reported'} open endpoint received. The workspace result uses the new physical revision; the earlier comparison remains historical evidence.` : !comparisonReady ? 'Complete a current, checked comparison before approval.' : !improvementApproved ? 'No checked improvement recommends opening P3. Keep the current layout.' : 'Approval requests movement. Only endpoint evidence can establish the resulting position.'}</p>
        </div>
      )}
      {visibleError && <div className="investigation-error" role="alert">{visibleError}</div>}
    </section>
  );
}
