import { useEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { hazardRenders, instanceBudget, type HazardRender } from '../twin/sceneModel.ts';
import type { DoorPlanResponse, HazardType, PlacedHazard } from '../twin/types.ts';
import { toWorld } from './coords.ts';
import { FIRE_HOT, HAZARD_COLOR, PALETTE } from './palette.ts';

interface ParticleStyle {
  spread: number; rise: number; size: number; speed: number; opacity: number;
  from: string; to: string; additive: boolean; base: number;
}

const STYLE: Partial<Record<HazardType, ParticleStyle>> = {
  FIRE: { spread: 0.9, rise: 2.2, size: 0.95, speed: 1.1, opacity: 0.85, from: FIRE_HOT, to: HAZARD_COLOR.FIRE, additive: true, base: 0.1 },
  SMOKE: { spread: 1.5, rise: 2.4, size: 1.7, speed: 0.16, opacity: 0.4, from: HAZARD_COLOR.SMOKE, to: '#5e6663', additive: false, base: 0.4 },
  GAS: { spread: 2.2, rise: 0.9, size: 2.5, speed: 0.1, opacity: 0.26, from: HAZARD_COLOR.GAS, to: '#a9b83a', additive: false, base: 0.3 },
  CHEMICAL: { spread: 1.0, rise: 1.5, size: 0.95, speed: 0.2, opacity: 0.24, from: HAZARD_COLOR.CHEMICAL, to: '#7d3fc4', additive: false, base: 0.2 },
};

const VERT = `
attribute vec4 aSeed;
uniform float uTime, uSpread, uRise, uSize, uSpeed, uBase, uStatic;
varying vec2 vUv;
varying float vLife;
void main() {
  float life = uStatic > 0.5 ? aSeed.z : fract(aSeed.z + uTime * uSpeed * (0.7 + aSeed.w * 0.6));
  vec3 centre = vec3(aSeed.x * uSpread * (0.4 + life * 0.6), uBase + life * uRise, aSeed.y * uSpread * (0.4 + life * 0.6));
  float s = uSize * (0.5 + aSeed.w * 0.7) * (0.35 + sin(life * 3.14159) * 0.9);
  vec4 mv = modelViewMatrix * vec4(centre, 1.0);
  mv.xy += position.xy * s;
  gl_Position = projectionMatrix * mv;
  vUv = uv;
  vLife = life;
}`;
const FRAG = `
uniform vec3 uFrom, uTo;
uniform float uOpacity;
varying vec2 vUv;
varying float vLife;
void main() {
  float d = length(vUv - 0.5) * 2.0;
  float a = smoothstep(1.0, 0.15, d) * smoothstep(0.0, 0.12, vLife) * (1.0 - vLife) * uOpacity;
  if (a < 0.01) discard;
  gl_FragColor = vec4(mix(uFrom, uTo, vLife), a);
}`;

function Particles({ type, count, reducedMotion }: { type: HazardType; count: number; reducedMotion: boolean }) {
  const style = STYLE[type]!;
  const mesh = useRef<THREE.InstancedMesh>(null);
  const material = useMemo(() => new THREE.ShaderMaterial({
    vertexShader: VERT,
    fragmentShader: FRAG,
    transparent: true,
    depthWrite: false,
    blending: style.additive ? THREE.AdditiveBlending : THREE.NormalBlending,
    uniforms: {
      uTime: { value: 0 }, uSpread: { value: style.spread }, uRise: { value: style.rise }, uSize: { value: style.size },
      uSpeed: { value: style.speed }, uBase: { value: style.base }, uStatic: { value: reducedMotion ? 1 : 0 },
      uFrom: { value: new THREE.Color(style.from) }, uTo: { value: new THREE.Color(style.to) }, uOpacity: { value: style.opacity },
    },
  }), [style, reducedMotion]);
  const geometry = useMemo(() => {
    const g = new THREE.InstancedBufferGeometry().copy(new THREE.PlaneGeometry(1, 1) as unknown as THREE.InstancedBufferGeometry);
    const seeds = new Float32Array(count * 4);
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const r = Math.sqrt(Math.random());
      seeds.set([Math.cos(angle) * r, Math.sin(angle) * r, Math.random(), Math.random()], i * 4);
    }
    g.setAttribute('aSeed', new THREE.InstancedBufferAttribute(seeds, 4));
    g.instanceCount = count;
    return g;
  }, [count]);
  useEffect(() => () => { material.dispose(); geometry.dispose(); }, [material, geometry]);
  useFrame(({ clock }) => {
    material.uniforms.uTime.value = clock.elapsedTime;
  });
  return <mesh ref={mesh as never} geometry={geometry} material={material} frustumCulled={false} renderOrder={5} />;
}

function Hazard({ hazard, count, armed, lowGraphics, reducedMotion, onSelect }: {
  hazard: HazardRender; count: number; armed: boolean; lowGraphics: boolean; reducedMotion: boolean; onSelect: (id: string) => void;
}) {
  const [x, y] = hazard.position;
  const light = useRef<THREE.PointLight>(null);
  const ripple = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    if (light.current && !reducedMotion) light.current.intensity = 14 + Math.sin(t * 11 + x) * 3 + Math.sin(t * 23) * 2;
    if (ripple.current && !reducedMotion) {
      const k = (t * 0.5) % 1;
      ripple.current.scale.setScalar(0.5 + k * 1.1);
      (ripple.current.material as THREE.MeshBasicMaterial).opacity = (1 - k) * 0.6;
    }
  });
  const dim = hazard.effective ? 1 : 0.55;
  return (
    <group position={toWorld(x, y, 0)}>
      {hazard.type === 'FIRE' && <pointLight ref={light} color={FIRE_HOT} position={[0, 1.2, 0]} intensity={14} distance={11} decay={2} />}
      {STYLE[hazard.type] && count > 0 && <Particles type={hazard.type} count={count} reducedMotion={reducedMotion} />}
      {hazard.type === 'CHEMICAL' && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
          <circleGeometry args={[1.5, 36]} />
          <meshBasicMaterial color={HAZARD_COLOR.CHEMICAL} transparent opacity={0.5 * dim} depthWrite={false} />
        </mesh>
      )}
      {hazard.type === 'WATER' && (
        <>
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
            <circleGeometry args={[1.8, 40]} />
            <meshStandardMaterial color={HAZARD_COLOR.WATER} transparent opacity={0.55 * dim} roughness={0.08} metalness={0.7} depthWrite={false} />
          </mesh>
          <mesh ref={ripple} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.05, 0]}>
            <ringGeometry args={[0.85, 1, 40]} />
            <meshBasicMaterial color="#bfe4ff" transparent opacity={0.4} depthWrite={false} />
          </mesh>
        </>
      )}
      {hazard.selected && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.07, 0]}>
          <ringGeometry args={[1.95, 2.1, 48]} />
          <meshBasicMaterial color={PALETTE.text} />
        </mesh>
      )}
      <mesh
        position={[0, 0.75, 0]}
        raycast={armed ? () => null : undefined}
        onClick={(event) => { event.stopPropagation(); onSelect(hazard.id); }}
        onPointerOver={() => { if (!armed) document.body.style.cursor = 'pointer'; }}
        onPointerOut={() => { document.body.style.cursor = ''; }}
      >
        <cylinderGeometry args={[1.5, 1.5, 1.5, 12]} />
        <meshBasicMaterial transparent opacity={0} depthWrite={false} />
      </mesh>
    </group>
  );
}

export default function Hazards({ plan, hazards, selectedId, armed, lowGraphics, reducedMotion, onSelect }: {
  plan: DoorPlanResponse | null; hazards: PlacedHazard[]; selectedId: string | null; armed: boolean;
  lowGraphics: boolean; reducedMotion: boolean; onSelect: (id: string) => void;
}) {
  const rendered = hazardRenders(plan, hazards, selectedId);
  const budget = instanceBudget(rendered.map((h) => h.type), lowGraphics);
  return (
    <group>
      {rendered.map((h, i) => (
        <Hazard key={h.id} hazard={h} count={budget[i]} armed={armed} lowGraphics={lowGraphics} reducedMotion={reducedMotion} onSelect={onSelect} />
      ))}
    </group>
  );
}
