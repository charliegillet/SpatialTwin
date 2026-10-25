import React, { useEffect, useState } from 'react';
import {
  HealthStatus,
  ScenarioSnapshot,
  GroundingProposalV1,
  InvestigationResult,
} from './types';
import {
  fetchHealth,
  fetchScenario,
  interpretGrounding,
  investigateScenario,
  operatorApproveGate,
  sendCommand,
  clearBlockage,
  fetchScenarioMatrix,
} from './api/client';
import { Header } from './components/Header';
import { LiveChangeTicker } from './components/LiveChangeTicker';
import { CameraFeedPanel } from './components/CameraFeedPanel';
import { BuildingTwin3D } from './components/BuildingTwin3D';
import { TerminalConsole, LogEntry } from './components/TerminalConsole';
import { AgentCockpitPanel } from './components/AgentCockpitPanel';
import { LedStickVisualizer } from './components/LedStickVisualizer';
import { PlanView2D } from './components/PlanView2D';
import { AuditDrawer } from './components/AuditDrawer';
import { LayoutGrid, Map, ShieldAlert, Sparkles, ChevronDown, ChevronUp } from 'lucide-react';
import { sounds } from './utils/audio';

export const App: React.FC = () => {
  const [snapshot, setSnapshot] = useState<ScenarioSnapshot | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [activeMainView, setActiveMainView] = useState<'cockpit' | 'blueprint'>('cockpit');
  const [selectedTarget, setSelectedTarget] = useState<string | null>(null);
  const [isJudgeMode, setIsJudgeMode] = useState<boolean>(true);

  // AI & Proposal States
  const [proposal, setProposal] = useState<GroundingProposalV1 | null>(null);
  const [investigation, setInvestigation] = useState<InvestigationResult | null>(null);
  const [matrixData, setMatrixData] = useState<any | null>(null);
  const [thinkingLevel, setThinkingLevel] = useState<'low' | 'medium' | 'high'>('low');
  const [isGroundingLoading, setIsGroundingLoading] = useState<boolean>(false);
  const [isInvestigationLoading, setIsInvestigationLoading] = useState<boolean>(false);
  const [showBlueprintDrawer, setShowBlueprintDrawer] = useState<boolean>(false);

  // Real-time Hacker Terminal Logs
  const [logs, setLogs] = useState<LogEntry[]>([
    {
      id: 'log-0',
      timestamp: new Date().toISOString().substring(11, 19),
      category: 'SYS',
      level: 'INFO',
      message: 'SpatialTwin initialized. Connecting to SHACK15 Demo Stage.',
    },
    {
      id: 'log-1',
      timestamp: new Date().toISOString().substring(11, 19),
      category: 'HARDWARE',
      level: 'SUCCESS',
      message: 'Hardware bridge connected: HELLO_ACK received. Microswitches D2=LOW, D3=HIGH.',
    },
    {
      id: 'log-2',
      timestamp: new Date().toISOString().substring(11, 19),
      category: 'ARGON',
      level: 'INFO',
      message: 'Gemini 4 Argon perception ready: Camera 1 streaming at 1080p 60fps.',
    },
    {
      id: 'log-3',
      timestamp: new Date().toISOString().substring(11, 19),
      category: 'SOLVER',
      level: 'INFO',
      message: 'Nominal flow solver: 120 synthetic occupants conserved across B1/B2.',
    },
  ]);

  const addLog = (
    category: LogEntry['category'],
    level: LogEntry['level'],
    message: string
  ) => {
    const newEntry: LogEntry = {
      id: `log-${Date.now()}-${Math.random().toString(36).substring(7)}`,
      timestamp: new Date().toISOString().substring(11, 19),
      category,
      level,
      message,
    };
    setLogs((prev) => [...prev.slice(-150), newEntry]);
  };

  // Initial load & SSE subscription
  useEffect(() => {
    fetchHealth()
      .then((h) => {
        setHealth(h);
        addLog('SYS', 'SUCCESS', `Backend health check OK: ${h.hardware_mode} active.`);
      })
      .catch((e) => addLog('SYS', 'ALERT', `Health check failed: ${e.message}`));

    fetchScenario()
      .then((s) => {
        setSnapshot(s);
        addLog(
          'SOLVER',
          'INFO',
          `Loaded scenario r${s.context.scenario_revision} (${s.context.geometry_revision}). Initial population: 120.`
        );
      })
      .catch(console.error);

    fetchScenarioMatrix().then(setMatrixData).catch(console.error);

    // SSE Stream
    const eventSource = new EventSource('/api/scenarios/facility-demo/events');

    eventSource.addEventListener('snapshot', (e) => {
      try {
        const data = JSON.parse(e.data);
        setSnapshot(data);
      } catch (err) {
        console.error('Failed to parse snapshot SSE:', err);
      }
    });

    eventSource.addEventListener('scenario_updated', (e) => {
      try {
        const data = JSON.parse(e.data);
        setSnapshot(data);
        addLog(
          'SOLVER',
          'WARN',
          `Scenario revision advanced to r${data.context.scenario_revision}. Blocked portals: [${data.blocked_portals?.join(
            ', '
          )}], Boundaries: [${data.blocked_boundaries?.join(', ')}]. Completed crossings: ${
            data.current_plan?.completed_crossings ?? 0
          }/120.`
        );
      } catch (err) {
        console.error('Failed to parse scenario_updated SSE:', err);
      }
    });

    eventSource.addEventListener('physical_state_confirmed', (e) => {
      try {
        const data = JSON.parse(e.data);
        setSnapshot(data);
        addLog(
          'HARDWARE',
          'SUCCESS',
          `Endpoint switch contact confirmed! Physical revision r${data.context.physical_revision}. Gate state: ${data.physical_gate_state}.`
        );
      } catch (err) {
        console.error('Failed to parse physical_state_confirmed SSE:', err);
      }
    });

    return () => {
      eventSource.close();
    };
  }, []);

  // Reset scenario
  const handleReset = async () => {
    if (!snapshot) return;
    try {
      const res = await sendCommand('facility-demo', {
        type: 'RESET_SCENARIO',
        expected_scenario_revision: snapshot.context.scenario_revision,
        idempotency_key: `reset-${Date.now()}-${Math.random().toString(36).substring(7)}`,
      });
      setSnapshot(res.snapshot);
      setSelectedTarget(null);
      setProposal(null);
      setInvestigation(null);
      addLog('SYS', 'INFO', 'RESET_SCENARIO executed. Restored nominal baseline.');
    } catch (e: any) {
      alert(`Reset failed: ${e.message}`);
    }
  };

  // Apply blockage
  const handleApplyBlockage = async (
    targetType: 'portal' | 'boundary',
    targetId: 'P1' | 'P2' | 'B2'
  ) => {
    if (!snapshot) return;
    try {
      addLog('ARGON', 'WARN', `Applying blockage mutation on ${targetType}:${targetId}...`);
      const res = await sendCommand('facility-demo', {
        type: 'APPLY_BLOCKAGE',
        expected_scenario_revision: snapshot.context.scenario_revision,
        idempotency_key: `cmd-${Date.now()}-${Math.random().toString(36).substring(7)}`,
        target_type: targetType,
        target_id: targetId,
        source: 'manual_override',
      });
      setSnapshot(res.snapshot);
      sounds.playBlockAlert();
    } catch (e: any) {
      alert(`Failed to apply blockage: ${e.message}`);
    }
  };

  // Toggle hazard (Touch interaction in 3D Cutaway)
  const handleToggleHazard = async (
    targetType: 'portal' | 'boundary',
    targetId: 'P1' | 'P2' | 'B2'
  ) => {
    if (!snapshot) return;
    const isCurrentlyBlocked =
      targetType === 'portal'
        ? snapshot.blocked_portals?.includes(targetId)
        : snapshot.blocked_boundaries?.includes(targetId);

    if (isCurrentlyBlocked) {
      try {
        addLog('SYS', 'INFO', `Clearing blockage on ${targetType}:${targetId}...`);
        const res = await clearBlockage(
          'facility-demo',
          snapshot.context.scenario_revision,
          targetType,
          targetId
        );
        setSnapshot(res.snapshot);
        sounds.playGateConfirmed();
      } catch (e: any) {
        alert(`Failed to clear blockage: ${e.message}`);
      }
    } else {
      await handleApplyBlockage(targetType, targetId);
    }
  };

  // Grounding
  const handleTriggerGrounding = async (
    imageBase64?: string,
    targetOverride?: string,
    level: 'low' | 'medium' | 'high' = 'low'
  ) => {
    setIsGroundingLoading(true);
    addLog(
      'ARGON',
      'INFO',
      `Invoking gemini-4-argon multimodal vision (thinking_level=${level})...`
    );
    try {
      const res = await interpretGrounding('facility-demo', {
        targetOverride,
        thinkingLevel: level,
        imageBase64,
      });
      setProposal(res.proposal);
      addLog(
        'ARGON',
        'SUCCESS',
        `Perception output: status=${res.proposal.status}, target=${res.proposal.selected_entity_type}:${
          res.proposal.selected_entity_id ?? 'none'
        }, box=${JSON.stringify(res.proposal.box_2d)}.`
      );
      return res.proposal;
    } catch (err: any) {
      addLog('ARGON', 'ALERT', `Grounding perception failed: ${err.message}`);
      throw err;
    } finally {
      setIsGroundingLoading(false);
    }
  };

  // Apply detected proposal
  const handleApplyProposal = async () => {
    if (!proposal || !proposal.selected_entity_type || !proposal.selected_entity_id) {
      await handleApplyBlockage('portal', 'P2');
      return;
    }
    await handleApplyBlockage(
      proposal.selected_entity_type,
      proposal.selected_entity_id as 'P1' | 'P2' | 'B2'
    );
  };

  // Investigation
  const handleRunInvestigation = async () => {
    setIsInvestigationLoading(true);
    addLog(
      'AGENT',
      'INFO',
      'Starting Antigravity multi-turn agent interaction (antigravity-preview-09-2026)...'
    );
    try {
      const res = await investigateScenario('facility-demo');
      setInvestigation(res.investigation);
      addLog(
        'AGENT',
        'SUCCESS',
        `Agent synthesis completed: recommended=${res.investigation.recommended_alternative}, tools_executed=${res.investigation.tool_ledger.length}.`
      );
      sounds.playAgentSuccess();
      return res.investigation;
    } catch (err: any) {
      addLog('AGENT', 'ALERT', `Investigation failed: ${err.message}`);
      throw err;
    } finally {
      setIsInvestigationLoading(false);
    }
  };

  // Physical Gate Approval
  const handleOperatorApproveGate = async () => {
    if (!snapshot) return;
    addLog(
      'HARDWARE',
      'WARN',
      'Operator confirmed gate movement command (OPEN_P3). Dispatching to serial bridge...'
    );
    await operatorApproveGate('OPEN_P3', snapshot.context.scenario_revision);
  };

  // Quick Presets from Header
  const handleQuickPreset = async (preset: 'nominal' | 'p2_blocked' | 'b2_blocked') => {
    if (preset === 'nominal') {
      await handleReset();
    } else if (preset === 'p2_blocked') {
      await handleApplyBlockage('portal', 'P2');
    } else if (preset === 'b2_blocked') {
      await handleApplyBlockage('boundary', 'B2');
    }
  };

  return (
    <div className="min-h-screen bg-[#050811] text-slate-100 flex flex-col font-sans bg-blueprint-grid bg-tactical-radial select-none">
      {/* Header */}
      <Header
        snapshot={snapshot}
        health={health}
        onReset={handleReset}
        isJudgeMode={isJudgeMode}
        setIsJudgeMode={setIsJudgeMode}
        onQuickPreset={handleQuickPreset}
      />

      {/* Main Mission Control Layout */}
      <main className="flex-1 p-3.5 lg:p-5 max-w-[1680px] mx-auto w-full space-y-4">
        {/* Real-time State & Delta Ticker */}
        <LiveChangeTicker snapshot={snapshot} />

        {/* TOP ROW: Camera 1 Viewport (Left) & 3D Building Twin (Right) - Matching Reference Photo */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Top-Left: Camera 1 Panel */}
          <div className="lg:col-span-5">
            <CameraFeedPanel
              onCaptureFrame={handleTriggerGrounding}
              proposal={proposal}
              thinkingLevel={thinkingLevel}
              setThinkingLevel={setThinkingLevel}
              onApplyProposal={handleApplyProposal}
              isGroundingLoading={isGroundingLoading}
            />
          </div>

          {/* Top-Right: 3D Spatial Twin Simulation (With Rising Smoke Plume & Neon Green Arrows) */}
          <div className="lg:col-span-7">
            <BuildingTwin3D
              snapshot={snapshot}
              onToggleHazard={handleToggleHazard}
              onTriggerArgonScan={async (t) => {
                await handleTriggerGrounding(undefined, t, thinkingLevel);
              }}
              selectedTarget={selectedTarget}
              onSelectTarget={setSelectedTarget}
            />
          </div>
        </div>

        {/* MIDDLE ROW: Live System Telemetry Console (Left) & Managed Agent Cockpit (Right) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Middle-Left: Live Phosphor Green Terminal Telemetry Console */}
          <div className="lg:col-span-6">
            <TerminalConsole logs={logs} onClear={() => setLogs([])} />
          </div>

          {/* Middle-Right: Antigravity Managed Agent & Physical Actuation Stepper */}
          <div className="lg:col-span-6">
            <AgentCockpitPanel
              snapshot={snapshot}
              investigation={investigation}
              onRunInvestigation={handleRunInvestigation}
              onOperatorApproveGate={handleOperatorApproveGate}
              matrixData={matrixData}
              isInvestigationLoading={isInvestigationLoading}
            />
          </div>
        </div>

        {/* BOTTOM SECTION: Hardware LED Strip Visualizer (24 NeoPixels) */}
        <LedStickVisualizer snapshot={snapshot} />

        {/* Collapsible 2D Technical Blueprint Drawer */}
        <div className="bg-slate-950/90 rounded-xl border border-slate-800/80 overflow-hidden shadow-xl text-xs">
          <button
            onClick={() => setShowBlueprintDrawer(!showBlueprintDrawer)}
            className="w-full px-4 py-2.5 flex items-center justify-between bg-slate-900/60 hover:bg-slate-900 transition text-slate-300 font-mono"
          >
            <div className="flex items-center space-x-2">
              <Map className="h-4 w-4 text-cyan-400" />
              <span className="font-bold text-slate-200">2D Tabletop Blueprint & 40-Second Flow Timeline Scrubber</span>
              <span className="text-slate-500">•</span>
              <span className="text-cyan-400 text-[11px]">NetworkX Min-Cost Finite-Horizon Graph Solver</span>
            </div>
            <div className="flex items-center space-x-2 text-slate-400 text-[11px]">
              <span>{showBlueprintDrawer ? 'Collapse 2D Blueprint' : 'Expand 2D Timeline Scrubber'}</span>
              {showBlueprintDrawer ? <ChevronUp className="h-4 w-4 text-cyan-400" /> : <ChevronDown className="h-4 w-4 text-cyan-400" />}
            </div>
          </button>

          {showBlueprintDrawer && (
            <div className="p-4 border-t border-slate-800">
              <PlanView2D
                snapshot={snapshot}
                onSelectTarget={(t, id) => setSelectedTarget(`${t}:${id}`)}
                selectedTarget={selectedTarget}
              />
            </div>
          )}
        </div>

        {/* Cryptographic Proof & Formal Constraint Audit Drawer */}
        <AuditDrawer snapshot={snapshot} />
      </main>
    </div>
  );
};