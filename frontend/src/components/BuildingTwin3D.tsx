import React, { useState } from 'react';
import { ScenarioSnapshot } from '../types';
import {
  Layers,
  Flame,
  ShieldAlert,
  Camera,
  RotateCcw,
  Sparkles,
  Info,
  Maximize2,
} from 'lucide-react';
import { sounds } from '../utils/audio';

interface BuildingTwin3DProps {
  snapshot: ScenarioSnapshot | null;
  onToggleHazard: (targetType: 'portal' | 'boundary', targetId: 'P1' | 'P2' | 'B2') => Promise<void>;
  onTriggerArgonScan?: (targetId: string) => Promise<void>;
  selectedTarget?: string | null;
  onSelectTarget?: (target: string | null) => void;
}

export const BuildingTwin3D: React.FC<BuildingTwin3DProps> = ({
  snapshot,
  onToggleHazard,
  onTriggerArgonScan,
  selectedTarget,
  onSelectTarget,
}) => {
  const [isScanning, setIsScanning] = useState(false);
  const [hoveredEntity, setHoveredEntity] = useState<string | null>(null);

  const blockedPortals = snapshot?.blocked_portals ?? [];
  const blockedBoundaries = snapshot?.blocked_boundaries ?? [];
  const gateState = snapshot?.physical_gate_state ?? 'CLOSED';
  const plan = snapshot?.current_plan;

  const isP1Blocked = blockedPortals.includes('P1');
  const isP2Blocked = blockedPortals.includes('P2');
  const isB2Blocked = blockedBoundaries.includes('B2');

  const handleEntityTouch = async (targetType: 'portal' | 'boundary', targetId: 'P1' | 'P2' | 'B2') => {
    sounds.playBlockAlert();
    if (onSelectTarget) {
      onSelectTarget(`${targetType}:${targetId}`);
    }
    await onToggleHazard(targetType, targetId);
  };

  const handleArgonCCTVScan = async () => {
    setIsScanning(true);
    sounds.playGroundingPing();
    const detectedTarget = isP2Blocked ? 'P2' : isP1Blocked ? 'P1' : isB2Blocked ? 'B2' : 'P2';
    setTimeout(() => {
      setIsScanning(false);
      sounds.playAgentSuccess();
      if (onTriggerArgonScan) {
        onTriggerArgonScan(detectedTarget);
      }
    }, 1200);
  };

  return (
    <div className="relative w-full h-[410px] bg-slate-950/95 rounded-xl border border-slate-800/90 flex flex-col justify-between overflow-hidden shadow-2xl">
      {/* Top Header */}
      <div className="flex items-center justify-between px-3.5 py-2 bg-slate-900/80 border-b border-slate-800 text-xs">
        <div className="flex items-center space-x-2">
          <Layers className="h-4 w-4 text-cyan-400" />
          <span className="font-bold text-slate-200 uppercase font-mono tracking-wide">
            3D Spatial Twin Simulation
          </span>
          <span className="text-slate-500">•</span>
          <span className="text-[11px] text-emerald-400 font-mono">
            {isP2Blocked || isP1Blocked || isB2Blocked ? '🔥 Hazard Active' : '🟢 Nominal Egress'}
          </span>
        </div>

        {/* Scan & Actions */}
        <div className="flex items-center space-x-2 text-[11px]">
          <button
            onClick={handleArgonCCTVScan}
            disabled={isScanning}
            className="flex items-center space-x-1 px-2.5 py-1 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white rounded text-xs font-semibold shadow-neon-cyan transition"
          >
            <Camera className="h-3 w-3" />
            <span>{isScanning ? 'Scanning...' : 'Scan via Argon'}</span>
          </button>
        </div>
      </div>

      {/* 3D Isometric Viewport Canvas */}
      <div className="relative flex-1 bg-[#070b16] flex items-center justify-center overflow-hidden">
        {/* Ambient Dark Blueprint Grid */}
        <div className="absolute inset-0 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:20px_20px] opacity-35" />

        {/* Laser Sweep Animation */}
        {isScanning && (
          <div className="absolute inset-0 pointer-events-none z-30">
            <div className="w-full h-1 bg-cyan-400 shadow-[0_0_20px_#22d3ee] animate-pulse absolute top-1/2 -translate-y-1/2" />
            <div className="absolute top-4 right-4 bg-cyan-950/90 border border-cyan-500/60 text-cyan-300 px-2 py-1 rounded text-[10px] font-mono animate-pulse">
              [ARGON CCTV SCANNING 3D TWIN...]
            </div>
          </div>
        )}

        {/* 3D Isometric SVG Model matching reference photo */}
        <svg viewBox="0 0 640 370" className="w-full h-full drop-shadow-2xl select-none">
          <defs>
            {/* Filters */}
            <filter id="neonGreenGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="flameSmokeGlow" x="-60%" y="-60%" width="220%" height="220%">
              <feGaussianBlur stdDeviation="8" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <linearGradient id="wallGradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#f8fafc" />
              <stop offset="100%" stopColor="#94a3b8" />
            </linearGradient>
            <linearGradient id="wallShadow" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#64748b" />
              <stop offset="100%" stopColor="#334155" />
            </linearGradient>
            <linearGradient id="greenRouteGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.4" />
              <stop offset="50%" stopColor="#34d399" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0.4" />
            </linearGradient>
          </defs>

          <g transform="translate(320, 80)">
            {/* Base Tabletop Slab */}
            <path
              d="M 0 30 L 260 160 L 0 290 L -260 160 Z"
              fill="#0b1120"
              stroke="#1e293b"
              strokeWidth="2"
            />
            {/* Slab Extrusion */}
            <path d="M -260 160 L 0 290 L 0 310 L -260 180 Z" fill="#060913" stroke="#1e293b" strokeWidth="1" />
            <path d="M 0 290 L 260 160 L 260 180 L 0 310 Z" fill="#080d1a" stroke="#1e293b" strokeWidth="1" />

            {/* Room Floor Inset (Grey/Blue Slab) */}
            <path
              d="M 0 45 L 230 160 L 0 275 L -230 160 Z"
              fill="#111827"
              stroke="#374151"
              strokeWidth="1.5"
            />

            {/* GREEN ILLUMINATED EVACUATION PATHS (Floor Channels) */}
            {/* West Route (to Exit B1) */}
            <path
              d="M 0 160 L -140 160 L -200 170"
              fill="none"
              stroke={isP1Blocked ? '#ef4444' : '#10b981'}
              strokeWidth="16"
              strokeLinecap="round"
              strokeOpacity={isP1Blocked ? '0.2' : '0.7'}
              filter={isP1Blocked ? undefined : 'url(#neonGreenGlow)'}
            />
            {/* East Route (to Exit B2) */}
            <path
              d="M 0 160 L 140 160 L 200 170"
              fill="none"
              stroke={isP2Blocked ? '#ef4444' : '#10b981'}
              strokeWidth="16"
              strokeLinecap="round"
              strokeOpacity={isP2Blocked ? '0.2' : '0.7'}
              filter={isP2Blocked ? undefined : 'url(#neonGreenGlow)'}
            />
            {/* Central Reserve Bypass Route (when P3 is OPEN) */}
            {gateState === 'OPEN' && (
              <path
                d="M 0 110 L 0 190 L 140 190 L 200 170"
                fill="none"
                stroke="#10b981"
                strokeWidth="12"
                strokeLinecap="round"
                strokeOpacity="0.85"
                filter="url(#neonGreenGlow)"
              />
            )}

            {/* WHITE ARCHITECTURAL 3D WALLS (Isometric Cutaway Partition Model) */}
            {/* Outer Perimeter Back Walls */}
            <path d="M -230 160 L 0 45 L 0 10 L -230 125 Z" fill="url(#wallShadow)" stroke="#94a3b8" strokeWidth="1.5" />
            <path d="M 0 45 L 230 160 L 230 125 L 0 10 Z" fill="url(#wallGradient)" stroke="#cbd5e1" strokeWidth="1.5" />

            {/* Interior Room Partition Walls (White Blocks with depth) */}
            {/* West Room Cluster */}
            <g>
              <path d="M -160 110 L -80 70 L -80 40 L -160 80 Z" fill="url(#wallGradient)" stroke="#cbd5e1" strokeWidth="1" />
              <path d="M -80 70 L -40 90 L -40 60 L -80 40 Z" fill="url(#wallShadow)" stroke="#94a3b8" strokeWidth="1" />
              <path d="M -160 145 L -80 185 L -80 155 L -160 115 Z" fill="url(#wallGradient)" stroke="#cbd5e1" strokeWidth="1" />
            </g>

            {/* East Room Cluster */}
            <g>
              <path d="M 80 70 L 160 110 L 160 80 L 80 40 Z" fill="url(#wallGradient)" stroke="#cbd5e1" strokeWidth="1" />
              <path d="M 40 90 L 80 70 L 80 40 L 40 60 Z" fill="url(#wallShadow)" stroke="#94a3b8" strokeWidth="1" />
              <path d="M 80 185 L 160 145 L 160 115 L 80 155 Z" fill="url(#wallGradient)" stroke="#cbd5e1" strokeWidth="1" />
            </g>

            {/* Front Perimeter Walls with Door Openings */}
            <path d="M -230 160 L -170 190 L -170 165 L -230 135 Z" fill="url(#wallGradient)" stroke="#cbd5e1" strokeWidth="1" />
            <path d="M -130 210 L 0 275 L 0 250 L -130 185 Z" fill="url(#wallGradient)" stroke="#cbd5e1" strokeWidth="1" />
            <path d="M 0 275 L 130 210 L 130 185 L 0 250 Z" fill="url(#wallShadow)" stroke="#94a3b8" strokeWidth="1" />
            <path d="M 170 190 L 230 160 L 230 135 L 170 165 Z" fill="url(#wallShadow)" stroke="#94a3b8" strokeWidth="1" />

            {/* FLOATING REAL-TIME OCCUPANCY METRIC HUD BADGES IN 3D SPACE */}
            <g transform="translate(0, 85)">
              <rect x="-65" y="-12" width="130" height="22" rx="4" fill="#090d16" stroke="#4338ca" strokeWidth="1" />
              <text x="0" y="3" fill="#c7d2fe" fontSize="9" fontWeight="bold" textAnchor="middle">
                EVENT HALL: {plan?.zone_occupancy?.['EVENT'] ?? plan?.remaining_population ?? 120} pers
              </text>
            </g>

            <g transform="translate(-105, 115)">
              <rect x="-46" y="-10" width="92" height="19" rx="3" fill="#090d16" stroke="#10b981" strokeWidth="1" />
              <text x="0" y="3" fill="#34d399" fontSize="8" fontWeight="bold" textAnchor="middle">
                WEST: {plan?.zone_occupancy?.['WEST'] ?? 0} pers
              </text>
            </g>

            <g transform="translate(105, 115)">
              <rect x="-46" y="-10" width="92" height="19" rx="3" fill="#090d16" stroke={isP2Blocked ? '#ef4444' : '#10b981'} strokeWidth="1" />
              <text x="0" y="3" fill={isP2Blocked ? '#ef4444' : '#34d399'} fontSize="8" fontWeight="bold" textAnchor="middle">
                {isP2Blocked ? 'BLOCKED 🔥' : `EAST: ${plan?.zone_occupancy?.['EAST'] ?? 0} pers`}
              </text>
            </g>

            {/* MINIATURE SERVO GATE P3 (Center Reserve Bypass) */}
            <g transform="translate(0, 160)">
              {/* Gate bracket */}
              <rect x="-8" y="-8" width="16" height="16" fill="#1e293b" stroke="#64748b" rx="2" />
              {/* Physical Gate Leaf (Swinging arm) */}
              <line
                x1="0"
                y1="0"
                x2={gateState === 'OPEN' ? '24' : '0'}
                y2={gateState === 'OPEN' ? '-18' : '20'}
                stroke={gateState === 'OPEN' ? '#10b981' : '#f59e0b'}
                strokeWidth="4"
                strokeLinecap="round"
                className="transition-all duration-700 ease-in-out"
              />
              <circle cx="0" cy="0" r="3" fill="#ffffff" />
              <text x="0" y="-14" fill="#f59e0b" fontSize="8" fontWeight="bold" textAnchor="middle">
                P3 GATE ({gateState})
              </text>
            </g>

            {/* ANIMATED GREEN DOT OCCUPANTS (Streaming along routes) */}
            {!isP1Blocked && (
              <g>
                <circle cx="-30" cy="160" r="3.5" fill="#34d399" className="animate-pulse" filter="url(#neonGreenGlow)" />
                <circle cx="-70" cy="160" r="3.5" fill="#34d399" className="animate-pulse" filter="url(#neonGreenGlow)" />
                <circle cx="-110" cy="160" r="3.5" fill="#34d399" className="animate-pulse" filter="url(#neonGreenGlow)" />
                <circle cx="-150" cy="165" r="3.5" fill="#34d399" className="animate-pulse" filter="url(#neonGreenGlow)" />
              </g>
            )}
            {!isP2Blocked && (
              <g>
                <circle cx="30" cy="160" r="3.5" fill="#34d399" className="animate-pulse" filter="url(#neonGreenGlow)" />
                <circle cx="70" cy="160" r="3.5" fill="#34d399" className="animate-pulse" filter="url(#neonGreenGlow)" />
                <circle cx="110" cy="160" r="3.5" fill="#34d399" className="animate-pulse" filter="url(#neonGreenGlow)" />
                <circle cx="150" cy="165" r="3.5" fill="#34d399" className="animate-pulse" filter="url(#neonGreenGlow)" />
              </g>
            )}
            {gateState === 'OPEN' && (
              <g>
                <circle cx="0" cy="130" r="3.5" fill="#34d399" className="animate-pulse" filter="url(#neonGreenGlow)" />
                <circle cx="40" cy="180" r="3.5" fill="#34d399" className="animate-pulse" filter="url(#neonGreenGlow)" />
                <circle cx="90" cy="180" r="3.5" fill="#34d399" className="animate-pulse" filter="url(#neonGreenGlow)" />
              </g>
            )}

            {/* BIG NEON GREEN EXIT ARROWS (Exactly matching reference photo!) */}
            {/* West Exit Arrow pointing bottom-left */}
            <g
              transform="translate(-230, 185)"
              className="cursor-pointer group"
              onClick={() => handleEntityTouch('boundary', 'B2')}
            >
              {/* Glowing Arrow Path */}
              <polygon
                points="-35,25 0,0 -15,0 -15,-20 -35,-20 -35,0 -50,0"
                fill="#10b981"
                filter="url(#neonGreenGlow)"
                className="group-hover:scale-110 transition-transform"
              />
              <text x="-30" y="42" fill="#34d399" fontSize="9" fontWeight="bold" textAnchor="middle">
                EXIT B1
              </text>
              <text x="-30" y="54" fill="#a7f3d0" fontSize="8" textAnchor="middle">
                {plan?.boundary_breakdown?.['B1'] ?? 60} Serviced
              </text>
            </g>

            {/* East Exit Arrow pointing bottom-right */}
            <g
              transform="translate(230, 185)"
              className="cursor-pointer group"
              onClick={() => handleEntityTouch('boundary', 'B2')}
            >
              {isB2Blocked ? (
                /* Blocked Exit Marker */
                <g>
                  <circle cx="20" cy="10" r="16" fill="#991b1b" stroke="#ef4444" strokeWidth="2" />
                  <text x="20" y="14" fill="#ffffff" fontSize="12" fontWeight="bold" textAnchor="middle">
                    ✕
                  </text>
                  <text x="20" y="38" fill="#ef4444" fontSize="9" fontWeight="bold" textAnchor="middle">
                    B2 BLOCKED
                  </text>
                  <text x="20" y="50" fill="#fca5a5" fontSize="8" textAnchor="middle">
                    0 Serviced (Downstream Failure)
                  </text>
                </g>
              ) : (
                /* Glowing Green Arrow Path */
                <g>
                  <polygon
                    points="35,25 0,0 15,0 15,-20 35,-20 35,0 50,0"
                    fill="#10b981"
                    filter="url(#neonGreenGlow)"
                    className="group-hover:scale-110 transition-transform"
                  />
                  <text x="30" y="42" fill="#34d399" fontSize="9" fontWeight="bold" textAnchor="middle">
                    EXIT B2
                  </text>
                  <text x="30" y="54" fill="#a7f3d0" fontSize="8" textAnchor="middle">
                    {plan?.boundary_breakdown?.['B2'] ?? 60} Serviced
                  </text>
                </g>
              )}
            </g>

            {/* PORTAL P1 (West Hall Doorway) */}
            <g
              transform="translate(-140, 160)"
              className="cursor-pointer"
              onClick={() => handleEntityTouch('portal', 'P1')}
            >
              <rect x="-8" y="-16" width="16" height="32" fill={isP1Blocked ? '#ef4444' : '#10b981'} rx="2" />
              {isP1Blocked && (
                <text x="0" y="-22" fill="#ef4444" fontSize="9" fontWeight="bold" textAnchor="middle">
                  P1 BLOCKED
                </text>
              )}
            </g>

            {/* PORTAL P2 (East Hall Doorway) & VERTICAL BILLOWING SMOKE/FIRE COLUMN */}
            <g
              transform="translate(140, 160)"
              className="cursor-pointer"
              onClick={() => handleEntityTouch('portal', 'P2')}
            >
              <rect x="-8" y="-16" width="16" height="32" fill={isP2Blocked ? '#ef4444' : '#10b981'} rx="2" />

              {/* VIBRANT BILLOWING RED SMOKE & FIRE COLUMN (Matching photo!) */}
              {isP2Blocked && (
                <g transform="translate(0, -10)" className="pointer-events-none select-none">
                  {/* Fire Base Embers */}
                  <ellipse cx="0" cy="0" rx="14" ry="7" fill="#fbbf24" filter="url(#flameSmokeGlow)" className="animate-pulse" />
                  <ellipse cx="0" cy="-6" rx="10" ry="6" fill="#f97316" filter="url(#flameSmokeGlow)" />

                  {/* Rising Smoke Plume (Multi-tiered expanding reddish-orange cloud) */}
                  <g className="animate-pulse">
                    <circle cx="-4" cy="-25" r="14" fill="#ef4444" opacity="0.85" filter="url(#flameSmokeGlow)" />
                    <circle cx="6" cy="-35" r="18" fill="#f87171" opacity="0.8" filter="url(#flameSmokeGlow)" />
                    <circle cx="-2" cy="-55" r="22" fill="#ea580c" opacity="0.75" filter="url(#flameSmokeGlow)" />
                    <circle cx="5" cy="-80" r="26" fill="#dc2626" opacity="0.65" filter="url(#flameSmokeGlow)" />
                    <circle cx="-3" cy="-110" r="30" fill="#991b1b" opacity="0.5" filter="url(#flameSmokeGlow)" />
                    <circle cx="2" cy="-140" r="34" fill="#7f1d1d" opacity="0.35" filter="url(#flameSmokeGlow)" />
                  </g>

                  {/* Target Hazard Label */}
                  <rect x="-38" y="-175" width="76" height="18" rx="3" fill="#0f172a" stroke="#ef4444" strokeWidth="1" />
                  <text x="0" y="-162" fill="#ef4444" fontSize="9" fontWeight="bold" textAnchor="middle">
                    🔥 P2 HAZARD
                  </text>
                </g>
              )}
            </g>
          </g>
        </svg>

        {/* Quick Touch Instruction Badge */}
        <div className="absolute bottom-2 left-2 flex items-center space-x-2 bg-slate-900/90 px-2.5 py-1 rounded-lg border border-slate-800 text-[11px] backdrop-blur font-mono text-slate-300">
          <Sparkles className="h-3 w-3 text-cyan-400" />
          <span>Touch Doorway (P1/P2) or Exit (B2) to Place/Clear Hazard</span>
        </div>

        {/* Live Evacuation Metric HUD */}
        <div className="absolute top-2 right-2 bg-slate-900/90 px-3 py-1.5 rounded-lg border border-slate-800 text-xs font-mono text-right backdrop-blur">
          <div className="text-slate-400 text-[10px]">REMAINING POPULATION</div>
          <div className="text-lg font-bold text-cyan-400">
            {plan ? plan.remaining_population : 120} <span className="text-xs text-slate-500">/ 120</span>
          </div>
        </div>
      </div>

      {/* Footer Status Bar */}
      <div className="px-3.5 py-2 bg-slate-900 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400 font-mono">
        <div className="flex items-center space-x-2">
          <Info className="h-3.5 w-3.5 text-cyan-400" />
          <span>P3 express connector redirects flow to East Exit B2</span>
        </div>
        <div>
          Confirmed Servo: <strong className={gateState === 'OPEN' ? 'text-emerald-400' : 'text-amber-400'}>{gateState}</strong>
        </div>
      </div>
    </div>
  );
};