export interface LadderInput {
  approved: boolean;
  acknowledged: boolean;
  gateState: string;
  endpointReported: boolean;
  resolved: number | null;
}
export interface LadderStep { id: string; label: string; state: 'done' | 'active' | 'pending'; }

/** Approved, then acknowledged (not arrival), then what the endpoint and the re-solve show. Later evidence implies earlier steps. */
export function approvalLadder(input: LadderInput): LadderStep[] {
  const open = input.endpointReported && input.gateState === 'OPEN';
  const moving = input.gateState === 'TRANSIT' || open;
  const reached = [input.approved, input.approved && input.acknowledged, moving, open, open && input.resolved !== null];
  const last = reached.lastIndexOf(true);
  const labels = ['Approved', 'Acknowledged · not arrival', 'Gate moving', 'Open switch', input.resolved === null ? 'Re-solved' : `Re-solved ${input.resolved}`];
  return labels.map((label, index) => ({ id: ['approved', 'acknowledged', 'moving', 'open', 'resolved'][index], label,
    state: index <= last ? 'done' as const : index === last + 1 && input.approved ? 'active' as const : 'pending' as const }));
}

export function comparisonLine(keep: number, open: number): string {
  return `Open P3: ${keep} → ${open} · checked`;
}

export function doneLine(resolved: number | null): string {
  return resolved === null ? 'Done' : `Done · re-solved ${resolved}`;
}

/** Moving physical hardware needs a live agent result; the simulator also accepts a local one. */
export function hasApprovableEvidence(physical: boolean, provenance: string | null | undefined): boolean {
  return !physical || provenance === 'live';
}

/** An approval belongs to the scenario revision it was made on; any later change ends the climax. */
export function approvalIsCurrent(approval: { revision: number } | null, currentRevision: number | null | undefined): boolean {
  return approval !== null && approval.revision === currentRevision;
}
