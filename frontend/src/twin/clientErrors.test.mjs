import assert from 'node:assert/strict';
import test from 'node:test';
import { ApiError, requestJson } from '../api/client.ts';

const withFetch = async (impl, run) => {
  const original = globalThis.fetch;
  globalThis.fetch = impl;
  try { await run(); } finally { globalThis.fetch = original; }
};

test('a timeout or a dead connection becomes readable copy; a caller cancel stays an abort', async () => {
  await withFetch(async () => { throw new DOMException('signal timed out', 'TimeoutError'); }, async () => {
    await assert.rejects(requestJson('/x', { fallback: 'The plan could not be computed' }), error =>
      error instanceof ApiError && error.detail === 'timeout' && error.message === 'The plan could not be computed: the server did not answer in time. Please try again.');
  });
  await withFetch(async () => { throw new TypeError('Failed to fetch'); }, async () => {
    await assert.rejects(requestJson('/x', { fallback: 'The plan could not be computed' }), error =>
      error instanceof ApiError && error.detail === 'unreachable' && /could not be reached/.test(error.message));
  });
  await withFetch(async () => { throw new DOMException('The operation was aborted.', 'AbortError'); }, async () => {
    await assert.rejects(requestJson('/x', { fallback: 'x' }), error => error instanceof DOMException && error.name === 'AbortError');
  });
});
