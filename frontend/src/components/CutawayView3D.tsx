import React, { useState, useEffect } from 'react';
import { ScenarioSnapshot } from '../types';
import {
  Layers,
  Flame,
  ShieldAlert,
  AlertTriangle,
  RotateCcw,
  Camera,
  CheckCircle2,
  Cpu,
  Info,
  Sparkles,
} from 'lucide-react';
import { sounds } from '../utils/audio';

interface CutawayView3DProps {
  snapshot: ScenarioSnapshot | null;
  onToggleHazard: (targetType: 'portal' | 'boundary', targetId: 'P1' | 'P2' | 'B2') => Promise<void>;
  onTriggerArgonScan?: (targetId: string) => Promise<void>;
  selectedTarget?: string | null;
  onSelectTarget?: (target: string | null) => void;
}

export type HazardKind = 'FIRE' | 'BARRIER' | 'DEBRIS';

export const CutawayView3D: React.FC<CutawayView3DProps> = ({
  snapshot,
  onToggleHazard,
  onTriggerArgonScan,
  selectedTarget,
  onSelectTarget,
}) => {
  const [selectedHazardKind, setSelectedHazardKind] = useState<HazardKind>('FIRE');
  const [isScanning, setIsScanning] = useState(false);
  const [hoveredEntity, setHoveredEntity] = useState<string | null>(null);
  const [activeBoundingBox, setActiveBoundingBox] = useState<{
    target: string;
    x: number;
    y: number;
    w: number;
    h: number;
  } | null>(null);

  const blockedPortals = snapshot?.blocked_portals ?? [];
  const blockedBoundaries = snapshot?.blocked_boundaries ?? [];
  const gateState = snapshot?.physical_gate_state ?? 'CLOSED';
  const plan = snapshot?.current_plan;

  const isP1Blocked = blockedPortals.includes('P1');
  const isP2Blocked = blockedPortals.includes('P2');
  const isB2Blocked = blockedBoundaries.includes('B2');

  // Handle direct touch/click on portal or boundary
  const handleEntityTouch = async (targetType: 'portal' | 'boundary', targetId: 'P1' | 'P2' | 'B2') => {
    sounds.playBlockAlert();
    if (onSelectTarget) {
      onSelectTarget(`${targetType}:${targetId}`);
    }
    await onToggleHazard(targetType, targetId);
  };

  // Trigger Argon CCTV Inspection Scan
  const handleArgonCCTVScan = async () => {
    setIsScanning(true);
    sounds.playGroundingPing();

    // Determine target to scan
    const detectedTarget = isP2Blocked ? 'P2' : isP1Blocked ? 'P1' : isB2Blocked ? 'B2' : 'P2';

    // Show AI bounding box at corresponding location
    setTimeout(() => {
      if (detectedTarget === 'P2') {
        setActiveBoundingBox({ target: 'portal:P2', x: 380, y: 110, w: 90, h: 70 });
      } else if (detectedTarget === 'P1') {
        setActiveBoundingBox({ target: 'portal:P1', x: 130, y: 110, w: 90, h: 70 });
      } else {
        setActiveBoundingBox({ target: 'boundary:B2', x: 420, y: 220, w: 80, h: 60 });
      }
      setIsScanning(false);
      sounds.playAgentSuccess();
      if (onTriggerArgonScan) {
        onTriggerArgonScan(detectedTarget);
      }
    }, 1200);
  };

  // Clear bounding box after timeout
  useEffect(() => {
    if (activeBoundingBox) {
      const timer = setTimeout(() => setActiveBoundingBox(null), 8000);
      return () => clearTimeout(timer);
    }
  }, [activeBoundingBox]);

  return (
    <div className="relative w-full bg-slate-950/95 rounded-xl border border-slate-800 p-4 flex flex-col space-y-3 overflow-hidden shadow-2xl">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400 z-10 border-b border-slate-800/80 pb-2">
        <div className="flex items-center space-x-2">
          <Layers className="h-4 w-4 text-sky-400" />
          <span className="font-bold text-slate-200">Interactive 3D Building Twin</span>
          <span className="text-slate-500">•</span>
          <span className="text-emerald-400 font-mono text-[11px] bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/60">
            Touch & Place Hazards Active
          </span>
        </div>

        {/* Hazard Selector & Scan Button */}
        <div className="flex items-center space-x-2">
          {/* Hazard Type Selector */}
          <div className="flex items-center space-x-1 bg-slate-900 border border-slate-800 p-0.5 rounded">
            <span className="text-[10px] text-slate-500 px-1 font-semibold uppercase">Hazard:</span>
            <button
              onClick={() => setSelectedHazardKind('FIRE')}
              className={`flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-bold transition ${
                selectedHazardKind === 'FIRE'
                  ? 'bg-rose-600 text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Flame className="h-3 w-3 text-amber-300" />
              <span>Fire</span>
            </button>
            <button
              onClick={() => setSelectedHazardKind('BARRIER')}
              className={`flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-bold transition ${
                selectedHazardKind === 'BARRIER'
                  ? 'bg-amber-600 text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <ShieldAlert className="h-3 w-3 text-amber-200" />
              <span>Barrier</span>
            </button>
            <button
              onClick={() => setSelectedHazardKind('DEBRIS')}
              className={`flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-bold transition ${
                selectedHazardKind === 'DEBRIS'
                  ? 'bg-purple-600 text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <AlertTriangle className="h-3 w-3 text-purple-300" />
              <span>Debris</span>
            </button>
          </div>

          {/* CCTV Drone Scan Button */}
          <button
            onClick={handleArgonCCTVScan}
            disabled={isScanning}
            className="flex items-center space-x-1.5 px-2.5 py-1 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white rounded text-xs font-semibold shadow glow-cyan transition"
          >
            <Camera className="h-3.5 w-3.5" />
            <span>{isScanning ? 'Argon Scanning...' : 'Scan via Argon'}</span>
          </button>
        </div>
      </div>

      {/* Touch Instruction Prompt for Judges */}
      <div className="flex items-center justify-between text-[11px] px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800">
        <div className="flex items-center space-x-2 text-slate-300">
          <Sparkles className="h-3.5 w-3.5 text-sky-400 animate-pulse" />
          <span>
            <strong className="text-sky-300">Judge Interaction:</strong> Touch or click any doorway (P1, P2) or stairwell (B2) below to place/clear a {selectedHazardKind.toLowerCase()} hazard in real-time.
          </span>
        </div>
        <div className="text-[10px] font-mono text-slate-500">
          Physical Servo Gate: <strong className={gateState === 'OPEN' ? 'text-emerald-400' : 'text-amber-400'}>{gateState}</strong>
        </div>
      </div>

      {/* 3D Isometric SVG Canvas */}
      <div className="relative w-full h-[380px] bg-gradient-to-b from-[#0b0f19] to-[#060911] rounded-lg border border-slate-800/80 flex items-center justify-center overflow-hidden">
        {/* Ambient Grid Background */}
        <div className="absolute inset-0 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:24px_24px] opacity-30"></div>

        {/* Laser Scanning Line Animation when active */}
        {isScanning && (
          <div className="absolute inset-0 pointer-events-none z-30">
            <div className="w-full h-1 bg-cyan-400 shadow-[0_0_15px_#22d3ee] animate-pulse absolute top-1/2 -translate-y-1/2"></div>
            <div className="absolute top-4 right-4 bg-cyan-950/80 border border-cyan-500/50 text-cyan-300 px-2 py-1 rounded text-[10px] font-mono animate-pulse">
              [ARGON CCTV SCAN IN PROGRESS...]
            </div>
          </div>
        )}

        <svg viewBox="0 0 600 360" className="w-full h-full drop-shadow-2xl select-none">
          <defs>
            {/* Gradients */}
            <linearGradient id="hallFloor" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#1e1b4b" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#0f172a" stopOpacity="0.95" />
            </linearGradient>
            <linearGradient id="flameGrad" x1="0%" y1="100%" x2="0%" y2="0%">
              <stop offset="0%" stopColor="#ef4444" />
              <stop offset="60%" stopColor="#f59e0b" />
              <stop offset="100%" stopColor="#fef08a" />
            </linearGradient>
            <linearGradient id="reserveTunnelGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#064e3b" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#022c22" stopOpacity="0.9" />
            </linearGradient>
            <filter id="neonGlowCyan" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="hazardGlowRed" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <g transform="translate(300, 50)">
            {/* Level 0: Foundation / Ground Slab */}
            <path
              d="M 0 0 L 260 130 L 0 260 L -260 130 Z"
              fill="#060911"
              stroke="#1e293b"
              strokeWidth="2"
            />
            <path
              d="M -260 130 L 0 260 L 0 280 L -260 150 Z"
              fill="#030712"
              stroke="#1e293b"
              strokeWidth="1"
            />
            <path
              d="M 0 260 L 260 130 L 260 150 L 0 280 Z"
              fill="#050a14"
              stroke="#1e293b"
              strokeWidth="1"
            />

            {/* Level 1: Upper Event Room (Elevated Architectural Cutaway) */}
            <g transform="translate(0, 20)">
              {/* Event Hall Floor */}
              <path
                d="M 0 0 L 170 85 L 0 170 L -170 85 Z"
                fill="url(#hallFloor)"
                stroke="#4338ca"
                strokeWidth="2"
                className="drop-shadow-lg"
              />

              {/* Glass Wall Cutaway Back Panels */}
              <path
                d="M -170 85 L 0 0 L 0 -35 L -170 50 Z"
                fill="#312e81"
                fillOpacity="0.25"
                stroke="#6366f1"
                strokeWidth="1.5"
                strokeDasharray="4 2"
              />
              <path
                d="M 0 0 L 170 85 L 170 50 L 0 -35 Z"
                fill="#3730a3"
                fillOpacity="0.25"
                stroke="#6366f1"
                strokeWidth="1.5"
                strokeDasharray="4 2"
              />

              {/* Hall Label & Occupants Metric */}
              <g transform="translate(0, 80)">
                <text x="0" y="-12" fill="#c7d2fe" fontSize="12" fontWeight="bold" textAnchor="middle">
                  SHACK15 MAIN EVENT HALL
                </text>
                <text x="0" y="4" fill="#a5b4fc" fontSize="10" textAnchor="middle">
                  Remaining Population: {plan ? plan.remaining_population : 120} / 120
                </text>

                {/* Animated Crowd Avatar Particles */}
                {Array.from({ length: 14 }).map((_, i) => {
                  const angle = (i / 14) * Math.PI * 2;
                  const rx = 40 + (i % 3) * 12;
                  const ry = 20 + (i % 2) * 8;
                  const cx = Math.cos(angle) * rx;
                  const cy = Math.sin(angle) * ry;
                  return (
                    <circle
                      key={i}
                      cx={cx}
                      cy={cy}
                      r="2.5"
                      fill="#38bdf8"
                      opacity="0.8"
                      className="animate-pulse"
                    />
                  );
                })}
              </g>

              {/* Floor Evacuation Directional Pulse Lines (West & East) */}
              {/* West Egress Path */}
              <path
                d="M -30 90 L -120 85 L -135 90"
                fill="none"
                stroke={isP1Blocked ? '#ef4444' : '#10b981'}
                strokeWidth="2.5"
                strokeDasharray="4 3"
                filter={isP1Blocked ? 'url(#hazardGlowRed)' : 'url(#neonGlowCyan)'}
              />
              {/* East Egress Path */}
              <path
                d="M 30 90 L 120 85 L 135 90"
                fill="none"
                stroke={isP2Blocked ? '#ef4444' : '#10b981'}
                strokeWidth="2.5"
                strokeDasharray="4 3"
                filter={isP2Blocked ? 'url(#hazardGlowRed)' : 'url(#neonGlowCyan)'}
              />

              {/* Central Reserve Express Path (from Hall to P3) */}
              <path
                d="M 0 110 L 0 165"
                fill="none"
                stroke={gateState === 'OPEN' ? '#10b981' : '#f59e0b'}
                strokeWidth={gateState === 'OPEN' ? '3' : '1.5'}
                strokeDasharray={gateState === 'OPEN' ? 'none' : '3 3'}
                filter={gateState === 'OPEN' ? 'url(#neonGlowCyan)' : undefined}
              />
            </g>

            {/* Central Reserve Tunnel & Miniature Servo Barrier P3 */}
            <g transform="translate(0, 185)">
              {/* Reserve Canal Floor */}
              <path
                d="M -25 0 L 25 0 L 40 35 L -10 35 Z"
                fill={gateState === 'OPEN' ? 'url(#reserveTunnelGrad)' : '#1e293b'}
                stroke={gateState === 'OPEN' ? '#10b981' : '#64748b'}
                strokeWidth="1.5"
              />

              {/* Microservo Motor Bracket */}
              <rect x="-14" y="-8" width="28" height="18" fill="#0f172a" stroke="#475569" strokeWidth="1" rx="2" />
              {/* PCA9685 Wiring Visual */}
              <line x1="-10" y1="10" x2="-10" y2="20" stroke="#f59e0b" strokeWidth="1" />
              <line x1="0" y1="10" x2="0" y2="20" stroke="#ef4444" strokeWidth="1" />
              <line x1="10" y1="10" x2="10" y2="20" stroke="#3b82f6" strokeWidth="1" />

              {/* Physical Gate Barrier Leaf (Animated Rotation) */}
              <rect
                x="-12"
                y="-28"
                width="24"
                height="22"
                fill={gateState === 'OPEN' ? '#10b981' : gateState === 'TRANSIT' ? '#f59e0b' : '#ef4444'}
                stroke="#f8fafc"
                strokeWidth="1.5"
                rx="2"
                transform={gateState === 'OPEN' ? 'rotate(-65, 0, -8)' : 'rotate(0, 0, -8)'}
                className="transition-transform duration-700 ease-in-out cursor-pointer"
                onClick={() => handleEntityTouch('portal', 'P2')}
              />

              {/* Gate P3 Status Badge */}
              <g transform="translate(0, -36)">
                <rect x="-42" y="-10" width="84" height="18" rx="4" fill="#020617" stroke={gateState === 'OPEN' ? '#10b981' : '#f59e0b'} strokeWidth="1" />
                <text x="0" y="3" fill="#f8fafc" fontSize="9" fontWeight="bold" textAnchor="middle">
                  P3 GATE: {gateState}
                </text>
              </g>

              {/* Dual Microswitch Indicators (D2 & D3) */}
              <g transform="translate(-40, 6)">
                <circle cx="0" cy="0" r="3.5" fill={gateState === 'CLOSED' ? '#10b981' : '#334155'} />
                <text x="-6" y="3" fill="#94a3b8" fontSize="7" textAnchor="end">D2</text>
              </g>
              <g transform="translate(40, 6)">
                <circle cx="0" cy="0" r="3.5" fill={gateState === 'OPEN' ? '#10b981' : '#334155'} />
                <text x="6" y="3" fill="#94a3b8" fontSize="7" textAnchor="start">D3</text>
              </g>
            </g>

            {/* PORTAL P1 (West Hall Door) - Touch Target */}
            <g
              transform="translate(-140, 110)"
              className="cursor-pointer group"
              onClick={() => handleEntityTouch('portal', 'P1')}
              onMouseEnter={() => setHoveredEntity('portal:P1')}
              onMouseLeave={() => setHoveredEntity(null)}
            >
              {/* Touch Zone Highlight */}
              <ellipse cx="0" cy="0" rx="35" ry="25" fill={isP1Blocked ? '#ef4444' : '#0284c7'} fillOpacity="0.15" />
              
              {/* Door Frame */}
              <rect
                x="-16"
                y="-26"
                width="32"
                height="38"
                fill={isP1Blocked ? '#991b1b' : '#047857'}
                stroke={isP1Blocked ? '#ef4444' : '#10b981'}
                strokeWidth="2"
                rx="3"
                className="group-hover:scale-105 transition-transform"
              />

              {/* Hazard Visual Rendering on P1 */}
              {isP1Blocked ? (
                <g>
                  {/* Fire / Barrier Icon */}
                  <polygon points="0,-22 10,-5 -10,-5" fill="url(#flameGrad)" className="animate-bounce" />
                  <rect x="-14" y="-8" width="28" height="6" fill="#f59e0b" stroke="#000" strokeWidth="0.5" />
                  <rect x="-14" y="2" width="28" height="6" fill="#f59e0b" stroke="#000" strokeWidth="0.5" />
                  <text x="0" y="-32" fill="#ef4444" fontSize="10" fontWeight="bold" textAnchor="middle">
                    🔥 P1 BLOCKED
                  </text>
                </g>
              ) : (
                <g>
                  <text x="0" y="-4" fill="#f8fafc" fontSize="10" fontWeight="bold" textAnchor="middle">
                    P1
                  </text>
                  <text x="0" y="-32" fill="#34d399" fontSize="10" fontWeight="bold" textAnchor="middle">
                    P1 OPEN
                  </text>
                </g>
              )}

              {/* Touch Helper Tag */}
              <rect x="-24" y="16" width="48" height="14" rx="3" fill="#0f172a" stroke="#334155" strokeWidth="1" />
              <text x="0" y="26" fill="#94a3b8" fontSize="8" textAnchor="middle">
                [Tap to {isP1Blocked ? 'Clear' : 'Block'}]
              </text>
            </g>

            {/* PORTAL P2 (East Hall Door) - Touch Target */}
            <g
              transform="translate(140, 110)"
              className="cursor-pointer group"
              onClick={() => handleEntityTouch('portal', 'P2')}
              onMouseEnter={() => setHoveredEntity('portal:P2')}
              onMouseLeave={() => setHoveredEntity(null)}
            >
              {/* Touch Zone Highlight */}
              <ellipse cx="0" cy="0" rx="35" ry="25" fill={isP2Blocked ? '#ef4444' : '#0284c7'} fillOpacity="0.15" />
              
              {/* Door Frame */}
              <rect
                x="-16"
                y="-26"
                width="32"
                height="38"
                fill={isP2Blocked ? '#991b1b' : '#047857'}
                stroke={isP2Blocked ? '#ef4444' : '#10b981'}
                strokeWidth="2"
                rx="3"
                className="group-hover:scale-105 transition-transform"
              />

              {/* Hazard Visual Rendering on P2 */}
              {isP2Blocked ? (
                <g>
                  <polygon points="0,-22 10,-5 -10,-5" fill="url(#flameGrad)" className="animate-bounce" />
                  <rect x="-14" y="-8" width="28" height="6" fill="#f59e0b" stroke="#000" strokeWidth="0.5" />
                  <rect x="-14" y="2" width="28" height="6" fill="#f59e0b" stroke="#000" strokeWidth="0.5" />
                  <text x="0" y="-32" fill="#ef4444" fontSize="10" fontWeight="bold" textAnchor="middle">
                    🔥 P2 BLOCKED
                  </text>
                </g>
              ) : (
                <g>
                  <text x="0" y="-4" fill="#f8fafc" fontSize="10" fontWeight="bold" textAnchor="middle">
                    P2
                  </text>
                  <text x="0" y="-32" fill="#34d399" fontSize="10" fontWeight="bold" textAnchor="middle">
                    P2 OPEN
                  </text>
                </g>
              )}

              {/* Touch Helper Tag */}
              <rect x="-24" y="16" width="48" height="14" rx="3" fill="#0f172a" stroke="#334155" strokeWidth="1" />
              <text x="0" y="26" fill="#94a3b8" fontSize="8" textAnchor="middle">
                [Tap to {isP2Blocked ? 'Clear' : 'Block'}]
              </text>
            </g>

            {/* BOUNDARY B1 (West Floor Stairwell to Street) */}
            <g transform="translate(-180, 215)">
              <circle cx="0" cy="0" r="18" fill="#047857" stroke="#10b981" strokeWidth="2" />
              <text x="0" y="-2" fill="#f8fafc" fontSize="10" fontWeight="bold" textAnchor="middle">
                B1
              </text>
              <text x="0" y="8" fill="#a7f3d0" fontSize="7" textAnchor="middle">
                2 p/s
              </text>
              <text x="0" y="28" fill="#34d399" fontSize="9" fontWeight="bold" textAnchor="middle">
                West Exit
              </text>
            </g>

            {/* BOUNDARY B2 (East Floor Stairwell to Street) - Touch Target */}
            <g
              transform="translate(180, 215)"
              className="cursor-pointer group"
              onClick={() => handleEntityTouch('boundary', 'B2')}
              onMouseEnter={() => setHoveredEntity('boundary:B2')}
              onMouseLeave={() => setHoveredEntity(null)}
            >
              {/* Touch Zone Highlight */}
              <ellipse cx="0" cy="0" rx="35" ry="25" fill={isB2Blocked ? '#ef4444' : '#0284c7'} fillOpacity="0.15" />

              <circle
                cx="0"
                cy="0"
                r="18"
                fill={isB2Blocked ? '#991b1b' : '#047857'}
                stroke={isB2Blocked ? '#ef4444' : '#10b981'}
                strokeWidth="2"
                className="group-hover:scale-105 transition-transform"
              />
              <text x="0" y="-2" fill="#f8fafc" fontSize="10" fontWeight="bold" textAnchor="middle">
                B2
              </text>
              <text x="0" y="8" fill="#f8fafc" fontSize="7" textAnchor="middle">
                {isB2Blocked ? 'BLOCKED' : '2 p/s'}
              </text>

              {/* Hazard Strobe on B2 */}
              {isB2Blocked && (
                <g>
                  <circle cx="0" cy="0" r="24" fill="none" stroke="#ef4444" strokeWidth="1.5" className="animate-ping" opacity="0.6" />
                  <text x="0" y="-26" fill="#ef4444" fontSize="10" fontWeight="bold" textAnchor="middle">
                    ✕ STAIRS BLOCKED
                  </text>
                </g>
              )}

              {/* Touch Helper Tag */}
              <rect x="-24" y="22" width="48" height="14" rx="3" fill="#0f172a" stroke="#334155" strokeWidth="1" />
              <text x="0" y="32" fill="#94a3b8" fontSize="8" textAnchor="middle">
                [Tap to {isB2Blocked ? 'Clear' : 'Block'}]
              </text>
            </g>

            {/* Live Gemini 4 Argon Spatial Bounding Box Overlay in 3D */}
            {activeBoundingBox && (
              <g transform={`translate(${activeBoundingBox.x - 300}, ${activeBoundingBox.y - 180})`}>
                <rect
                  x="0"
                  y="0"
                  width={activeBoundingBox.w}
                  height={activeBoundingBox.h}
                  fill="#ef4444"
                  fillOpacity="0.2"
                  stroke="#f43f5e"
                  strokeWidth="2"
                  strokeDasharray="4 2"
                  filter="url(#hazardGlowRed)"
                  rx="4"
                  className="animate-pulse"
                />
                {/* Target Pin Badge */}
                <rect x="0" y="-18" width={activeBoundingBox.w} height="16" fill="#e11d48" rx="2" />
                <text x={activeBoundingBox.w / 2} y="-6" fill="#ffffff" fontSize="9" fontWeight="bold" textAnchor="middle">
                  {activeBoundingBox.target} (ARGON 98.4%)
                </text>
                {/* Crosshairs */}
                <line x1={activeBoundingBox.w / 2 - 8} y1={activeBoundingBox.h / 2} x2={activeBoundingBox.w / 2 + 8} y2={activeBoundingBox.h / 2} stroke="#ffffff" strokeWidth="1.5" />
                <line x1={activeBoundingBox.w / 2} y1={activeBoundingBox.h / 2 - 8} x2={activeBoundingBox.w / 2} y2={activeBoundingBox.h / 2 + 8} stroke="#ffffff" strokeWidth="1.5" />
              </g>
            )}
          </g>
        </svg>

        {/* Floating Quick Action Presets on 3D Canvas */}
        <div className="absolute bottom-2 left-2 flex items-center space-x-1.5 bg-slate-900/90 p-1 rounded-lg border border-slate-800 text-[11px] backdrop-blur z-20">
          <span className="text-slate-400 font-semibold px-1">Judge Presets:</span>
          <button
            onClick={() => handleEntityTouch('portal', 'P2')}
            className={`px-2 py-0.5 rounded font-medium border transition ${
              isP2Blocked
                ? 'bg-rose-600/30 text-rose-300 border-rose-500'
                : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700'
            }`}
          >
            {isP2Blocked ? '✓ P2 Hazard Active' : 'Trigger P2 Hazard'}
          </button>
          <button
            onClick={() => handleEntityTouch('boundary', 'B2')}
            className={`px-2 py-0.5 rounded font-medium border transition ${
              isB2Blocked
                ? 'bg-amber-600/30 text-amber-300 border-amber-500'
                : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700'
            }`}
          >
            {isB2Blocked ? '✓ B2 Hazard Active' : "Falsify (B2 Block)"}
          </button>
        </div>

        {/* Hover inspection toast */}
        {hoveredEntity && (
          <div className="absolute top-2 left-2 bg-slate-900/90 text-sky-300 px-2.5 py-1 rounded border border-sky-500/40 text-[11px] font-mono backdrop-blur z-20">
            Inspecting: <strong>{hoveredEntity}</strong> • Tap to toggle status
          </div>
        )}
      </div>

      {/* Footer Technical Explanation */}
      <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
        <div className="flex items-center space-x-1.5">
          <Info className="h-3.5 w-3.5 text-sky-400" />
          <span>Finite transfer capacity: B1 = 2 pers/s, B2 = 2 pers/s. P3 connects to existing B2.</span>
        </div>
        <div className="font-mono text-slate-500">
          Actuation Rule: Command ACK ≠ Arrival (Requires D2/D3 switch confirmation)
        </div>
      </div>
    </div>
  );
};