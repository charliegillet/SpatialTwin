# Direct Argon image grounding

The adapter uses `google-genai==2.33.0` and `await client.aio.interactions.create(model="gemini-4-argon", ...)`. It proposes a scenario change; it never accepts a change, solves routes or controls hardware. Account access and grounding accuracy still require authorized live evidence. The production-path tests use mocked HTTP, not the Google service.

## Capture and result boundary

`interpret_capture(capture, context, force_target=None, thinking_level="low", deadline_seconds=20.0)` returns `GroundingResult`. A successful result contains a proposal, explicit `live` or `fixture` provenance, provider identity/usage where available, SDK version and measured local latency. Failed, unavailable, timed-out or cancelled results contain **no proposal**. Missing configuration, invalid images and provider failures never manufacture a matched fixture.

Live interpretation requires:

- A `tabletop_camera` or `annotated_plan` source, a full `source_context` equal to the supplied current context, and matching source geometry/scenario/physical revisions. Parameters, solver version and canonical context hash are included in full-context matching.
- An actual ISO timestamp with a timezone, no more than 120 seconds old and no more than 5 seconds in the future. Freshness is rechecked before returning a successful proposal. The API owner checks against the latest accepted context again after the asynchronous operation.
- Strict base64 containing a complete JPEG, at most 5 MiB decoded, at most 16 million pixels and no dimension above 8192 pixels. Pillow verifies and fully decodes the image off the event loop. Encoded dimensions must equal the capture dimensions. If `image_sha256` is supplied, it must match the decoded image bytes.

A capture's notes do not select a target or determine a live answer. Camera preview is local video; Argon receives one captured still. Bounding boxes describe that image, not physical board or building dimensions.

Fixtures require an explicit `force_target` in `P1`, `P2`, `B2`, `ambiguous`, or `no_match`, plus `source_kind="fixture"`. Unknown or empty targets fail instead of defaulting to P2. Fixtures validate source revisions but may retain historical fixture timestamps, since they do not claim fresh physical observation. They state that no image perception occurred. The API additionally gates fixture mode; the adapter does not infer fixture mode from missing credentials or image data.

## Actual SDK request shape

The schema is generated from the adapter's strict `_GroundingOutput` Pydantic model. The pinned SDK converts the content list below into a `user_input` step on the wire; offline tests inspect the resulting HTTP JSON.

```python
interaction = await client.aio.interactions.create(
    model="gemini-4-argon",
    system_instruction=GROUNDING_SYSTEM_INSTRUCTION,
    input=[
        {"type": "text", "text": source_context_and_reviewed_catalog_json},
        {"type": "image", "data": validated_jpeg_base64, "mime_type": "image/jpeg"},
    ],
    generation_config={"thinking_level": "low", "max_output_tokens": 8192},
    response_format={
        "type": "text",
        "mime_type": "application/json",
        "schema": _GroundingOutput.model_json_schema(),
    },
    store=True,
    stream=False,
    timeout=remaining_deadline_seconds,
)
```

The adapter applies an outer asynchronous deadline to image validation and provider waiting. Supported deadlines are positive finite values up to 60 seconds; nonpositive values immediately return `timed_out`. HTTP retries are disabled. In pinned SDK 2.33, `HttpRetryOptions.attempts` is normalized by the parent client and then misinterpreted as a retry count by Interactions. The adapter explicitly sets the cached async Interactions resource's retry strategy to `none`; this is a per-client compatibility adjustment, not a global SDK patch. Mocked 429, 503 and transport-timeout tests verify exactly one HTTP request. There is no automatic polling, provider continuation, model substitution or fallback request. This output budget is deliberately bounded for a short perception proposal; truncation produces a failed result instead of accepting partial JSON. Low/medium/high thinking are explicit choices; unsupported settings fail locally. The application must await `adapter.aclose()` at shutdown to close both SDK transports.

Only `completed` interactions may produce a proposal. If returned, the model must match `gemini-4-argon`. A provider interaction ID is required and retained exactly as an opaque string: long/base64/padded IDs are accepted, with a 16,384-character bound and control characters rejected. Noncompleted statuses, provider errors and unexpected tool/unknown steps cannot publish. Provider cancellation and local cancellation return `cancelled`; deadline expiry returns `timed_out`. Typed SDK `Usage` fields are converted to a bounded allowlist of nonnegative integer token counts, rather than accessed as a dictionary. Returned model/usage metadata is retained even when the interaction ID is missing; such a response still yields no proposal.

### Provider-side storage and retention

Direct calls explicitly use `store=True`, the documented default for Interactions observability and retrieval of stored requests/responses. The source image, prompt and result are therefore stored by Google under the project's policy, in addition to the application's local evidence records. The [official retention guide](https://ai.google.dev/gemini-api/docs/interactions-overview#data-storage-retention) states 55 days for paid-tier interactions (configurable in AI Studio to 7, 14, 28 or 55 days), and 1 day for free-tier interactions. Stored interactions can be deleted through the provider API or AI Studio; this adapter does not delete evidence automatically.

`store=False` opts out of interaction storage and prevents chaining, but the documentation reviewed does not explicitly promise or prohibit an interaction ID in a stateless response. SDK 2.33 represents missing IDs as an empty string. The adapter requests stored mode to support durable provider receipts and still fails closed if no ID is returned; it does not fabricate an ID or treat model/usage metadata alone as a completed, reviewable proposal.

## Strict output and semantics

Every response must include exactly these fields; extra or missing fields fail:

```json
{
  "status": "matched",
  "candidate_ids": ["portal:P2"],
  "selected_entity_type": "portal",
  "selected_entity_id": "P2",
  "operation": "SET_UNAVAILABLE",
  "evidence": "Circular token overlaps the printed T_P2 pad.",
  "box_2d": [200, 600, 320, 720]
}
```

- The only typed candidates are `portal:P1`, `portal:P2` and `boundary:B2`; duplicates and unknown candidates fail.
- A matched selection must be a valid type/ID pair and must occur in its candidate list. Ambiguous/no-match outputs must have both selection fields null. No-match must have no candidates.
- `operation` must already equal `SET_UNAVAILABLE`. The adapter does not rewrite an unauthorized operation or convert invalid output into ambiguity.
- Evidence must be a nonblank string of at most 1000 characters.
- A nonnull box must contain exactly four **integers** within 0–1000 in `[ymin,xmin,ymax,xmax]` order, with positive width and height. Strings, floats, booleans and inverted/empty boxes fail. A box may be null when not supplied by the model.
- Malformed/truncated JSON, duplicate object keys and non-JSON numeric constants fail. The complete textual result is limited to 16,384 characters.

A valid JSON shape cannot establish that the visual selection is correct. Human review remains required before applying the proposal. Image instructions are explicitly treated as untrusted content. No visual output may invent measured dimensions, real occupancy or additional exits.

## Error and evidence handling

Errors are application-owned codes such as `configuration_missing`, `stale_capture`, `invalid_capture_image`, `capture_dimension_mismatch`, `invalid_provider_output`, `provider_model_mismatch` and `provider_status_not_completed`. Typed SDK HTTP codes produce `provider_access_denied` (401/403), `provider_rate_limited` (429), `provider_request_rejected` (400/404/409/422), `provider_unavailable` (other 5xx), or `provider_timeout` (408/504). The pinned Interactions SDK wraps transport timeouts in its typed `APITimeoutError`; this also produces `timed_out` with `provider_timeout`. Cancellation produces `provider_cancelled`, and unknown failures retain `provider_failure`. Provider exception text, API keys, payloads and raw error bodies are not logged or returned. A configured client means configuration exists, not that a real account is entitled to the requested model.

The API owner persists the capture and returned proposal separately, assigns the proposal ID and requires current explicit review before acceptance. No proposal is returned on failure. Local manual selection remains the separate recovery path.

## Verification and limits

Run the offline suite with:

```sh
.venv/bin/python -m pytest tests/ai_contracts/test_grounding.py tests/ai_contracts/test_grounding_production.py -q
```

The production tests exercise actual SDK 2.33.0 serialization and typed response handling through mocked async HTTP, with real sockets and synchronous HTTP blocked. They cover schema transmission, model/status/receipt checks, invalid fields and boxes, duplicate/partial JSON, stale captures, full context changes, corrupt images, dimensions/hash mismatch, missing configuration, explicit fixtures, cancellation and a short deadline while the event loop remains responsive.

Not established by these tests: live account/model access, actual image-grounding accuracy, provider latency/billing, twenty varied fresh-camera trials or physical-device validation. Those require separately authorized provider and bench evidence and must remain distinct from these offline tests.

Official references (current source snapshots are cached under `.firecrawl/argon-*`):

- [Structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [Argon capabilities](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon)
- [Image understanding](https://ai.google.dev/gemini-api/docs/image-understanding)
- [Interactions reference](https://ai.google.dev/api/interactions-api)
- [Python SDK](https://github.com/googleapis/python-genai)

The repository's earlier handoff and installed Gemini skills contain older examples. The verified SDK request/response surface and current official documentation take precedence over those examples.
