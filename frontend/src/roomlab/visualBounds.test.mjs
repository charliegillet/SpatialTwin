import test from "node:test";
import assert from "node:assert/strict";
import {
  buildObjectVisualParts,
  buildOpeningVisualParts,
  classifyVisualCategory,
  computeLocalVisualBounds,
  verifyPartsWithinOBB,
} from "./visualBounds.ts";

test("all object categories fit strictly inside declared OBB in both proxy and bounds modes", () => {
  const cases = [
    { category: "table", label: "Conference Table", w: 1.8, h: 0.75, d: 0.9 },
    { category: "counter", label: "Marble Reception Desk", w: 0.95, h: 1.1, d: 3.8 },
    { category: "stool", label: "Wooden Stool 1", w: 0.4, h: 0.48, d: 0.4 },
    { category: "chair", label: "Office Chair", w: 0.55, h: 0.85, d: 0.55 },
    { category: "sofa", label: "Lounge Sofa", w: 2.0, h: 0.8, d: 0.9 },
    { category: "plant", label: "Potted Plant (Near Stairs)", w: 0.75, h: 1.65, d: 0.75 },
    { category: "bicycle", label: "Parked Bicycles", w: 0.9, h: 1.05, d: 1.7 },
    { category: "stairs", label: "Interior Staircase", w: 3.2, h: 3.2, d: 1.6 },
    { category: "bin", label: "White Bin", w: 0.4, h: 0.65, d: 0.4 },
    { category: "pillar", label: "Structural Column", w: 0.5, h: 3.0, d: 0.5 },
    { category: "unknown_custom", label: "Mystery Crate", w: 1.1, h: 0.6, d: 0.7 },
  ];

  for (const c of cases) {
    const proxyParts = buildObjectVisualParts(c.w, c.h, c.d, c.category, c.label, "proxy");
    assert.ok(proxyParts.length >= 1, `Expected parts for ${c.category}`);
    assert.equal(
      verifyPartsWithinOBB(proxyParts, c.w, c.h, c.d),
      true,
      `Proxy parts for ${c.category} (${c.label}) exceeded OBB`,
    );

    const boundsParts = buildObjectVisualParts(c.w, c.h, c.d, c.category, c.label, "bounds");
    assert.equal(boundsParts.length, 1);
    const b = computeLocalVisualBounds(boundsParts);
    assert.ok(Math.abs(b.minX + c.w * 0.5) < 1e-6);
    assert.ok(Math.abs(b.maxX - c.w * 0.5) < 1e-6);
    assert.ok(Math.abs(b.minY - 0) < 1e-6);
    assert.ok(Math.abs(b.maxY - c.h) < 1e-6);
    assert.ok(Math.abs(b.minZ + c.d * 0.5) < 1e-6);
    assert.ok(Math.abs(b.maxZ - c.d * 0.5) < 1e-6);
  }

  // Ensure incidental "Near Stairs" plant is classified as plant, not stairs
  assert.equal(classifyVisualCategory("plant", "Potted Plant (Near Stairs)"), "plant");
  assert.equal(classifyVisualCategory("stairs", "Interior Staircase"), "stairs");
});

test("opening visual parts fit strictly within aperture width, sill..sill+height, and wall thickness", () => {
  for (const kind of ["door", "window", "passage"]) {
    const w = 1.8;
    const h = 2.2;
    const sill = kind === "window" ? 0.55 : 0.0;
    const thick = 0.14;
    const parts = buildOpeningVisualParts(kind, w, h, sill, thick);
    const b = computeLocalVisualBounds(parts);
    assert.ok(b.minX >= -w * 0.5 - 1e-6);
    assert.ok(b.maxX <= w * 0.5 + 1e-6);
    assert.ok(b.minY >= sill - 1e-6);
    assert.ok(b.maxY <= sill + h + 1e-6);
    assert.ok(b.minZ >= -thick * 0.5 - 1e-6);
    assert.ok(b.maxZ <= thick * 0.5 + 1e-6);
  }
});

test("small imported dimensions never enlarge proxy or aperture geometry", () => {
  for (const category of ['table','counter','chair','stool','sofa','plant','bicycle','stairs','bin','pillar','custom']) {
    for (const mode of ['proxy','bounds']) {
      assert.ok(verifyPartsWithinOBB(buildObjectVisualParts(.003,.007,.011,category,'',mode),.003,.007,.011), category);
    }
  }
  for (const kind of ['door','window','passage']) {
    const b=computeLocalVisualBounds(buildOpeningVisualParts(kind,.003,.007,.2,.001));
    assert.ok(b.minX>=-.0015-1e-6 && b.maxX<=.0015+1e-6);
    assert.ok(b.minY>=.2-1e-6 && b.maxY<=.207+1e-6);
    assert.ok(b.minZ>=-.0005-1e-6 && b.maxZ<=.0005+1e-6);
  }
});
