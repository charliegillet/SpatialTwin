import React, { useState, useEffect } from 'react';
import { ScenarioSnapshot } from '../types';
import {
  Activity,
  ArrowRight,
  TrendingUp,
  Cpu,
  ShieldCheck,
  AlertTriangle,
  Flame,
  CheckCircle2,
  Sliders,
  Layers,
} from 'lucide-react';

interface LiveChangeTickerProps {
  snapshot: ScenarioSnapshot | null;
}

export const LiveChangeTicker: React.FC<LiveChangeTickerProps> = ({ snapshot }) => {
  const plan = snapshot?.current_plan;
  const ctx = snapshot?.context;
  const gateState = snapshot?.physical_gate_state ?? 'CLOSED';

  const isP1Blocked = snapshot?.blocked_portals?.includes('P1') ?? false;
  const isP2Blocked = snapshot?.blocked_portals?.includes('P2') ?? false;
  const isB2Blocked = snapshot?.blocked_boundaries?.includes('B2') ?? false;

  const completed = plan?.completed_crossings ?? 0;
  const residual = plan?.remaining_population ?? 120;
  const completionRate = ((completed / 120) * 100).toFixed(0);

  // Compute live net gain relative to 60 (blocked baseline)
  const isHazardActive = isP1Blocked || isP2Blocked || isB2Blocked;
  let netGain = 0;
  let netGainLabel = 'Nominal (80-120 pers)';
  if (isP2Blocked && !isB2Blocked) {
    if (gateState === 'OPEN') {
      netGain = completed - 60;
      netGainLabel = `+${netGain} pers rescued (+${((netGain / 60) * 100).toFixed(0)}%)`;
    } else {
      netGainLabel = '0 (P3 Closed: Bottleneck at P2)';
    }
  } else if (isB2Blocked) {
    netGainLabel = '+0 pers (Falsified: B2 Blocked)';
  }

  // Flash highlight on state change
  const [highlight, setHighlight] = useState(false);
  useEffect(() => {
    setHighlight(true);
    const timer = setTimeout(() => setHighlight(false), 900);
    return () => clearTimeout(timer);
  }, [snapshot?.context?.scenario_revision, snapshot?.context?.physical_revision]);

  return (
    <div
      className={`w-full rounded-xl border p-2.5 shadow-xl transition-all duration-500 flex flex-wrap items-center justify-between gap-3 text-xs font-mono select-none ${
        highlight
          ? 'bg-slate-900 border-cyan-400 shadow-neon-cyan'
          : 'bg-slate-950/90 border-slate-800/80 backdrop-blur-xl'
      }`}
    >
      {/* 1. Active State Hazard Status */}
      <div className="flex items-center space-x-2.5 pl-1">
        <div className="relative">
          <span
            className={`w-3 h-3 rounded-full inline-block ${
              isHazardActive ? 'bg-rose-500 animate-ping' : 'bg-emerald-400 animate-pulse'
            }`}
          />
          <span
            className={`w-3 h-3 rounded-full absolute top-0 left-0 ${
              isHazardActive ? 'bg-rose-500' : 'bg-emerald-400'
            }`}
          />
        </div>
        <div>
          <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
            Current Scenario
          </div>
          <div className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
            {isP2Blocked ? (
              <span className="text-rose-400 flex items-center gap-1">
                <Flame className="h-3.5 w-3.5" /> P2 Blocked (East Hall)
              </span>
            ) : isB2Blocked ? (
              <span className="text-amber-400 flex items-center gap-1">
                <AlertTriangle className="h-3.5 w-3.5" /> B2 Stairwell Blocked
              </span>
            ) : isP1Blocked ? (
              <span className="text-rose-400 flex items-center gap-1">
                <Flame className="h-3.5 w-3.5" /> P1 Blocked (West Hall)
              </span>
            ) : (
              <span className="text-emerald-400 flex items-center gap-1">
                <CheckCircle2 className="h-3.5 w-3.5" /> Nominal (All Corridors Open)
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="h-7 w-px bg-slate-800 hidden md:block" />

      {/* 2. Population Conservation Throughput */}
      <div className="flex items-center space-x-3">
        <div className="w-24">
          <div className="flex justify-between text-[10px] text-slate-400 mb-1">
            <span>Evacuation:</span>
            <span className="font-bold text-cyan-400">{completionRate}%</span>
          </div>
          <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-cyan-500 to-emerald-400 transition-all duration-700"
              style={{ width: `${Math.min(100, (completed / 120) * 100)}%` }}
            />
          </div>
        </div>
        <div>
          <div className="text-[10px] text-slate-500 font-bold uppercase">Throughput / Conservation</div>
          <div className="text-xs font-bold text-slate-200">
            <span className="text-emerald-400">{completed}</span>
            <span className="text-slate-500"> / 120 Serviced</span>
            <span className="text-slate-500 font-normal ml-1.5">({residual} residual)</span>
          </div>
        </div>
      </div>

      <div className="h-7 w-px bg-slate-800 hidden md:block" />

      {/* 3. Net Intervention Benefit Delta */}
      <div>
        <div className="text-[10px] text-slate-500 font-bold uppercase flex items-center gap-1">
          <TrendingUp className="h-3 w-3 text-cyan-400" />
          <span>Intervention Delta (Δ)</span>
        </div>
        <div
          className={`text-xs font-bold ${
            isB2Blocked
              ? 'text-rose-400'
              : gateState === 'OPEN'
              ? 'text-emerald-400'
              : 'text-slate-300'
          }`}
        >
          {netGainLabel}
        </div>
      </div>

      <div className="h-7 w-px bg-slate-800 hidden md:block" />

      {/* 4. Physical Gate & Endpoint Switches */}
      <div className="flex items-center space-x-2">
        <div className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-center">
          <div className="text-[9px] text-slate-500 font-bold">GATE P3</div>
          <div
            className={`text-[11px] font-bold ${
              gateState === 'OPEN'
                ? 'text-emerald-400'
                : gateState === 'TRANSIT'
                ? 'text-amber-400 animate-pulse'
                : 'text-slate-400'
            }`}
          >
            {gateState}
          </div>
        </div>
        {/* Dual Microswitch Status Pills */}
        <div className="space-y-0.5 text-[9px]">
          <div className="flex items-center space-x-1">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                gateState === 'CLOSED' ? 'bg-emerald-400' : 'bg-slate-700'
              }`}
            />
            <span className="text-slate-400">D2:</span>
            <span className={gateState === 'CLOSED' ? 'text-emerald-400 font-bold' : 'text-slate-500'}>
              {gateState === 'CLOSED' ? 'LOW (Closed)' : 'HIGH'}
            </span>
          </div>
          <div className="flex items-center space-x-1">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                gateState === 'OPEN' ? 'bg-emerald-400' : 'bg-slate-700'
              }`}
            />
            <span className="text-slate-400">D3:</span>
            <span className={gateState === 'OPEN' ? 'text-emerald-400 font-bold' : 'text-slate-500'}>
              {gateState === 'OPEN' ? 'HIGH (Open)' : 'LOW'}
            </span>
          </div>
        </div>
      </div>

      <div className="h-7 w-px bg-slate-800 hidden md:block" />

      {/* 5. Revision Monotonicity Pills */}
      <div className="pr-1 text-right hidden sm:block">
        <div className="text-[10px] text-slate-500 font-bold uppercase">Revision State</div>
        <div className="text-[11px] text-slate-300 font-bold">
          <span className="text-cyan-400">s:r{ctx?.scenario_revision ?? 1}</span>
          <span className="text-slate-600 mx-1">|</span>
          <span className="text-emerald-400">p:r{ctx?.physical_revision ?? 1}</span>
          <span className="text-slate-600 mx-1">|</span>
          <span className="text-amber-400">ep:{snapshot?.last_gate_epoch ?? 0}</span>
        </div>
      </div>
    </div>
  );
};