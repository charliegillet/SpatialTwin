import * as THREE from "three";
import type { Material } from "./appearance";
export function createFloorTexture(
  material: Material,
): THREE.CanvasTexture | null {
  if (
    ![
      "wood",
      "terrazzo",
      "tile",
      "stone",
      "marble",
      "carpet",
      "concrete",
    ].includes(material)
  )
    return null;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 512;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  let seed = 9127;
  const random = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  ctx.fillStyle = "#f5f5f1";
  ctx.fillRect(0, 0, 512, 512);
  const noise =
    material === "terrazzo" ? 1500 : material === "carpet" ? 6000 : 2000;
  for (let i = 0; i < noise; i++) {
    const g =
      material === "terrazzo"
        ? 125 + Math.floor(random() * 90)
        : 210 + Math.floor(random() * 35);
    ctx.fillStyle = `rgba(${g},${g},${g},${material === "terrazzo" ? 0.38 : 0.18})`;
    const s = material === "terrazzo" ? 1 + random() * 5 : 1;
    ctx.fillRect(random() * 512, random() * 512, s, s);
  }
  if (material === "wood") {
    for (let y = 0; y < 512; y += 64) {
      ctx.strokeStyle = "#c7c5bc";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(512, y);
      ctx.stroke();
      for (let i = 0; i < 18; i++) {
        ctx.strokeStyle = "rgba(140,135,120,.09)";
        const gy = y + random() * 64;
        ctx.beginPath();
        ctx.moveTo(0, gy);
        ctx.bezierCurveTo(150, gy + 4, 350, gy - 4, 512, gy);
        ctx.stroke();
      }
      ctx.strokeStyle = "#c7c5bc";
      const x = ((y / 64) % 2) * 256;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x, y + 64);
      ctx.stroke();
    }
  } else if (material === "tile" || material === "stone") {
    const size = material === "tile" ? 128 : 256;
    ctx.strokeStyle = "#c5c5bd";
    ctx.lineWidth = 2;
    for (let n = 0; n <= 512; n += size) {
      ctx.beginPath();
      ctx.moveTo(n, 0);
      ctx.lineTo(n, 512);
      ctx.moveTo(0, n);
      ctx.lineTo(512, n);
      ctx.stroke();
    }
  } else if (material === "marble") {
    ctx.strokeStyle = "rgba(130,135,128,.16)";
    ctx.lineWidth = 1;
    for (let n = 0; n < 10; n++) {
      const x = random() * 512;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.bezierCurveTo(x - 90, 160, x + 100, 360, x + 30, 512);
      ctx.stroke();
    }
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  // ShapeGeometry UVs are world X/Z before its floor rotation; 2 estimated scene units per tile.
  texture.repeat.set(0.5, 0.5);
  texture.anisotropy = 2;
  return texture;
}
