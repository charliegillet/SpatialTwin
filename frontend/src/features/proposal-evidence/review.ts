import type { RunContext, ScenarioSnapshot } from '../../types.ts';
import { sameContext } from '../../ai/policy.ts';
import { requestJson } from '../../api/client.ts';

export type Severity = 'info' | 'advisory' | 'alert';
export type Escalation = 'nominal' | 'advisory' | 'escalated';
export type NextStep = 'none' | 'compare_alternatives' | 'await_endpoint' | 'no_allowed_alternative';
export type RequirementStatus = 'pass' | 'fail' | 'checker_attested' | 'cannot_measure' | 'not_run';

export interface EvidencePointer { source: 'checked_plan' | 'venue_spec' | 'reported_state' | 'investigation'; ref: string; field: string; }
export interface WatchRecord {
  record_id: string; watcher_id: string; kind: string; severity: Severity; summary: string;
  value?: number | null; limit?: number | null; unit?: string | null; at_seconds?: number | null; evidence: EvidencePointer[];
}
export interface WatcherStatus { watcher_id: string; label: string; scope: 'zone' | 'passage' | 'boundary' | 'reserve'; severity: Severity; record_ids: string[]; }
export interface WatchReport {
  version: 'zone-watch-v1'; base_context: RunContext; run_id: string; candidate_hash: string;
  watchers: WatcherStatus[]; records: WatchRecord[]; escalation: Escalation; escalation_reasons: string[];
  next_step: NextStep; delivery: 'local_record_only'; notice: string;
}
export interface Requirement {
  requirement_id: string; category: string; scope: string; statement: string;
  method: 'measured' | 'checker' | 'outside_model'; status: RequirementStatus;
  measured?: string | null; expected?: string | null; value?: number | null; limit?: number | null; evidence: EvidencePointer[];
}
export interface VerificationReport {
  version: 'verification-v1'; base_context: RunContext; run_id: string; candidate_hash: string;
  verdict: 'verified_within_model' | 'not_verified' | 'incomplete';
  summary: { passed: number; failed: number; checker_attested: number; cannot_measure: number; not_run: number };
  requirements: Requirement[]; scope_note: string;
}
export interface EscalationRecord {
  record_id: string; created_at_iso: string; context_hash: string; run_id: string; escalation: 'escalated';
  reasons: string[]; next_step: NextStep; delivery: 'local_record_only'; notice: string;
}
export interface ReviewPayload {
  provenance: 'local_review'; generated_at_iso: string; base_context: RunContext; run_id: string; candidate_hash: string;
  hardware_mode: string; watch: WatchReport; verification: VerificationReport; escalation_record: EscalationRecord | null; notice: string;
}
export type ReviewView =
  | { available: true; payload: ReviewPayload }
  | { available: false; message: string };

const severityRank: Record<Severity, number> = { info: 0, advisory: 1, alert: 2 };
const sources = new Set(['checked_plan', 'venue_spec', 'reported_state', 'investigation']);
const scopes = new Set(['zone', 'passage', 'boundary', 'reserve']);
const steps = new Set(['none', 'compare_alternatives', 'await_endpoint', 'no_allowed_alternative']);
const statuses: RequirementStatus[] = ['pass', 'fail', 'checker_attested', 'cannot_measure', 'not_run'];
const methods = new Set(['measured', 'checker', 'outside_model']);

const record = (value: unknown): value is Record<string, any> => Boolean(value && typeof value === 'object' && !Array.isArray(value));
const text = (value: unknown): value is string => typeof value === 'string' && value.length > 0;
const optionalCount = (value: unknown) => value === undefined || value === null || Number.isSafeInteger(value);
const timestamp = (value: unknown) => text(value) && Number.isFinite(Date.parse(value));
const sameList = (a: unknown, b: string[]) => Array.isArray(a) && a.length === b.length && a.every((item, index) => item === b[index]);

function pointers(value: unknown, runId: string): boolean {
  return Array.isArray(value) && value.every(pointer => record(pointer) && sources.has(pointer.source) && text(pointer.ref)
    && text(pointer.field) && (pointer.source !== 'checked_plan' || pointer.ref === runId));
}

function validWatch(watch: unknown, runId: string, gateState: string): watch is WatchReport {
  if (!record(watch) || watch.version !== 'zone-watch-v1' || watch.delivery !== 'local_record_only' || !text(watch.notice)
    || !Array.isArray(watch.records) || !Array.isArray(watch.watchers) || !watch.records.length || !watch.watchers.length) return false;
  const records = new Map<string, WatchRecord>();
  for (const item of watch.records) {
    if (!record(item) || !text(item.record_id) || records.has(item.record_id) || !text(item.watcher_id) || !text(item.kind)
      || !(item.severity in severityRank) || !text(item.summary) || !pointers(item.evidence, runId)
      || !['value', 'limit', 'at_seconds'].every(key => optionalCount(item[key]))) return false;
    records.set(item.record_id, item as WatchRecord);
  }
  const owned = new Set<string>();
  const watcherIds = new Set<string>();
  for (const watcher of watch.watchers) {
    if (!record(watcher) || !text(watcher.watcher_id) || watcherIds.has(watcher.watcher_id) || !text(watcher.label)
      || !scopes.has(watcher.scope) || !Array.isArray(watcher.record_ids) || !watcher.record_ids.length) return false;
    watcherIds.add(watcher.watcher_id);
    const found: WatchRecord[] = [];
    for (const id of watcher.record_ids) {
      const item = typeof id === 'string' ? records.get(id) : undefined;
      if (!item || item.watcher_id !== watcher.watcher_id || owned.has(item.record_id)) return false;
      owned.add(item.record_id);
      found.push(item);
    }
    if (watcher.severity !== found.reduce<Severity>((top, item) => severityRank[item.severity] > severityRank[top] ? item.severity : top, 'info')) return false;
  }
  if (owned.size !== records.size) return false;
  const all = [...records.values()];
  const alerts = all.filter(item => item.severity === 'alert').map(item => item.record_id);
  const advisories = all.filter(item => item.severity === 'advisory').map(item => item.record_id);
  const escalation = alerts.length ? 'escalated' : advisories.length ? 'advisory' : 'nominal';
  if (watch.escalation !== escalation || !sameList(watch.escalation_reasons, alerts.length ? alerts : advisories)) return false;
  if (!steps.has(watch.next_step)) return false;
  // The watch may only route to an existing step; an unconfirmed reserve always waits for an endpoint.
  if (!['OPEN', 'CLOSED'].includes(gateState)) return watch.next_step === 'await_endpoint';
  return watch.next_step !== 'await_endpoint'
    && (escalation === 'escalated' || !['compare_alternatives', 'no_allowed_alternative'].includes(watch.next_step));
}

function validVerification(report: unknown, runId: string): report is VerificationReport {
  if (!record(report) || report.version !== 'verification-v1' || !text(report.scope_note) || !record(report.summary)
    || !Array.isArray(report.requirements) || !report.requirements.length) return false;
  const ids = new Set<string>();
  for (const item of report.requirements) {
    if (!record(item) || !text(item.requirement_id) || ids.has(item.requirement_id) || !text(item.statement)
      || !statuses.includes(item.status) || !methods.has(item.method)
      || (item.method === 'outside_model') !== (item.status === 'cannot_measure')
      || !pointers(item.evidence, runId) || !optionalCount(item.value) || !optionalCount(item.limit)) return false;
    ids.add(item.requirement_id);
  }
  const count = (status: RequirementStatus) => report.requirements.filter((item: Requirement) => item.status === status).length;
  const summary = report.summary;
  if (summary.passed !== count('pass') || summary.failed !== count('fail') || summary.checker_attested !== count('checker_attested')
    || summary.cannot_measure !== count('cannot_measure') || summary.not_run !== count('not_run')) return false;
  // A report that names no limit of its own scope is not accepted.
  if (!summary.cannot_measure) return false;
  // Any failure means not verified; otherwise the server says whether every measured item ran.
  return summary.failed ? report.verdict === 'not_verified'
    : report.verdict === 'verified_within_model' || report.verdict === 'incomplete';
}

/** Fail closed before any watch record or requirement reaches the component. */
export function reviewPayload(payload: unknown, snapshot: ScenarioSnapshot | null | undefined, isCurrent: boolean): ReviewView {
  const unavailable = (message: string): ReviewView => ({ available: false, message });
  if (!isCurrent) return unavailable('A connected, current checked result is required. Earlier watch records are hidden.');
  const plan = snapshot?.current_plan;
  if (!snapshot || !plan) return unavailable('No checked run to review yet.');
  if (!record(payload) || payload.provenance !== 'local_review' || !timestamp(payload.generated_at_iso) || !text(payload.notice))
    return unavailable('The response is not a local review of the accepted run.');
  if (![payload.base_context, payload.watch?.base_context, payload.verification?.base_context].every(item => sameContext(item, snapshot.context)))
    return unavailable('The scenario changed. Review the current run again.');
  const runId = plan.run_id;
  if ([payload.run_id, payload.watch?.run_id, payload.verification?.run_id].some(id => id !== runId)
    || [payload.candidate_hash, payload.watch?.candidate_hash, payload.verification?.candidate_hash].some(hash => hash !== plan.candidate_hash))
    return unavailable('The review belongs to a different run. Review the current run again.');
  if (!validWatch(payload.watch, runId, snapshot.physical_gate_state)) return unavailable('The watch records are incomplete or inconsistent.');
  if (!validVerification(payload.verification, runId)) return unavailable('The verification report is incomplete or inconsistent.');
  const escalationRecord = payload.escalation_record;
  if (payload.watch.escalation === 'escalated') {
    if (!record(escalationRecord) || !text(escalationRecord.record_id) || escalationRecord.delivery !== 'local_record_only'
      || escalationRecord.run_id !== runId || escalationRecord.context_hash !== snapshot.context.context_hash
      || !timestamp(escalationRecord.created_at_iso) || !sameList(escalationRecord.reasons, payload.watch.escalation_reasons))
      return unavailable('The local escalation record does not match the watch.');
  } else if (escalationRecord !== null) return unavailable('A non-escalated watch cannot carry an escalation record.');
  return { available: true, payload: payload as ReviewPayload };
}

export function nextStepCopy(step: NextStep): string {
  return {
    none: 'No operator action is suggested.',
    compare_alternatives: 'Compare the checked alternatives. The comparison decides whether OPEN_P3 changes crossings; zero is a valid result.',
    await_endpoint: 'Wait for a fresh endpoint observation. P3 stays unavailable while its position is unconfirmed.',
    no_allowed_alternative: 'No further allowed alternative. Remaining occupants stay accounted for in holding.',
  }[step];
}

export function escalationLabel(escalation: Escalation): string {
  return escalation === 'escalated' ? 'Escalated · local record' : escalation === 'advisory' ? 'Advisory' : 'Nominal';
}

export const statusLabel: Record<RequirementStatus, string> = {
  pass: 'Pass', fail: 'Fail', checker_attested: 'Checker', cannot_measure: 'Cannot measure', not_run: 'Not run',
};

export const fetchReview = (context: RunContext, investigationId: string | null, signal?: AbortSignal) =>
  requestJson<unknown>('/api/scenarios/facility-demo/review', {
    method: 'POST', body: { expected_context: context, ...(investigationId ? { investigation_id: investigationId } : {}) },
    signal, timeoutMs: 15_000, fallback: 'The review could not finish',
  });

const escape = (value: unknown): string => String(value ?? '—').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]!));

export function reviewJson(payload: ReviewPayload, exportedAt = new Date().toISOString()): string {
  return JSON.stringify({ exported_at: exportedAt, scope: 'Illustrative tabletop model with synthetic occupants', review: payload }, null, 2);
}

/** Portable report. No scripts, external resources, provider requests or state changes. */
export function buildReviewHtml(payload: ReviewPayload, exportedAt = new Date().toISOString()): string {
  const { watch, verification } = payload;
  const records = new Map(watch.records.map(item => [item.record_id, item]));
  const watcherRows = watch.watchers.map(watcher => `<tr><th scope="row">${escape(watcher.label)}</th><td>${escape(watcher.severity)}</td><td>${watcher.record_ids.map(id => escape(records.get(id)?.summary)).join('<br>')}</td></tr>`).join('');
  const measured = verification.requirements.filter(item => item.status !== 'cannot_measure');
  const outside = verification.requirements.filter(item => item.status === 'cannot_measure');
  const requirementRows = measured.map(item => `<tr><th scope="row">${escape(item.statement)}</th><td>${escape(item.measured)}</td><td>${escape(item.expected)}</td><td>${escape(statusLabel[item.status])}</td></tr>`).join('');
  const record = payload.escalation_record;
  const summary = verification.summary;
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>SpatialTwin verification report</title><style>
*{box-sizing:border-box}body{max-width:940px;margin:40px auto;padding:0 24px;font:15px/1.6 system-ui,sans-serif;color:#17201c;background:#fff}h1{font-size:28px;line-height:1.2;margin:12px 0}h2{font-size:19px;margin:28px 0 10px}p{max-width:80ch}.scope,footer{color:#45554b;font-size:13px}.notice{padding:12px 16px;background:#edf2e8;border:1px solid #859875}.alert{background:#fff1e5;border-color:#a56b3b}table{width:100%;border-collapse:collapse;margin:14px 0;font-size:13px;table-layout:fixed}th,td{padding:9px 10px;border-bottom:1px solid #b7c3b7;text-align:left;vertical-align:top;overflow-wrap:anywhere}thead{background:#edf2e8}th[scope=row]{width:38%;font-weight:500}footer{border-top:1px solid #859875;margin-top:30px;padding-top:14px}@media print{@page{margin:15mm}body{max-width:none;margin:0;padding:0;font-size:11px}table{font-size:10px}tr,.notice{break-inside:avoid}}
</style></head><body><header><p class="scope">Illustrative tabletop · synthetic population · saved snapshot</p><h1>SpatialTwin verification report</h1><p>Exported ${escape(exportedAt)}; reviewed ${escape(payload.generated_at_iso)}. Run ${escape(payload.run_id)} · context ${escape(payload.base_context.context_hash)}. Reopen the application to check freshness.</p><p class="notice">${escape(verdictNotice(verification.verdict))} ${escape(summary.passed)} measured pass · ${escape(summary.failed)} fail · ${escape(summary.checker_attested)} checker-attested · ${escape(summary.cannot_measure)} cannot measure · ${escape(summary.not_run)} not run.</p></header><main>
<h2>Zone watch</h2><p class="notice${watch.escalation === 'escalated' ? ' alert' : ''}">${escape(escalationLabel(watch.escalation))}. ${escape(nextStepCopy(watch.next_step))} ${record ? `Record ${escape(record.record_id)} created ${escape(record.created_at_iso)}.` : ''} ${escape(watch.notice)}</p>
<table><thead><tr><th scope="col">Watcher</th><th scope="col">Severity</th><th scope="col">Records</th></tr></thead><tbody>${watcherRows}</tbody></table>
<h2>Requirements checked</h2><table><thead><tr><th scope="col">Requirement</th><th scope="col">Measured</th><th scope="col">Expected</th><th scope="col">Status</th></tr></thead><tbody>${requirementRows}</tbody></table>
<h2>Outside the model</h2><ul>${outside.map(item => `<li><strong>${escape(item.statement)}</strong> ${escape(item.measured)}</li>`).join('')}</ul></main>
<footer>${escape(verification.scope_note)} Checker items rely on named server checks. This document does not authorize movement, notify anyone or provide venue emergency instructions.</footer></body></html>`;
}

/** Plain-words verdict for the panel and the printable report. */
export function verdictLabel(verdict: VerificationReport['verdict']): string {
  return verdict === 'verified_within_model' ? 'Verified within the model'
    : verdict === 'incomplete' ? 'Incomplete' : 'Not verified';
}

export function verdictNotice(verdict: VerificationReport['verdict']): string {
  return verdict === 'verified_within_model' ? 'Verified within the model at review time.'
    : verdict === 'incomplete' ? 'Incomplete: no measured requirement failed, but at least one did not run.'
    : 'Not verified: at least one measured requirement failed.';
}
