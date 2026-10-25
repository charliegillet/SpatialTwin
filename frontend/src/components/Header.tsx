import React, { useState, useEffect } from 'react';
import { HealthStatus, ScenarioSnapshot } from '../types';
import {
  RotateCcw,
  Cpu,
  Sparkles,
  ShieldCheck,
  Activity,
  Radio,
  Clock,
  Volume2,
  VolumeX,
  Zap,
} from 'lucide-react';
import { sounds } from '../utils/audio';

interface HeaderProps {
  snapshot: ScenarioSnapshot | null;
  health: HealthStatus | null;
  onReset: () => void;
  isJudgeMode: boolean;
  setIsJudgeMode: (val: boolean) => void;
  onQuickPreset?: (preset: 'nominal' | 'p2_blocked' | 'b2_blocked') => void;
}

export const Header: React.FC<HeaderProps> = ({
  snapshot,
  health,
  onReset,
  isJudgeMode,
  setIsJudgeMode,
  onQuickPreset,
}) => {
  const [timeStr, setTimeStr] = useState<string>('');
  const [isAudioMuted, setIsAudioMuted] = useState<boolean>(false);

  const ctx = snapshot?.context;
  const isP2Blocked = snapshot?.blocked_portals?.includes('P2') ?? false;
  const isB2Blocked = snapshot?.blocked_boundaries?.includes('B2') ?? false;

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(
        now.toLocaleTimeString('en-US', {
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        })
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-xl px-5 py-2.5 sticky top-0 z-50 shadow-2xl">
      <div className="flex flex-wrap items-center justify-between gap-3 max-w-[1600px] mx-auto">
        {/* Brand & Mission Title */}
        <div className="flex items-center space-x-3.5">
          <div className="relative flex items-center justify-center">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/30 border border-cyan-400/40 flex items-center justify-center text-cyan-400 shadow-neon-cyan">
              <Activity className="h-5 w-5 animate-pulse" />
            </div>
            {/* Live SSE Pulse Ping */}
            <span className="absolute -top-1 -right-1 flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
          </div>

          <div>
            <div className="flex items-center space-x-2.5">
              <h1 className="text-xl font-bold font-display tracking-wider text-white uppercase flex items-center gap-1.5">
                <span>Spatial</span>
                <span className="text-cyan-400">Twin</span>
              </h1>
              <span className="text-[11px] px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 font-semibold font-mono tracking-wide">
                GEMINI 4 ARGON
              </span>
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/60 font-mono hidden sm:inline-block">
                SHACK15 STAGE
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-sans hidden sm:block">
              Autonomous Multimodal Evacuation Twin with Real-Time Physical Gate Assurance
            </p>
          </div>
        </div>

        {/* Center: Quick Judging Demo Bar */}
        {onQuickPreset && (
          <div className="hidden lg:flex items-center space-x-1.5 bg-slate-900/90 border border-slate-800 p-1 rounded-lg text-xs font-medium">
            <span className="text-[10px] text-slate-400 uppercase font-mono px-2 flex items-center gap-1">
              <Zap className="h-3 w-3 text-amber-400" />
              Judging Trials:
            </span>
            <button
              onClick={() => onQuickPreset('nominal')}
              className={`px-2.5 py-1 rounded text-xs transition ${
                !isP2Blocked && !isB2Blocked
                  ? 'bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
            >
              1. Nominal Flow
            </button>
            <button
              onClick={() => onQuickPreset('p2_blocked')}
              className={`px-2.5 py-1 rounded text-xs transition ${
                isP2Blocked && !isB2Blocked
                  ? 'bg-rose-600/30 text-rose-300 border border-rose-500/40 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
            >
              2. P2 Blocked (AI Reroute)
            </button>
            <button
              onClick={() => onQuickPreset('b2_blocked')}
              className={`px-2.5 py-1 rounded text-xs transition ${
                isB2Blocked
                  ? 'bg-amber-600/30 text-amber-300 border border-amber-500/40 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
            >
              3. B2 Blocked (Falsify 0-Gain)
            </button>
          </div>
        )}

        {/* Right Status Indicators & Controls */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {/* Mission Telemetry Clock */}
          <div className="hidden md:flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 font-mono text-[11px] text-slate-300">
            <Clock className="h-3.5 w-3.5 text-cyan-400" />
            <span className="text-slate-500">SF:</span>
            <span className="text-slate-200 font-bold">{timeStr || '12:00:00'}</span>
          </div>

          {/* Context Revision Pill */}
          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-slate-900/90 border border-slate-800 font-mono text-[11px] text-slate-300">
            <span className="text-slate-500">REV</span>
            <span className="text-cyan-400 font-bold">s:{ctx?.scenario_revision ?? 1}</span>
            <span className="text-slate-600">/</span>
            <span className="text-emerald-400 font-bold">p:{ctx?.physical_revision ?? 1}</span>
          </div>

          {/* AI Provider Status */}
          <div
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border text-[11px] font-semibold ${
              health?.live_api_configured
                ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                : 'bg-amber-500/10 text-amber-300 border-amber-500/30'
            }`}
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>{health?.live_api_configured ? 'Argon API' : 'Argon Fixture'}</span>
          </div>

          {/* Hardware Bridge Status */}
          <div
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border text-[11px] font-semibold ${
              health?.hardware_mode === 'physical_serial'
                ? 'bg-purple-500/10 text-purple-300 border-purple-500/30'
                : 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30'
            }`}
          >
            <Cpu className="h-3.5 w-3.5" />
            <span>{health?.hardware_mode === 'physical_serial' ? 'UNO R4 USB' : 'Simulator'}</span>
          </div>

          {/* Reset Scenario */}
          <button
            onClick={onReset}
            className="flex items-center space-x-1.5 px-3 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-800 hover:border-slate-700 transition font-medium"
            title="Reset active scenario blockages to baseline"
          >
            <RotateCcw className="h-3.5 w-3.5 text-slate-400" />
            <span>Reset</span>
          </button>
        </div>
      </div>
    </header>
  );
};