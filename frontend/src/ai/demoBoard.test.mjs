import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { DEMO_BOARD_SIZE, DEMO_TARGETS, DEMO_ZONES, demoBoardCapture, demoBoardSvg } from './demoBoard.ts';
import { captureEvidence } from './evidence.ts';

test('synthetic board uses every canonical four-zone polygon at the declared translation', async () => {
  const venue = JSON.parse(await readFile(new URL('../../../venue/reviewed_venue.json', import.meta.url), 'utf8'));
  assert.deepEqual(DEMO_ZONES.map(zone => zone.id), venue.zones.map(zone => zone.id));
  for (const zone of DEMO_ZONES) {
    const canonical = venue.zones.find(candidate => candidate.id === zone.id);
    assert.deepEqual(canonical.polygon.map(([x, y]) => [x - 50, y - 50]), [
      [zone.x, zone.y], [zone.x + zone.width, zone.y],
      [zone.x + zone.width, zone.y + zone.height], [zone.x, zone.y + zone.height],
    ]);
  }
});

test('P1, P2 and B2 token pads have distinct canonical passage or boundary positions', () => {
  assert.deepEqual(Object.keys(DEMO_TARGETS), ['P1', 'P2', 'B2']);
  assert.deepEqual(DEMO_TARGETS.P1, { x: 60, y: 210, typedId: 'portal:P1', padId: 'T_P1' });
  assert.deepEqual(DEMO_TARGETS.P2, { x: 240, y: 210, typedId: 'portal:P2', padId: 'T_P2' });
  assert.deepEqual(DEMO_TARGETS.B2, { x: 240, y: 374, typedId: 'boundary:B2', padId: 'T_B2' });
  assert.equal(new Set(Object.values(DEMO_TARGETS).map(({ x, y }) => `${x},${y}`)).size, 3);
});

test('the shared preview/upload image has exactly one red BLOCKED token at the selected pad', () => {
  for (const target of Object.keys(DEMO_TARGETS)) {
    const svg = demoBoardSvg(target);
    const pad = DEMO_TARGETS[target];
    assert.match(svg, new RegExp(`<g transform="translate\\(${pad.x} ${pad.y}\\)" data-blocked-target="${target}">`));
    assert.equal((svg.match(/data-blocked-target=/g) ?? []).length, 1);
    assert.equal((svg.match(/fill="#d92d2a"/g) ?? []).length, 1);
    assert.equal((svg.match(/>BLOCKED<\/text>/g) ?? []).length, 1);
    for (const candidate of Object.values(DEMO_TARGETS)) assert.ok(svg.includes(`>${candidate.padId}</text>`));
    assert.match(svg, /SYNTHETIC TABLETOP/);
    assert.match(svg, /not a surveyed building/);
    assert.match(svg, /no physical hardware/);
  }
  assert.throws(() => demoBoardSvg('P3'), /Choose P1, P2 or B2/);
});

test('demo board capture is live annotated-image input with original metadata and no forced target', async () => {
  const context = { state_epoch: 'server-1', geometry_revision: 'geometry-1', scenario_revision: 2, physical_revision: 3, parameters_revision: 'params-1', solver_version: 'solver-1', context_hash: 'current-context-hash' };
  const metadata = { captureId: 'synthetic-capture-1', timestampIso: '2026-10-24T10:12:34.123Z', context, thinkingLevel: 'low' };
  const pixels = btoa('renderer image bytes');
  const capture = await captureEvidence(demoBoardCapture(pixels, metadata));
  assert.equal(capture.mode, 'live');
  assert.equal(capture.source_kind, 'annotated_plan');
  assert.equal(capture.image_base64, pixels);
  assert.equal(capture.capture_id, metadata.captureId);
  assert.equal(capture.timestamp_iso, metadata.timestampIso);
  assert.equal(capture.thinking_level, 'low');
  assert.equal(capture.deadline_seconds, 45);
  assert.deepEqual(capture.dimensions, [...DEMO_BOARD_SIZE]);
  assert.deepEqual(capture.source_context, context);
  assert.notEqual(capture.source_context, context);
  assert.match(capture.image_sha256, /^[a-f0-9]{64}$/);
  for (const forbidden of ['fixture_target', 'force_target', 'target_override', 'selected_entity_id', 'intended_target']) assert.equal(forbidden in capture, false);
  context.scenario_revision = 99;
  assert.equal(capture.source_context.scenario_revision, 2);
  assert.throws(() => demoBoardCapture('', metadata), /could not be captured/);
});
