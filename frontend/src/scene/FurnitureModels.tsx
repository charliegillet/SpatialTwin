import React, { createContext, useContext, useMemo } from 'react';
import * as THREE from 'three';
import type { FloorMaterial, VenueFurniture, ZoneLook } from '../twin/types.ts';

/*
 * Presentation-only room look, ported from the video-to-room work (charlie-video, RoomModels.tsx): simple
 * recognizable furniture models, colours read from the video by Argon (falling back to guesses from the label), and
 * floor textures. Every model fits the piece's box: local X = width, local Z = depth, y from 0 to height.
 */

export type ObjectKind =
  | 'plant' | 'sofa' | 'chair' | 'stool' | 'table' | 'desk' | 'partition'
  | 'railing' | 'stairs' | 'shelf' | 'bed' | 'bin' | 'generic';

const KIND_RULES: [ObjectKind, RegExp][] = [
  ['partition', /partition|glass wall|storefront|divider|screen wall/],
  ['railing', /railing|balustrade|guardrail|handrail|banister/],
  ['stairs', /stair|steps/],
  ['plant', /plant|fig\b|tree|fern|palm|planter|foliage|flower/],
  ['stool', /stool/],
  ['chair', /chair/],
  ['sofa', /sofa|couch|loveseat|sectional|lounge/],
  ['bed', /\bbed\b/],
  ['desk', /desk|counter|reception|island|kiosk/],
  ['table', /table|bench/],
  ['shelf', /shel(f|ves)|bookcase|cabinet|cupboard|dresser|wardrobe|locker|fridge|refrigerator/],
  ['bin', /\bbin\b|trash|waste|bucket/],
];

export const OBJECT_KINDS: readonly ObjectKind[] = ['sofa', 'chair', 'stool', 'table', 'desk', 'shelf', 'bed', 'plant', 'bin', 'partition', 'railing', 'stairs', 'generic'];

type Piece = Pick<VenueFurniture, 'label' | 'category' | 'color'>;

export function objectKind(obj: Piece): ObjectKind {
  const text = `${obj.category ?? ''} ${obj.label}`.toLowerCase();
  return KIND_RULES.find(([, re]) => re.test(text))?.[0] ?? 'generic';
}

const COLOR_WORDS: [RegExp, string][] = [
  [/marble/, '#ece8e1'],
  [/walnut|dark wood|espresso/, '#5e4029'],
  [/wood|oak|timber|bamboo/, '#a8743f'],
  [/bronze|brass|copper/, '#7b5a32'],
  [/black|charcoal/, '#2e3238'],
  [/white|ivory/, '#efede7'],
  [/grey|gray|concrete|steel|metal|aluminum|chrome/, '#8c939b'],
  [/leather|brown/, '#7a5236'],
  [/beige|cream|tan\b/, '#d9ccb0'],
  [/blue|navy/, '#4a6a9a'],
  [/green/, '#4f8a43'],
  [/red\b/, '#a8423a'],
  [/yellow|mustard/, '#d1a63a'],
  [/terrazzo|stone|granite/, '#cfc8bc'],
];

const KIND_COLOR: Record<ObjectKind, string> = {
  plant: '#4a8a3e', sofa: '#6f7f8e', chair: '#5d6875', stool: '#a8743f', table: '#a8743f',
  desk: '#d9d3c8', partition: '#7b5a32', railing: '#7b5a32', stairs: '#cfc8bc', shelf: '#8a6a4a',
  bed: '#d8d4cc', bin: '#5a5f66', generic: '#9aa3ad',
};

function colorFromWords(text: string): string | undefined {
  const lower = text.toLowerCase();
  return COLOR_WORDS.find(([re]) => re.test(lower))?.[1];
}

/** Provider color first; else a color word in the label, then the note; else a per-kind default. */
export function objectColor(obj: Piece, kind: ObjectKind): string {
  if (obj.color) return obj.color;
  // Plant labels describe pots and surroundings, not foliage.
  if (kind === 'plant') return KIND_COLOR.plant;
  return colorFromWords(obj.label) ?? KIND_COLOR[kind];
}

const FLOOR_COLOR: Record<FloorMaterial, string> = {
  wood: '#a87a4f', tile: '#d6d2ca', stone: '#d8d2c6', terrazzo: '#cbc6bd',
  carpet: '#8a8f96', concrete: '#a3a29d', unknown: '#bdb7ab',
};
const DEFAULT_WALL_COLOR = '#e6e0d3';

export interface ResolvedAppearance {
  wallColor: string;
  floorColor: string;
  floorMaterial: FloorMaterial;
}

/** A room's look with defaults filled in; null when the room has no look at all (the twin keeps its dark floor). */
export function resolveZoneLook(look: ZoneLook | undefined): ResolvedAppearance | null {
  if (!look || (!look.wall_color && !look.floor_color && (look.floor_material ?? 'unknown') === 'unknown')) return null;
  const material: FloorMaterial = look.floor_material ?? 'unknown';
  return {
    wallColor: look.wall_color || DEFAULT_WALL_COLOR,
    floorColor: look.floor_color || FLOOR_COLOR[material],
    floorMaterial: material,
  };
}

export function shade(hex: string, lightness: number): string {
  return `#${new THREE.Color(hex).offsetHSL(0, 0, lightness).getHexString()}`;
}

function seededRandom(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** One texture tile covers 2m x 2m of floor (floor UVs are in metres). */
export const FLOOR_TILE_M = 2;

export function makeFloorTexture(material: FloorMaterial, base: string): THREE.CanvasTexture {
  const size = 512;
  const px = size / FLOOR_TILE_M; // pixels per metre
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const g = canvas.getContext('2d')!;
  const rand = seededRandom(7);
  g.fillStyle = base;
  g.fillRect(0, 0, size, size);

  const speckle = (count: number, colors: string[], minS: number, maxS: number) => {
    for (let i = 0; i < count; i++) {
      g.fillStyle = colors[i % colors.length];
      const s = minS + rand() * (maxS - minS);
      g.fillRect(rand() * size, rand() * size, s, s * (0.6 + rand() * 0.8));
    }
  };
  const grid = (cellM: number, line: string, width: number) => {
    g.strokeStyle = line;
    g.lineWidth = width;
    for (let p = 0; p <= size; p += cellM * px) {
      g.beginPath(); g.moveTo(p, 0); g.lineTo(p, size); g.stroke();
      g.beginPath(); g.moveTo(0, p); g.lineTo(size, p); g.stroke();
    }
  };

  switch (material) {
    case 'terrazzo':
      speckle(2600, [shade(base, -0.25), shade(base, 0.12), shade(base, -0.4), '#b7aa95', shade(base, 0.18)], 1, 4.5);
      break;
    case 'wood': {
      const plankH = 0.2 * px;
      for (let row = 0; row * plankH < size; row++) {
        let x = -rand() * 1.2 * px;
        while (x < size) {
          const len = (0.9 + rand() * 0.9) * px;
          g.fillStyle = shade(base, (rand() - 0.5) * 0.1);
          g.fillRect(x, row * plankH, len, plankH);
          g.fillStyle = shade(base, -0.18);
          g.fillRect(x, row * plankH, 2, plankH);
          x += len;
        }
        g.fillStyle = shade(base, -0.2);
        g.fillRect(0, row * plankH, size, 1.5);
      }
      speckle(900, [shade(base, -0.08), shade(base, 0.06)], 1, 3);
      break;
    }
    case 'tile':
      speckle(500, [shade(base, -0.04), shade(base, 0.04)], 2, 6);
      grid(0.5, shade(base, -0.18), 2);
      break;
    case 'stone':
      speckle(800, [shade(base, -0.06), shade(base, 0.05)], 2, 9);
      grid(1, shade(base, -0.12), 2);
      break;
    case 'carpet':
      speckle(9000, [shade(base, -0.07), shade(base, 0.06)], 1, 2);
      break;
    case 'concrete':
      speckle(1600, [shade(base, -0.06), shade(base, 0.05)], 2, 10);
      break;
    default:
      speckle(1200, [shade(base, -0.04), shade(base, 0.04)], 1, 4);
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(1 / FLOOR_TILE_M, 1 / FLOOR_TILE_M);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}

/* ------------------------------------------------------------------ */
/* Model parts                                                         */
/* ------------------------------------------------------------------ */

/** Emissive tint applied to every part of a highlighted (selected / anchor) model. */
export const GlowContext = createContext<{ color: string; intensity: number }>({ color: '#000000', intensity: 0 });

type Vec3 = [number, number, number];

function Mat({ color, glass, roughness = 0.75, metalness = 0.05, flat }: {
  color: string; glass?: boolean; roughness?: number; metalness?: number; flat?: boolean;
}) {
  const glow = useContext(GlowContext);
  if (glass) {
    return <meshStandardMaterial color={color} transparent opacity={0.3} roughness={0.05} metalness={0.1} depthWrite={false} />;
  }
  return (
    <meshStandardMaterial
      color={color}
      roughness={roughness}
      metalness={metalness}
      flatShading={flat}
      emissive={glow.color}
      emissiveIntensity={glow.intensity}
    />
  );
}

function Box({ size, pos, color, glass, roughness, metalness }: {
  size: Vec3; pos: Vec3; color: string; glass?: boolean; roughness?: number; metalness?: number;
}) {
  return (
    <mesh position={pos} castShadow={!glass} receiveShadow>
      <boxGeometry args={size} />
      <Mat color={color} glass={glass} roughness={roughness} metalness={metalness} />
    </mesh>
  );
}

function Cyl({ radiusTop, radiusBottom = radiusTop, height, pos, color, segments = 18, metalness }: {
  radiusTop: number; radiusBottom?: number; height: number; pos: Vec3; color: string; segments?: number; metalness?: number;
}) {
  return (
    <mesh position={pos} castShadow receiveShadow>
      <cylinderGeometry args={[radiusTop, radiusBottom, height, segments]} />
      <Mat color={color} metalness={metalness} />
    </mesh>
  );
}

const GLASS = '#bfe3ee';
const METAL = '#2b2f36';

export interface ModelProps { w: number; d: number; h: number; color: string }

/** Lay a linear model (len along X, thick along Z) along whichever footprint axis is longer. */
function AlongLongAxis({ w, d, render }: { w: number; d: number; render: (len: number, thick: number) => React.ReactNode }) {
  if (w >= d) return <>{render(w, d)}</>;
  return <group rotation={[0, Math.PI / 2, 0]}>{render(d, w)}</group>;
}

function Plant({ w, d, h, color }: ModelProps) {
  const r = Math.min(w, d) / 2;
  const potH = Math.min(0.45, h * 0.25);
  const blobs = useMemo(() => {
    const crown = h - potH;
    const rand = seededRandom(Math.round((w + d + h) * 1000));
    return Array.from({ length: 6 }, (_, i) => {
      const br = r * (0.45 + rand() * 0.25);
      const y = potH + crown * (0.35 + 0.6 * (i / 5)) - br * 0.3;
      const a = rand() * Math.PI * 2;
      const off = r * 0.35 * rand();
      return { pos: [Math.cos(a) * off, Math.min(y, h - br * 0.8), Math.sin(a) * off] as Vec3, r: br, tone: (i % 3) - 1 };
    });
  }, [w, d, h, r, potH]);
  return (
    <>
      <Cyl radiusTop={r * 0.7} radiusBottom={r * 0.55} height={potH} pos={[0, potH / 2, 0]} color="#d9d3c7" />
      <Cyl radiusTop={0.025} height={(h - potH) * 0.7} pos={[0, potH + (h - potH) * 0.35, 0]} color="#6b4a2b" segments={8} />
      {blobs.map((b, i) => (
        <mesh key={i} position={b.pos} rotation={[i, i * 2, 0]} castShadow>
          <icosahedronGeometry args={[b.r, 0]} />
          <Mat color={shade(color, b.tone * 0.07)} flat />
        </mesh>
      ))}
    </>
  );
}

function Sofa({ w, d, h, color }: ModelProps) {
  return (
    <AlongLongAxis w={w} d={d} render={(len, depth) => {
      const seatH = h * 0.5, backT = Math.min(0.25, depth * 0.25), armW = Math.min(0.22, len * 0.1);
      const cushion = shade(color, 0.06);
      const inner = len - armW * 2;
      return (
        <>
          <Box size={[len, seatH * 0.8, depth]} pos={[0, seatH * 0.4, 0]} color={color} />
          <Box size={[len, h, backT]} pos={[0, h / 2, -depth / 2 + backT / 2]} color={color} />
          <Box size={[armW, h * 0.72, depth]} pos={[-len / 2 + armW / 2, h * 0.36, 0]} color={color} />
          <Box size={[armW, h * 0.72, depth]} pos={[len / 2 - armW / 2, h * 0.36, 0]} color={color} />
          {[-1, 1].map((s) => (
            <Box key={s} size={[inner / 2 - 0.02, seatH * 0.22, depth - backT - 0.04]}
              pos={[(s * inner) / 4, seatH * 0.9, backT / 2]} color={cushion} />
          ))}
        </>
      );
    }} />
  );
}

function Chair({ w, d, h, color }: ModelProps) {
  const seatY = Math.min(0.48, h * 0.5), legT = 0.04;
  const legs: Vec3[] = [[-1, 0, -1], [1, 0, -1], [-1, 0, 1], [1, 0, 1]];
  return (
    <>
      <Box size={[w, 0.07, d]} pos={[0, seatY, 0]} color={color} />
      <Box size={[w, h - seatY, 0.06]} pos={[0, seatY + (h - seatY) / 2, -d / 2 + 0.03]} color={color} />
      {legs.map(([sx, , sz], i) => (
        <Box key={i} size={[legT, seatY, legT]} pos={[sx * (w / 2 - legT), seatY / 2, sz * (d / 2 - legT)]} color={METAL} />
      ))}
    </>
  );
}

function Stools({ w, d, h, color }: ModelProps) {
  return (
    <AlongLongAxis w={w} d={d} render={(len, thick) => {
      const n = Math.max(1, Math.round(len / 0.6));
      const spacing = len / n;
      const r = Math.min(0.2, spacing * 0.38, thick * 0.5);
      return (
        <>
          {Array.from({ length: n }, (_, i) => {
            const x = -len / 2 + spacing * (i + 0.5);
            return (
              <group key={i} position={[x, 0, 0]}>
                <Cyl radiusTop={r} height={0.06} pos={[0, h - 0.03, 0]} color={color} />
                <Cyl radiusTop={0.025} height={h - 0.06} pos={[0, (h - 0.06) / 2, 0]} color={METAL} segments={8} metalness={0.6} />
                <Cyl radiusTop={r * 0.85} height={0.02} pos={[0, 0.01, 0]} color={METAL} metalness={0.6} />
              </group>
            );
          })}
        </>
      );
    }} />
  );
}

function Table({ w, d, h, color }: ModelProps) {
  const topT = Math.min(0.05, h * 0.1), legT = Math.min(0.06, Math.min(w, d) * 0.1);
  const legColor = shade(color, -0.22);
  return (
    <>
      <Box size={[w, topT, d]} pos={[0, h - topT / 2, 0]} color={color} />
      {[[-1, -1], [1, -1], [-1, 1], [1, 1]].map(([sx, sz], i) => (
        <Box key={i} size={[legT, h - topT, legT]} pos={[sx * (w / 2 - legT), (h - topT) / 2, sz * (d / 2 - legT)]} color={legColor} />
      ))}
    </>
  );
}

function Desk({ w, d, h, color }: ModelProps) {
  return (
    <>
      <Box size={[w, h * 0.95, d]} pos={[0, h * 0.475, 0]} color={color} roughness={0.35} />
      <Box size={[w + 0.06, h * 0.05, d + 0.06]} pos={[0, h * 0.975, 0]} color={shade(color, 0.05)} roughness={0.3} />
      <Box size={[w, h * 0.1, 0.02]} pos={[0, h * 0.78, d / 2 + 0.01]} color={shade(color, -0.25)} />
    </>
  );
}

function Partition({ w, d, h, color }: ModelProps) {
  return (
    <AlongLongAxis w={w} d={d} render={(len, thick) => {
      const n = Math.max(1, Math.round(len / 1.2));
      const t = Math.min(thick, 0.1);
      return (
        <>
          <Box size={[len, h, 0.03]} pos={[0, h / 2, 0]} color={GLASS} glass />
          <Box size={[len, 0.08, t]} pos={[0, h - 0.04, 0]} color={color} metalness={0.5} roughness={0.4} />
          <Box size={[len, 0.12, t]} pos={[0, 0.06, 0]} color={color} metalness={0.5} roughness={0.4} />
          {Array.from({ length: n + 1 }, (_, i) => (
            <Box key={i} size={[0.06, h, t]} pos={[-len / 2 + (i * len) / n, h / 2, 0]} color={color} metalness={0.5} roughness={0.4} />
          ))}
        </>
      );
    }} />
  );
}

function Railing({ w, d, h, color }: ModelProps) {
  return (
    <AlongLongAxis w={w} d={d} render={(len, thick) => (
      <>
        <Box size={[len, Math.max(0.1, h - 0.1), 0.03]} pos={[0, h / 2, 0]} color={GLASS} glass />
        <Box size={[len, 0.06, Math.min(thick, 0.12)]} pos={[0, h - 0.03, 0]} color={color} metalness={0.5} roughness={0.4} />
        <Box size={[len, 0.06, thick]} pos={[0, 0.03, 0]} color={shade(color, 0.35)} />
      </>
    )} />
  );
}

function Stairs({ w, d, h, color }: ModelProps) {
  const n = Math.min(20, Math.max(3, Math.round(h / 0.18)));
  const run = d / n;
  return (
    <>
      {Array.from({ length: n }, (_, i) => {
        const stepH = (h * (i + 1)) / n;
        return <Box key={i} size={[w, stepH, run]} pos={[0, stepH / 2, d / 2 - run * (i + 0.5)]} color={shade(color, (i % 2) * 0.02)} />;
      })}
      <Box size={[0.05, 0.05, Math.hypot(d, h)]} pos={[w / 2 - 0.03, h / 2 + 0.9, 0]} color={shade(color, -0.35)} />
    </>
  );
}

function Shelf({ w, d, h, color }: ModelProps) {
  const groove = shade(color, -0.2);
  const rows = Math.max(2, Math.round(h / 0.45));
  return (
    <>
      <Box size={[w, h, d]} pos={[0, h / 2, 0]} color={color} />
      {Array.from({ length: rows - 1 }, (_, i) => (
        <Box key={i} size={[w * 0.96, 0.025, 0.01]} pos={[0, (h * (i + 1)) / rows, d / 2 + 0.005]} color={groove} />
      ))}
    </>
  );
}

function Bed({ w, d, h, color }: ModelProps) {
  const frameH = h * 0.45;
  return (
    <>
      <Box size={[w, frameH, d]} pos={[0, frameH / 2, 0]} color={shade(color, -0.25)} />
      <Box size={[w * 0.96, h * 0.3, d * 0.95]} pos={[0, frameH + h * 0.15, 0.02]} color={color} />
      <Box size={[w * 0.8, h * 0.12, d * 0.15]} pos={[0, frameH + h * 0.36, -d / 2 + d * 0.12]} color={shade(color, 0.08)} />
      <Box size={[w, h * 1.6, 0.06]} pos={[0, h * 0.8, -d / 2 + 0.03]} color={shade(color, -0.3)} />
    </>
  );
}

function Bin({ w, d, h, color }: ModelProps) {
  const r = (Math.min(w, d) / 2) * 0.9;
  return <Cyl radiusTop={r} radiusBottom={r * 0.88} height={h} pos={[0, h / 2, 0]} color={color} />;
}

function Generic({ w, d, h, color }: ModelProps) {
  return (
    <>
      <Box size={[w, h - 0.04, d]} pos={[0, 0.04 + (h - 0.04) / 2, 0]} color={color} />
      <Box size={[w * 0.94, 0.04, d * 0.94]} pos={[0, 0.02, 0]} color={shade(color, -0.25)} />
    </>
  );
}

const MODELS: Record<ObjectKind, React.FC<ModelProps>> = {
  plant: Plant, sofa: Sofa, chair: Chair, stool: Stools, table: Table, desk: Desk, partition: Partition,
  railing: Railing, stairs: Stairs, shelf: Shelf, bed: Bed, bin: Bin, generic: Generic,
};

export function ObjectModel({ kind, ...props }: ModelProps & { kind: ObjectKind }) {
  const Model = MODELS[kind];
  return <Model {...props} />;
}
