---
name: robustness-sweep
description: Run the N-1 robustness sweep of a door-state candidate with the sandbox solver kit and turn it into claims.
---
# Robustness sweep

1. Run the default sweep (checked best candidate, single failures, untenable sensitivity, second hazards):

   ```bash
   cd /workspace/kit && python3 -m spatialtwin_kit.sweep
   ```

   It prints a one-line summary and the suggested claims (`[scenario, completed_crossings]` pairs), and writes
   `/workspace/out/sweep.json`. `engine_label` says whether the exact copy
   of the local solver ran or the pure-Python "sandbox estimate" (networkx missing).
2. If the summary shows breaks, sweep a more robust candidate, for example
   `python3 -m spatialtwin_kit.sweep --candidate D4=open,D9=open --only-single`.
3. Read `suggested_claims` from `/workspace/out/sweep.json`: each claim is `{scenario, completed_crossings,
   candidate_hash}` for the candidate swept. Use them as they are; do not edit numbers.
4. Optionally call `verify_candidates` for up to 8 `{door_states, scenario}` pairs to see the local checker's
   numbers before you submit.
5. Call `submit_recommendation` once: `door_states` (every controllable door), `fallback_if_jammed` (the state to
   use if a door you open jams shut), at most 12 claims (`applies_to` is `recommended` or `fallback`) and a
   rationale of at most 400 characters about the numerical tradeoff.

Counts are modeled crossings of a synthetic population, never survival.
