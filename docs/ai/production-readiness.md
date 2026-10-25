# Argon integration: operation and verification

Updated 24 October 2026. This describes the hardened still-image and fixed-tool integration, not every optional Argon feature or certification of the illustrative venue/hardware.

## Install and verify offline

Use Python 3.13.11 and Node 25.2.1 for the recorded environment. `requirements.txt` pins the direct dependencies; `requirements.lock` records the exact tested Python environment, including transitive packages. The frontend uses `package-lock.json`.

```sh
uv venv --python 3.13 .venv
uv pip sync --python .venv/bin/python requirements.lock
.venv/bin/python -m pytest tests -q
cd frontend
npm ci
npm test
npm run build
```

The test harness blocks outbound sockets, blanks provider/serial configuration, and assigns temporary databases. Tests do not contact Gemini or a physical device. Actual SDK 2.33.0 serialization, typed responses, errors and retry counts are exercised with mocked HTTP. Frontend policy/client tests use Node's built-in test runner; the current recorded command uses native TypeScript stripping.

## Configuration and execution modes

Export `GEMINI_API_KEY` into the backend environment using your normal secret manager or shell setup. Do not put it in frontend variables, tracked files, commands committed to scripts, or evidence. `.env` is gitignored and **is loaded at startup** (`backend/app/env_file.py`): only this app's keys are read (`GEMINI_API_KEY`, `SERIAL_PORT`, `SERIAL_BAUD`, `HOST`, `PORT`, `SPATIALTWIN_*`), values already in the process environment win, and `SPATIALTWIN_ENV_FILE=` (empty) disables loading. For production, prefer the process environment from your secret manager over a file.

```sh
export SPATIALTWIN_MODE=production
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

This remains a local workstation application. Authenticate and terminate TLS at an appropriate access-controlled boundary before exposing it outside the workstation; this change does not deploy a public service. `SPATIALTWIN_ORIGINS` is an explicit comma-separated browser origin allowlist. The default allows only localhost development/presentation origins. CORS is not an authentication mechanism.

| Mode/outcome | Evidence and behavior |
|---|---|
| Live completed grounding | A real provider receipt, validated completed schema and current capture produce a proposal. UI displays the live result receipt. |
| Live failed/unavailable/timed out/cancelled | No applicable proposal or successful recommendation. Diagnostic codes remain visible; there is no fixture/local substitution. |
| Fixture grounding | Explicit operator selection and `mode=fixture`; source is visibly fixture, usage empty. Disabled in production. |
| Local investigation | Explicit `mode=local`; only fixed numerical tools run. No provider identity or invented tokens. Disabled in production. |
| Replayed investigation | Same completed investigation ID returns its saved result with `replayed=true`. Original provenance is retained; no fresh provider call is implied. |
| Configured client | `/health` reports configuration only. It never certifies account/model access merely because a key exists. Verification is per execution receipt. |

For failed direct attempts, provenance describes the attempted live path; successful execution additionally requires completed status, no errors and a valid receipt/proposal. Do not treat a `live` provenance value on a failed result as success. Managed failures preserve received provider identities/usage when available. Missing usage remains unknown rather than zero estimated usage.

## Capture, proposal and review contracts

`POST /api/scenarios/facility-demo/grounding` requires an original `capture_id`, timestamp with timezone, pixel dimensions, full `source_context`, source kind, image and thinking level. Fixture mode instead requires an explicit supported fixture target and no camera bytes. The source context includes geometry/scenario/physical/parameter revisions, solver version, process-session epoch and canonical hash. Camera timestamps/dimensions are captured by the browser at the actual snapshot, not manufactured at server receipt.

JPEGs are size/dimension/decode checked; source digests are verified. Live captures must be no more than 120 seconds old or 5 seconds in the future. The direct model receives the reviewed target catalog and a strict JSON schema. JSON/semantic checks reject unknown fields/operations/candidates, duplicate keys/IDs, invalid selected type/ID pairs, invalid abstention fields and unordered/out-of-range boxes. A failed live request never becomes a positive fixture.

SQLite retains capture-time metadata and image bytes, result provenance and saved `proposal_id`. Apply requires that saved proposal, explicit review, matching selected target and full current context. A command event and its proposal-review ID are committed together. Live capture freshness is checked again at Apply, so an old unreviewed image cannot remain applicable indefinitely. Capture IDs cannot be overwritten, and a proposal cannot be reviewed twice. Each process restart starts a new authoritative session and an UNKNOWN physical state; prior evidence stays historical and cannot become current when revision counters repeat. The illustrative scenario begins at baseline after restart; this change does not restore an old live scenario automatically. Manual canonical selection remains explicit and separate from model evidence.

Runtime SQLite contains images and interaction evidence. Keep `runtime/` private and untracked, apply your own retention/backup policy, and delete data only when its review/audit record is no longer needed. No provider key is retained there. Both direct and managed calls explicitly request provider-stored interactions to retain receipts/state. Google documents paid retention of 55 days (configurable 7/14/28/55) and free retention of one day; confirm account settings. Provider retention is separate; local deletion does not delete them.

## Managed orchestration and authority

Only `get_reviewed_scenario`, `evaluate_allowed_alternative` and `get_checked_comparison` are available. They are read-only and accept strict arguments. P3 remains an internal reserve connection; it does not create boundary capacity. There are no serial, motor, host-shell or arbitrary-code cloud tools.

The async loop polls stored background interactions, correlates pending call IDs, reuses the returned environment, and handles every lifecycle outcome. A durable SQLite claim precedes a tool's worker. Completed duplicate calls reuse evidence; uncertain execution after a crash is not retried. Numerical request IDs also cache the original checked run. Four unique calls and four continuations are separate caps. The initial 20,000-token best-effort provider allowance is reduced by measured cumulative uncached usage for continuations. Provider retries are disabled through the tested per-instance SDK workaround; request-count regressions guard SDK upgrades.

Monotonic deadlines include provider, polling, ledger and tool waits. Provider cancellation is bounded and best effort; unconfirmed cancellation is explicit. A Python CPU worker cannot be forcibly killed after timeout. Such a worker may finish its already claimed read-only computation, but cannot replace a failed/timed-out investigation with a recommendation.

Recommendations require completed execution and both current, publishable, population-conserving results under equal population/horizon/time step. Missing, stale, failed or inconsistent evidence cannot win by defaulting the other alternative to zero. Model prose never supplies numerical values.

Gate approval is a separate operator transaction. The backend requires full current context, saved completed investigation, checked improved OPEN_P3 run ID and a unique approval submission key. Request acceptance/ACK and endpoint observation remain separate. A change to transit/unknown/fault invalidates the old physical revision and recomputes with P3 unavailable. No physical hardware was moved by this verification work.

## Opt-in live smoke check

With credentials already exported:

```sh
.venv/bin/python -m tools.verify_argon --live
```

This makes potentially billed direct and managed requests, limits direct work to 30 seconds and managed work to 60 seconds (also the default investigation allowance, selected after a measured 39.9-second live run), and disables automatic retries. It uses isolated temporary state, never imports/starts the hardware bridge, and writes sanitized results to `runtime/argon-live-check.json`. The default image is a synthetic labeled test board. It verifies the provider path, not real-camera performance. Use `--image /absolute/path/to/reviewed-board.jpg` for a reviewed actual capture and `--output` to retain a separate receipt.

Inspect status, diagnostic codes, actual model/interaction identity, tool ledger, usage and timings. A configured client or mocked test pass does not pass this gate. A successful synthetic-image result does not pass the build plan's 20-varied-real-capture trial. Keep fixture, synthetic live-provider, real-camera, replay and physical bench evidence distinct.

## Release gates

- Offline backend, frontend tests/build and isolated browser status/error/staleness checks pass.
- Successful real direct and managed receipts establish account access and expected tool continuation; the recorded synthetic live checks passed. Real-image performance remains a separate gate. See verification-2026-10-24.md.
- Twenty varied real board captures record correct/corrected/abstained outcomes, malformed/ambiguous/occluded cases and actual latency.
- Review independent numerical checker and actual physical bench evidence separately. This AI integration does not certify a real building's egress plan or mechanical assembly.
- Optional video/long-decode/search/runtime-skill expansion requires its own product scope and validation. It is not necessary for the agreed still-image/read-only-tool demonstrator.

The UI polls `GET /api/scenarios/facility-demo/investigations/{id}/progress` while analysis is active. `POST` to the matching `/cancel` endpoint with the original `expected_context` requests cancellation of that owning job, even if the scenario has since changed. Repeated cancellation requests do not interrupt terminal persistence again. A transport abort alone is not a cancellation receipt. Completed summaries, sanitized lifecycle events and allowlisted tool details remain inspectable. Capture metadata/image/digest can be retrieved from `/captures/{capture_id}`; the UI export includes the held original image and metadata.

For a full public-API-to-provider trial with isolated state and hardware disabled, run `.venv/bin/python -m tools.verify_argon_http --live`. It verifies capture, saved review/Apply, managed investigation, run retrieval, replay, stale rejection and production fixture blocking. See [latest integration assurance](integration-assurance-2026-10-24.md) for the recorded result and final regression counts.

See [grounding.md](grounding.md), [managed.md](managed.md) and the dated [audit](../research/2026-10-24-argon-venue-audit.md). The audit is a historical baseline; it is not overwritten to conceal defects found before this implementation.
