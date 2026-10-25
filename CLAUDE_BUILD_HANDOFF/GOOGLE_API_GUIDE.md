# Argon and Managed Agents: build-prompt documentation pack

Verified 23 October 2026. This is a task-relevant source register and implementation briefing, not a claim to include the entire Google documentation corpus. New documentation was fetched with Firecrawl `maxAge=0`; existing same-session official snapshots were reused. No Gemini model requests were made. SDK compatibility, event-account access, model grounding accuracy, and latency remain to be established by implementation smoke tests.

## Required model and API distinction

| Capability | Direct model | Managed Antigravity agent |
|---|---|---|
| Published ID | `gemini-4-argon` | `antigravity-preview-09-2026` |
| Selecting Argon | `model="gemini-4-argon"` | `agent_config={"type":"antigravity","model":"gemini-4-argon"}` |
| Default model if config omitted | Explicit model required | Gemini 3.8 Flash, so never omit initial model selection |
| Inputs | Text, images, video, audio, PDF | Text and images only |
| Outputs | Text; supports schema-constrained JSON | Text and execution steps; no structured-output response schema |
| Client functions | Supported | Supported in stateful mode only |
| Live API | Unsupported | Do not imply native continuous Argon voice/video |
| Generation settings | Thinking low/medium/high; direct output limit supported | `temperature`, `top_p`, `top_k`, `stop_sequences`, `max_output_tokens` unsupported |
| Run budget | Normal direct model controls; keep proposals small | `agent_config.max_total_tokens`, best effort |
| MCP | Not needed for direct proposal | Remote Streamable HTTP supported; legacy SSE MCP unsupported |

Use direct Argon to interpret one captured board/photo frame into a small reviewed proposal. Use the managed Argon agent to investigate approved alternatives by requesting real local functions. Derive all numerical UI cards from checked tool results, never the agent's prose. Camera preview is a local stream; the AI core analyzes deliberately captured stills. Motor movement requires explicit approval and local confirmed-state handling; no raw motor-control tool is exposed to the cloud agent.

## Core implementation contracts

### Direct proposal

Python SDK is `google-genai` (`from google import genai`), not legacy `google-generativeai`. Interactions is the documented starting point. Typical request fields:

```python
interaction = client.interactions.create(
    model="gemini-4-argon",
    input=[
        {"type": "text", "text": bounded_prompt_with_entity_catalog},
        {"type": "image", "data": frame_base64, "mime_type": "image/jpeg"},
    ],
    generation_config={"thinking_level": "low"},
    response_format={
        "type": "text", "mime_type": "application/json", "schema": proposal_schema,
    },
)
# Parse complete interaction.output_text, then schema + semantic validation.
```

This is a documentation-derived integration sketch, not an executed request. Verify the pinned SDK accepts the supplied image representation before live use. URI input is an alternative documented representation. Encode exactly once. Restrict entity IDs to the current reviewed catalog. Require source revision, operation, candidates/abstention and concise evidence. Never infer real building dimensions, eligible egress, hidden doors or occupancy from a visual claim alone. Include orientation/pixel dimensions; normalized boxes use `[ymin,xmin,ymax,xmax]` on 0–1000, whereas polygon coordinates use `[x,y]`. Image boxes are not floor-plan meters. A tabletop homography/fiducial mapping is deterministic computer vision and must be described as such.

### Managed alternative investigation

```python
interaction = client.interactions.create(
    agent="antigravity-preview-09-2026",
    agent_config={
        "type": "antigravity", "model": "gemini-4-argon",
        "max_total_tokens": configured_run_budget,
    },
    environment="remote",
    input=bounded_investigation_prompt,
    tools=read_only_local_function_definitions,
)
```

Each function name is explicitly allowlisted. Arguments are validated locally; scope is immutable scenario revision plus approved alternative ID. Functions request evaluated evidence, not arbitrary code, SQL, serial bytes or motor motion. The local client executes the solver/checker when requested; remote Google environments cannot reach the laptop's `localhost` directly.

On `requires_action`, inspect `interaction.steps`. Pending calls are `function_call` steps whose `id` has no matching `function_result.call_id`. Execute only complete, validated arguments. Record the call once in a durable/idempotent ledger. Send `input=[{"type":"function_result","name":call.name,"call_id":call.id,"result":checked_result}]` with `previous_interaction_id=interaction.id` and `environment=interaction.environment_id`. Follow the pinned SDK's actual returned types. Preserve interaction and environment IDs across continuations. The guide resumes without restating initial agent config; prove Argon continuity rather than assuming model context from free text.

Suggested tools: `get_reviewed_scenario`, `evaluate_allowed_alternative`, `get_checked_comparison`. The evaluation result should include input/revision hash, run ID, validator verdict, conservation counts, boundary queues and any unresolved assumptions. No cloud function is the authority for accepted application state.

### Budget and lifecycle

`max_total_tokens` is an **agent config field**, not `generation_config.max_output_tokens`. It covers input, output and thinking while excluding cached tokens; it is best effort and can slightly overshoot between steps. Exhaustion returns `incomplete`, not `completed`. Continuation with previous interaction/environment receives a fresh budget; do not automatically chain paid continuations indefinitely.

The exact downloaded OpenAPI represents this property as `type: string, format: int64`, while the Python guide uses an integer and JavaScript examples use a string. Implement against a pinned `google-genai` version and its actual declared types/serialization. Do not copy the JavaScript representation into Python blindly. Record SDK version plus schema snapshot checksum in the live-check result.

Background mode is top-level `background=True` and requires stored interactions (`store=True`, default). A robust local orchestrator handles **all** published statuses: `in_progress`, `requires_action`, `completed`, `failed`, `cancelled`, `incomplete`. Polling until only completed/failed is insufficient: it can hang at a custom-function request or budget exhaustion. Implement deadlines, cancellation, bounded retries and explicit resume. Avoid freezing the UI while waiting. Do not call a saved fixture a live result.

For an optional saved managed agent, `client.agents.create` uses `base_agent="antigravity-preview-09-2026"`, Argon `agent_config`, `system_instruction`, tools and `base_environment`. Model selection is locked when the named agent is created; it cannot be overridden per interaction. Inline configuration is the smallest initial integration. Save a named agent only when justified by the event requirement or deployment needs.

### Streaming and displayed evidence

Interactions uses step events: `interaction.created`, `interaction.status_update`, `step.start`, `step.delta`, `step.stop`, `interaction.completed`. Text deltas have `delta.type="text"`; function argument fragments have `delta.type="arguments_delta"`. Assemble by step index/identity, handle interruptions, and execute nothing from partial arguments or JSON. Accumulated usage may be present on `step.stop`; do not sum cumulative usage repeatedly. Completed direct JSON must still pass schema and semantic validation.

Expose genuine stages and durable tool evidence: captured frame → proposed match → confirmation → evaluator call → checker verdict → comparison. Do not render a fixed timer as real progress or expose raw reasoning/thought traces. Never apply stale revision output. A valid JSON shape is not proof the selected entity is correct.

## Documentation manifest

All following snapshots are included under this portable package; the complete 21-source index is reference/GOOGLE_SOURCES.json. For a portable bundle, retain the canonical URL, acquisition date, publisher, and each source's license/footer. Google Developers pages state CC BY 4.0 for prose and Apache 2.0 for code unless otherwise noted. Preserve attribution when redistributing snapshots. The downloaded OpenAPI has no standalone license field; preserve its originating reference URL and site-policy attribution rather than inventing a license declaration.

| Canonical source | Cache | Read/verified purpose |
|---|---|---|
| https://ai.google.dev/gemini-api/docs/models/gemini-4-argon | `reference/google/argon-model.md` | Model capabilities, stable ID, unsupported Live, input/output modalities; footer 2026-10-14 |
| https://ai.google.dev/gemini-api/docs/latest-model | `reference/google/latest-model.md` | Argon controls, managed support, migration and introductory pricing; footer 2026-10-16 |
| https://ai.google.dev/gemini-api/docs/antigravity-agent | `reference/google/antigravity-agent.md` | Agent model selection, tools, custom-function continuation, budgets, limitations; footer 2026-10-16 |
| https://ai.google.dev/gemini-api/docs/interactions-overview | `reference/google/interactions-overview.md` | Interaction/steps resource, state, retention, guide discovery; footer 2026-10-15 |
| https://ai.google.dev/gemini-api/docs/structured-output | `reference/google/structured-output.md` | Direct schema shape, validation, streaming partial JSON; footer 2026-10-21 |
| https://ai.google.dev/gemini-api/docs/image-understanding | `reference/google/image-understanding.md` | Image input, normalized coordinates, image interpretation; footer 2026-09-23 |
| https://ai.google.dev/gemini-api/docs/robotics-spatial | `reference/google/robotics-spatial.md` | Prevent misattribution: examples use Robotics ER, not Argon; footer 2026-09-04 |
| https://ai.google.dev/gemini-api/docs/managed-agents-quickstart | `reference/google/managed-quickstart.md` | Fresh this turn; multi-turn state, environment reuse, streaming, saved agents; footer 2026-10-01 |
| https://ai.google.dev/gemini-api/docs/streaming | `reference/google/streaming.md` | Fresh this turn; exact step event layout and argument deltas; footer 2026-09-23 |
| https://ai.google.dev/gemini-api/docs/coding-agents | `reference/google/coding-agents.md` | Fresh this turn; official Docs MCP, current SDK, llms index/markdown endpoints; footer 2026-10-06 |
| https://ai.google.dev/api/interactions-api | `reference/google/interactions-reference.md` | Fresh this turn; full REST field reference, lifecycle statuses, OpenAPI link; footer 2026-10-22 |
| https://ai.google.dev/static/api/interactions.openapi.json | `reference/google/interactions.openapi.json` | Fresh downloaded exact JSON, parsed OpenAPI 3.0.3, 20 paths; includes interactions and agents, AntigravityAgentConfig |
| https://ai.google.dev/gemini-api/docs/custom-agents | `reference/google/custom-agents.md` | Fresh this turn; saved agent config/model lock and base environment; footer 2026-10-09 |
| https://ai.google.dev/gemini-api/docs/agent-environment | `reference/google/agent-environment.md` | Fresh this turn; environment sources, reuse/network configs; footer 2026-10-07 |

Additional official sources: function-calling, background execution, files, hooks, rate limits and troubleshooting are also included under reference/google/. The live index and SDK links remain remote references:

- https://ai.google.dev/gemini-api/docs/function-calling — full function-calling guide.
- https://ai.google.dev/gemini-api/docs/background-execution — background polling, streaming, cancellation.
- https://ai.google.dev/gemini-api/docs/agent-hooks — sandbox hooks; optional if remote side effects are introduced. Current core runs side-effect validation locally.
- https://ai.google.dev/gemini-api/docs/files — uploaded-image lifecycle if URI input chosen.
- https://ai.google.dev/gemini-api/docs/pricing — recheck before projecting a paid event budget; do not use generic Flash agent cost examples as an Argon estimate.
- https://ai.google.dev/gemini-api/docs/rate-limits — account-specific event throughput.
- https://ai.google.dev/gemini-api/docs/troubleshooting — errors and retries.
- https://googleapis.github.io/python-genai/ and https://github.com/googleapis/python-genai — official Python SDK docs/source, verify pinned release and Interactions types.
- https://ai.google.dev/gemini-api/docs/llms.txt — complete live Gemini documentation index, explicitly documented by coding-agents guide.
- https://ai.google.dev/static/api/interactions.md.txt — exact REST reference's machine-readable endpoint.
- For individual developer pages append `.md.txt`; this machine-readable pattern is officially documented, e.g. https://ai.google.dev/gemini-api/docs/coding-agents.md.txt .

Official Claude Code docs integration from Google's coding-agents guide:

```sh
claude mcp add --transport http geminiDocs https://gemini-api-docs-mcp.dev
```

Verify `/mcp`; tools are `gemini_search_docs` and `gemini_get_doc`. This documentation MCP is distinct from a production facility-tool MCP server. Do not install packages or modify global config merely to inspect a doc pack; users can choose project-scoped setup. Existing local Gemini skills may be older than these October docs. Fresh official schema and pinned SDK types win over stale skill examples.

## Mandatory live smoke-test order for Claude's implementation

1. **Offline contract check first:** pin SDK; verify import/version and Interactions surface; record model IDs/config; validate request construction against actual SDK types/OpenAPI. This is not proof of cloud access.
2. **Small direct Argon text call:** one bounded response using event credentials; log actual provider/model and status without logging secrets. Fail clearly on missing entitlement. Do not silently replace with Flash.
3. **Direct small structured call:** parse complete JSON into the typed proposal and check entity enums/revision; invalid semantic content is rejected.
4. **Captured still grounding:** one controlled image/catalog then a varied local set (similar features, occlusion, rotation, no matching feature). Manual selection remains available; abstention is a valid result. No calibrated confidence percentage without calibration.
5. **Managed Argon client function:** explicit initial Argon configuration; get one real pending custom-function step, run local read-only evaluator, return correctly matched result in same interaction/environment chain. Prove exactly-once handling with duplicate-call fixtures.
6. **Alternative comparison:** bounded approved alternatives on the same revision; UI obtains numbers from validated evaluator records. Confirm agent can truthfully report no improvement.
7. **Lifecycle controls:** requires_action, incomplete budget, failed, cancelled, timeout, stale revision and reconnect. No unbounded resumption. Record SDK vs wire budget representation.
8. **Streaming only after nonstreaming succeeds:** assemble text/arguments fully; test chunk boundaries/duplicate events and usage accounting with deterministic fake fixtures separate from live evidence.
9. **Hardware separated from agent:** approved predicted alternative → local motor command → switch confirmation → observed state revision → new checked plan/LED output. Stuck or contradictory switches retain unconfirmed state and do not publish observed improvement.
10. **Rehearse:** measure actual end-to-end timings and token usage; choose timeout/fallbacks from measurements. Record independent live run evidence vs offline tests/replays in separate artifacts.

No step above has been executed against the Gemini API in this research turn. Source snapshots establish documented support, not account-specific API availability or physical safety validation.


## Portable package additions

The source manifest adds pricing and six operational guides to the core table above. For raw API fields use reference/google/interactions.openapi.json. A field in a generic OpenAPI request does not establish model/agent support: the Antigravity guide explicitly disallows managed structured output even if a generic response_format field exists. The six operational snapshots do not override Argon-specific capability restrictions.
