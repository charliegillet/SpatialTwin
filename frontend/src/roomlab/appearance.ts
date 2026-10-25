import type {
  AppearanceChoice,
  RoomObject,
  RoomSceneV1,
  SurfaceAppearance,
  Wall,
} from "./contracts.generated";
import { classifyVisualCategory } from "./visualBounds.ts";
export type Material = NonNullable<AppearanceChoice["material"]>;
export type ResolvedAppearance = {
  color: string;
  material: Material;
  source: "user_choice" | "model_estimate" | "heuristic_fallback";
  note: string;
  evidence_frame_ids: string[];
};
export const MATERIAL_COLORS: Partial<Record<Material, string>> = {
  wood: "#b7a082",
  terrazzo: "#d5d2c8",
  tile: "#d6d4cc",
  stone: "#c6c4bc",
  marble: "#deddd5",
  carpet: "#b9b8ac",
  concrete: "#c5c5be",
  glass: "#bbd4cd",
  paint: "#d9d9ce",
  fabric: "#b6aca0",
  metal: "#8c9591",
  ceramic: "#c0ac90",
  foliage: "#7e946b",
};
const words: Material[] = [
  "terrazzo",
  "wood",
  "tile",
  "stone",
  "marble",
  "carpet",
  "concrete",
  "glass",
  "metal",
  "fabric",
];
export function materialHint(text: string): Material {
  // A scoped description is still only a heuristic, never a recovered texture.
  if (/\b(no|not|non|without|possibly|maybe|uncertain|mixed)\b/i.test(text))
    return "unknown";
  const found = words.filter((word) =>
    new RegExp(`\\b${word}(?:en)?\\b`, "i").test(text),
  );
  return found.length === 1 ? found[0] : "unknown";
}
export function resolveAppearance(
  a: SurfaceAppearance | null | undefined,
  color = "#c8cec1",
  hint: Material = "unknown",
): ResolvedAppearance {
  const chosen = a?.user_override ?? a;
  const material = chosen?.material ?? hint;
  return {
    color: chosen?.color ?? MATERIAL_COLORS[material] ?? color,
    material,
    source: a?.user_override
      ? "user_choice"
      : (a?.provenance?.source ?? "heuristic_fallback"),
    note: a?.user_override
      ? "User display choice; geometry unchanged."
      : (a?.provenance?.note ??
        (hint === "unknown"
          ? "Neutral category default."
          : "Scoped description hint; illustrative, not measured.")),
    evidence_frame_ids: a?.user_override
      ? []
      : (a?.provenance?.evidence_frame_ids ?? []),
  };
}
export function resolveFloorAppearance(scene: RoomSceneV1): ResolvedAppearance {
  // Only explicit floor-finish statements. Object labels and notes never decide the floor.
  const statements = (scene.notes ?? []).filter((n) =>
    /^\s*(?:the\s+)?floor\s*(?:material|finish|is|:)/i.test(n),
  );
  const hints = statements.map((n) =>
    /\b(?:landing|zone|section|kitchen|lobby|lounge|corridor|side|half)\b/i.test(
      n,
    )
      ? "unknown"
      : materialHint(n),
  );
  const hint =
    hints.length &&
    hints.every((m) => m !== "unknown") &&
    new Set(hints).size === 1
      ? hints[0]
      : "unknown";
  return resolveAppearance(scene.floor_appearance, "#dbddd3", hint);
}
export function resolveWallAppearance(
  wall: Wall | undefined,
  sceneDefault?: SurfaceAppearance | null,
): ResolvedAppearance {
  return resolveAppearance(
    wall?.appearance?.user_override
      ? wall.appearance
      : wall?.role === "shell" && sceneDefault?.user_override
        ? {
            ...(wall.appearance ?? sceneDefault),
            user_override: sceneDefault.user_override,
          }
        : (wall?.appearance ?? sceneDefault),
    "#c9cec0",
    materialHint(
      (wall?.provenance?.note ?? "").split(
        /\b(?:separating|adjacent|beside)\b/i,
      )[0],
    ),
  );
}
export function objectRoleAppearance(obj: RoomObject, role: string) {
  const kind = classifyVisualCategory(obj.category, obj.label);
  const hint = materialHint(obj.label ?? "");
  const defaults: Partial<Record<typeof kind, string>> = {
    sofa: "#b5aaa0",
    plant: "#bba586",
    stairs: "#c2ac85",
    counter: "#dadcd5",
    table: "#b7a082",
    stool: "#c4b295",
    chair: "#adb5b4",
    bicycle: "#7796a8",
    bin: "#d1d5ce",
    pillar: "#b6bcb0",
  };
  const base = resolveAppearance(
    obj.appearance,
    defaults[kind] ?? "#b6b8ab",
    hint,
  );
  if (role === "foliage")
    return { ...base, color: "#7c956d", material: "foliage" as Material };
  if (role === "frame")
    return { ...base, color: "#818a83", material: "metal" as Material };
  if (role === "secondary" && kind === "counter" && base.material === "marble")
    return { ...base, color: "#bbb4a8", material: "paint" as Material };
  return base;
}
export function setAppearanceChoice(
  base: SurfaceAppearance | null | undefined,
  choice: AppearanceChoice,
): SurfaceAppearance {
  return {
    ...(base ?? {
      material: "unknown",
      provenance: {
        source: "heuristic_fallback",
        evidence_frame_ids: [],
        note: "Neutral default.",
      },
    }),
    user_override: choice,
  };
}
