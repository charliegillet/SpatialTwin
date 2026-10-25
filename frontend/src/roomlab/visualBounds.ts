/**
 * Pure local-space visual primitive specification and strict OBB bounding assertions.
 *
 * Every visual proxy rendered for a `RoomObject` is defined in object-local coordinates
 * where the floor is at `y = 0`, the footprint is centered at `(x = 0, z = 0)`, and all
 * child primitives MUST fit strictly within:
 *   x in [-width_m / 2, +width_m / 2]
 *   y in [0, height_m]
 *   z in [-depth_m / 2, +depth_m / 2]
 *
 * The parent (`RoomCanvas3D`) applies the world `center: [x, z]`, `yaw_deg` rotation,
 * hit-testing, and uncertainty/clearance overlays so the canonical solver footprint
 * and `geometry_hash` never change when switching between `'proxy'` and `'bounds'` modes.
 */

export type VisualDisplayMode = "proxy" | "bounds";

export type CanonicalVisualCategory =
  | "table"
  | "counter"
  | "chair"
  | "stool"
  | "sofa"
  | "plant"
  | "bicycle"
  | "stairs"
  | "bin"
  | "pillar"
  | "box"
  | "door_leaf"
  | "stand";

export interface LocalVisualPart {
  id: string;
  shape: "box" | "cylinder" | "wheel";
  /** Optional local XYZ Euler rotation; sizes are pre-rotation geometry extents. */
  rotation?: [number, number, number];
  /** Local center [x, y, z] in meters relative to object floor-origin (0, 0, 0). */
  position: [number, number, number];
  /** Full extents [sizeX, sizeY, sizeZ] in meters. For cylinders, sizeX and sizeZ are diameter. */
  size: [number, number, number];
  role: "primary" | "secondary" | "frame" | "foliage" | "glass";
}

export interface LocalBoxBounds {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
  minZ: number;
  maxZ: number;
}

export function classifyVisualCategory(
  category?: string | null,
  label?: string | null,
): CanonicalVisualCategory {
  const cat = (category || "").trim().toLowerCase();
  const lbl = (label || "").trim().toLowerCase();

  if (cat === "door_leaf") return "door_leaf";
  if (cat === "stand" || cat === "sanitizer_stand") return "stand";
  if (
    cat === "stairs" ||
    cat === "staircase" ||
    cat === "stair" ||
    lbl.startsWith("stair") ||
    lbl.startsWith("interior stair")
  ) {
    return "stairs";
  }
  if (cat.includes("stool") || lbl.includes("stool")) return "stool";
  if (
    cat.includes("counter") ||
    cat.includes("reception") ||
    cat.includes("island") ||
    lbl.includes("reception") ||
    lbl.includes("counter")
  ) {
    return "counter";
  }
  if (
    cat.includes("sofa") ||
    cat.includes("couch") ||
    cat.includes("bench") ||
    lbl.includes("sofa") ||
    lbl.includes("couch")
  ) {
    return "sofa";
  }
  if (cat.includes("chair") || cat.includes("seat")) return "chair";
  if (cat.includes("table") || cat.includes("desk")) return "table";
  if (cat.includes("plant") || cat.includes("tree") || cat.includes("planter"))
    return "plant";
  if (
    cat.includes("bicycle") ||
    cat.includes("bike") ||
    cat.includes("scooter") ||
    lbl.includes("bicycle") ||
    lbl.includes("scooter")
  ) {
    return "bicycle";
  }
  if (
    cat.includes("bin") ||
    cat.includes("trash") ||
    lbl.includes("bin") ||
    lbl.includes("trash")
  ) {
    return "bin";
  }
  if (cat.includes("pillar") || cat.includes("column")) return "pillar";
  return "box";
}

function clampPartToBounds(
  part: LocalVisualPart,
  widthM: number,
  heightM: number,
  depthM: number,
): LocalVisualPart {
  const halfW = widthM * 0.5;
  const halfD = depthM * 0.5;
  const maxH = heightM;

  const sx = Math.min(Math.max(0.01, part.size[0]), widthM);
  const sy = Math.min(Math.max(0.01, part.size[1]), maxH);
  const sz = Math.min(Math.max(0.01, part.size[2]), depthM);

  const maxPosX = Math.max(0, halfW - sx * 0.5);
  const maxPosZ = Math.max(0, halfD - sz * 0.5);

  const px = Math.min(Math.max(part.position[0], -maxPosX), maxPosX);
  const py = Math.min(Math.max(part.position[1], sy * 0.5), maxH - sy * 0.5);
  const pz = Math.min(Math.max(part.position[2], -maxPosZ), maxPosZ);

  return {
    ...part,
    position: [px, py, pz],
    size: [sx, sy, sz],
  };
}

/**
 * Build deterministic local-space visual parts guaranteed to fit within
 * [-width_m/2, +width_m/2] x [0, height_m] x [-depth_m/2, +depth_m/2].
 */
function buildRawObjectVisualParts(
  widthM: number,
  heightM: number,
  depthM: number,
  category?: string | null,
  label?: string | null,
  mode: VisualDisplayMode = "proxy",
): LocalVisualPart[] {
  const w = Number.isFinite(widthM) && widthM > 0 ? widthM : 0.8;
  const h = Number.isFinite(heightM) && heightM > 0 ? heightM : 0.75;
  const d = Number.isFinite(depthM) && depthM > 0 ? depthM : 0.8;

  if (mode === "bounds") {
    return [
      {
        id: "bounds-box",
        shape: "box",
        position: [0, h * 0.5, 0],
        size: [w, h, d],
        role: "primary",
      },
    ];
  }

  const kind = classifyVisualCategory(category, label);
  const rawParts: LocalVisualPart[] = [];

  if (kind === "table") {
    const topThick = Math.min(0.06, h * 0.12);
    const legH = Math.max(0.02, h - topThick);
    const legThick = Math.min(0.07, w * 0.12, d * 0.12);
    const ox = Math.max(0, w * 0.5 - legThick * 0.75);
    const oz = Math.max(0, d * 0.5 - legThick * 0.75);
    rawParts.push({
      id: "table-top",
      shape: "box",
      position: [0, h - topThick * 0.5, 0],
      size: [w, topThick, d],
      role: "primary",
    });
    const corners: Array<[string, number, number]> = [
      ["leg-nw", -ox, -oz],
      ["leg-ne", ox, -oz],
      ["leg-se", ox, oz],
      ["leg-sw", -ox, oz],
    ];
    for (const [id, lx, lz] of corners) {
      rawParts.push({
        id,
        shape: "box",
        position: [lx, legH * 0.5, lz],
        size: [legThick, legH, legThick],
        role: "frame",
      });
    }
  } else if (kind === "counter") {
    const topH = Math.min(0.08, h * 0.1);
    const kickH = Math.min(0.1, h * 0.12);
    const bodyH = Math.max(0.04, h - topH - kickH);
    rawParts.push(
      {
        id: "counter-plinth",
        shape: "box",
        position: [0, kickH * 0.5, 0],
        size: [w * 0.9, kickH, d * 0.9],
        role: "frame",
      },
      {
        id: "counter-body",
        shape: "box",
        position: [0, kickH + bodyH * 0.5, 0],
        size: [w * 0.96, bodyH, d * 0.96],
        role: "secondary",
      },
      {
        id: "counter-top",
        shape: "box",
        position: [0, h - topH * 0.5, 0],
        size: [w, topH, d],
        role: "primary",
      },
    );
  } else if (kind === "stool") {
    const diam = Math.min(w, d);
    const seatH = Math.min(0.06, h * 0.14);
    const legH = Math.max(0.02, h - seatH);
    const legT = Math.min(0.045, diam * 0.14);
    const off = Math.max(0, diam * 0.32 - legT * 0.5);
    rawParts.push(
      {
        id: "stool-seat",
        shape: "cylinder",
        position: [0, h - seatH * 0.5, 0],
        size: [diam, seatH, diam],
        role: "primary",
      },
      {
        id: "stool-ring",
        shape: "cylinder",
        position: [0, h * 0.35, 0],
        size: [diam * 0.72, Math.min(0.03, h * 0.07), diam * 0.72],
        role: "frame",
      },
    );
    for (const [id, lx, lz] of [
      ["sleg-1", -off, -off],
      ["sleg-2", off, -off],
      ["sleg-3", off, off],
      ["sleg-4", -off, off],
    ] as const) {
      rawParts.push({
        id,
        shape: "box",
        position: [lx, legH * 0.5, lz],
        size: [legT, legH, legT],
        role: "frame",
      });
    }
  } else if (kind === "chair") {
    const seatY = h * 0.48;
    const seatThick = Math.min(0.06, h * 0.08);
    const legH = Math.max(0.02, seatY - seatThick * 0.5);
    const legT = Math.min(0.05, w * 0.12, d * 0.12);
    const backThick = Math.min(0.06, d * 0.15);
    const backH = Math.max(0.04, h - seatY - seatThick * 0.5);
    const ox = Math.max(0, w * 0.5 - legT * 0.7);
    const oz = Math.max(0, d * 0.5 - legT * 0.7);
    rawParts.push(
      {
        id: "chair-seat",
        shape: "box",
        position: [0, seatY, 0],
        size: [w * 0.94, seatThick, d * 0.92],
        role: "primary",
      },
      {
        id: "chair-back",
        shape: "box",
        position: [
          0,
          seatY + seatThick * 0.5 + backH * 0.5,
          -d * 0.5 + backThick * 0.5,
        ],
        size: [w * 0.92, backH, backThick],
        role: "secondary",
      },
    );
    for (const [id, lx, lz] of [
      ["cleg-1", -ox, -oz],
      ["cleg-2", ox, -oz],
      ["cleg-3", ox, oz],
      ["cleg-4", -ox, oz],
    ] as const) {
      rawParts.push({
        id,
        shape: "box",
        position: [lx, legH * 0.5, lz],
        size: [legT, legH, legT],
        role: "frame",
      });
    }
  } else if (kind === "sofa") {
    const baseH = h * 0.45;
    const backThick = Math.min(0.22, d * 0.26);
    const armW = Math.min(0.18, w * 0.14);
    const armH = h * 0.68;
    rawParts.push(
      {
        id: "sofa-seat",
        shape: "box",
        position: [0, baseH * 0.5, backThick * 0.2],
        size: [
          Math.max(0.05, w - armW * 2),
          baseH,
          Math.max(0.05, d - backThick * 0.4),
        ],
        role: "primary",
      },
      {
        id: "sofa-back",
        shape: "box",
        position: [0, h * 0.5, -d * 0.5 + backThick * 0.5],
        size: [w, h, backThick],
        role: "secondary",
      },
      {
        id: "sofa-arm-l",
        shape: "box",
        position: [-w * 0.5 + armW * 0.5, armH * 0.5, 0],
        size: [armW, armH, d],
        role: "secondary",
      },
      {
        id: "sofa-arm-r",
        shape: "box",
        position: [w * 0.5 - armW * 0.5, armH * 0.5, 0],
        size: [armW, armH, d],
        role: "secondary",
      },
    );
  } else if (kind === "plant") {
    const diam = Math.min(w, d);
    const potH = Math.min(0.55, h * 0.34);
    const stemH = Math.max(0.05, h * 0.42);
    const crownH = Math.max(0.08, h - potH);
    rawParts.push(
      {
        id: "plant-pot",
        shape: "cylinder",
        position: [0, potH * 0.5, 0],
        size: [diam * 0.56, potH, diam * 0.56],
        role: "secondary",
      },
      {
        id: "plant-stem",
        shape: "cylinder",
        position: [0, potH + stemH * 0.5, 0],
        size: [Math.max(0.03, diam * 0.1), stemH, Math.max(0.03, diam * 0.1)],
        role: "frame",
      },
      {
        id: "plant-crown-lower",
        shape: "cylinder",
        position: [0, potH + crownH * 0.45, 0],
        size: [diam * 0.96, crownH * 0.55, diam * 0.96],
        role: "foliage",
      },
      {
        id: "plant-crown-upper",
        shape: "cylinder",
        position: [0, h - crownH * 0.22, 0],
        size: [diam * 0.72, crownH * 0.44, diam * 0.72],
        role: "foliage",
      },
    );
  } else if (kind === "bicycle") {
    const longX = w >= d;
    const span = longX ? w : d;
    const thick = Math.min(0.18, (longX ? d : w) * 0.38);
    const wheelR = Math.min(h * 0.44, span * 0.32);
    const wheelD = wheelR * 2;
    const offset = Math.max(0, span * 0.5 - wheelR - 0.02);
    rawParts.push(
      {
        id: "bike-wheel-1",
        shape: "wheel",
        position: longX ? [-offset, wheelR, 0] : [0, wheelR, -offset],
        size: longX ? [wheelD, wheelD, thick] : [thick, wheelD, wheelD],
        role: "frame",
      },
      {
        id: "bike-wheel-2",
        shape: "wheel",
        position: longX ? [offset, wheelR, 0] : [0, wheelR, offset],
        size: longX ? [wheelD, wheelD, thick] : [thick, wheelD, wheelD],
        role: "frame",
      },
      {
        id: "bike-frame",
        shape: "box",
        position: [0, h * 0.58, 0],
        size: longX
          ? [span * 0.65, h * 0.07, thick * 0.65]
          : [thick * 0.65, h * 0.07, span * 0.65],
        role: "primary",
      },
      {
        id: "bike-handlebar",
        shape: "box",
        position: longX
          ? [offset * 0.7, h * 0.88, 0]
          : [0, h * 0.88, offset * 0.7],
        size: longX
          ? [Math.min(0.12, span * 0.12), h * 0.18, d * 0.85]
          : [w * 0.85, h * 0.18, Math.min(0.12, span * 0.12)],
        role: "secondary",
      },
    );
    for (const sign of [-1, 1])
      rawParts.push({
        id: "bike-fork-" + sign,
        shape: "box",
        position: longX
          ? [sign * offset * 0.8, h * 0.52, 0]
          : [0, h * 0.52, sign * offset * 0.8],
        size: longX
          ? [Math.min(0.05, w * 0.08), h * 0.4, thick * 0.65]
          : [thick * 0.65, h * 0.4, Math.min(0.05, d * 0.08)],
        role: "frame",
      });
  } else if (kind === "stairs") {
    // Illustrative stepped treads inside the fixed single-level bounding box
    // Illustrative treads, not a recovered step count. Uphill follows the positive long axis.
    const numSteps = 14;
    const alongX = w >= d;
    const runSpan = alongX ? w : d;
    const stepRun = runSpan / numSteps;
    for (let i = 0; i < numSteps; i++) {
      const stepH = ((i + 1) / numSteps) * (h * 0.8);
      const coord = -runSpan * 0.5 + stepRun * (i + 0.5);
      rawParts.push({
        id: `stair-step-${i + 1}`,
        shape: "box",
        position: alongX ? [coord, stepH * 0.5, 0] : [0, stepH * 0.5, coord],
        size: alongX ? [stepRun, stepH, d * 0.94] : [w * 0.94, stepH, stepRun],
        role: i % 2 === 0 ? "primary" : "secondary",
      });
    }
    const railThick = Math.min(
      0.035,
      h * 0.025,
      runSpan * 0.025,
      (alongX ? d : w) * 0.08,
    );
    const rise = h * 0.74,
      run = runSpan * 0.88;
    const railLength = Math.hypot(run, rise),
      angle = Math.atan2(rise, run);
    rawParts.push({
      id: "stair-sloped-rail",
      shape: "box",
      position: alongX ? [0, h * 0.59, -d * 0.45] : [-w * 0.45, h * 0.59, 0],
      size: alongX
        ? [railLength, railThick, railThick]
        : [railThick, railThick, railLength],
      rotation: alongX ? [0, 0, angle] : [-angle, 0, 0],
      role: "frame",
    });
  } else if (kind === "stand") {
    rawParts.push(
      {
        id: "stand-base",
        shape: "box",
        position: [0, h * 0.025, 0],
        size: [w, h * 0.05, d],
        role: "frame",
      },
      {
        id: "stand-stem",
        shape: "box",
        position: [0, h * 0.47, 0],
        size: [w * 0.14, h * 0.88, d * 0.14],
        role: "frame",
      },
      {
        id: "stand-dispenser",
        shape: "box",
        position: [0, h * 0.92, 0],
        size: [w * 0.7, h * 0.16, d * 0.6],
        role: "secondary",
      },
    );
  } else if (kind === "door_leaf") {
    // Explicit, source-supported static snapshot only. Not a generic inferred door state.
    const jamb = Math.min(0.045, w * 0.08),
      head = Math.min(0.055, h * 0.06),
      kick = Math.min(0.2, h * 0.1);
    rawParts.push(
      {
        id: "leaf-glass",
        shape: "box",
        position: [0, kick + (h - head - kick) / 2, 0],
        size: [w - jamb * 2, h - head - kick, d * 0.25],
        role: "glass",
      },
      {
        id: "leaf-left",
        shape: "box",
        position: [-w / 2 + jamb / 2, h / 2, 0],
        size: [jamb, h, d * 0.95],
        role: "frame",
      },
      {
        id: "leaf-right",
        shape: "box",
        position: [w / 2 - jamb / 2, h / 2, 0],
        size: [jamb, h, d * 0.95],
        role: "frame",
      },
      {
        id: "leaf-head",
        shape: "box",
        position: [0, h - head / 2, 0],
        size: [w, head, d * 0.95],
        role: "frame",
      },
      {
        id: "leaf-kick",
        shape: "box",
        position: [0, kick / 2, 0],
        size: [w, kick, d * 0.95],
        role: "frame",
      },
    );
  } else if (kind === "bin") {
    rawParts.push(
      {
        id: "bin-body",
        shape: "box",
        position: [0, h * 0.46, 0],
        size: [w * 0.92, h * 0.92, d * 0.92],
        role: "primary",
      },
      {
        id: "bin-rim",
        shape: "box",
        position: [0, h - h * 0.05, 0],
        size: [w, h * 0.1, d],
        role: "secondary",
      },
    );
  } else if (kind === "pillar") {
    rawParts.push({
      id: "pillar-column",
      shape: "box",
      position: [0, h * 0.5, 0],
      size: [w, h, d],
      role: "frame",
    });
  } else {
    rawParts.push({
      id: "generic-box",
      shape: "box",
      position: [0, h * 0.5, 0],
      size: [w, h, d],
      role: "primary",
    });
  }

  return rawParts.map((part) =>
    part.rotation ? part : clampPartToBounds(part, w, h, d),
  );
}

/** Long-axis proxy layout only; canonical pose/dimensions remain unchanged. */
export function buildObjectVisualParts(
  w: number,
  h: number,
  d: number,
  category?: string | null,
  label?: string | null,
  mode: VisualDisplayMode = "proxy",
): LocalVisualPart[] {
  const kind = classifyVisualCategory(category, label);
  if (mode === "proxy" && d > w && (kind === "sofa" || kind === "counter")) {
    return buildRawObjectVisualParts(d, h, w, category, label, mode).map(
      (p) => ({
        ...p,
        position: [p.position[2], p.position[1], -p.position[0]],
        size: [p.size[2], p.size[1], p.size[0]],
      }),
    );
  }
  return buildRawObjectVisualParts(w, h, d, category, label, mode);
}

/**
 * Compute the exact union axis-aligned bounding box of a set of local visual parts.
 */
export function computeLocalVisualBounds(
  parts: LocalVisualPart[],
): LocalBoxBounds {
  if (parts.length === 0) {
    return { minX: 0, maxX: 0, minY: 0, maxY: 0, minZ: 0, maxZ: 0 };
  }
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;

  for (const p of parts) {
    const [px, py, pz] = p.position;
    const [sx, sy, sz] = p.size;
    for (const x of [-sx / 2, sx / 2])
      for (const y of [-sy / 2, sy / 2])
        for (const z of [-sz / 2, sz / 2]) {
          const [rx, ry, rz] = p.rotation ?? [0, 0, 0];
          // Three.js Euler XYZ: apply Z, then Y, then X to local vertices.
          const xz = x * Math.cos(rz) - y * Math.sin(rz),
            yz = x * Math.sin(rz) + y * Math.cos(rz);
          const xy = xz * Math.cos(ry) + z * Math.sin(ry),
            zy = -xz * Math.sin(ry) + z * Math.cos(ry);
          const yy = yz * Math.cos(rx) - zy * Math.sin(rx),
            zz = yz * Math.sin(rx) + zy * Math.cos(rx);
          minX = Math.min(minX, px + xy);
          maxX = Math.max(maxX, px + xy);
          minY = Math.min(minY, py + yy);
          maxY = Math.max(maxY, py + yy);
          minZ = Math.min(minZ, pz + zz);
          maxZ = Math.max(maxZ, pz + zz);
        }
  }

  return { minX, maxX, minY, maxY, minZ, maxZ };
}

/**
 * Verify that every local visual part fits strictly inside the declared OBB
 * [-width_m/2, +width_m/2] x [0, height_m] x [-depth_m/2, +depth_m/2].
 */
export function verifyPartsWithinOBB(
  parts: LocalVisualPart[],
  widthM: number,
  heightM: number,
  depthM: number,
  eps = 1e-6,
): boolean {
  const b = computeLocalVisualBounds(parts);
  return (
    b.minX >= -widthM * 0.5 - eps &&
    b.maxX <= widthM * 0.5 + eps &&
    b.minY >= -eps &&
    b.maxY <= heightM + eps &&
    b.minZ >= -depthM * 0.5 - eps &&
    b.maxZ <= depthM * 0.5 + eps
  );
}

/**
 * Build wall-local visual parts for an Opening (`door` | `window` | `passage`).
 * Origin is at the opening's horizontal center on the floor (`y = 0`).
 * All parts fit within `[-width_m/2, +width_m/2] x [sill_m, sill_m + height_m] x [-thickness_m/2, +thickness_m/2]`.
 * No assumed hinge or swing arc is emitted because `Opening` v1 has no hinge/leaf-state metadata.
 */
export function buildOpeningVisualParts(
  kind: "door" | "window" | "passage",
  widthM: number,
  heightM: number,
  sillM: number,
  wallThicknessM: number,
): LocalVisualPart[] {
  const w = widthM;
  const h = heightM;
  const sill = Math.max(0, sillM);
  const t = wallThicknessM;
  const jambW = Math.min(0.045, w * 0.08);
  const headH = Math.min(0.045, h * 0.08);

  const parts: LocalVisualPart[] = [
    // Left jamb
    {
      id: "jamb-left",
      shape: "box",
      position: [-w * 0.5 + jambW * 0.5, sill + h * 0.5, 0],
      size: [jambW, h, t * 0.96],
      role: "frame",
    },
    // Right jamb
    {
      id: "jamb-right",
      shape: "box",
      position: [w * 0.5 - jambW * 0.5, sill + h * 0.5, 0],
      size: [jambW, h, t * 0.96],
      role: "frame",
    },
    // Top head frame
    {
      id: "frame-head",
      shape: "box",
      position: [0, sill + h - headH * 0.5, 0],
      size: [w, headH, t * 0.96],
      role: "frame",
    },
  ];

  if (kind === "window") {
    const sillBarH = Math.min(0.04, h * 0.08);
    const paneW = Math.max(0.04, w - jambW * 2);
    const paneH = Math.max(0.04, h - headH - sillBarH);
    parts.push(
      {
        id: "window-sill",
        shape: "box",
        position: [0, sill + sillBarH * 0.5, 0],
        size: [w, sillBarH, t],
        role: "frame",
      },
      {
        id: "window-glass",
        shape: "box",
        position: [0, sill + sillBarH + paneH * 0.5, 0],
        size: [paneW, paneH, Math.min(0.02, t * 0.25)],
        role: "glass",
      },
    );
    if (w >= 1.5) {
      parts.push({
        id: "window-mullion",
        shape: "box",
        position: [0, sill + sillBarH + paneH * 0.5, 0],
        size: [Math.min(0.035, jambW), paneH, t * 0.6],
        role: "frame",
      });
    }
  } else if (kind === "door") {
    const threshH = Math.min(0.02, h * 0.02);
    parts.push({
      id: "door-threshold",
      shape: "box",
      position: [0, sill + threshH * 0.5, 0],
      size: [w, threshH, t * 0.98],
      role: "secondary",
    });
  } else {
    const threshH = Math.min(0.015, h * 0.015);
    parts.push({
      id: "passage-threshold",
      shape: "box",
      position: [0, sill + threshH * 0.5, 0],
      size: [w, threshH, t * 0.8],
      role: "secondary",
    });
  }

  return parts.map((part) => {
    const local = clampPartToBounds(
      {
        ...part,
        position: [part.position[0], part.position[1] - sill, part.position[2]],
      },
      w,
      h,
      t,
    );
    return {
      ...local,
      position: [
        local.position[0],
        local.position[1] + sill,
        local.position[2],
      ] as [number, number, number],
    };
  });
}
