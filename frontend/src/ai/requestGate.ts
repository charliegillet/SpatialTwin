// A synchronous guard for work that starts before React can commit busy state.
// Tokens keep a late completion from releasing a newer request after a reset.
export function createRequestGate() {
  let sequence = 0;
  let owner: number | null = null;
  return {
    start(): number | null {
      if (owner !== null) return null;
      owner = ++sequence;
      return owner;
    },
    isCurrent(token: number): boolean { return owner === token; },
    finish(token: number): void { if (owner === token) owner = null; },
    invalidate(): void { owner = null; },
  };
}
