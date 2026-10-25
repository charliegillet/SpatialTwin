import React, { useState } from 'react';
import { ScenarioSnapshot } from '../types';
import { ShieldCheck, ChevronDown, ChevronUp, Terminal } from 'lucide-react';

interface AuditDrawerProps {
  snapshot: ScenarioSnapshot | null;
}

export const AuditDrawer: React.FC<AuditDrawerProps> = ({ snapshot }) => {
  const [isOpen, setIsOpen] = useState(false);
  const plan = snapshot?.current_plan;
  const ctx = snapshot?.context;

  return (
    <div className="bg-slate-950/90 rounded-xl border border-slate-800 overflow-hidden shadow-xl text-xs">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-2.5 flex items-center justify-between bg-slate-900/60 hover:bg-slate-900 transition text-slate-300"
      >
        <div className="flex items-center space-x-2">
          <ShieldCheck className="h-4 w-4 text-emerald-400" />
          <span className="font-semibold text-slate-200">System Provenance & Constraint Audit</span>
          <span className="text-slate-500">•</span>
          <span className="text-slate-400 font-mono">Run: {plan?.run_id ?? 'none'}</span>
        </div>
        {isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>

      {isOpen && (
        <div className="p-4 space-y-3 border-t border-slate-800 bg-slate-950 font-mono text-[11px]">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="p-3 rounded bg-slate-900/80 border border-slate-800 space-y-1">
              <div className="text-slate-400 font-bold mb-1">Context & Revisions</div>
              <div><span className="text-slate-500">Geometry:</span> {ctx?.geometry_revision}</div>
              <div><span className="text-slate-500">Scenario Rev:</span> {ctx?.scenario_revision}</div>
              <div><span className="text-slate-500">Physical Rev:</span> {ctx?.physical_revision}</div>
              <div><span className="text-slate-500">Context Hash:</span> {ctx?.context_hash}</div>
              <div><span className="text-slate-500">Candidate Hash:</span> {plan?.candidate_hash}</div>
            </div>

            <div className="p-3 rounded bg-slate-900/80 border border-slate-800 space-y-1">
              <div className="text-slate-400 font-bold mb-1">Solver & Verification</div>
              <div><span className="text-slate-500">Solver Version:</span> {ctx?.solver_version}</div>
              <div><span className="text-slate-500">Compute Time:</span> {plan?.timings_ms} ms</div>
              <div><span className="text-slate-500">Status:</span> {plan?.status}</div>
              <div><span className="text-slate-500">Conservation:</span> {plan?.validator_report?.conservation_verified ? 'VERIFIED' : 'FAILED'}</div>
              <div><span className="text-slate-500">Quotas Respected:</span> {plan?.validator_report?.quota_respected ? 'TRUE' : 'FALSE'}</div>
            </div>
          </div>

          <div className="p-3 rounded bg-slate-900/80 border border-slate-800">
            <div className="text-slate-400 font-bold mb-1">Declared Model Assumptions:</div>
            <ul className="list-disc list-inside text-slate-300 space-y-0.5">
              {plan?.assumptions?.map((asm, idx) => (
                <li key={idx}>{asm}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};
