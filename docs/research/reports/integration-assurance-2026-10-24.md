# Gemini 4 Argon integration assurance

Follow-up verification on 24 October 2026. The project's still-image grounding and managed numerical investigation are integrated through the public API and active UI. The physical board is not ready, so real-camera accuracy remains pending.

## Completed software workflow

| Step | Evidence |
|---|---|
| Capture image with original timestamp, dimensions, SHA-256 and full context | Browser metadata/export tests, strict API intake and live synthetic-image trial |
| Direct Argon returns a schema-validated proposal | Actual `gemini-4-argon` receipt, correct synthetic P2, no fixture substitution |
| Persist image and proposal evidence | Public capture endpoint returned exactly the original image/digest/context in the trial |
| Explicit review and Apply | Missing review rejected; saved proposal applied to isolated state; repeated/stale Apply rejected |
| Managed Argon investigates changed state | Actual model receipt and client-executed checked-comparison tool on the P2-blocked scenario |
| Checked candidates and evidence | Modeled crossings 60 for KEEP_CURRENT and 117 for OPEN_P3; full numerical runs persisted |
| Show progress, summary and tool ledger | Active UI consumes sanitized provider progress and exposes returned tool evidence |
| Cancel investigation | Server endpoint cancels the owning task, preserves canonical cancellation and checks original context; offline/API/browser regressions |
| Replay completed investigation | Saved result and original provider identity returned with replay label, without another model request |
| Handle stale/failure/no-benefit results | Backend and UI block recommendations/actions when evidence is not current or beneficial |
| Recover configuration after reconnect | SSE reconnect refreshes health flags without fetching an old scenario over newer state |

The trial's review was an automated test review of a synthetic board. It was not a human judge trial or a real physical capture. The computed numbers describe the illustrative synthetic model.

## Final verification

- **167 backend tests passed** in 3.66 seconds; outbound network and devices blocked, temporary SQLite. One existing Starlette/httpx TestClient deprecation warning remains.
- **13 frontend policy/client tests passed**; TypeScript and Vite production build passed.
- **49 managed tests** include delayed terminal writes, stale finalization, immediate cancellation and busy metadata claims. A late worker cannot publish canonical success after failure/cancellation.
- Dependency compatibility check passed for the exact 40-package Python environment.
- Isolated browser checks passed for reconnect, live/fixture/local labels, progress/cancel, no-benefit approval blocking, tool evidence, manual labels, capture export and mobile layout. These browser provider responses were mocked.
- **Real-provider public-API workflow passed**, with both responses reporting `gemini-4-argon`. The total trial took 71.53 seconds: direct grounding 14.39 seconds; managed investigation 56.99 seconds. These are observed samples, not a latency guarantee.
- **Zero hardware commands** in the isolated live workflow. The user's preview scenario and runtime database were not used for that trial.

Actual provider usage in this trial: direct 2,256 total tokens; managed 12,183 total tokens including 3,261 cached tokens. No estimated usage was substituted. Prior successful checks and failures remain in the earlier verification record.

## Reproduce

```sh
.venv/bin/python -m pytest tests -q
cd frontend
npm test
npm run build
```

From the repository root, with server-side credentials configured, opt into a potentially billed isolated API trial:

```sh
.venv/bin/python -m tools.verify_argon_http --live
```

It uses public JSON request/response contracts through an isolated ASGI HTTP transport, temporary SQLite and a hardware stub. It does not run against or alter the user's active backend. The default image is synthetic. Root module import is refused if the application was already loaded, preventing accidental use of an existing singleton database.

Private local receipt: `runtime/argon-http-live-check.json`.

```text
SHA-256: e77bb4c33a8cd28b5bb075cf826f5a1a01d5d671da97c1289863e3c10d541d5e
```

Mocked browser evidence and its reproducible harness are in `runtime/ai-ui-verification/`. The preview simulator snapshot was saved before restarting the backend with the final API routes.

## Corrections made during this recheck

Terminal persistence is now staged before an immutable publication transaction. Only the terminal transaction can make a result canonical, with current-context/deadline/cancellation validation under the authoritative state lock. Delayed writes cannot replace that decision. Initial ownership uses a short non-waiting SQLite claim before the first await, avoiding cancellation that leaves a late orphaned running row. Metadata commits disable lock waiting; filesystem I/O latency itself cannot be given a strict application cap.

The API revalidates current context after awaited canonical lookup and before publishing/indexing. Shutdown cancels owned work and closes both provider clients even if the lifespan consumer raises. UI approval matches the backend requirement for a positive checked OPEN_P3 recommendation. Provider progress and the explicit Cancel action use the client-owned investigation ID and its original context.

## Remaining physical validation

User confirmed the board is not ready. The build plan's twenty varied real-board captures, framing/calibration checks and actual physical bench observations remain pending. Software/provider success does not establish real-camera accuracy, approved venue geometry or actual gate behavior. Fixtures and local computations stay explicitly labeled and are disabled in production mode.

See [operation and release gates](production-readiness.md) and [earlier verification](verification-2026-10-24.md).
