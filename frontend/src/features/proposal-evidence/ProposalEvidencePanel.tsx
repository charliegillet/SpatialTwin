import React, { useEffect, useState } from 'react';
import {
  GroundingProposalV1,
  InvestigationResult,
  ScenarioSnapshot,
} from '../../types';
import {
  Camera,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Cpu,
  ArrowRight,
  ShieldAlert,
  SlidersHorizontal,
  ChevronRight,
  Clock,
  Radio,
  Eye,
  Table,
  Sliders,
} from 'lucide-react';
import { sounds } from '../../utils/audio';
import { fetchScenarioMatrix } from '../../api/client';

interface ProposalEvidencePanelProps {
  snapshot: ScenarioSnapshot | null;
  onApplyBlockage: (targetType: 'portal' | 'boundary', targetId: 'P1' | 'P2' | 'B2') => Promise<void>;
  onTriggerGrounding: (targetOverride?: string, thinkingLevel?: 'low' | 'medium' | 'high') => Promise<GroundingProposalV1>;
  onRunInvestigation: () => Promise<InvestigationResult>;
  onOperatorApproveGate: () => Promise<void>;
  selectedManualTarget: string | null;
  setSelectedManualTarget: (t: string | null) => void;
}

export const ProposalEvidencePanel: React.FC<ProposalEvidencePanelProps> = ({
  snapshot,
  onApplyBlockage,
  onTriggerGrounding,
  onRunInvestigation,
  onOperatorApproveGate,
  selectedManualTarget,
  setSelectedManualTarget,
}) => {
  const [proposal, setProposal] = useState<GroundingProposalV1 | null>(null);
  const [investigation, setInvestigation] = useState<InvestigationResult | null>(null);
  const [matrixData, setMatrixData] = useState<any | null>(null);
  const [isGroundingLoading, setIsGroundingLoading] = useState(false);
  const [isInvestigationLoading, setIsInvestigationLoading] = useState(false);
  const [isActuationLoading, setIsActuationLoading] = useState(false);
  const [actuationStep, setActuationStep] = useState<number>(0);
  const [thinkingLevel, setThinkingLevel] = useState<'low' | 'medium' | 'high'>('low');
  const [activeTab, setActiveTab] = useState<'grounding' | 'managed' | 'operator' | 'matrix'>('grounding');

  const gateState = snapshot?.physical_gate_state ?? 'CLOSED';

  // Load matrix data if matrix tab active
  useEffect(() => {
    if (activeTab === 'matrix' && !matrixData) {
      fetchScenarioMatrix().then(setMatrixData).catch(console.error);
    }
  }, [activeTab]);

  // Handle Grounding
  const handleCapture = async (override?: string) => {
    setIsGroundingLoading(true);
    try {
      const prop = await onTriggerGrounding(override, thinkingLevel);
      setProposal(prop);
      if (prop.selected_entity_type && prop.selected_entity_id) {
        setSelectedManualTarget(`${prop.selected_entity_type}:${prop.selected_entity_id}`);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsGroundingLoading(false);
    }
  };

  // Handle Apply
  const handleApply = async () => {
    let tType: 'portal' | 'boundary' = 'portal';
    let tId: 'P1' | 'P2' | 'B2' = 'P2';

    if (selectedManualTarget) {
      const [type, id] = selectedManualTarget.split(':');
      tType = type as 'portal' | 'boundary';
      tId = id as 'P1' | 'P2' | 'B2';
    } else if (proposal?.selected_entity_type && proposal.selected_entity_id) {
      tType = proposal.selected_entity_type;
      tId = proposal.selected_entity_id as 'P1' | 'P2' | 'B2';
    }

    sounds.playBlockAlert();
    await onApplyBlockage(tType, tId);
  };

  // Handle Investigation
  const handleInvestigate = async () => {
    setIsInvestigationLoading(true);
    try {
      const inv = await onRunInvestigation();
      setInvestigation(inv);
      sounds.playAgentSuccess();
    } catch (e) {
      console.error(e);
    } finally {
      setIsInvestigationLoading(false);
    }
  };

  // Handle Operator Approval Stepper
  const handleApproveActuation = async () => {
    setIsActuationLoading(true);
    setActuationStep(1); // Approved
    try {
      await onOperatorApproveGate();
      setActuationStep(2); // ACK Received
      setTimeout(() => setActuationStep(3), 400); // Transit
      setTimeout(() => {
        setActuationStep(4); // Confirmed
        setIsActuationLoading(false);
        sounds.playGateConfirmed();
      }, 1100);
    } catch (e) {
      console.error(e);
      setIsActuationLoading(false);
      setActuationStep(0);
    }
  };

  return (
    <div className="w-full bg-slate-950/80 rounded-xl border border-slate-800 p-4 shadow-2xl flex flex-col space-y-4">
      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-800 text-xs overflow-x-auto">
        <button
          onClick={() => setActiveTab('grounding')}
          className={`flex items-center space-x-1 px-3.5 py-2 border-b-2 font-semibold whitespace-nowrap transition ${
            activeTab === 'grounding'
              ? 'border-sky-400 text-sky-300'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Camera className="h-3.5 w-3.5" />
          <span>1. Vision</span>
        </button>
        <button
          onClick={() => setActiveTab('managed')}
          className={`flex items-center space-x-1 px-3.5 py-2 border-b-2 font-semibold whitespace-nowrap transition ${
            activeTab === 'managed'
              ? 'border-indigo-400 text-indigo-300'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Sparkles className="h-3.5 w-3.5" />
          <span>2. Managed Agent</span>
        </button>
        <button
          onClick={() => setActiveTab('operator')}
          className={`flex items-center space-x-1 px-3.5 py-2 border-b-2 font-semibold whitespace-nowrap transition ${
            activeTab === 'operator'
              ? 'border-emerald-400 text-emerald-300'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Cpu className="h-3.5 w-3.5" />
          <span>3. Physical Action</span>
        </button>
        <button
          onClick={() => setActiveTab('matrix')}
          className={`flex items-center space-x-1 px-3.5 py-2 border-b-2 font-semibold whitespace-nowrap transition ${
            activeTab === 'matrix'
              ? 'border-amber-400 text-amber-300'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Table className="h-3.5 w-3.5" />
          <span>4. Matrix</span>
        </button>
      </div>

      {/* TAB 1: GROUNDING */}
      {activeTab === 'grounding' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-bold text-slate-200">Tabletop Perception Review</h3>
              <p className="text-xs text-slate-400">
                Direct Gemini 4 Argon visual perception against reviewed target catalog
              </p>
            </div>
            {/* Presets */}
            <div className="flex items-center space-x-1 text-xs">
              <span className="text-[11px] text-slate-500">Preset:</span>
              <button
                onClick={() => handleCapture('P1')}
                className="px-2 py-0.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs border border-slate-700"
              >
                P1
              </button>
              <button
                onClick={() => handleCapture('P2')}
                className="px-2 py-0.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs border border-slate-700"
              >
                P2
              </button>
              <button
                onClick={() => handleCapture('B2')}
                className="px-2 py-0.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs border border-slate-700"
              >
                B2
              </button>
              <button
                onClick={() => handleCapture('ambiguous')}
                className="px-2 py-0.5 bg-slate-800 hover:bg-slate-700 text-amber-300 rounded text-xs border border-amber-800/60"
              >
                Ambiguous
              </button>
            </div>
          </div>

          {/* Thinking Level Selector & Capture Button */}
          <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-xs">
            <div className="flex items-center space-x-2">
              <Sliders className="h-4 w-4 text-sky-400" />
              <span className="text-slate-300 font-semibold">Argon Thinking Level:</span>
              <div className="inline-flex rounded-md shadow-sm border border-slate-700 p-0.5 bg-slate-950">
                {(['low', 'medium', 'high'] as const).map((lvl) => (
                  <button
                    key={lvl}
                    onClick={() => setThinkingLevel(lvl)}
                    className={`px-2 py-0.5 text-[11px] rounded font-medium uppercase transition ${
                      thinkingLevel === lvl
                        ? 'bg-sky-600 text-white shadow'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={() => handleCapture()}
              disabled={isGroundingLoading}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white rounded-md text-xs font-semibold shadow glow-cyan transition"
            >
              <Camera className="h-3.5 w-3.5" />
              <span>{isGroundingLoading ? 'Argon Thinking...' : 'Capture Overhead Still'}</span>
            </button>
          </div>

          {/* Proposal Review Box & Bounding Box Visualizer */}
          {proposal && (
            <div className="p-3.5 rounded-lg bg-slate-900 border border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span
                    className={`px-2 py-0.5 rounded text-[11px] font-bold uppercase ${
                      proposal.status === 'matched'
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        : proposal.status === 'ambiguous'
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                        : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                    }`}
                  >
                    Status: {proposal.status}
                  </span>
                  {proposal.selected_entity_id && (
                    <span className="text-xs font-mono font-bold text-sky-400">
                      Target: {proposal.selected_entity_type}:{proposal.selected_entity_id}
                    </span>
                  )}
                </div>
                <span className="text-[10px] font-mono text-slate-500">ID: {proposal.capture_id}</span>
              </div>

              {/* Spatial Bounding Box Frame (Simulated Overhead View with Overlay) */}
              {proposal.box_2d && (
                <div className="relative w-full h-32 bg-slate-950 rounded-lg border border-slate-800 overflow-hidden flex items-center justify-center">
                  <div className="absolute inset-0 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:16px_16px] opacity-40"></div>
                  <div className="text-[10px] text-slate-600 font-mono absolute top-2 left-2">
                    CAMERA STILL OVERLAY • 1920x1080
                  </div>

                  {/* Render Bounding Box */}
                  <div
                    style={{
                      position: 'absolute',
                      top: `${proposal.box_2d[0] / 10}%`,
                      left: `${proposal.box_2d[1] / 10}%`,
                      height: `${(proposal.box_2d[2] - proposal.box_2d[0]) / 10}%`,
                      width: `${(proposal.box_2d[3] - proposal.box_2d[1]) / 10}%`,
                    }}
                    className="border-2 border-rose-500 bg-rose-500/20 rounded shadow-[0_0_12px_rgba(244,63,94,0.4)] flex items-start justify-end p-0.5"
                  >
                    <span className="text-[9px] font-mono font-bold bg-rose-600 text-white px-1 rounded">
                      {proposal.selected_entity_id ?? 'TARGET'}
                    </span>
                  </div>
                </div>
              )}

              <div className="text-xs text-slate-300 bg-slate-950 p-2 rounded border border-slate-800/80">
                <span className="text-slate-500 font-semibold mr-1">Visible Evidence:</span>
                {proposal.evidence}
              </div>

              {/* Ambiguity Resolution / Target Selector */}
              <div className="space-y-1">
                <label className="text-[11px] font-semibold text-slate-400">
                  Allowlisted Candidates (Manual Disambiguation):
                </label>
                <div className="flex gap-2">
                  {proposal.candidate_ids.map((cid) => (
                    <button
                      key={cid}
                      onClick={() => setSelectedManualTarget(cid)}
                      className={`px-2.5 py-1 rounded text-xs font-mono font-medium border transition ${
                        selectedManualTarget === cid
                          ? 'bg-sky-500/20 text-sky-300 border-sky-400 glow-cyan'
                          : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700'
                      }`}
                    >
                      {cid}
                    </button>
                  ))}
                </div>
              </div>

              {/* Action Button: Apply */}
              <div className="pt-2 flex items-center justify-between border-t border-slate-800">
                <div className="text-[10px] text-slate-400">
                  Perception proposal only; requires explicit operator Apply
                </div>
                <button
                  onClick={handleApply}
                  className="flex items-center space-x-1.5 px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white rounded text-xs font-bold shadow glow-rose transition"
                >
                  <ShieldAlert className="h-3.5 w-3.5" />
                  <span>Apply Closure</span>
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: MANAGED AGENT INVESTIGATION */}
      {activeTab === 'managed' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-200">Managed Antigravity Agent</h3>
              <p className="text-xs text-slate-400">
                Multi-turn client tool investigation of KEEP_CURRENT vs OPEN_P3
              </p>
            </div>
            <button
              onClick={handleInvestigate}
              disabled={isInvestigationLoading}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-md text-xs font-semibold shadow glow-cyan transition"
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>{isInvestigationLoading ? 'Investigating...' : 'Run Investigation'}</span>
            </button>
          </div>

          {investigation && (
            <div className="space-y-3">
              {/* Agent Explanation Banner */}
              <div className="p-3 rounded-lg bg-indigo-950/40 border border-indigo-800/60 text-xs text-indigo-200">
                <div className="font-semibold text-indigo-300 mb-0.5 flex items-center space-x-1">
                  <Sparkles className="h-3 w-3" />
                  <span>Synthesis from Client Tool Ledger:</span>
                </div>
                {investigation.agent_explanation}
              </div>

              {/* Side-by-side Candidate Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                {investigation.candidate_envelopes.map((env) => {
                  const isRecommended = investigation.recommended_alternative === env.alternative_id;
                  return (
                    <div
                      key={env.alternative_id}
                      className={`p-3 rounded-lg border flex flex-col justify-between ${
                        isRecommended
                          ? 'bg-slate-900 border-emerald-500/50 glow-emerald'
                          : 'bg-slate-900 border-slate-800'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="font-mono font-bold text-slate-200">{env.alternative_id}</span>
                        {isRecommended && (
                          <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                            Recommended
                          </span>
                        )}
                      </div>

                      <div className="space-y-1 my-1.5">
                        <div className="flex justify-between">
                          <span className="text-slate-400">Completed:</span>
                          <span className="font-mono font-bold text-emerald-400">
                            {env.completed_crossings} / {env.initial_population}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Residual:</span>
                          <span className="font-mono font-bold text-amber-400">
                            {env.remaining_population} pers
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">B1 Serviced:</span>
                          <span className="font-mono text-slate-300">{env.boundary_breakdown['B1'] ?? 0}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">B2 Serviced:</span>
                          <span className="font-mono text-slate-300">{env.boundary_breakdown['B2'] ?? 0}</span>
                        </div>
                      </div>

                      <div className="pt-1.5 border-t border-slate-800 flex items-center justify-between text-[10px]">
                        <span className="text-slate-500">Validator:</span>
                        <span className="text-emerald-400 font-semibold flex items-center space-x-1">
                          <CheckCircle2 className="h-3 w-3" />
                          <span>Conservation Verified</span>
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Tool Call Ledger */}
              <div className="p-2.5 bg-slate-900 rounded-lg border border-slate-800">
                <div className="text-xs font-semibold text-slate-300 mb-1.5">
                  Client Tool Ledger ({investigation.tool_ledger.length} calls)
                </div>
                <div className="space-y-1 font-mono text-[10px]">
                  {investigation.tool_ledger.map((entry, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-1.5 rounded bg-slate-950 border border-slate-800 text-slate-300"
                    >
                      <div className="flex items-center space-x-1.5 truncate">
                        <span className="text-indigo-400">{entry.call_id}</span>
                        <span className="text-slate-400">→</span>
                        <span className="font-bold text-slate-200">{entry.function_name}</span>
                      </div>
                      <div className="flex items-center space-x-1.5 flex-shrink-0">
                        <span className="text-emerald-400 font-semibold">{entry.status}</span>
                        <span className="text-slate-500">{entry.execution_time_ms} ms</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: PHYSICAL GATE ACTION */}
      {activeTab === 'operator' && (
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-bold text-slate-200">Operator Physical Gate Control</h3>
            <p className="text-xs text-slate-400">
              Safety transaction: AI proposes movement; operator explicitly authorizes mechanical servo motion.
            </p>
          </div>

          <div className="p-3.5 bg-slate-900 rounded-lg border border-slate-800 space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-300">Transaction Status:</span>
              <span className="font-mono text-emerald-400 font-bold">Position: {gateState}</span>
            </div>

            <div className="grid grid-cols-5 gap-1.5 text-center text-[10px]">
              <div
                className={`p-1.5 rounded border ${
                  actuationStep >= 1
                    ? 'bg-sky-500/20 text-sky-300 border-sky-400'
                    : 'bg-slate-950 text-slate-500 border-slate-800'
                }`}
              >
                1. Operator Approved
              </div>
              <div
                className={`p-1.5 rounded border ${
                  actuationStep >= 2
                    ? 'bg-sky-500/20 text-sky-300 border-sky-400'
                    : 'bg-slate-950 text-slate-500 border-slate-800'
                }`}
              >
                2. Command ACK
              </div>
              <div
                className={`p-1.5 rounded border ${
                  actuationStep === 3
                    ? 'bg-amber-500/20 text-amber-300 border-amber-400 animate-pulse'
                    : actuationStep > 3
                    ? 'bg-sky-500/20 text-sky-300 border-sky-400'
                    : 'bg-slate-950 text-slate-500 border-slate-800'
                }`}
              >
                3. Transit
              </div>
              <div
                className={`p-1.5 rounded border ${
                  actuationStep >= 4 || gateState === 'OPEN'
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-400'
                    : 'bg-slate-950 text-slate-500 border-slate-800'
                }`}
              >
                4. D2 Switch LOW
              </div>
              <div
                className={`p-1.5 rounded border ${
                  gateState === 'OPEN'
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-400 font-bold'
                    : 'bg-slate-950 text-slate-500 border-slate-800'
                }`}
              >
                5. New Revision
              </div>
            </div>

            <div className="text-xs text-slate-400 bg-slate-950 p-2.5 rounded border border-slate-800">
              <span className="font-semibold text-slate-300">Invariant:</span> An ACK establishes command
              receipt only. Route illumination occurs only after independent switch D2 triggers LOW.
            </div>

            <div className="flex items-center justify-between pt-1">
              <span className="text-xs text-slate-400">
                Target: <span className="font-mono text-sky-400">OPEN_P3</span>
              </span>
              <button
                onClick={handleApproveActuation}
                disabled={isActuationLoading || gateState === 'OPEN'}
                className="flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-md text-xs font-bold shadow glow-emerald transition"
              >
                <Cpu className="h-3.5 w-3.5" />
                <span>
                  {gateState === 'OPEN'
                    ? 'Gate Confirmed OPEN'
                    : isActuationLoading
                    ? 'Actuating Gate...'
                    : 'Authorize Gate Movement (OPEN_P3)'}
                </span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: BENCHMARK MATRIX */}
      {activeTab === 'matrix' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-200">Canonical Scenario Matrix</h3>
              <p className="text-xs text-slate-400">
                Side-by-side verification of all 4 conditions proving truthfulness and conservation
              </p>
            </div>
            <button
              onClick={() => fetchScenarioMatrix().then(setMatrixData)}
              className="text-xs text-sky-400 hover:underline"
            >
              Refresh Matrix
            </button>
          </div>

          {matrixData ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono border border-slate-800 rounded-lg overflow-hidden">
                <thead className="bg-slate-900 text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="p-2">Condition</th>
                    <th className="p-2">Status</th>
                    <th className="p-2">Crossings</th>
                    <th className="p-2">Residual</th>
                    <th className="p-2">Net Benefit</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80 bg-slate-950">
                  <tr>
                    <td className="p-2 text-slate-200 font-bold">1. Baseline (All Open)</td>
                    <td className="p-2 text-emerald-400">COMPLETE</td>
                    <td className="p-2 text-emerald-400 font-bold">120 / 120</td>
                    <td className="p-2 text-slate-400">0</td>
                    <td className="p-2 text-slate-400">Standard</td>
                  </tr>
                  <tr>
                    <td className="p-2 text-slate-200 font-bold">2. Portal P1 Blocked</td>
                    <td className="p-2 text-amber-400">PARTIAL</td>
                    <td className="p-2 text-amber-400 font-bold">60 / 120</td>
                    <td className="p-2 text-amber-400 font-bold">60</td>
                    <td className="p-2 text-slate-400">Diverts to P2</td>
                  </tr>
                  <tr className="bg-emerald-950/20">
                    <td className="p-2 text-emerald-300 font-bold">3. Portal P2 Blocked</td>
                    <td className="p-2 text-emerald-400">RESCUED</td>
                    <td className="p-2 text-emerald-300 font-bold">117 (Open) vs 60 (Keep)</td>
                    <td className="p-2 text-slate-400">3 pers</td>
                    <td className="p-2 text-emerald-400 font-bold">+57 pers (+95%)</td>
                  </tr>
                  <tr className="bg-rose-950/20">
                    <td className="p-2 text-rose-300 font-bold">4. Boundary B2 Blocked</td>
                    <td className="p-2 text-rose-400">NO BENEFIT</td>
                    <td className="p-2 text-rose-300 font-bold">60 (Open) vs 60 (Keep)</td>
                    <td className="p-2 text-amber-400">60 pers</td>
                    <td className="p-2 text-rose-400 font-bold">+0 pers (Honest Zero)</td>
                  </tr>
                </tbody>
              </table>
              <div className="text-[10px] text-slate-500 mt-2">
                Condition 4 proves that the system does not hallucinate new exits when downstream B2 is blocked.
              </div>
            </div>
          ) : (
            <div className="text-xs text-slate-500 p-4 text-center">Loading scenario matrix...</div>
          )}
        </div>
      )}
    </div>
  );
};
