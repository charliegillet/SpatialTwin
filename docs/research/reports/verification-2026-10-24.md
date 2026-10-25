# Argon integration verification — 24 October 2026

The audited defects have been corrected in the working tree based on commit `29b33da149b6c9d7a7e52957079565e8bd202619`. This record distinguishes actual provider execution from mocks, synthetic inputs and physical trials.

## Recorded checks

| Check | Result | Scope |
|---|---|---|
| Backend `python -m pytest tests -q` | **155 passed**, 3.30 seconds | Network blocked, empty provider/serial configuration, temporary SQLite. Includes actual pinned SDK request/response serialization with mocked HTTP. |
| Frontend `npm test` | **9 passed** | Full context/epoch checks, provenance labels, failed/stale action blocking, request metadata and error behavior. |
| Frontend `npm run build` | **Passed** | TypeScript and Vite production build. |
| Dependency compatibility | **Passed**, 40 packages | Exact Python environment recorded in requirements.lock. |
| Isolated browser smoke | **Passed** | Mocked provider/API/SSE, fake browser camera; fixture/live/local/failure/staleness/production-mode/mobile checks. No hardware requests. |
| Real direct Argon | **Completed, live** | Correct P2 selection on a synthetic labeled JPEG, strict schema/current capture, actual model/interaction receipt and measured usage. |
| Real managed Argon | **Completed, live** | Actual `gemini-4-argon`, one real client-executed `get_checked_comparison` call, both checked alternatives and valid final provider completion. |
| Old timed-out provider job cleanup | **Confirmed cancelled** | Inspection/cancellation of only the earlier smoke interaction. |
| Local preview | **Refreshed** | Old simulator backend snapshot preserved; new localhost backend exposes session epoch and explicit AI configuration. |
| Real-camera accuracy trial | **Pending board assembly** | User confirmed the board is not ready. Twenty varied real board captures are required by BUILD_PLAN; synthetic images and fake-camera browser tests do not satisfy this. |
| Physical bench test | **Not performed** | No servo/device operation was used for this implementation verification. |

The backend suite emits one deprecation warning from the pinned Starlette TestClient/httpx compatibility layer; it passes. No warning was suppressed to turn a failure into success.

## Actual live measurements

| Path | Measured elapsed | Reported total tokens | Cached tokens | Result |
|---|---:|---:|---:|---|
| Direct stored interaction | 7,690 ms | 2,256 | 0 | completed, actual model `gemini-4-argon`, synthetic P2 correct |
| Managed investigation | 39,877 ms | 12,279 | 3,264 | completed, one checked-comparison function, no errors |

These are single observed samples, not a latency or accuracy guarantee. The managed default is 60 seconds based on this measurement; the browser transport allows 65 seconds. Provider/token limits remain best effort as documented. The full local ledger retains checked envelopes; cloud tool responses omit bulky visualization timelines and repeat data.

Earlier checks were retained as failures: two stateless direct responses lacked an acceptable interaction receipt, and the initial four-tool managed run reached its deadline. The final direct implementation explicitly requests stored execution and the subsequent real check returned a valid receipt. Provider retention is documented in production-readiness.md. The final managed prompt requests one checked comparison and compact tool summaries. The earlier timed-out job was later confirmed cancelled; it is not reclassified as a successful application run.

## Local evidence

These files are deliberately ignored runtime evidence, not credentials or tracked fixtures:

- `runtime/argon-direct-stored-live-check.json`: actual direct receipt and response structure; synthetic input explicitly labeled.
- `runtime/argon-managed-live-check.json`: actual managed model, interaction/environment, checked ledger, usage and sanitized lifecycle progress.
- `runtime/argon-live-check.json`, `runtime/argon-direct-live-check.json`: earlier failed checks, retained honestly.
- `runtime/argon-final-cleanup-check.json`: confirmed cancellation of the earlier timed-out interaction.
- `runtime/ai-ui-verification/`: screenshots and isolated mocked browser harness. A screenshot with mock receipt IDs is browser-test evidence, not a real-provider screenshot.
- `runtime/ai-preview-before-restart.json`: saved simulator snapshot before loading the new backend contracts.

SHA-256 checksums of the two successful receipts:

```text
argon-direct-stored-live-check.json
65516baf49a6af6016c51cd5a4cfc692e0935961f152071509f98dc15ad3229b

argon-managed-live-check.json
95ba600597cbec27d11f9ebd415fc62cadf4f29bb12288259c7be11bd6436e48
```

The recorded live receipts were produced during the hardening work. Later changes added stronger API indexing/admission checks and adjusted the measured default deadline; offline tests verify those changes. Their successful provider request shapes remain unchanged.

## Audit resolution

| Audited issue | Resolution |
|---|---|
| Typed usage `.get()` failure | Typed/dictionary-safe usage extraction and actual SDK regression tests. |
| Hidden fallback / synthetic usage | Explicit live/fixture/local modes, unavailable/error outcomes, measured provider usage only. |
| Missing schema / malformed grounding | Strict provider schema plus JSON and local semantic validation, completed status required. |
| Stale capture/context | Capture-time identity, frozen canonical full context with process epoch, expiry at interpretation and Apply, stale in-flight result rejection. |
| Lifecycle/deadline/cancellation | Async background/polling, explicit terminal status, whole-run monotonic bounds, recorded cancellation outcome. |
| Repeated calls / missing durable ledger | Claim-before-execute SQLite ledger, numerical request caching, bounded calls/continuations, uncertain crash replay blocked. |
| Invalid default recommendation | Both current valid checked alternatives required under equal conditions; failed/incomplete results have none. |
| Dependency drift / overstated completion | SDK and exact environment pinned; status docs replaced with explicit evidence gates. |
| Backend/UI provenance mismatch | Saved receipts drive labels/actions; configured status alone remains unverified; replays labeled. |
| Review-time approval gaps | Saved proposal/target/context, transactional review binding, immutable canonical investigation index, checked candidate and approval idempotency required. |
| Restart counter collision | Fresh process epoch prevents historical evidence becoming current after different edits reproduce counters. |
| Uncertain physical state retaining old result | Every physical availability change invalidates context and recomputes conservatively. |
| Misleading venue provenance | Four-zone model explicitly illustrative; no public plan was promoted to reviewed real geometry. |

Long decode, video, broad tool access and runtime skill mounting remain optional product expansions. The agreed production path is one still plus a fixed read-only numerical investigation; those optional capabilities were not silently added to cloud authority.

See [production-readiness.md](production-readiness.md) for operation, retention, limits and the remaining real-camera/physical release gates.
