import type { InvestigationProgress, InvestigationResult } from '../types';
import { agentLines } from '../ai/agentPhases';
import { investigationLabel } from '../ai/policy';
import { TerminalPane } from './TerminalPane';

interface Props {
  investigation: InvestigationResult | null;
  progress: InvestigationProgress | null;
  isLoading: boolean;
  mode: 'live' | 'local';
}

/** One run in at most eight lines: phases with elapsed time, each tool call, the short interaction id. Provider thought content is never shown. */
export function AgentPane({ investigation, progress, isLoading, mode }: Props) {
  const events = isLoading || !investigation?.provider_progress?.length ? progress?.provider_progress ?? investigation?.provider_progress ?? [] : investigation.provider_progress;
  const ledger = investigation?.tool_ledger ?? [];
  const lines = agentLines({ events, ledger, interactionId: investigation?.provider_interaction_id });
  const empty = !lines.phases && !lines.tools.length;
  const status = investigation ? (investigation.provenance === 'live' && investigation.status === 'completed' ? 'Agent investigated · checker decided' : investigationLabel(investigation)) : undefined;
  return <TerminalPane id="agent" title="Agent" status={status}>
    <div className="terminal-body" role="log" tabIndex={0} aria-label="Investigation trace" aria-live={isLoading ? 'polite' : 'off'} aria-relevant="additions">
      {lines.phases && <div className="t-line t-phases"><span className="t-src">phases</span><span className="t-msg">{lines.phases}</span></div>}
      {lines.tools.map((tool, index) => <div key={`${index}-${tool}`} className="t-line t-tool t-success"><span className="t-src">tool</span><span className="t-msg">{tool}</span></div>)}
      {lines.id && <div className="t-line"><span className="t-src">run</span><span className="t-msg">interaction {lines.id}</span></div>}
      {empty && <div className="t-empty">{isLoading ? (mode === 'local' ? 'Local solver running…' : 'Request submitted. Waiting for a receipt…') : 'No analysis yet. The agent investigates, the local checker decides.'}</div>}
    </div>
  </TerminalPane>;
}
