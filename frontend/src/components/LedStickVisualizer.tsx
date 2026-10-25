import React from 'react';
import { ScenarioSnapshot } from '../types';
import { Lightbulb, Cpu, Radio } from 'lucide-react';

interface LedStickVisualizerProps {
  snapshot: ScenarioSnapshot | null;
}

export const LedStickVisualizer: React.FC<LedStickVisualizerProps> = ({ snapshot }) => {
  const isP1Blocked = snapshot?.blocked_portals?.includes('P1') ?? false;
  const isP2Blocked = snapshot?.blocked_portals?.includes('P2') ?? false;
  const gateState = snapshot?.physical_gate_state ?? 'CLOSED';
  const plan = snapshot?.current_plan;

  const p1Active = !isP1Blocked && (plan?.boundary_breakdown?.['B1'] ?? 0) > 0;
  const p2Active = !isP2Blocked && (plan?.boundary_breakdown?.['B2'] ?? 0) > 0;

  const p1State = isP1Blocked ? 'red' : p1Active ? 'green' : 'off';
  const p2State = isP2Blocked ? 'red' : p2Active ? 'green' : 'off';
  const p3State = gateState === 'OPEN' ? 'green' : gateState === 'TRANSIT' ? 'amber' : 'off';

  const renderSegment = (
    label: string,
    sublabel: string,
    startIndex: number,
    state: 'green' | 'red' | 'amber' | 'off'
  ) => {
    // Colors and glow styling for NeoPixel simulation
    const ledStyles = {
      green: {
        core: 'bg-emerald-300',
        ring: 'border-emerald-400 shadow-[0_0_12px_#34d399,inset_0_0_4px_#10b981]',
        barGlow: 'border-emerald-500/30 bg-emerald-950/20',
        text: 'text-emerald-400',
        status: 'CLEAR / FLOWING',
      },
      red: {
        core: 'bg-rose-400',
        ring: 'border-rose-500 shadow-[0_0_12px_#f43f5e,inset_0_0_4px_#ef4444]',
        barGlow: 'border-rose-500/30 bg-rose-950/20',
        text: 'text-rose-400',
        status: 'BLOCKED / HAZARD',
      },
      amber: {
        core: 'bg-amber-300 animate-pulse',
        ring: 'border-amber-400 shadow-[0_0_12px_#fbbf24,inset_0_0_4px_#f59e0b]',
        barGlow: 'border-amber-500/30 bg-amber-950/20',
        text: 'text-amber-400',
        status: 'GATE IN TRANSIT',
      },
      off: {
        core: 'bg-slate-700/40',
        ring: 'border-slate-800 shadow-none',
        barGlow: 'border-slate-800 bg-slate-950/40',
        text: 'text-slate-500',
        status: 'OFFLINE / STANDBY',
      },
    }[state];

    return (
      <div className={`flex-1 rounded-xl p-3.5 border transition-all duration-300 flex flex-col justify-between ${ledStyles.barGlow}`}>
        {/* Header info */}
        <div className="flex items-center justify-between text-xs mb-2.5">
          <div>
            <div className="font-bold text-slate-200 text-xs flex items-center gap-1.5">
              <span>{label}</span>
              <span className={`text-[10px] font-mono font-bold ${ledStyles.text}`}>• {ledStyles.status}</span>
            </div>
            <div className="text-[10px] text-slate-500 font-mono">{sublabel}</div>
          </div>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400">
            PX {startIndex}..{startIndex + 7}
          </span>
        </div>

        {/* Anodized Aluminum Light Bar Housing */}
        <div className="bg-[#05070f] p-2 rounded-lg border border-slate-800/90 shadow-inner flex items-center justify-between gap-1.5">
          {Array.from({ length: 8 }).map((_, idx) => (
            <div
              key={idx}
              className={`relative flex-1 h-5 rounded-md border flex items-center justify-center transition-all duration-300 ${ledStyles.ring}`}
              title={`NeoPixel ${startIndex + idx}`}
            >
              {/* Emitter Core */}
              <div className={`w-2 h-2 rounded-full ${ledStyles.core}`} />
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="bg-slate-950/90 rounded-xl border border-slate-800/80 p-4 shadow-2xl space-y-3">
      {/* Title & Technical Specs */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs border-b border-slate-800/80 pb-2">
        <div className="flex items-center space-x-2">
          <Lightbulb className="h-4 w-4 text-emerald-400" />
          <span className="font-bold text-slate-200">Tabletop Hardware LED Telemetry Bar</span>
          <span className="text-slate-500">•</span>
          <span className="text-slate-400 font-mono text-[11px]">24 WS2812B NeoPixels</span>
        </div>
        <div className="flex items-center space-x-3 text-[11px] font-mono text-slate-500">
          <span>PIN: D6 (Uno R4)</span>
          <span>BUS: PCA9685</span>
          <span className="text-emerald-400 flex items-center gap-1">
            <Radio className="h-3 w-3" />
            10 Hz Refresh
          </span>
        </div>
      </div>

      {/* 3 Physical Light Bar Segments */}
      <div className="flex flex-col md:flex-row gap-3">
        {renderSegment('Stick A — West Portal P1', 'Floor corridor to West Transfer B1', 0, p1State)}
        {renderSegment('Stick B — East Portal P2', 'Floor corridor to East Transfer B2', 8, p2State)}
        {renderSegment('Stick C — Reserve Gate P3', 'Internal bypass linking to East Exit B2', 16, p3State)}
      </div>
    </div>
  );
};