import React from 'react';
import { ScenarioSnapshot } from '../types';
import { Layers } from 'lucide-react';

interface CutawayView3DProps {
  snapshot: ScenarioSnapshot | null;
}

export const CutawayView3D: React.FC<CutawayView3DProps> = ({ snapshot }) => {
  const gateState = snapshot?.physical_gate_state ?? 'CLOSED';
  const isP1Blocked = snapshot?.blocked_portals?.includes('P1') ?? false;
  const isP2Blocked = snapshot?.blocked_portals?.includes('P2') ?? false;
  const isB2Blocked = snapshot?.blocked_boundaries?.includes('B2') ?? false;

  return (
    <div className="relative w-full h-[460px] bg-slate-950/90 rounded-xl border border-slate-800 p-4 flex flex-col justify-between overflow-hidden shadow-2xl">
      <div className="flex items-center justify-between text-xs text-slate-400 z-10">
        <div className="flex items-center space-x-2">
          <Layers className="h-4 w-4 text-sky-400" />
          <span className="font-semibold text-slate-200">2.5D Isometric Cutaway</span>
          <span className="text-slate-500">•</span>
          <span className="text-slate-400">Spatial Depth & Miniature Gate Elevation</span>
        </div>
        <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-sky-400">
          Isometric Projection
        </span>
      </div>

      {/* Isometric Canvas */}
      <div className="relative flex-1 flex items-center justify-center">
        <svg viewBox="0 0 600 340" className="w-full h-full max-h-[340px] drop-shadow-2xl">
          <g transform="translate(300, 40)">
            {/* Base Tabletop Slab */}
            <path
              d="M 0 0 L 240 120 L 0 240 L -240 120 Z"
              fill="#0b0f19"
              stroke="#1e293b"
              strokeWidth="2"
            />
            {/* Slab Extrusion */}
            <path
              d="M -240 120 L 0 240 L 0 260 L -240 140 Z"
              fill="#060911"
              stroke="#1e293b"
              strokeWidth="1"
            />
            <path
              d="M 0 240 L 240 120 L 240 140 L 0 260 Z"
              fill="#080c16"
              stroke="#1e293b"
              strokeWidth="1"
            />

            {/* Main Event Room Floor */}
            <path
              d="M 0 20 L 160 100 L 0 180 L -160 100 Z"
              fill="#1e1b4b"
              stroke="#4338ca"
              strokeWidth="2"
            />
            {/* Main Event Room Wall Cutaways */}
            <path
              d="M -160 100 L 0 20 L 0 -15 L -160 65 Z"
              fill="#2e1065"
              fillOpacity="0.4"
              stroke="#6366f1"
              strokeWidth="1.5"
            />
            <path
              d="M 0 20 L 160 100 L 160 65 L 0 -15 Z"
              fill="#312e81"
              fillOpacity="0.4"
              stroke="#6366f1"
              strokeWidth="1.5"
            />

            {/* Portal P1 (West Portal) */}
            <g transform="translate(-100, 130)">
              <rect
                x="-15"
                y="-25"
                width="30"
                height="35"
                fill={isP1Blocked ? '#ef4444' : '#10b981'}
                stroke="#f8fafc"
                strokeWidth="1"
                rx="2"
              />
              <text x="0" y="-30" fill="#f8fafc" fontSize="9" fontWeight="bold" textAnchor="middle">
                P1 {isP1Blocked ? 'BLOCKED' : 'OPEN'}
              </text>
            </g>

            {/* Portal P2 (East Portal) */}
            <g transform="translate(100, 130)">
              <rect
                x="-15"
                y="-25"
                width="30"
                height="35"
                fill={isP2Blocked ? '#ef4444' : '#10b981'}
                stroke="#f8fafc"
                strokeWidth="1"
                rx="2"
              />
              <text x="0" y="-30" fill="#f8fafc" fontSize="9" fontWeight="bold" textAnchor="middle">
                P2 {isP2Blocked ? 'BLOCKED' : 'OPEN'}
              </text>
            </g>

            {/* Miniature Servo Gate P3 */}
            <g transform="translate(0, 170)">
              {/* Microservo base bracket */}
              <rect x="-12" y="-10" width="24" height="20" fill="#1e293b" stroke="#64748b" strokeWidth="1" rx="2" />
              {/* Gate Partition Leaf */}
              <rect
                x="-10"
                y="-30"
                width="20"
                height="22"
                fill={gateState === 'OPEN' ? '#10b981' : '#f59e0b'}
                stroke="#f8fafc"
                strokeWidth="1.5"
                transform={gateState === 'OPEN' ? 'rotate(-60, 0, -10)' : 'rotate(0, 0, -10)'}
                className="transition-transform duration-500 ease-in-out"
              />
              <text x="0" y="-36" fill="#f59e0b" fontSize="10" fontWeight="bold" textAnchor="middle">
                GATE P3: {gateState}
              </text>
            </g>

            {/* Boundary B1 (West floor transfer) */}
            <g transform="translate(-150, 190)">
              <circle cx="0" cy="0" r="14" fill="#047857" stroke="#10b981" strokeWidth="2" />
              <text x="0" y="4" fill="#f8fafc" fontSize="9" fontWeight="bold" textAnchor="middle">
                B1
              </text>
            </g>

            {/* Boundary B2 (East floor transfer) */}
            <g transform="translate(150, 190)">
              <circle
                cx="0"
                cy="0"
                r="14"
                fill={isB2Blocked ? '#991b1b' : '#047857'}
                stroke={isB2Blocked ? '#ef4444' : '#10b981'}
                strokeWidth="2"
              />
              <text x="0" y="4" fill="#f8fafc" fontSize="9" fontWeight="bold" textAnchor="middle">
                {isB2Blocked ? 'B2 ✕' : 'B2'}
              </text>
            </g>
          </g>
        </svg>
      </div>

      <div className="text-center text-xs text-slate-500 z-10">
        Physical gate P3 is independently confirmed via dual microswitches before route calculation
      </div>
    </div>
  );
};
