import type { LocalVisualPart } from "./visualBounds.ts";
export function wallFrameParts(
  length: number,
  height: number,
  thickness: number,
): LocalVisualPart[] {
  const post = Math.min(0.04, length * 0.12),
    rail = Math.min(0.045, height * 0.12),
    depth = thickness * 0.95;
  const parts: LocalVisualPart[] = [
    {
      id: "bottom",
      shape: "box",
      position: [0, -height / 2 + rail / 2, 0],
      size: [length, rail, depth],
      role: "frame",
    },
    {
      id: "top",
      shape: "box",
      position: [0, height / 2 - rail / 2, 0],
      size: [length, rail, depth],
      role: "frame",
    },
  ];
  const count = Math.min(12, Math.max(1, Math.ceil(length / 1.2)));
  for (let i = 0; i <= count; i++)
    parts.push({
      id: "post-" + i,
      shape: "box",
      position: [-length / 2 + post / 2 + ((length - post) * i) / count, 0, 0],
      size: [post, height, depth],
      role: "frame",
    });
  return parts;
}
