// Bumped whenever the workflow is reset. A response that started in an earlier epoch is discarded.
export function createWorkflowEpoch() {
  let epoch = 0;
  return {
    current(): number { return epoch; },
    bump(): number { return ++epoch; },
    isCurrent(started: number): boolean { return started === epoch; },
  };
}

/** Consecutive 404s on the progress poll are tolerated while the server registers the run, then polling stops. */
export const MAX_NOT_FOUND_POLLS = 10;

export function nextNotFoundCount(status: string, previous: number): number {
  return status === 'not_found' ? previous + 1 : 0;
}

export function shouldKeepPolling(status: string, notFoundCount: number): boolean {
  if (status === 'not_found') return notFoundCount < MAX_NOT_FOUND_POLLS;
  return status === 'running';
}
