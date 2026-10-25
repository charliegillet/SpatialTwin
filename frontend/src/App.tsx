import React, { useEffect, useState } from 'react';
import { HealthStatus, ScenarioSnapshot } from './types';
import {
  fetchHealth,
  fetchScenario,
  interpretGrounding,
  investigateScenario,
  operatorApproveGate,
  sendCommand,
  clearBlockage,
} from './api/client';
import { Header } from './components/Header';
import { PlanView2D } from './components/PlanView2D';
import { CutawayView3D } from './components/CutawayView3D';
import { LedStickVisualizer } from './components/LedStickVisualizer';
import { ProposalEvidencePanel } from './features/proposal-evidence/ProposalEvidencePanel';
import { AuditDrawer } from './components/AuditDrawer';
import { Map, Layers } from 'lucide-react';

export const App: React.FC = () => {
  const [snapshot, setSnapshot] = useState<ScenarioSnapshot | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [activeView, setActiveView] = useState<'2d' | '3d'>('2d');
  const [selectedTarget, setSelectedTarget] = useState<string | null>(null);
  const [isJudgeMode, setIsJudgeMode] = useState<boolean>(false);

  // Initial load & SSE subscription
  useEffect(() => {
    fetchHealth().then(setHealth).catch(console.error);
    fetchScenario().then(setSnapshot).catch(console.error);

    // Setup SSE connection
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
      } catch (err) {
        console.error('Failed to parse scenario_updated SSE:', err);
      }
    });

    eventSource.addEventListener('physical_state_confirmed', (e) => {
      try {
        const data = JSON.parse(e.data);
        setSnapshot(data);
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
      const res = await sendCommand('facility-demo', {
        type: 'APPLY_BLOCKAGE',
        expected_scenario_revision: snapshot.context.scenario_revision,
        idempotency_key: `cmd-${Date.now()}-${Math.random().toString(36).substring(7)}`,
        target_type: targetType,
        target_id: targetId,
        source: 'manual_override',
      });
      setSnapshot(res.snapshot);
    } catch (e: any) {
      alert(`Failed to apply blockage: ${e.message}`);
    }
  };

  // Toggle hazard (Touch interaction in 3D Cutaway or 2D Plan)
  const handleToggleHazard = async (
    targetType: 'portal' | 'boundary',
    targetId: 'P1' | 'P2' | 'B2'
  ) => {
    if (!snapshot) return;
    const isCurrentlyBlocked = targetType === 'portal'
      ? snapshot.blocked_portals?.includes(targetId)
      : snapshot.blocked_boundaries?.includes(targetId);

    if (isCurrentlyBlocked) {
      try {
        const res = await clearBlockage(
          'facility-demo',
          snapshot.context.scenario_revision,
          targetType,
          targetId
        );
        setSnapshot(res.snapshot);
      } catch (e: any) {
        alert(`Failed to clear blockage: ${e.message}`);
      }
    } else {
      await handleApplyBlockage(targetType, targetId);
    }
  };

  // Trigger Argon Scan from 3D Cutaway
  const handleTriggerArgonScan = async (targetId: string) => {
    await handleTriggerGrounding(targetId, 'low');
  };

  // Grounding
  const handleTriggerGrounding = async (
    targetOverride?: string,
    thinkingLevel?: 'low' | 'medium' | 'high',
    imageBase64?: string
  ) => {
    const res = await interpretGrounding('facility-demo', {
      targetOverride,
      thinkingLevel,
      imageBase64,
    });
    return res.proposal;
  };

  // Investigation
  const handleRunInvestigation = async () => {
    const res = await investigateScenario('facility-demo');
    return res.investigation;
  };

  // Physical Gate Approval
  const handleOperatorApproveGate = async () => {
    if (!snapshot) return;
    await operatorApproveGate('OPEN_P3', snapshot.context.scenario_revision);
  };

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col font-sans">
      <Header
        snapshot={snapshot}
        health={health}
        onReset={handleReset}
        isJudgeMode={isJudgeMode}
        setIsJudgeMode={setIsJudgeMode}
      />

      <main className="flex-1 p-4 lg:p-6 max-w-7xl mx-auto w-full space-y-5">
        {/* View Switcher Controls */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2 bg-slate-900 p-1 rounded-lg border border-slate-800 text-xs">
            <button
              onClick={() => setActiveView('2d')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md font-medium transition ${
                activeView === '2d'
                  ? 'bg-sky-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Map className="h-3.5 w-3.5" />
              <span>2D Tabletop Plan</span>
            </button>
            <button
              onClick={() => setActiveView('3d')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md font-medium transition ${
                activeView === '3d'
                  ? 'bg-sky-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="h-3.5 w-3.5" />
              <span>2.5D Isometric Cutaway</span>
            </button>
          </div>

          <div className="text-xs text-slate-400 font-mono hidden sm:block">
            Target: SHACK15 Demo Stage • Unit: meters / seconds
          </div>
        </div>

        {/* Cockpit Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Left Column: Visualizers (7 cols) */}
          <div className="lg:col-span-7 space-y-4">
            {activeView === '2d' ? (
              <PlanView2D
                snapshot={snapshot}
                onSelectTarget={(t, id) => setSelectedTarget(`${t}:${id}`)}
                selectedTarget={selectedTarget}
              />
            ) : (
              <CutawayView3D
                snapshot={snapshot}
                onToggleHazard={handleToggleHazard}
                onTriggerArgonScan={handleTriggerArgonScan}
                selectedTarget={selectedTarget}
                onSelectTarget={setSelectedTarget}
              />
            )}

            {/* LED Indicator Stick View */}
            <LedStickVisualizer snapshot={snapshot} />
          </div>

          {/* Right Column: AI Proposal, Investigation & Operator Flow (5 cols) */}
          <div className="lg:col-span-5">
            <ProposalEvidencePanel
              snapshot={snapshot}
              onApplyBlockage={handleApplyBlockage}
              onTriggerGrounding={handleTriggerGrounding}
              onRunInvestigation={handleRunInvestigation}
              onOperatorApproveGate={handleOperatorApproveGate}
              selectedManualTarget={selectedTarget}
              setSelectedManualTarget={setSelectedTarget}
            />
          </div>
        </div>

        {/* Technical Provenance & Constraint Audit Drawer */}
        <AuditDrawer snapshot={snapshot} />
      </main>
    </div>
  );
};
