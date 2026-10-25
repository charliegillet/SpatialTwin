import { useEffect, useState } from 'react';
import { Check, LoaderCircle, Play, RotateCcw, ShieldCheck } from 'lucide-react';
import type { InvestigationMode, ScenarioSnapshot, InvestigationResult } from '../types';
import { canApproveInvestigation, canCompareInvestigation, sameContext } from '../ai/policy';
import { gainText } from '../ai/stageView';
import { approvalLadder, comparisonLine, doneLine, approvalIsCurrent, hasApprovableEvidence } from '../ai/decisionView';
import type { OperatorOutcome } from '../ai/operator';

export interface DecisionBarProps {
  snapshot: ScenarioSnapshot | null;
  investigation: InvestigationResult | null;
  isLoading: boolean;
  error: string | null;
  isCurrent: boolean;
  availabilityMessage?: string;
  onInvestigate: (mode: InvestigationMode) => Promise<void>;
  onCancel: () => Promise<void>;
  isCancelling: boolean;
  cancellationRequested: boolean;
  onApprove: () => Promise<OperatorOutcome>;
  isApproving: boolean;
  /** Physical serial hardware: commands need an operator token, held in the presenter menu. */
  physical: boolean;
  tokenHeld: boolean;
  apiConfigured: boolean;
  localEnabled: boolean;
  mode: InvestigationMode;
  /** Checked count of the current plan, shown once an approved opening is observed. */
  resolvedCount: number | null;
}

/** The compact decision surface over the model: compare, then approve opening P3. */
export function DecisionBar({ snapshot, investigation, isLoading, error, isCurrent, availabilityMessage, onInvestigate, onCancel, isCancelling, cancellationRequested, onApprove, isApproving, physical, tokenHeld, apiConfigured, localEnabled, mode, resolvedCount }: DecisionBarProps) {
  const [localError, setLocalError] = useState<string | null>(null);
  const [approval, setApproval] = useState<{ context: string; acknowledged: boolean; revision: number } | null>(null);
  const [requestInFlight, setRequestInFlight] = useState(false);
  const currentContext = snapshot?.context;
  const investigationCurrent = Boolean(isCurrent && currentContext && investigation && sameContext(investigation.base_context, currentContext));
  const baseline = investigation?.candidate_envelopes.find(candidate => candidate.alternative_id === 'KEEP_CURRENT');
  const reserve = investigation?.candidate_envelopes.find(candidate => candidate.alternative_id === 'OPEN_P3');
  const comparisonReady = investigationCurrent && canCompareInvestigation(investigation, currentContext);
  const gain = comparisonReady && baseline && reserve ? reserve.completed_crossings - baseline.completed_crossings : null;
  const contextKey = currentContext ? `${currentContext.context_hash ?? currentContext.geometry_revision}:${currentContext.scenario_revision}:${currentContext.physical_revision}:${currentContext.parameters_revision}:${currentContext.solver_version}` : null;
  const requestSubmitted = Boolean(contextKey && approval?.context === contextKey);
  const gateState = snapshot?.physical_gate_state ?? 'UNKNOWN';
  const endpointReported = Boolean(snapshot?.last_hardware_boot_id);
  const observedOpen = endpointReported && gateState === 'OPEN';
  // Opening the gate is what changes the context, so an approved request whose movement was observed still counts.
  // The approval belongs to the scenario revision it was made on. Any later hazard or clear ends the climax.
  const approved = approvalIsCurrent(approval, currentContext?.scenario_revision);
  const done = approved && observedOpen;
  const busy = isApproving || requestInFlight;
  const improvementApproved = investigationCurrent && canApproveInvestigation(investigation, currentContext);
  // Moving physical hardware needs a live agent result; the simulator accepts a local one.
  const liveEvidence = hasApprovableEvidence(physical, investigation?.provenance);
  const canApprove = Boolean(improvementApproved && snapshot && !isLoading && !busy && gateState === 'CLOSED' && !requestSubmitted && (!physical || tokenHeld) && liveEvidence);
  const visibleError = error || localError;
  const modeAvailable = mode === 'live' ? apiConfigured : localEnabled;
  const stale = Boolean(investigation && !investigationCurrent) && !done;
  const failedLive = !isLoading && !comparisonReady && !done && localEnabled && (mode === 'live' || investigation?.provenance === 'live')
    && Boolean(error || (investigation && investigation.status !== 'completed'));
  const hint = !modeAvailable ? (mode === 'live' ? 'Gemini is not configured.' : 'Local solver is disabled.')
    : stale ? (availabilityMessage ?? 'Outdated · compare again.')
    : improvementApproved && !approved ? (physical && !tokenHeld ? 'Operator token required. Open the presenter menu.' : gateState !== 'CLOSED' ? `P3 is ${gateState.toLowerCase()}.` : '')
    : '';

  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!isLoading) { setElapsed(0); return; }
    const started = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [isLoading]);

  const run = async (chosen: InvestigationMode = mode) => {
    if (isLoading || !snapshot) return;
    setLocalError(null);
    try { await onInvestigate(chosen); }
    catch (failure) { setLocalError(failure instanceof Error ? failure.message : 'Analysis could not be completed.'); }
  };
  const approve = async () => {
    if (!canApprove) return;
    setLocalError(null);
    setRequestInFlight(true);
    try {
      const outcome = await onApprove();
      if (outcome.ok && contextKey) setApproval({ context: contextKey, acknowledged: Boolean(outcome.acknowledged), revision: currentContext!.scenario_revision });
      else if (!outcome.ok) setLocalError(outcome.message);
    } catch (failure) {
      setLocalError(failure instanceof Error ? failure.message : 'Opening request not accepted.');
    } finally { setRequestInFlight(false); }
  };
  const ladder = approved ? approvalLadder({ approved, acknowledged: Boolean(approval?.acknowledged), gateState, endpointReported, resolved: observedOpen ? resolvedCount : null }) : null;

  return <section className="decision" aria-label="Decision">
    <div className="decision-row">
      {isLoading ? <>
        <span className="decision-busy" role="status"><LoaderCircle size={14} className="spin" aria-hidden="true" />{mode === 'live' ? 'Agent investigating' : 'Local solver running'}<span className="decision-clock" aria-hidden="true"> · {elapsed} s</span></span>
        <button type="button" className="btn" onClick={() => void onCancel()} disabled={isCancelling || cancellationRequested}>{isCancelling ? 'Requesting…' : cancellationRequested ? 'Cancelling…' : 'Cancel'}</button>
      </> : comparisonReady && !done
        ? <button type="button" className="btn btn-icon" onClick={() => void run()} disabled={!snapshot || !modeAvailable} aria-label="Run comparison again" title="Run comparison again"><RotateCcw size={15} aria-hidden="true" /></button>
        : !done && <button type="button" className="btn btn-primary" onClick={() => void run()} disabled={!snapshot || !modeAvailable}><Play size={14} fill="currentColor" aria-hidden="true" />Compare options</button>}
      {failedLive && <button type="button" className="btn" onClick={() => void run('local')} title="Local solver · no Gemini call"><Play size={14} aria-hidden="true" />Run local check<small>Local solver · no Gemini call</small></button>}
    </div>
    {done && <div className="decision-row decision-done" role="status"><Check size={15} aria-hidden="true" /><strong>{doneLine(resolvedCount)}</strong></div>}
    {comparisonReady && !isLoading && !done && baseline && reserve && <div className="decision-row decision-result">
      <span className="decision-gain"><ShieldCheck size={15} aria-hidden="true" /><strong className={gain !== null && gain > 0 ? 'is-gain' : gain !== null && gain < 0 ? 'is-loss' : ''}>{comparisonLine(baseline.completed_crossings, reserve.completed_crossings)}</strong>{gain !== null && gain <= 0 && <span className="decision-nogain">{gainText(gain)} · approval blocked</span>}</span>
      {improvementApproved && !approved && !liveEvidence && <><span className="decision-nogain">Moving the gate needs a live agent result</span><button type="button" className="btn" onClick={() => void run('live')} disabled={!apiConfigured || !snapshot}>Retry agent</button></>}
      {improvementApproved && !approved && liveEvidence && <button type="button" className="btn btn-primary" disabled={!canApprove} onClick={() => void approve()}>{busy ? <LoaderCircle size={14} className="spin" aria-hidden="true" /> : null}{busy ? 'Sending…' : 'Approve opening P3'}</button>}
      <span className="decision-provenance">{investigation?.provenance === 'live' ? 'Agent investigated · checker decided' : 'Local solver · checker decided'}</span>
    </div>}
    {ladder && <ol className="ladder" aria-label="Approval progress">{ladder.map(step => <li key={step.id} className={`ladder-${step.state}`} aria-current={step.state === 'active' ? 'step' : undefined}>{step.state === 'done' && <Check size={11} aria-hidden="true" />}{step.label}</li>)}</ol>}
    {hint && <p className="decision-hint" role="status">{hint}</p>}
    {visibleError && <p className="decision-error" role="alert">{visibleError}</p>}
  </section>;
}
