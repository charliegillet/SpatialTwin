# Bounded managed Argon investigations

The managed adapter requests `antigravity-preview-09-2026` with explicit
`gemini-4-argon` configuration through the pinned `google-genai 2.33.0` SDK.
Its provider transport, polling, lifecycle and request serialization are tested
offline with mocked HTTP and blocked sockets. These tests establish local
behavior; they do not establish account entitlement, live provider reliability,
real image accuracy or physical bench validation.

## Execution modes and evidence

`investigate_scenario(context, investigation_id=None, deadline_seconds=60.0,
mode="live")` defaults to a live investigation. Missing credentials return
`failed` with `provenance="unavailable"`, no recommendation and no provider
usage. Provider exceptions also produce an explicit diagnostic; they never
switch to local computation. Raw exception messages and credentials are not
logged or returned.
Typed HTTP status metadata produces safe diagnostics: `provider_access_denied`
for 401/403, `provider_rate_limited` for 429, `provider_request_rejected` for
other 4xx, and `provider_unavailable` for 5xx. Exception text is never used to
construct these diagnostics.

An operator can deliberately choose `mode="local"` to run the fixed numerical
tools without a provider. Results carry `provenance="local"`, empty provider
usage and no provider interaction/model identity. The explanation attributes
the comparison to local checked computation. The API disables this demonstration
mode in production. Local numerical timings are measured; token counts are
never invented.

Actual provider results retain interaction/environment IDs, the reported model,
SDK version and measured local latency. `provenance="live"` records receipt of
an actual provider response; its `status` and diagnostics must also be inspected.
A failed or incomplete provider response is not a successful investigation.
Results do not claim that a configured client alone proves model access.

## Read-only tool boundary

Only these custom functions are declared:

| Function | Accepted arguments | Effect |
|---|---|---|
| `get_reviewed_scenario` | `{}` | Read the reviewed context and fixed target catalog. |
| `evaluate_allowed_alternative` | Exactly `{"alternative_id":"KEEP_CURRENT"}` or `{"alternative_id":"OPEN_P3"}` | Evaluate an immutable numerical alternative. |
| `get_checked_comparison` | `{}` | Evaluate both fixed alternatives under equal conditions. |

Missing/extra arguments, unknown functions, unknown alternatives and incomplete
argument material are rejected before execution. The provider receives no
actuation, serial, arbitrary local code, shell or state-mutation function.
Numerical tools are the source of displayed values. Provider prose is never
parsed into metrics or used to choose a recommendation.

The adapter validates publishable checker verdicts, full current context,
nonnegative/conserved population and matching population, horizon and time step.
Only a provider `completed` status with both valid current alternatives permits
a live recommendation. Local mode applies the same comparison checks. An equal
result legitimately recommends `KEEP_CURRENT`; opening P3 cannot increase the
receiving capacity of B2.
Already checked candidate envelopes are retained if the provider later times out;
they remain numerical evidence, with no successful-investigation or winning-option
claim until the required lifecycle and current-context checks pass.

## Asynchronous lifecycle and cumulative limits

Every cloud call uses `await client.aio.interactions.*`. Initial and continuation
requests use stored background execution; active interactions are retrieved by
ID. The loop handles queued/in-progress, requires-action, completed, failed,
cancelled, incomplete and budget-exceeded outcomes. It does not automatically
resume a budget-exhausted interaction. SDK retries are explicitly disabled
on the per-client Interactions retry strategy; offline 429/503 tests assert one
HTTP request. In SDK 2.33.0, setting `HttpRetryOptions(attempts=0)` alone still
normalizes to a retry, so the adapter explicitly sets the resource strategy to
`none` without modifying global SDK behavior.

Initial configuration is:

```python
await client.aio.interactions.create(
    agent="antigravity-preview-09-2026",
    agent_config={
        "type": "antigravity",
        "model": "gemini-4-argon",
        "max_total_tokens": 20000,
    },
    environment="remote",
    background=True,
    store=True,
    tools=TOOL_DEFINITIONS,
    input=bounded_prompt,
)
```

The SDK accepts a Python integer and serializes the budget as a wire string.
No managed structured response schema or unsupported generation configuration
is sent. Typed SDK usage is read by field access. Repeated polling for one
interaction takes the maximum reported cumulative value per field; new
interaction IDs contribute separately. Continuations receive only the remaining
20,000-token uncached budget, and do not receive another full allowance.
Missing continuation usage fails closed. The provider's budget is best effort;
an overshoot is recorded and blocks further continuation, not retroactively
claimed to have been impossible.

At most four distinct accepted client calls and four continuations are allowed.
The alternatives are limited to KEEP_CURRENT/OPEN_P3. These bounds are separate
from one another and from the whole-run deadline. Already fulfilled function
calls are filtered from returned history; completed duplicate local calls reuse
their durable result. Function-result payloads carry the matching provider
call ID and preserve the interaction/environment chain. The bounded JSON result
is serialized as a function-result string, supported by the pinned SDK.

Cloud tool replies retain context, candidate/run identity, checker verdicts,
counts, finite horizon, boundary breakdown and assumptions, while omitting full
playback timelines. Full envelopes remain in the local ledger and final result.
The prompt requests one checked-comparison call and a concise final explanation
to avoid redundant provider turns. This reduces input size; it does not promise
provider completion within the deadline. Official managed-agent documentation
warns that multi-step work can take minutes.
An authorized live smoke on 24 October 2026 completed in approximately 39.9
seconds using the actual Argon model and one `get_checked_comparison` call,
with 12,279 reported total tokens (3,264 cached) and no errors. This is one
measured sample, not a latency guarantee or camera/hardware validation. The
default investigation allowance is therefore 60 seconds, with 0.5-second poll
spacing; the whole-run deadline and cancellation bounds still apply.

`await adapter.get_progress(investigation_id)` returns durable sanitized phase
receipts (the latest 64 are included as `provider_progress`): provider
request/response method, opaque interaction ID/status, elapsed
time, local tool completion/timing and compact result size. It contains no model
thoughts, provider text, credentials or raw tool arguments. Smoke tools should
retain these receipts before deleting an isolated temporary database.
`last_provider_status` retains only a fixed status enum (or `unknown`), including
a reported cancellation status when a cancel response arrives. Up to three
seconds, bounded by ten percent of the requested deadline, are reserved for
cancellation/persistence; the cancel round trip is capped at two seconds.

A monotonic deadline bounds provider requests, polling, background ledger access
and numerical-tool waits. Part of the allowance is reserved for a bounded,
best-effort provider cancellation and final persistence. Deadline/cancellation
results have no recommendation. Cancellation is acknowledged only as a request
unless a provider receipt establishes its outcome; failure to confirm is a
diagnostic. Task cancellation becomes a persisted `cancelled` investigation.

Synchronous numerical computation runs in a worker thread so it cannot block
the API/heartbeat event loop. Python cannot forcibly stop a running thread: a
late read-only worker may finish its already claimed computation, but cannot
publish a new successful investigation or overwrite a timeout/cancellation.
Its persisted claim prevents retrying that uncertain execution.

## Durable recovery and replay

The leaf ledger adds `managed_runs_v1` and `managed_calls_v1` tables to the
scenario store's SQLite database. Interaction/environment identity, provider
status and cumulative usage are persisted during the loop. A call is claimed
transactionally before its worker starts. The scenario service also caches
evaluation request IDs scoped by investigation and provider call.
Initial investigation ownership is resolved in a non-waiting metadata transaction
before the adapter's first await. A busy ledger fails closed without starting
background ownership work. Cancellation after API task registration therefore
cannot leave a delayed begin worker creating an orphaned running investigation.
As with final publication, filesystem commit latency is not a hard timing guarantee.

Completed investigation results are persisted before return. Reusing the same
investigation ID, mode and full context returns the stored result with
`replayed=true`, retaining its original execution provenance and timing. It
does not make another provider request. Reusing an ID with different inputs is
rejected.
The API's public result index reads `await adapter.get_saved_result(id)`, which
exposes only the durable finished owner's record. A transient conflict returned
to a concurrent nonowner cannot occupy that index before the owner completes.

Final persistence has two phases. A background worker stages the result in an
unpublished `finalizing` state. Only a terminal compare-and-set makes it public;
late staging writes cannot replace a finished record. The adapter checks the
deadline, caller cancellation and full current context at that terminal write
while holding the authoritative state lock. There is no await between that check,
the terminal decision and return. The metadata transaction acquires locks without
waiting and disables SQLite busy waiting; unavailable storage fails closed rather
than exposing a staged success. Provider and numerical work remain asynchronous.
The final SQLite metadata commit is synchronous: disabling busy waiting does not
provide a hard wall-clock bound on filesystem I/O.
A cancellation received before this commit produces a cancelled record; a request
after an already committed completion does not rewrite history. A timed-out or
cancelled staging worker may finish later, but cannot publish its earlier success.
Cancellation during final ledger reads is handled the same way. Staged results
left after a process interruption are never returned as completed replays.

An interrupted run with a pending claim fails closed as
`tool_execution_uncertain`; the adapter does not run that function again.
Other unfinished runs report `investigation_recovery_required`. There is no
automatic paid resume after a process restart. An operator reviews the evidence
and explicitly starts a new investigation ID when a new attempt is wanted.

## Validation and remaining limits

Run the focused offline tests from the repository root:

```sh
.venv/bin/python -m pytest tests/ai_contracts/test_managed_agent.py tests/ai_contracts/test_managed_production.py -q
```

They cover the actual async SDK's typed usage and wire serialization, explicit
local mode, missing access, lifecycle outcomes, cumulative usage, call limits,
strict arguments, durable replay/restart behavior, stale/mismatched evidence,
timeouts, caller cancellation, late workers and sanitized errors.
Finalization regressions include delayed persistence beyond the deadline,
cancellation during final reads/writes, context drift during final reads,
immutable terminal records and restart with an unpublished staged result.
They also cover cancellation on the adapter's first turn and a busy initial
ownership lock, which must not produce a late running row.
Provider streaming, runtime skill mounts, saved agents, video and long decode remain
separate optional features. Use the live smoke command and record actual
request/status/model/usage evidence before claiming successful cloud access.

Physical movement remains a separate reviewed local transaction. An AI
recommendation is never an endpoint observation or hardware approval.
