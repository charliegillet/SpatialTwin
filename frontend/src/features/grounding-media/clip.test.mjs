import test from 'node:test';
import assert from 'node:assert/strict';
import { validateClip, MAX_CLIP_BYTES, MAX_CLIP_SECONDS } from './clip.ts';

const base = { type: 'video/mp4', size: 1024, durationSeconds: 5 };

test('valid mp4 and webm are accepted', () => {
  assert.deepEqual(validateClip(base), { ok: true });
  assert.deepEqual(validateClip({ ...base, type: 'video/webm' }), { ok: true });
});

test('gif and other types are rejected', () => {
  for (const type of ['image/gif', 'video/quicktime', 'application/pdf', '']) {
    const result = validateClip({ ...base, type });
    assert.equal(result.ok, false);
    assert.match(result.reason, /MP4 or WebM/);
  }
});

test('over 8 MB is rejected', () => {
  const result = validateClip({ ...base, size: MAX_CLIP_BYTES + 1 });
  assert.equal(result.ok, false);
  assert.match(result.reason, /8 MB/);
});

test('15.5 seconds is rejected', () => {
  const result = validateClip({ ...base, durationSeconds: 15.5 });
  assert.equal(result.ok, false);
  assert.match(result.reason, /15 seconds/);
});

test('unknown duration is reported, not accepted', () => {
  for (const durationSeconds of [undefined, Number.NaN, Number.POSITIVE_INFINITY]) {
    const result = validateClip({ ...base, durationSeconds });
    assert.equal(result.ok, false);
    assert.match(result.reason, /server-side check/);
  }
});

test('exactly 15 s and exactly 8 MB are accepted', () => {
  assert.deepEqual(validateClip({ ...base, durationSeconds: MAX_CLIP_SECONDS }), { ok: true });
  assert.deepEqual(validateClip({ ...base, size: MAX_CLIP_BYTES }), { ok: true });
});

test('empty file is rejected', () => {
  assert.equal(validateClip({ ...base, size: 0 }).ok, false);
});
