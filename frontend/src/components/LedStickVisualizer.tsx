import React from 'react';
import { ScenarioSnapshot } from '../types';
import { Lightbulb } from 'lucide-react';

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

  const renderStick = (label: string, startIndex: number, state: 'green' | 'red' | 'amber' | 'off') => {
    const colorClass = {
      green: 'bg-emerald-400 shadow-[0_0_10px_#34d399] border-emerald-300',
      red: 'bg-rose-500 shadow-[0_0_10px_#f43f5e] border-rose-300',
      amber: 'bg-amber-400 shadow-[0_0_10px_#fbbf24] border-amber-300 animate-pulse',
      off: 'bg-slate-800 border-slate-700 opacity-60',
    }[state];

    return (
      <div className="flex-1 bg-slate-900/90 rounded-lg p-3 border border-slate-800 flex flex-col justify-between">
        <div className="flex items-center justify-between text-xs mb-2">
          <span className="font-semibold text-slate-300">{label}</span>
          <span className="text-[10px] font-mono text-slate-500">
            LEDs {startIndex}..{startIndex + 7}
          </span>
        </div>
        <div className="grid grid-cols-8 gap-1.5 py-1">
          {Array.from({ length: 8 }).map((_, idx) => (
            <div
              key={idx}
              className={`h-5 w-full rounded-sm border transition-all duration-300 ${colorClass}`}
              title={`Pixel ${startIndex + idx}`}
            />
          ))}
        </div>
      </div>
    );
  };

  const p1State = isP1Blocked ? 'red' : p1Active ? 'green' : 'off';
  const p2State = isP2Blocked ? 'red' : p2Active ? 'green' : 'off';
  const p3State =
    gateState === 'OPEN' ? 'green' : gateState === 'TRANSIT' ? 'amber' : 'off';

  return (
    <div className="bg-slate-950/80 rounded-xl border border-slate-800 p-4 shadow-xl">
      <div className="flex items-center justify-between text-xs mb-3">
        <div className="flex items-center space-x-2">
          <Lightbulb className="h-4 w-4 text-emerald-400" />
          <span className="font-semibold text-slate-200">Tabletop LED Indicators</span>
          <span className="text-slate-500">•</span>
          <span className="text-slate-400">24 NeoPixels (WS2812B) Driven via PCA9685/UNO R4</span>
        </div>
        <span className="text-[11px] font-mono text-emerald-400">Rate: &lt;= 10 Hz</span>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        {renderStick('Stick A — Portal P1 (West)', 0, p1State)}
        {renderStick('Stick B — Portal P2 (East)', 8, p2State)}
        {renderStick('Stick C — Gate P3 (Reserve)', 16, p3State)}
      </div>
    </div>
  );
};
