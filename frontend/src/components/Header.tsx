import React from 'react';
import { HealthStatus, ScenarioSnapshot } from '../types';
import { RotateCcw, Cpu, Sparkles, ShieldCheck, Activity } from 'lucide-react';

interface HeaderProps {
  snapshot: ScenarioSnapshot | null;
  health: HealthStatus | null;
  onReset: () => void;
  isJudgeMode: boolean;
  setIsJudgeMode: (val: boolean) => void;
}

export const Header: React.FC<HeaderProps> = ({
  snapshot,
  health,
  onReset,
  isJudgeMode,
  setIsJudgeMode,
}) => {
  const ctx = snapshot?.context;

  return (
    <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur-md px-6 py-3 sticky top-0 z-50">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Brand */}
        <div className="flex items-center space-x-3">
          <div className="h-9 w-9 rounded-lg bg-sky-500/20 border border-sky-400/40 flex items-center justify-center text-sky-400 shadow-lg glow-cyan">
            <Activity className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold text-white tracking-wide">SpatialTwin</h1>
              <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-medium">
                Gemini 4 Argon
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Deterministic evacuation twin with physical position confirmation & managed tools
            </p>
          </div>
        </div>

        {/* Revisions & Status Badges */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {/* Revisions */}
          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-slate-800/80 border border-slate-700/60 font-mono text-slate-300">
            <span className="text-slate-500">REV</span>
            <span className="text-sky-400">scen:r{ctx?.scenario_revision ?? 1}</span>
            <span className="text-slate-600">|</span>
            <span className="text-emerald-400">phys:r{ctx?.physical_revision ?? 1}</span>
            <span className="text-slate-600">|</span>
            <span className="text-slate-400 truncate max-w-[70px]">{ctx?.context_hash?.slice(0, 8)}</span>
          </div>

          {/* AI Provider Status */}
          <div
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded border font-medium ${
              health?.live_api_configured
                ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                : 'bg-amber-500/10 text-amber-300 border-amber-500/30'
            }`}
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>{health?.live_api_configured ? 'Argon API Live' : 'Argon Fixture'}</span>
          </div>

          {/* Hardware Bridge Status */}
          <div
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded border font-medium ${
              health?.hardware_mode === 'physical_serial'
                ? 'bg-purple-500/10 text-purple-300 border-purple-500/30'
                : 'bg-sky-500/10 text-sky-300 border-sky-500/30'
            }`}
          >
            <Cpu className="h-3.5 w-3.5" />
            <span>{health?.hardware_mode === 'physical_serial' ? 'UNO R4 USB' : 'Simulator'}</span>
          </div>

          {/* Mode Switcher */}
          <button
            onClick={() => setIsJudgeMode(!isJudgeMode)}
            className={`px-3 py-1 rounded text-xs font-semibold transition border ${
              isJudgeMode
                ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 glow-rose'
                : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700'
            }`}
          >
            {isJudgeMode ? 'Mode: Judge Trial' : 'Mode: Presenter'}
          </button>

          {/* Reset Scenario */}
          <button
            onClick={onReset}
            className="flex items-center space-x-1 px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
            title="Reset active scenario blockages to baseline"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>Reset</span>
          </button>
        </div>
      </div>
    </header>
  );
};
