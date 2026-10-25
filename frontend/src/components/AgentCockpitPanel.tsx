import React, { useState } from 'react';
import {
  Sparkles,
  Cpu,
  Table,
  CheckCircle2,
  ShieldAlert,
  ArrowRight,
  Clock,
  Play,
  Pause,
  RotateCcw,
} from 'lucide-react';
import { InvestigationResult, ScenarioSnapshot } from '../types';
import { sounds } from '../utils/audio';

interface AgentCockpitPanelProps {
  snapshot: ScenarioSnapshot | null;
  investigation: InvestigationResult | null;
  onRunInvestigation: () => Promise<InvestigationResult>;
  onOperatorApproveGate: () => Promise<void>;
  matrixData: any | null;
  isInvestigationLoading: boolean;
}

export const AgentCockpitPanel: React.FC<AgentCockpitPanelProps> = ({
  snapshot,
  investigation,
  onRunInvestigation,
  onOperatorApproveGate,
  matrixData,
  isInvestigationLoading,
}) => {
  const [activeTab, setActiveTab] = useState<'investigation' | 'diff' | 'actuation' | 'matrix'>('investigation');
  const [actuationStep, setActuationStep] = useState<number>(0);
  const [isActuating, setIsActuating] = useState<boolean>(false);

  const gateState = snapshot?.physical_gate_state ?? 'CLOSED';
  const plan = snapshot?.current_plan;

  const handleApprove = async () => {
    setIsActuating(true);
    setActuationStep(1); // Approved
    try {
      await onOperatorApproveGate();
      setActuationStep(2); // ACK
      setTimeout(() => setActuationStep(3), 400); // Transit
      setTimeout(() => {
        setActuationStep(4); // Confirmed
        setIsActuating(false);
        sounds.playGateConfirmed();
      }, 1100);
    } catch (e) {
      console.error(e);
      setIsActuating(false);
      setActuationStep(0);
    }
  };

  return (
    <div className="relative w-full h-[290px] bg-slate-950/95 rounded-xl border border-slate-800/90 flex flex-col justify-between overflow-hidden shadow-2xl font-sans">
      {/* Tab Navigation */}
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-slate-900 border-b border-slate-800 text-xs">
        <div className="flex items-center space-x-1">
          <button
            onClick={() => setActiveTab('investigation')}
            className={`flex items-center space-x-1.5 px-3 py-1 rounded-md font-semibold text-xs transition ${
              activeTab === 'investigation'
                ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
            <span>Agent Brain</span>
          </button>
          <button
            onClick={() => setActiveTab('diff')}
            className={`flex items-center space-x-1.5 px-3 py-1 rounded-md font-semibold text-xs transition ${
              activeTab === 'diff'
                ? 'bg-cyan-600/30 text-cyan-300 border border-cyan-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <ArrowRight className="h-3.5 w-3.5 text-cyan-400" />
            <span>Live State Diff (Δ)</span>
          </button>
          <button
            onClick={() => setActiveTab('actuation')}
            className={`flex items-center space-x-1.5 px-3 py-1 rounded-md font-semibold text-xs transition ${
              activeTab === 'actuation'
                ? 'bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Cpu className="h-3.5 w-3.5 text-emerald-400" />
            <span>Physical Gate Actuation</span>
          </button>
          <button
            onClick={() => setActiveTab('matrix')}
            className={`flex items-center space-x-1.5 px-3 py-1 rounded-md font-semibold text-xs transition ${
              activeTab === 'matrix'
                ? 'bg-amber-600/30 text-amber-300 border border-amber-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Table className="h-3.5 w-3.5 text-amber-400" />
            <span>Benchmark Matrix</span>
          </button>
        </div>

        <div className="text-[11px] font-mono text-slate-400">
          Gate Status: <strong className={gateState === 'OPEN' ? 'text-emerald-400' : 'text-amber-400'}>{gateState}</strong>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 p-3.5 overflow-y-auto">
        {/* TAB 1: AGENT INVESTIGATION */}
        {activeTab === 'investigation' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-slate-200">
                  Antigravity Managed Agent Synthesis
                </h4>
                <p className="text-[11px] text-slate-400">
                  Client-executed numerical tools evaluate KEEP_CURRENT vs OPEN_P3
                </p>
              </div>
              <button
                onClick={onRunInvestigation}
                disabled={isInvestigationLoading}
                className="flex items-center space-x-1.5 px-3 py-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded text-xs font-bold shadow-neon-cyan transition"
              >
                <Sparkles className="h-3 w-3" />
                <span>{isInvestigationLoading ? 'Investigating...' : 'Run Investigation'}</span>
              </button>
            </div>

            {investigation ? (
              <div className="space-y-2 text-xs">
                {/* Explanation Card */}
                <div className="p-2.5 rounded-lg bg-indigo-950/40 border border-indigo-800/60 text-indigo-200 text-[11px] leading-relaxed">
                  <span className="font-bold text-indigo-300 mr-1">Agent Recommendation:</span>
                  {investigation.agent_explanation}
                </div>

                {/* Candidate Envelopes */}
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  {investigation.candidate_envelopes.map((env) => {
                    const isRec = investigation.recommended_alternative === env.alternative_id;
                    return (
                      <div
                        key={env.alternative_id}
                        className={`p-2 rounded border flex flex-col justify-between ${
                          isRec
                            ? 'bg-emerald-950/20 border-emerald-500/50 text-emerald-300'
                            : 'bg-slate-900 border-slate-800 text-slate-300'
                        }`}
                      >
                        <div className="flex items-center justify-between font-mono font-bold">
                          <span>{env.alternative_id}</span>
                          {isRec && (
                            <span className="text-[9px] uppercase px-1 py-0.2 rounded bg-emerald-500/30 text-emerald-300">
                              OPTIMAL
                            </span>
                          )}
                        </div>
                        <div className="flex justify-between my-1 text-[10px]">
                          <span className="text-slate-400">Evacuated:</span>
                          <span className="font-bold text-emerald-400">
                            {env.completed_crossings} / {env.initial_population}
                          </span>
                        </div>
                        <div className="text-[9px] text-slate-500 font-mono">
                          B1: {env.boundary_breakdown['B1'] ?? 0} pers | B2: {env.boundary_breakdown['B2'] ?? 0} pers
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="p-4 rounded bg-slate-900/60 border border-slate-800 text-slate-400 text-xs text-center italic">
                Click <strong>"Run Investigation"</strong> to execute multi-turn agent evaluation against local NetworkX solver.
              </div>
            )}
          </div>
        )}

        {/* TAB: LIVE STATE DIFF (BEFORE VS AFTER) */}
        {activeTab === 'diff' && (
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between text-[11px] font-mono">
              <span className="font-bold text-slate-200">Granular Causal Impact Delta:</span>
              <span className="text-cyan-400 font-bold">KEEP_CURRENT vs OPEN_P3</span>
            </div>

            <table className="w-full text-left text-[11px] font-mono border border-slate-800 rounded overflow-hidden">
              <thead className="bg-slate-900 text-slate-400">
                <tr>
                  <th className="p-1.5">State Parameter</th>
                  <th className="p-1.5">Before (P3 Closed)</th>
                  <th className="p-1.5">After (P3 Open)</th>
                  <th className="p-1.5 text-right">Net Delta (Δ)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80 bg-slate-950">
                <tr>
                  <td className="p-1.5 text-slate-300 font-semibold">Total Evacuated</td>
                  <td className="p-1.5 text-slate-400">60 pers (50%)</td>
                  <td className="p-1.5 text-emerald-400 font-bold">117 pers (97.5%)</td>
                  <td className="p-1.5 text-right text-emerald-400 font-bold">+57 pers (+95%)</td>
                </tr>
                <tr>
                  <td className="p-1.5 text-slate-300 font-semibold">Unserviced Residual</td>
                  <td className="p-1.5 text-rose-400 font-bold">60 pers</td>
                  <td className="p-1.5 text-slate-400">3 pers</td>
                  <td className="p-1.5 text-right text-emerald-400 font-bold">-57 pers (-95%)</td>
                </tr>
                <tr>
                  <td className="p-1.5 text-slate-300 font-semibold">Exit B1 (West Transfer)</td>
                  <td className="p-1.5 text-slate-300">60 / 60 (100% quota)</td>
                  <td className="p-1.5 text-slate-300">60 / 60 (100% quota)</td>
                  <td className="p-1.5 text-right text-slate-500">0 (Maxed Out)</td>
                </tr>
                <tr>
                  <td className="p-1.5 text-slate-300 font-semibold">Exit B2 (East Transfer)</td>
                  <td className="p-1.5 text-rose-400">0 / 60 (Starved)</td>
                  <td className="p-1.5 text-emerald-400 font-bold">57 / 60 (95% full)</td>
                  <td className="p-1.5 text-right text-emerald-400 font-bold">+57 pers unlocked</td>
                </tr>
                <tr>
                  <td className="p-1.5 text-slate-300 font-semibold">Physical Servo Barrier</td>
                  <td className="p-1.5 text-amber-400">CLOSED (D2 Active)</td>
                  <td className="p-1.5 text-emerald-400">OPEN (D3 Active)</td>
                  <td className="p-1.5 text-right text-cyan-400 font-bold">Angle: 0° → 90°</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}

        {/* TAB 2: PHYSICAL GATE ACTUATION */}
        {activeTab === 'actuation' && (
          <div className="space-y-3 text-xs">
            <div>
              <h4 className="text-xs font-bold text-slate-200">
                Operator Physical Authorization Stepper
              </h4>
              <p className="text-[11px] text-slate-400">
                Physical Movement Protocol: Command ACK does NOT commit open state. Dual microswitches (D2/D3) required.
              </p>
            </div>

            {/* Stepper Status Indicators */}
            <div className="grid grid-cols-4 gap-2 text-center text-[10px] font-mono">
              <div className={`p-1.5 rounded border ${actuationStep >= 1 ? 'bg-cyan-500/20 text-cyan-300 border-cyan-400' : 'bg-slate-900 text-slate-500 border-slate-800'}`}>
                1. Operator Approved
              </div>
              <div className={`p-1.5 rounded border ${actuationStep >= 2 ? 'bg-cyan-500/20 text-cyan-300 border-cyan-400' : 'bg-slate-900 text-slate-500 border-slate-800'}`}>
                2. Command ACK
              </div>
              <div className={`p-1.5 rounded border ${actuationStep === 3 ? 'bg-amber-500/20 text-amber-300 border-amber-400 animate-pulse' : actuationStep > 3 ? 'bg-cyan-500/20 text-cyan-300 border-cyan-400' : 'bg-slate-900 text-slate-500 border-slate-800'}`}>
                3. Transit
              </div>
              <div className={`p-1.5 rounded border ${gateState === 'OPEN' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-400 font-bold' : 'bg-slate-900 text-slate-500 border-slate-800'}`}>
                4. D3 Switch Confirmed
              </div>
            </div>

            <div className="p-2.5 rounded bg-slate-900 border border-slate-800 flex items-center justify-between">
              <div>
                <div className="font-bold text-slate-200 text-xs">Servo Barrier P3</div>
                <div className="text-[10px] text-slate-500 font-mono">Target: OPEN_P3 (90° Rotation)</div>
              </div>
              <button
                onClick={handleApprove}
                disabled={isActuating || gateState === 'OPEN'}
                className="flex items-center space-x-1.5 px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded text-xs font-bold shadow-neon-emerald transition"
              >
                <Cpu className="h-3.5 w-3.5" />
                <span>
                  {gateState === 'OPEN'
                    ? 'Gate Confirmed OPEN'
                    : isActuating
                    ? 'Actuating...'
                    : 'Authorize Movement (OPEN_P3)'}
                </span>
              </button>
            </div>
          </div>
        )}

        {/* TAB 3: BENCHMARK MATRIX */}
        {activeTab === 'matrix' && (
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
              <span>Canonical 4-Condition Falsification Matrix</span>
              <span className="text-emerald-400 font-bold">100% Deterministic</span>
            </div>
            <table className="w-full text-left text-[11px] font-mono border border-slate-800 rounded overflow-hidden">
              <thead className="bg-slate-900 text-slate-400">
                <tr>
                  <th className="p-1.5">Condition</th>
                  <th className="p-1.5">Crossings</th>
                  <th className="p-1.5">Residual</th>
                  <th className="p-1.5">Net Gain</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80 bg-slate-950">
                <tr>
                  <td className="p-1.5 text-slate-300 font-semibold">1. Baseline (All Open)</td>
                  <td className="p-1.5 text-emerald-400 font-bold">120 / 120</td>
                  <td className="p-1.5 text-slate-400">0</td>
                  <td className="p-1.5 text-slate-500">Nominal</td>
                </tr>
                <tr className="bg-emerald-950/20">
                  <td className="p-1.5 text-emerald-300 font-bold">2. P2 Blocked (P3 Rescue)</td>
                  <td className="p-1.5 text-emerald-300 font-bold">117 vs 60</td>
                  <td className="p-1.5 text-slate-400">3 pers</td>
                  <td className="p-1.5 text-emerald-400 font-bold">+57 (+95%)</td>
                </tr>
                <tr className="bg-rose-950/20">
                  <td className="p-1.5 text-rose-300 font-bold">3. B2 Blocked (Falsify)</td>
                  <td className="p-1.5 text-rose-300 font-bold">60 vs 60</td>
                  <td className="p-1.5 text-amber-400">60 pers</td>
                  <td className="p-1.5 text-rose-400 font-bold">+0 (Honest Zero)</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Footer Invariant Note */}
      <div className="px-3.5 py-1.5 bg-slate-900/90 border-t border-slate-800 text-[10px] text-slate-500 font-mono flex items-center justify-between">
        <span>AI returns typed proposals only • Client runs allowlisted local numerical tools</span>
        <span className="text-emerald-400">Zero Arbitrary Serial Execution</span>
      </div>
    </div>
  );
};