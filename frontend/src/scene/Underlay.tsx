// The accepted venue's source photo on the floor, under the model, aligned to venue metres. It never takes a pick:
// hazard drops raycast the y = 0 plane (PickBridge) and the DropPlane, never this mesh.
import { useEffect, useMemo, useState } from 'react';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { featherMask, underlayPlacement, type Underlay as UnderlaySpec } from '../twin/underlay.ts';
import type { Point2 } from '../twin/types.ts';
import { ORDER } from './Building.tsx';

const MASK = 64;
const noPick = () => null;

export default function Underlay({ underlay, extent, opacity, onReady }: {
  underlay: UnderlaySpec; extent: Point2; opacity: number; onReady: (ready: boolean) => void;
}) {
  const { gl, invalidate } = useThree();
  const [texture, setTexture] = useState<THREE.Texture | null>(null);
  const placement = useMemo(() => underlayPlacement(underlay, extent), [underlay, extent]);

  useEffect(() => {
    let alive = true;
    let loaded: THREE.Texture | null = null;
    setTexture(null);
    onReady(false);
    new THREE.TextureLoader().load(underlay.imageUrl, (tex) => {
      if (!alive) { tex.dispose(); return; }
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = Math.min(8, gl.capabilities.getMaxAnisotropy());
      tex.needsUpdate = true;
      loaded = tex;
      setTexture(tex);
      onReady(true);
      invalidate();
    }, undefined, () => { if (alive) onReady(false); });
    return () => {
      alive = false;
      loaded?.dispose();
    };
  }, [underlay.imageUrl, gl, invalidate, onReady]);

  const geometry = useMemo(() => {
    if (!placement) return null;
    const { x0, y0, x1, y1, u0, v0, u1, v1 } = placement;
    const g = new THREE.BufferGeometry();
    // Corners SW, SE, NE, NW in world space (floor (x, y) -> (x, h, -y)), just below the floor plate.
    g.setAttribute('position', new THREE.Float32BufferAttribute([x0, -0.02, -y0, x1, -0.02, -y0, x1, -0.02, -y1, x0, -0.02, -y1], 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute([u0, v0, u1, v0, u1, v1, u0, v1], 2));
    g.setAttribute('uv1', new THREE.Float32BufferAttribute([0, 0, 1, 0, 1, 1, 0, 1], 2));
    g.setIndex([0, 1, 2, 0, 2, 3]);
    return g;
  }, [placement]);
  useEffect(() => () => geometry?.dispose(), [geometry]);

  // Soft edges on the crop (second uv set), so the photo fades into the canvas instead of ending in a hard rectangle.
  const mask = useMemo(() => {
    if (!placement) return null;
    // alphaMap reads the green channel: store the ramp in every channel of an RGBA texture.
    const ramp = featherMask(MASK, placement.featherU, placement.featherV);
    const rgba = new Uint8Array(MASK * MASK * 4);
    ramp.forEach((a, i) => rgba.fill(a, i * 4, i * 4 + 4));
    const tex = new THREE.DataTexture(rgba, MASK, MASK, THREE.RGBAFormat);
    tex.magFilter = THREE.LinearFilter;
    tex.minFilter = THREE.LinearFilter;
    tex.channel = 1;
    tex.needsUpdate = true;
    return tex;
  }, [placement]);
  useEffect(() => () => mask?.dispose(), [mask]);

  if (!texture || !geometry || !mask || opacity <= 0) return null;
  return (
    <mesh geometry={geometry} renderOrder={ORDER.underlay} raycast={noPick}>
      {/* A slight green-grey multiply keeps a white poster from glaring on the dark stage. */}
      <meshBasicMaterial map={texture} alphaMap={mask} color="#b8c1bc" transparent opacity={opacity} depthWrite={false} toneMapped={false} />
    </mesh>
  );
}
