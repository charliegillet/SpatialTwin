import React from 'react';
import { ScenarioSnapshot } from '../types';
import { ShieldAlert, CheckCircle2, ArrowRight } from 'lucide-react';

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
  const blockedPortals = snapshot?.blocked_portals ?? [];
  const blockedBoundaries = snapshot?.blocked_boundaries ?? [];
  const gateState = snapshot?.physical_gate_state ?? 'CLOSED';
  const plan = snapshot?.current_plan;

  const isP1Blocked = blockedPortals.includes('P1');
  const isP2Blocked = blockedPortals.includes('P2');
  const isB2Blocked = blockedBoundaries.includes('B2');

  const b1Flow = plan?.boundary_breakdown?.['B1'] ?? 0;
  const b2Flow = plan?.boundary_breakdown?.['B2'] ?? 0;

  return (
    <div className="relative w-full h-[460px] bg-slate-950/80 rounded-xl border border-slate-800 p-4 flex flex-col justify-between overflow-hidden shadow-2xl">
      {/* Top Legend */}
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
        <span className="font-mono text-slate-500">Click pads to simulate token placement</span>
      </div>

      {/* SVG Canvas */}
      <div className="relative flex-1 flex items-center justify-center my-2">
        <svg
          viewBox="0 0 760 380"
          className="w-full h-full max-h-[380px] drop-shadow-md select-none"
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
            y="20"
            width="680"
            height="150"
            rx="12"
            fill="url(#eventGrad)"
            stroke="#4338ca"
            strokeWidth="2"
            strokeDasharray={plan?.remaining_population ? '4 2' : undefined}
          />
          <text x="380" y="50" fill="#e0e7ff" fontSize="15" fontWeight="bold" textAnchor="middle">
            MAIN EVENT HALL (Zone: EVENT)
          </text>
          <text x="380" y="75" fill="#94a3b8" fontSize="12" textAnchor="middle">
            Initial Population: 120 | Capacity: 200
          </text>

          {/* Real-time Occupant Badge inside Event Hall */}
          <g transform="translate(300, 95)">
            <rect x="0" y="0" width="160" height="34" rx="6" fill="#0f172a" stroke="#6366f1" strokeWidth="1.5" />
            <text x="80" y="22" fill="#a5b4fc" fontSize="12" fontWeight="bold" textAnchor="middle">
              {plan ? `Remaining: ${plan.remaining_population} pers` : 'Remaining: 120'}
            </text>
          </g>

          {/* ZONE 2: WEST CORRIDOR */}
          <rect
            x="40"
            y="210"
            width="200"
            height="140"
            rx="10"
            fill="url(#corridorGrad)"
            stroke="#334155"
            strokeWidth="2"
          />
          <text x="140" y="240" fill="#cbd5e1" fontSize="13" fontWeight="bold" textAnchor="middle">
            WEST CORRIDOR
          </text>
          <text x="140" y="260" fill="#64748b" fontSize="11" textAnchor="middle">
            Servicing Exit B1
          </text>

          {/* ZONE 3: EAST CORRIDOR */}
          <rect
            x="520"
            y="210"
            width="200"
            height="140"
            rx="10"
            fill="url(#corridorGrad)"
            stroke="#334155"
            strokeWidth="2"
          />
          <text x="620" y="240" fill="#cbd5e1" fontSize="13" fontWeight="bold" textAnchor="middle">
            EAST CORRIDOR
          </text>
          <text x="620" y="260" fill="#64748b" fontSize="11" textAnchor="middle">
            Servicing Exit B2
          </text>

          {/* ZONE 4: RESERVE CHANNEL */}
          <rect
            x="290"
            y="210"
            width="180"
            height="90"
            rx="8"
            fill="url(#reserveGrad)"
            stroke={gateState === 'OPEN' ? '#10b981' : '#6366f1'}
            strokeWidth="2"
          />
          <text x="380" y="240" fill="#e0e7ff" fontSize="12" fontWeight="bold" textAnchor="middle">
            RESERVE CHANNEL
          </text>
          <text x="380" y="260" fill="#a5b4fc" fontSize="10" textAnchor="middle">
            Internal Bypass to East
          </text>

          {/* PORTAL P1 (Interactive Target) */}
          <g
            className="cursor-pointer transition-transform hover:scale-105"
            onClick={() => onSelectTarget('portal', 'P1')}
          >
            <rect
              x="100"
              y="160"
              width="80"
              height="60"
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
            <text x="140" y="185" fill="#f8fafc" fontSize="12" fontWeight="bold" textAnchor="middle">
              P1 {isP1Blocked ? '✕ BLOCKED' : '✓ OPEN'}
            </text>
            <text x="140" y="205" fill="#94a3b8" fontSize="10" textAnchor="middle">
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
              y="160"
              width="80"
              height="60"
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
            <text x="620" y="185" fill="#f8fafc" fontSize="12" fontWeight="bold" textAnchor="middle">
              P2 {isP2Blocked ? '✕ BLOCKED' : '✓ OPEN'}
            </text>
            <text x="620" y="205" fill="#94a3b8" fontSize="10" textAnchor="middle">
              Pad T_P2
            </text>
          </g>

          {/* PORTAL P3 (Miniature Servo Gate) */}
          <g transform="translate(340, 160)">
            <rect
              x="0"
              y="0"
              width="80"
              height="60"
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
            <text x="40" y="25" fill="#f8fafc" fontSize="11" fontWeight="bold" textAnchor="middle">
              GATE P3
            </text>
            <text
              x="40"
              y="45"
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
            y1="255"
            x2="520"
            y2="255"
            stroke={gateState === 'OPEN' ? '#10b981' : '#475569'}
            strokeWidth="3"
            strokeDasharray="4 2"
          />
          <text x="495" y="248" fill="#94a3b8" fontSize="9" textAnchor="middle">
            P4 Link
          </text>

          {/* BOUNDARY B1 (Exit West) */}
          <g transform="translate(90, 310)">
            <rect x="0" y="0" width="100" height="34" rx="6" fill="#047857" stroke="#10b981" strokeWidth="1.5" />
            <text x="50" y="16" fill="#f8fafc" fontSize="11" fontWeight="bold" textAnchor="middle">
              EXIT B1
            </text>
            <text x="50" y="28" fill="#a7f3d0" fontSize="9" textAnchor="middle">
              {b1Flow} serviced
            </text>
          </g>

          {/* BOUNDARY B2 (Exit East - Interactive Target) */}
          <g
            className="cursor-pointer transition-transform hover:scale-105"
            transform="translate(570, 310)"
            onClick={() => onSelectTarget('boundary', 'B2')}
          >
            <rect
              x="0"
              y="0"
              width="100"
              height="34"
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
            <text x="50" y="16" fill="#f8fafc" fontSize="11" fontWeight="bold" textAnchor="middle">
              EXIT B2 {isB2Blocked ? '✕' : ''}
            </text>
            <text x="50" y="28" fill={isB2Blocked ? '#fca5a5' : '#a7f3d0'} fontSize="9" textAnchor="middle">
              {isB2Blocked ? 'BLOCKED' : `${b2Flow} serviced`}
            </text>
          </g>
        </svg>
      </div>

      {/* Numerical Summary Cards */}
      <div className="grid grid-cols-4 gap-2 text-xs z-10">
        <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
          <div className="text-slate-400">Total Population</div>
          <div className="text-base font-bold text-slate-100 font-mono">120 pers</div>
        </div>
        <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
          <div className="text-slate-400">Completed Crossings</div>
          <div className="text-base font-bold text-emerald-400 font-mono">
            {plan?.completed_crossings ?? 0} pers
          </div>
        </div>
        <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
          <div className="text-slate-400">Residual In Hall</div>
          <div className="text-base font-bold text-amber-400 font-mono">
            {plan?.remaining_population ?? 0} pers
          </div>
        </div>
        <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
          <div className="text-slate-400">Conservation Check</div>
          <div className="flex items-center space-x-1 text-emerald-400 font-semibold mt-0.5">
            <CheckCircle2 className="h-4 w-4" />
            <span>120 = {plan ? plan.completed_crossings + plan.remaining_population : 120}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
