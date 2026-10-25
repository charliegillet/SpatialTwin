import React, { useState } from 'react';
import { ScenarioSnapshot } from '../types';
import { ShieldAlert, CheckCircle2, ArrowRight, Play, Pause, RotateCcw } from 'lucide-react';

interface PlanView2DProps {
  snapshot: ScenarioSnapshot | null;
  onSelectTarget: (type: 'portal' | 'boundary', id: 'P1' | 'P2' | 'B2') => void;
  selectedTarget: string | null;
}

export const PlanView2D: React.FC<PlanView2DProps> = ({
  snapshot,
  onSelectTarget,
  selectedTarget,
}) => {
  const [selectedStep, setSelectedStep] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const blockedPortals = snapshot?.blocked_portals ?? [];
  const blockedBoundaries = snapshot?.blocked_boundaries ?? [];
  const gateState = snapshot?.physical_gate_state ?? 'CLOSED';
  const plan = snapshot?.current_plan;

  const isP1Blocked = blockedPortals.includes('P1');
  const isP2Blocked = blockedPortals.includes('P2');
  const isB2Blocked = blockedBoundaries.includes('B2');

  const timeline = plan?.timeline ?? [];
  const maxStep = timeline.length > 0 ? timeline.length - 1 : 20;
  const currentStepIdx = selectedStep !== null ? Math.min(selectedStep, maxStep) : maxStep;
  const currentFrame = timeline[currentStepIdx] ?? {
    time_seconds: 40,
    event_occupancy: plan?.remaining_population ?? 0,
    west_occupancy: 0,
    east_occupancy: 0,
    reserve_occupancy: 0,
    b1_cumulative: plan?.boundary_breakdown?.['B1'] ?? 0,
    b2_cumulative: plan?.boundary_breakdown?.['B2'] ?? 0,
    total_completed: plan?.completed_crossings ?? 0,
  };

  // Play animation loop
  React.useEffect(() => {
    let interval: any = null;
    if (isPlaying) {
      interval = setInterval(() => {
        setSelectedStep((prev) => {
          const next = (prev === null ? 0 : prev + 1);
          if (next > maxStep) {
            setIsPlaying(false);
            return maxStep;
          }
          return next;
        });
      }, 350);
    }
    return () => clearInterval(interval);
  }, [isPlaying, maxStep]);

  return (
    <div className="relative w-full h-[490px] bg-slate-950/80 rounded-xl border border-slate-800 p-4 flex flex-col justify-between overflow-hidden shadow-2xl">
      {/* Top Legend & Scrubber Indicator */}
      <div className="flex items-center justify-between text-xs text-slate-400 z-10">
        <div className="flex items-center space-x-3">
          <span className="font-semibold text-slate-200">2D Tabletop Floor Plan</span>
          <span className="text-slate-500">•</span>
          <span className="flex items-center space-x-1">
            <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
            <span>Open Passage</span>
          </span>
          <span className="flex items-center space-x-1">
            <span className="h-2 w-2 rounded-full bg-rose-500"></span>
            <span>Blocked Target</span>
          </span>
          <span className="flex items-center space-x-1">
            <span className="h-2 w-2 rounded-full bg-amber-400"></span>
            <span>Gate P3 ({gateState})</span>
          </span>
        </div>
        <div className="flex items-center space-x-2 font-mono text-sky-400 font-bold">
          <span>Time: {currentFrame.time_seconds}s / 40s</span>
        </div>
      </div>

      {/* SVG Canvas */}
      <div className="relative flex-1 flex items-center justify-center my-1">
        <svg
          viewBox="0 0 760 360"
          className="w-full h-full max-h-[350px] drop-shadow-md select-none"
        >
          <defs>
            <linearGradient id="eventGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#1e1b4b" stopOpacity="0.85" />
              <stop offset="100%" stopColor="#0f172a" stopOpacity="0.9" />
            </linearGradient>
            <linearGradient id="corridorGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#1e293b" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#0f172a" stopOpacity="0.8" />
            </linearGradient>
            <linearGradient id="reserveGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#2e1065" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#1e1b4b" stopOpacity="0.8" />
            </linearGradient>
          </defs>

          {/* ZONE 1: EVENT HALL */}
          <rect
            x="40"
            y="15"
            width="680"
            height="145"
            rx="12"
            fill="url(#eventGrad)"
            stroke="#4338ca"
            strokeWidth="2"
          />
          <text x="380" y="42" fill="#e0e7ff" fontSize="14" fontWeight="bold" textAnchor="middle">
            MAIN EVENT HALL (Zone: EVENT)
          </text>
          <text x="380" y="62" fill="#94a3b8" fontSize="11" textAnchor="middle">
            Initial Population: 120 pers | Max Capacity: 200
          </text>

          {/* Dynamic Occupant Badge inside Event Hall */}
          <g transform="translate(300, 80)">
            <rect x="0" y="0" width="160" height="34" rx="6" fill="#0f172a" stroke="#6366f1" strokeWidth="1.5" />
            <text x="80" y="22" fill="#a5b4fc" fontSize="12" fontWeight="bold" textAnchor="middle">
              Occupancy: {currentFrame.event_occupancy} pers
            </text>
          </g>

          {/* ZONE 2: WEST CORRIDOR */}
          <rect
            x="40"
            y="195"
            width="200"
            height="135"
            rx="10"
            fill="url(#corridorGrad)"
            stroke="#334155"
            strokeWidth="2"
          />
          <text x="140" y="222" fill="#cbd5e1" fontSize="12" fontWeight="bold" textAnchor="middle">
            WEST CORRIDOR
          </text>
          <text x="140" y="240" fill="#64748b" fontSize="10" textAnchor="middle">
            In-Transit: {currentFrame.west_occupancy} pers
          </text>

          {/* ZONE 3: EAST CORRIDOR */}
          <rect
            x="520"
            y="195"
            width="200"
            height="135"
            rx="10"
            fill="url(#corridorGrad)"
            stroke="#334155"
            strokeWidth="2"
          />
          <text x="620" y="222" fill="#cbd5e1" fontSize="12" fontWeight="bold" textAnchor="middle">
            EAST CORRIDOR
          </text>
          <text x="620" y="240" fill="#64748b" fontSize="10" textAnchor="middle">
            In-Transit: {currentFrame.east_occupancy} pers
          </text>

          {/* ZONE 4: RESERVE CHANNEL */}
          <rect
            x="290"
            y="195"
            width="180"
            height="85"
            rx="8"
            fill="url(#reserveGrad)"
            stroke={gateState === 'OPEN' ? '#10b981' : '#6366f1'}
            strokeWidth="2"
          />
          <text x="380" y="222" fill="#e0e7ff" fontSize="11" fontWeight="bold" textAnchor="middle">
            RESERVE CHANNEL
          </text>
          <text x="380" y="240" fill="#a5b4fc" fontSize="10" textAnchor="middle">
            {gateState === 'OPEN' ? `Flow: ${currentFrame.reserve_occupancy} pers` : 'Closed by Servo P3'}
          </text>

          {/* PORTAL P1 (Interactive Target) */}
          <g
            className="cursor-pointer transition-transform hover:scale-105"
            onClick={() => onSelectTarget('portal', 'P1')}
          >
            <rect
              x="100"
              y="150"
              width="80"
              height="55"
              rx="6"
              fill={isP1Blocked ? '#450a0a' : '#064e3b'}
              stroke={
                selectedTarget === 'portal:P1'
                  ? '#38bdf8'
                  : isP1Blocked
                  ? '#ef4444'
                  : '#10b981'
              }
              strokeWidth={selectedTarget === 'portal:P1' ? '3' : '2'}
            />
            <text x="140" y="175" fill="#f8fafc" fontSize="11" fontWeight="bold" textAnchor="middle">
              P1 {isP1Blocked ? '✕ BLOCKED' : '✓ OPEN'}
            </text>
            <text x="140" y="193" fill="#94a3b8" fontSize="9" textAnchor="middle">
              Pad T_P1
            </text>
          </g>

          {/* PORTAL P2 (Interactive Target) */}
          <g
            className="cursor-pointer transition-transform hover:scale-105"
            onClick={() => onSelectTarget('portal', 'P2')}
          >
            <rect
              x="580"
              y="150"
              width="80"
              height="55"
              rx="6"
              fill={isP2Blocked ? '#450a0a' : '#064e3b'}
              stroke={
                selectedTarget === 'portal:P2'
                  ? '#38bdf8'
                  : isP2Blocked
                  ? '#ef4444'
                  : '#10b981'
              }
              strokeWidth={selectedTarget === 'portal:P2' ? '3' : '2'}
            />
            <text x="620" y="175" fill="#f8fafc" fontSize="11" fontWeight="bold" textAnchor="middle">
              P2 {isP2Blocked ? '✕ BLOCKED' : '✓ OPEN'}
            </text>
            <text x="620" y="193" fill="#94a3b8" fontSize="9" textAnchor="middle">
              Pad T_P2
            </text>
          </g>

          {/* PORTAL P3 (Miniature Servo Gate) */}
          <g transform="translate(340, 150)">
            <rect
              x="0"
              y="0"
              width="80"
              height="55"
              rx="6"
              fill={
                gateState === 'OPEN'
                  ? '#064e3b'
                  : gateState === 'TRANSIT'
                  ? '#451a03'
                  : '#1e293b'
              }
              stroke={
                gateState === 'OPEN'
                  ? '#10b981'
                  : gateState === 'TRANSIT'
                  ? '#f59e0b'
                  : '#64748b'
              }
              strokeWidth="2"
            />
            <text x="40" y="24" fill="#f8fafc" fontSize="11" fontWeight="bold" textAnchor="middle">
              GATE P3
            </text>
            <text
              x="40"
              y="42"
              fill={gateState === 'OPEN' ? '#34d399' : '#f59e0b'}
              fontSize="10"
              fontWeight="bold"
              textAnchor="middle"
            >
              {gateState === 'OPEN' ? 'OPEN (SERVO)' : gateState === 'TRANSIT' ? 'TRANSIT...' : 'CLOSED'}
            </text>
          </g>

          {/* PORTAL P4 (Internal Link from Reserve to East) */}
          <line
            x1="470"
            y1="240"
            x2="520"
            y2="240"
            stroke={gateState === 'OPEN' ? '#10b981' : '#475569'}
            strokeWidth="3"
            strokeDasharray="4 2"
          />

          {/* BOUNDARY B1 (Exit West) */}
          <g transform="translate(90, 290)">
            <rect x="0" y="0" width="100" height="32" rx="6" fill="#047857" stroke="#10b981" strokeWidth="1.5" />
            <text x="50" y="15" fill="#f8fafc" fontSize="11" fontWeight="bold" textAnchor="middle">
              EXIT B1
            </text>
            <text x="50" y="27" fill="#a7f3d0" fontSize="9" textAnchor="middle">
              {currentFrame.b1_cumulative} serviced
            </text>
          </g>

          {/* BOUNDARY B2 (Exit East - Interactive Target) */}
          <g
            className="cursor-pointer transition-transform hover:scale-105"
            transform="translate(570, 290)"
            onClick={() => onSelectTarget('boundary', 'B2')}
          >
            <rect
              x="0"
              y="0"
              width="100"
              height="32"
              rx="6"
              fill={isB2Blocked ? '#450a0a' : '#047857'}
              stroke={
                selectedTarget === 'boundary:B2'
                  ? '#38bdf8'
                  : isB2Blocked
                  ? '#ef4444'
                  : '#10b981'
              }
              strokeWidth={selectedTarget === 'boundary:B2' ? '3' : '1.5'}
            />
            <text x="50" y="15" fill="#f8fafc" fontSize="11" fontWeight="bold" textAnchor="middle">
              EXIT B2 {isB2Blocked ? '✕' : ''}
            </text>
            <text x="50" y="27" fill={isB2Blocked ? '#fca5a5' : '#a7f3d0'} fontSize="9" textAnchor="middle">
              {isB2Blocked ? 'BLOCKED' : `${currentFrame.b2_cumulative} serviced`}
            </text>
          </g>
        </svg>
      </div>

      {/* Time Horizon Interactive Scrubber Bar */}
      <div className="bg-slate-900/90 px-3 py-1.5 rounded-lg border border-slate-800 flex items-center space-x-3 text-xs z-10">
        <button
          onClick={() => setIsPlaying(!isPlaying)}
          className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 transition"
          title={isPlaying ? 'Pause timeline' : 'Play evacuation simulation'}
        >
          {isPlaying ? <Pause className="h-3.5 w-3.5 text-amber-400" /> : <Play className="h-3.5 w-3.5 text-emerald-400" />}
        </button>
        <button
          onClick={() => { setIsPlaying(false); setSelectedStep(0); }}
          className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
          title="Reset timeline to t=0"
        >
          <RotateCcw className="h-3 w-3" />
        </button>

        <span className="text-[11px] font-mono text-slate-400 whitespace-nowrap">Timeline Scrub:</span>

        <input
          type="range"
          min="0"
          max={maxStep}
          value={currentStepIdx}
          onChange={(e) => {
            setIsPlaying(false);
            setSelectedStep(parseInt(e.target.value));
          }}
          className="w-full accent-sky-500 h-1.5 bg-slate-800 rounded-lg cursor-pointer"
        />

        <span className="text-[11px] font-mono font-bold text-emerald-400 whitespace-nowrap">
          {currentFrame.total_completed} / 120 Evacuated
        </span>
      </div>
    </div>
  );
};
