# Gemini 4 Argon and Managed (Antigravity) Agents: capabilities WalkTwin could use

Scope: what the docs say Argon and the Antigravity managed agent can do, with exact API shapes and limits, and for each one a concrete WalkTwin use or an honest "adds nothing". Researched 25 October 2026.

Source handling:
- Live official pages were fetched today as `.md.txt` (ai.google.dev). Local snapshots dated 23 October are in `CLAUDE_BUILD_HANDOFF/reference/google/`. Where the two differ, that is noted.
- Nothing here was run against the API. Everything is **documented** support, not **verified in practice**, and nothing establishes what the team's account can access.
- Items marked [secondary] are not from Google.
- Several official pages contradict each other (agentic video models, Maps grounding models, saved-agent models). The Task 2 live probe has to settle each one.

---

## 1. Agentic video understanding (`processing: "agentic"`)

### Takeaway
Agentic mode lets the model move around the video timeline itself, loading transcript, frames or audio on demand at a frame rate and resolution it chooses. You cannot direct it: no fps, clipping or seek parameters, and the steps it reports are opaque. Timestamps are only as good as the prompt and schema make them. For WalkTwin's 90–150 s clips the docs say static mode is the usual choice, so the "agentic beats static" benchmark could come out flat. The strongest Argon-specific moves are (a) keeping the whole video in context across critique turns with `previous_interaction_id`, and (b) mixing an agentic full-video part with static, clipped, high-fps "zoom" parts in one request.

### Cited Findings
- What it does: "the model dynamically explores the video timeline, selectively inspecting transcripts and adaptively adjusting frame rates and resolution on the fly based on the prompt." Static (the default) extracts frames at 1 FPS in one pass. — [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding#agentic-video-understanding)
- Claimed gains: agentic is "Up to 88% more token-efficient and ~7% higher quality on long-form content." — [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding#agentic-video-understanding)
- Guidance: use agentic for long-form video or queries about specific moments. Use static for "Latency-sensitive queries on short clips (under 5 minutes), or cases where frame-level precision across the entire clip is needed." On clips under 5 minutes, navigation "may slightly increase Time to First Token". — [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding#technical-details-about-videos)
- **Model support conflict.** The live video page lists agentic support only for Gemini 3.8 Flash, 3.6 Flash and 3.5 Flash Lite; its technical-details section adds "and later models". The Argon model page says "Agentic video understanding: Supported (defaults to `static`)". The "What's new" page says agentic video understanding "is now generally available". — [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding); [Argon model page](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon); [Latest model](https://ai.google.dev/gemini-api/docs/latest-model)
- Wire shape: in the OpenAPI, `VideoContent.processing` is either the string enum `"static" | "agentic"` or a `StaticMediaProcessing` object `{"type":"static","fps":<double>,"start_offset":"10.5s","end_offset":"30s"}`. There is **no object form for agentic**. `VideoContent` also has `resolution` (`low|medium|high|ultra_high`), `uri`/`data`, `mime_type`, and `name`, which is described as "A user-defined name for this content block. Can be referenced by the model in the final response." — [interactions.openapi.json](https://ai.google.dev/static/api/interactions.openapi.json) (local copy `reference/google/interactions.openapi.json`)
- Clipping (`start_offset`/`end_offset`) and custom `fps` "are only supported when processing the video in `static` mode." — [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding#customize-video-processing)
- Different videos in one request can use different processing modes ("Mix processing modes across videos"). — [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding#mix-processing-modes-across-videos)
- Trace: agentic adds `processing_call` (with `id`) and `processing_result` (with `call_id`) steps, interleaved with `thought` steps when summaries are on. In the schema these steps carry only `id`/`call_id` and an opaque `signature`, not which segment or frames were loaded. "They can be used to show a progress trace in your UI." To confirm agentic ran, check for these steps. — [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding#response-steps); [OpenAPI ProcessingCallStep](https://ai.google.dev/static/api/interactions.openapi.json)
- Thought summaries are turned on with `generation_config.thinking_summaries: "auto"`. The doc example shows summaries such as "Loading visual frames to verify slide content...". — [OpenAPI GenerationConfig](https://ai.google.dev/static/api/interactions.openapi.json); [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding#response-steps)
- Multi-turn: "Video context is preserved across turns." In stateful mode (`previous_interaction_id`) "The server retains the video context. No additional handling is needed." — [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding#multi-turn-video-conversations)
- Timestamps: prompts can refer to moments as `MM:SS`. In static mode "Timestamps are added every second." No structured timestamp-citation feature is documented; timestamps come back only if the prompt or schema asks for them. — [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding#refer-to-timestamps-in-the-content)
- Limits:
  - With a 1M context, video up to 3 hours at low media resolution or 1 hour at high.
  - Static tokens: 258 per frame (66 at low resolution) plus 32/s of audio. About 100 tokens per second at default/low resolution, about 300 per second at high.
  - Agentic tokens are reported as `total_thought_tokens` (navigation) plus `total_tool_use_tokens` (loaded media).
  - Supported formats include `video/mp4`, `video/mov`, `video/webm` and `video/3gpp`.
  - — [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding#technical-details-about-videos)
- Transport: use the Files API above 20 MB or for reuse. Files API: 2 GB per file, 20 GB per project, files deleted after 48 hours. Use `background=True` or streaming for long agentic runs; synchronous requests can surface as `401` or timeouts. — [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding); [Files](https://ai.google.dev/gemini-api/docs/files) (local `reference/google/files.md`)
- Prompt placement: put the text prompt after the video part. — [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding#technical-details-about-videos)

### Inferences
- **Critique on top of the extraction interaction (strongest change).** Today Task 11 sends at most 8 (frame, render) pairs to a fresh call. Instead, chain each critique turn with `previous_interaction_id=<extraction id>` so Argon still has the whole walkthrough while it looks at the new renders. The claim becomes "Argon compares its render against the entire video, not 8 stills." That fits PS2 and "1M unified context" much better.
  - Unknowns to probe: whether chained turns re-bill the video context, and how they interact with implicit caching.
  - This is a design change to Task 11. The plan forbids changing the plan, so it is offered as a suggestion only.
- **Targeted "zoom" with mixed modes.** When the critique flags a door (say D3 seen at [41 s, 46 s]), send the full walkthrough as `"agentic"` plus a second part from the same file URI with `{"type":"static","start_offset":"40s","end_offset":"47s","fps":5}` and `resolution:"high"`, named `door_D3_zoom`. This is the only documented way to force a seek and zoom. It is controllable and easy to show on screen. Whether one URI can appear twice in a request is unverified.
- **Show the real trace.** Count `processing_call` steps and stream thought summaries into the extraction progress panel. That is honest, live evidence of agentic navigation, not a fixed timer. The trace does not show *which* frames were loaded, so don't claim it does.
- **Benchmark risk.** Google's own guidance favours static for clips under 5 minutes. The static vs agentic comparison in Task 12 may show no gain, or a loss, on 90–150 s walkthroughs.
  - Add a third baseline: static at 2–4 fps with `resolution:"high"`. By my arithmetic, 150 s × 4 fps × 258 ≈ 155K tokens plus audio, which a 1M context handles easily.
  - Report whatever comes out. A flat result reported honestly still scores on the "real verification loop" criterion.
- **Timestamp evidence has to be schema-enforced** (it already is: `[start_s, end_s]` per door). Validate locally that each interval lies inside the video duration, and show the cited frame next to each claim so judges can check it themselves.
- **1M context as a real differentiator.** One walkthrough is only about 15–45K tokens, so "1M context" is weak for a single clip. It becomes real if one request holds several things at once: the walkthrough, a second pass (walk in, walk back), every earlier iteration's renders and discrepancies (which also counters Review Focus #3 oscillation), and the graph JSON.
- **Plan fix.** Task 9 uses `thinking_level:"high"` with `max_output_tokens:32768`. `max_output_tokens` covers thinking plus output, and running out returns `incomplete` with possibly empty text. Since the call is already `background=True`, raise it to 65,536 or more; see section 2.

### Gaps
- Whether Argon specifically accepts `"agentic"` (the docs conflict). Only the Task 2 probe settles it.
- No documented control over agentic zoom or seek, the maximum agentic duration, or agentic latency for 2-minute clips.
- No published timestamp accuracy for Argon.
- Whether the same file URI can appear twice in one input array, with different processing, is undocumented.
- Billing for video context retained across stateful turns is not documented.

---

## 2. Long decode (up to 1M output tokens) and one-pass world generation

### Takeaway
Long decode is real but slow, and WalkTwin's live path doesn't need it. A three.js twin is tens of thousands of tokens at most, well under the 64K synchronous cap. Google's own example shows the first 64K tokens take about 10 minutes. The on-theme PS2 move is not a 1M-token output. It is having Argon *make* part of what gets rendered (scene code or a floorplan SVG), so the loop "renders what it made". The egress geometry should stay deterministic from the graph.

### Cited Findings
- Limits: max output is 65,536 synchronous, or up to 1,048,576 with long decode. The context window is unified at 1,048,576 tokens. — [Argon model page](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon)
- Mechanics: needs `background: true` and `max_output_tokens` > 65,536. The server generates 64K "hops", and each hop adds a `model_output` step, so the client joins them. `background:false` with `max_output_tokens` > 65,536 returns a 400 error. — [Long decode](https://ai.google.dev/gemini-api/docs/long-decode)
- Background long decode can run for up to 24 hours. Client-side continuation is GenerateContent-only, 20 minutes. — [Long decode](https://ai.google.dev/gemini-api/docs/long-decode#choose-how-to-run-long-decode)
- Speed: when streaming, "After the first 64K tokens (about the first 10 minutes), the stream sends output in chunks of about 5,000 tokens." Set HTTP read timeouts to 15–20 minutes per stream. — [Long decode](https://ai.google.dev/gemini-api/docs/long-decode#stream-long-decode)
- When to use it: yes for hard math and science and "The hardest coding and agentic tasks". No for extraction, latency-sensitive requests, or "Agents that call tools in many short turns". "Most coding and agentic tasks finish under 64K." — [Long decode](https://ai.google.dev/gemini-api/docs/long-decode#when-to-use-long-decode)
- Statuses: `incomplete` means `max_output_tokens` was used up, and "Text can be empty if the model was still thinking." `total_input_tokens` sums every hop's input, so it overstates context size. Every hop is billed; repeated hop input gets the 95% implicit-cache discount. — [Long decode](https://ai.google.dev/gemini-api/docs/long-decode#background-status)
- Thinking levels are `low`, `medium` (default) and `high`. `max_output_tokens` is a hard cap on thinking plus output. Google recommends at least 32,768 and says to lower `thinking_level` to save tokens instead of shrinking the cap. Sampling parameters are ignored. Explicit caching is unsupported; implicit caching applies at ≥4,096 tokens with a 95% discount. — [Latest model](https://ai.google.dev/gemini-api/docs/latest-model)
- Price: introductory $2 per 1M input and $10 per 1M output (thinking included) through 30 November 2026. Not on the free tier. — [Latest model](https://ai.google.dev/gemini-api/docs/latest-model#pricing)
- PS2 framing, from the user's brief: Argon "can generate high-fidelity 3D games and procedural worlds in one pass". The task is to build a system that "renders what it made, watches the result, critiques it against the goal, and fixes it in a loop." (Not independently fetched; the participant guide is not public.)
- Google's 3D guide credits Argon's 3D ability to "Long-horizon autonomy" with a 1M context and output window, "Native multimodality" (including looking at "its own rendered screenshots"), and spatial and mathematical reasoning. Its quickstart prompt is a three.js black hole. — [AI Studio 3D guide](https://aistudio.google.com/learn/building-3d-games-and-worlds-with-gemini-4-argon); [Latest model quickstart](https://ai.google.dev/gemini-api/docs/latest-model#quickstart)

### Inferences
- **Hybrid twin (recommended).** Keep `buildScene(graph)` deterministic for the structural shell: floors, walls, door gaps and exits are what the solver uses. Add one Argon call that, after extraction, writes a sandboxed `dressing` module (furniture blocks, materials, lighting colour from the video) in one synchronous pass under 64K tokens. The renderer runs both. The critique then judges geometry Argon made, which matches "renders what it made".
  - Load the dressing in an iframe or a restricted loader, with no network and a timeout.
  - Dressing must never feed the solver.
- **Floorplan-first variant** (from Google's Workflow 6; see section 5). Have Argon draw a top-down SVG floorplan in meters from the video. Render the graph's top-down orthographic view and have Argon critique graph against floorplan against frames. This is cheap, demo-friendly, and it is Google's own recommended pattern for multi-room interiors.
- **Long decode itself:** an honest "adds nothing" for the live demo. 10+ minutes per 64K of output doesn't fit a 3-minute pitch or the 50% live-demo criterion. At most, run one labelled, offline "Argon one-pass procedural twin" (for example `max_output_tokens: 131072`, `thinking_level: "high"`) as a side artifact, shown as a saved run, to tick the long-decode box. Don't let it gate anything.
- **Practical use of the background flag:** with `background=True` already set for extraction and critique, raising `max_output_tokens` to 65,536–131,072 costs nothing unless it is used. It protects against `incomplete` when high thinking eats the 32K cap.

### Gaps
- No Argon tokens-per-second figure beyond the "about 10 minutes for the first 64K" streaming note.
- No published measure of three.js one-pass quality or token counts for interiors.
- The AI Studio guide's showcase apps were not individually inspected.

---

## 3. Managed Antigravity agent

### Takeaway
The managed agent is much more than a function-calling wrapper. It gets a 4-CPU / 16 GB Ubuntu sandbox with code execution, a persistent filesystem, mounted sources (Git, GCS, inline), env vars and credentials, network allowlists or a fully disabled network, synchronous pre- and post-tool hooks, `AGENTS.md` and skills, saved agents with a `base_environment`, triggers, background runs and streaming. One interaction can mix the agent's own `code_execution` with client-executed custom functions.

The plan as written uses almost none of this: text-only input, two client tools, a 20K-token budget. That reads as a thin wrapper. The plan also says the agent takes text only, but the docs allow text **and images** (inline base64).

### Cited Findings

**Basics and limits**
- What it is: a general-purpose agent that "reasons, executes code, manages files, and browses the web inside your own secure Linux sandbox". The default model is Gemini 3.8 Flash; Argon is chosen with `agent_config={"type":"antigravity","model":"gemini-4-argon"}`. — [Antigravity agent](https://ai.google.dev/gemini-api/docs/antigravity-agent)
- Default tools: `code_execution` (bash, Python, Node, with stdout and stderr), `google_search` and `url_context`. Filesystem tools come automatically with `environment`. You can add custom `function` and `mcp_server` tools. Passing `tools` replaces the default set. — [Antigravity agent: Supported tools](https://ai.google.dev/gemini-api/docs/antigravity-agent#supported-tools)
- Multimodal input: "Currently, only `text` and `image` inputs are supported. Images must be supplied as inline base64-encoded strings". Audio, video and documents are not supported. — [Antigravity agent: Multimodal Input](https://ai.google.dev/gemini-api/docs/antigravity-agent#multimodal-input); [Limitations](https://ai.google.dev/gemini-api/docs/antigravity-agent#limitations)
- Not supported in the agent: structured outputs, `file_search`, `computer_use` and `google_maps`. `temperature`, `top_p`, `top_k`, `stop_sequences` and `max_output_tokens` return 400. — [Antigravity agent: Limitations](https://ai.google.dev/gemini-api/docs/antigravity-agent#limitations)

**Code execution together with client-executed tools**
- The official example passes `tools=[{"type":"code_execution"}, get_weather_tool]` in one interaction. On `requires_action` the client finds `function_call` steps with no matching `function_result.call_id`, runs them, and continues with `previous_interaction_id` and `environment=interaction.environment_id`.
- Doc comment: "Filesystem tools (like write_to_file) are also represented as function calls but are executed automatically by the environment." Function calling works in stateful mode only.
- — [Antigravity agent: Function calling](https://ai.google.dev/gemini-api/docs/antigravity-agent#function-calling)

**Environment (sandbox)**
- `environment` takes `"remote"` (fresh), `"env_..."` (reuse, keeping files and state), or a config object. — [Antigravity agent: Environments](https://ai.google.dev/gemini-api/docs/antigravity-agent#environments)
- Sources: `repository` (Git, 500 MB), `gcs` (2 GB), `inline` (1 MB per file, 2 MB total). You can't mount at `/`. — [Agent environment](https://ai.google.dev/gemini-api/docs/agent-environment#mount-from-a-source)
- Pre-installed: Ubuntu, Python 3.12 (numpy, pandas, requests, google-genai, bs4, pyyaml), Node.js 22 (create-vite, typescript), git, curl, jq and the gcloud CLI. `pip install` and `npm install` work, and packages persist when the `environment_id` is reused. — [Agent environment: Pre-installed software](https://ai.google.dev/gemini-api/docs/agent-environment#pre-installed-software)
- Network:
  - Outbound is unrestricted by default.
  - `network.allowlist` takes `[{domain, credential?, transform?}]`.
  - `network: "disabled"` blocks all egress.
  - `env` sets variables, either literals or `{"credential": id}`.
  - — [Agent environment: Network configuration](https://ai.google.dev/gemini-api/docs/agent-environment#network-configuration)
- Resources and lifecycle: 4 CPU and 16 GB. Compute is not billed during the preview. Startup takes about 5 s. An environment goes idle (auto-snapshot) after 15 minutes and is kept offline for 7 days. — [Agent environment: Pricing & resources, Lifecycle](https://ai.google.dev/gemini-api/docs/agent-environment#environment-lifecycle)
- File I/O from the client: `client.environments.files.upload(environment=..., path=..., file=..., mime_type=..., overwrite=True)`, plus list, metadata, single-file download and tar-directory download. "The agent is currently constrained to reading text and image files. Binary file support is not yet available." — [Agent environment: Manage files](https://ai.google.dev/gemini-api/docs/agent-environment#manage-files-in-the-environment)
- Remote environments can't reach the laptop's `localhost`. The local handoff guide relies on client-executed functions for exactly this reason. — local `CLAUDE_BUILD_HANDOFF/GOOGLE_API_GUIDE.md` (derived from the official docs)

**Hooks**
- Events are `pre_tool_execution` (can `allow` or `deny` with a reason; the model sees the reason and adapts) and `post_tool_execution` (cannot block).
- Configured in `.agents/hooks.json`, with an RE2 `matcher` over `code_execution`, `view_file`, `write_to_file`, `replace_file_content`, `list_dir` and `delete_file`.
- Handlers are `command` (stdin JSON in, stdout decision out, default 30 s timeout) or `http` (POST to an allowlisted HTTPS URL; loopback is blocked).
- Hooks **fail open**: a crash, timeout, non-2xx response or unrecognised output counts as allow.
- They **do not fire** for custom `function` or `mcp_server` tools.
- The agent can rewrite hook files unless they are mounted from read-only sources.
- — [Hooks](https://ai.google.dev/gemini-api/docs/agent-hooks)

**Skills, AGENTS.md and saved agents**
- `.agents/AGENTS.md` loads automatically as system instructions, on top of any `system_instruction`. Skills live at `.agents/skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description`) and are auto-discovered. — [Custom agents](https://ai.google.dev/gemini-api/docs/custom-agents#file-based-customization)
- Saved agents:
  - `client.agents.create(id=..., base_agent="antigravity-preview-09-2026", agent_config=..., system_instruction=..., tools=..., base_environment=...)`. A sandbox with those sources is provisioned on every invocation.
  - You can also fork an existing, already set-up environment into an agent.
  - The model is locked at creation, and IDs can't start with reserved prefixes such as `gemini-`, `google-` or `antigravity-`.
  - Up to 1,000 agents. No versioning. "No subagent nesting".
  - — [Custom agents](https://ai.google.dev/gemini-api/docs/custom-agents#create-a-managed-agent)
- **Saved-agent model conflict.** The custom-agents Limitations section (live and the 23 October snapshot) lists only `gemini-3.8-flash`, `gemini-3.6-flash` and `gemini-3.5-flash-lite` as supported `agent_config` models. The Antigravity page's model table includes `gemini-4-argon` and says `agents.create` configures the model "in the exact same way". The AI Studio guide says Argon has day-one support "in Managed Agents". — [Custom agents: Limitations](https://ai.google.dev/gemini-api/docs/custom-agents#limitations); [Antigravity agent: Model selection](https://ai.google.dev/gemini-api/docs/antigravity-agent#model-selection); [AI Studio 3D guide](https://aistudio.google.com/learn/building-3d-games-and-worlds-with-gemini-4-argon)

**MCP**
- `{"type":"mcp_server","name":"^[a-z0-9_-]+$","url":...,"headers"?:{},"allowed_tools"?:[]}`. Streamable HTTP only, no SSE. Uppercase names give a generic 400. — [Antigravity agent: MCP servers](https://ai.google.dev/gemini-api/docs/antigravity-agent#mcp-servers)

**Background, streaming, budget, cost**
- Background: `background=True` requires `store=True`. Streaming uses step events (`step.start`, `step.delta`, `step.stop`, `interaction.status_update`, and so on). Automatic context compaction starts at about 135K tokens. — [Antigravity agent](https://ai.google.dev/gemini-api/docs/antigravity-agent#background-execution); [Managed quickstart](https://ai.google.dev/gemini-api/docs/managed-agents-quickstart) (local `reference/google/managed-quickstart.md`)
- Budget: `agent_config.max_total_tokens` covers input, output and thinking, excludes cached tokens, is best effort, and ends the run with `incomplete`. Continuing gets a fresh budget. The OpenAPI types it as `string`/`int64`. — [Antigravity agent: Budget controls](https://ai.google.dev/gemini-api/docs/antigravity-agent#budget-controls); [OpenAPI AntigravityAgentConfig](https://ai.google.dev/static/api/interactions.openapi.json)
- Typical use per Google's estimate table: 100K–500K input tokens per task (3M for data processing), with 50–70% cached. Complex runs reach 3–5M tokens. — [Antigravity agent: Estimated costs](https://ai.google.dev/gemini-api/docs/antigravity-agent#estimated-costs)
- Triggers: `client.triggers.create(schedule=<cron>, time_zone=..., interaction={...})` reuses one environment across runs. — [Antigravity agent: Triggers](https://ai.google.dev/gemini-api/docs/antigravity-agent#triggers)
- Prize: the organizer page lists "Best use of Managed Agents: $5,000" but gives no criteria. The page asks for projects "that push Argon to its limits" and "something that wasn't possible last week." — [Cerebral Valley event page](https://cerebralvalley.ai/e/gemini-4-argon-sf)

### Inferences (concrete WalkTwin design for "best use", most valuable first)
1. **Two-tier investigation: explore in the sandbox, verify on the client.**
   - Mount the solver, the graph-check code and the scenario JSON into the sandbox with `environment.sources`: a `repository` source of the public `walktwin` repo, or `inline` sources if under 2 MB.
   - Let Argon use `code_execution` to run broad what-if sweeps there: door combinations, alternative hazard placements, sensitivity of the declared parameters (±20% flow and walk speed), and a bottleneck ranking.
   - It then sends a shortlist to the client function `evaluate_interventions`, whose solver and independent checker are the only source of on-screen numbers.
   - The demo line becomes "Argon ran 200 scenarios in its own sandbox; our checker verified the 4 it recommends." That is real managed-agent work, not a wrapper, and it keeps the authority rules intact. Show a sandbox result and a checker result side by side, and flag any disagreement. A disagreement is a good verification moment.
2. **Hooks as a visible guardrail.**
   - A `pre_tool_execution` hook on `write_to_file|replace_file_content` denies writes to `/workspace/accepted/` (the accepted graph is read-only to the agent), and denies `code_execution` commands that match `curl|wget|pip` once setup is done.
   - A `post_tool_execution` hook runs `graph_check.py` after any write to `/workspace/scenarios/*.json` and appends to an audit log the client downloads.
   - Mount `hooks.json` from the repo source so it is harder to tamper with (the docs warn about this).
   - Be honest: hooks fail open and do not cover custom functions. Present them as policy guidance plus audit, not as the authority layer, which stays local.
3. **AGENTS.md and skills carry the domain method.**
   - `AGENTS.md` holds the copy rules (never "safe", "compliant" or "survive"), the declared parameters, and "numbers come only from evaluate_interventions".
   - `skills/egress-sweep/SKILL.md` describes how to enumerate interventions, run sensitivity checks and rank bottlenecks.
   - `skills/ada-egress/SKILL.md` holds the relevant ADA 2010 sections as static text, so citations don't depend on web search.
   - This is cheap and visible: the files can be shown in the repo.
4. **Saved agent plus forked environment, network off.** Set up the environment once (pip install networkx and pydantic, mount the code), fork it into a saved agent `walktwin-investigator`, then invoke by ID with `network: "disabled"`. The pitch line is "a reusable investigator with no internet access." **Risk:** the saved-agent docs conflict on Argon support. Probe it early; the fallback is an inline config with the same sources.
5. **Give the agent images, which the docs allow.** Send a top-down twin render with the hazard and per-door flow overlay as an inline base64 image with the text prompt. Or upload renders and video keyframes (JPEG/PNG) to `/workspace/frames/` with `environments.files.upload`. This corrects the plan's "text only" constraint. The agent still can't take video.
6. **Optional, highest ambition and highest risk: run the PS2 loop inside the managed agent.**
   - Upload the extracted video frames. The agent installs Playwright and Chromium in the sandbox (network needed at setup), renders the twin, views the screenshots, edits `graph.json`, and a post-hook runs the graph checks.
   - This mirrors Google's "automated browser screenshot checks" pattern for Antigravity.
   - Unverified: headless WebGL in the sandbox, Chromium download size and time, whether `view_file` on a PNG gives the model the pixels, and compaction at about 135K. Only attempt it after the direct loop works.
7. **Final answer through a function.** The agent has no structured output, so give it a client function `submit_recommendation(intervention_id, rationale, caveats[])` with a JSON schema. The arguments come back schema-shaped, so prose isn't parsed.
8. **Budget.** `max_total_tokens: 20000` in the plan is probably far too low for Argon plus tool definitions plus code runs, given Google's 100K–500K estimates. It will likely end `incomplete` after a step or two. Use roughly 200K–400K. At introductory prices that is under $1 to $2 per run, by my estimate.
9. **Stream the steps.** Show `code_execution` calls, `function_call` steps and hook denials live in the investigation panel as evidence, never as a fake timer.
10. **Filter pending calls by name.** Filesystem tools appear as `function_call` steps but run automatically, so only execute names on the allowlist (`get_situation`, `evaluate_interventions`). The plan's ledger handles duplicates, but it should also skip non-client names.
11. **Probably not worth it.**
    - MCP: a Streamable HTTP MCP server would need a public tunnel to the laptop. Client-executed functions do the same job without one.
    - Triggers: a nightly re-check can't be shown in a 3-minute demo; at most mention it as the product path.
    - `google_search` and `url_context`: pass an explicit `tools` list without them, so the agent doesn't browse off-task.

### Gaps
- Whether a saved agent can use `gemini-4-argon` (the docs conflict).
- Whether the agent's `view_file` on a PNG gives the model the image content, beyond "constrained to reading text and image files".
- Whether Playwright/Chromium and headless WebGL work in the sandbox.
- Exact sandbox network egress for pip and the Playwright CDN.
- Whether `url_context` and `google_search` respect `network.allowlist`, since they may run on Google's side.
- Prize criteria for "Best use of Managed Agents" are not published.
- Latency per agent round with Argon is undocumented.

---

## 4. Other Argon features: computer use, code execution, Maps, URL context, search, structured outputs, thinking

### Takeaway
On the direct model, Argon documents structured outputs (combinable with tools), function calling, code execution, search, URL context, Maps grounding (the Maps page omits Argon), and computer use (preview, client-executed). For WalkTwin:
- **Structured outputs and function calling:** essential, already planned.
- **Computer use:** could drive the twin UI, but a `set_camera` function is more precise. It is weak value.
- **Maps grounding:** can anchor the venue's real name, address and hours in the ops note. It adds no indoor geometry and has display obligations.
- **Code execution (direct):** only marginal.

### Cited Findings
- Argon capabilities (model page): agentic video; implicit caching only; code execution; computer use (Preview); file search; function calling; Grounding with Google Maps; search grounding; structured outputs; thinking (low, medium, high); URL context; Batch, Flex and Priority inference. Not supported: Live API, image generation, audio generation. — [Argon model page](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon)
- **Computer use:**
  - Model list includes `gemini-4-argon` "supporting computer use for complex reasoning and agentic UI workflows". Gemini 3.8 Flash is "the recommended model for computer use".
  - Tool shape: `{"type":"computer_use","environment":"browser"|"mobile"|"desktop","enable_prompt_injection_detection":bool,"excluded_predefined_functions":[...],"disabled_safety_policies":[...]}`.
  - Actions such as `click`, `drag_and_drop` and `take_screenshot` use normalized `x,y` in 0–999 plus an `intent` string. The client scales and executes them (for example with Playwright) and returns a screenshot in `function_result`. The response may include `safety_decision` with `require_confirmation`. Python SDK ≥ 2.7.0.
  - Not available in the managed agent.
  - — [Computer use](https://ai.google.dev/gemini-api/docs/computer-use); [OpenAPI ComputerUse](https://ai.google.dev/static/api/interactions.openapi.json); [Antigravity limitations](https://ai.google.dev/gemini-api/docs/antigravity-agent#limitations)
- **Maps grounding:**
  - Tool `{"type":"google_maps","latitude"?,"longitude"?,"enable_widget"?}`.
  - "The tool is a textual search tool". It retrieves places, reviews, photos, addresses and opening hours, and returns source annotations (URL, name).
  - You **must** show the Maps sources right after the grounded content.
  - English only; may not be available in all regions. $14 per 1,000 queries after 5,000 free per month for Gemini 3+.
  - The Maps page's supported-model table does **not** list Argon, while the Argon model page says supported.
  - Not available in the managed agent.
  - — [Maps grounding](https://ai.google.dev/gemini-api/docs/maps-grounding); [Argon model page](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon)
- **Code execution (direct model):** Python only, 30 s maximum runtime, up to 5 regenerations on error, file input (CSV and text work best), Matplotlib graph output returned inline. "Code Execution with images" (zoom/crop) is documented for **Gemini 3 Flash**; the page doesn't say it applies to Argon. — [Code execution](https://ai.google.dev/gemini-api/docs/code-execution)
- **Structured outputs:** `response_format={"type":"text","mime_type":"application/json","schema":...}` on the direct model. They combine with Google Search, URL Context, Code Execution, File Search and Function Calling. Not supported in the managed agent. — [Structured output](https://ai.google.dev/gemini-api/docs/structured-output#structured-outputs-with-tools) (local `reference/google/structured-output.md`); [Antigravity limitations](https://ai.google.dev/gemini-api/docs/antigravity-agent#limitations)
- **Thinking:** Argon is on by default at `medium`, settable to `low|medium|high`. Thought signatures are handled server-side in stateful mode. `thinking_summaries: "auto"|"none"` in `generation_config`. — [Thinking](https://ai.google.dev/gemini-api/docs/thinking); [OpenAPI GenerationConfig](https://ai.google.dev/static/api/interactions.openapi.json)
- **Media resolution:** per image or video part, `resolution: low|medium|high|ultra_high`, independent of `processing`. — [OpenAPI MediaResolution](https://ai.google.dev/static/api/interactions.openapi.json); [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding#technical-details-about-videos)

### Inferences
- **Computer use:** an honest "adds little". For render-vs-video matching, a custom function such as `render_view(x, y, heading_deg, fov)` that returns a deterministic PNG gives exact camera control. Mouse drags on an orbit control give imprecise, unreproducible poses.
  - One defensible use: a **viewpoint search** where direct Argon calls `render_view` repeatedly to find the twin camera pose that best matches a video frame. That turns the critique into Argon "watching" its own render from poses it chooses.
  - That is function calling, not computer use.
  - Using computer use for UI QA of the twin app adds demo risk and no judging value.
- **Maps grounding:** a small, optional add-on. After the user types the venue name (for example "SHACK15, Ferry Building"), one Maps-grounded call fills the ops-note header with the official name, address and hours, with the required Maps attribution shown. It does not give indoor exits or floor plans and must not be presented as egress evidence. Given the doc conflict on Argon support and the display obligations, it is low priority. Lat/long only bias "near me" queries.
- **URL context and search:** "adds nothing" to the core loop. Put ADA text in a local skill or static file instead of fetching it live, for reproducibility. Leave both off the managed agent's tool list.
- **Code execution (direct):** it could compute IoU between a render and a frame, but local deterministic code does that better and keeps the rule "every number comes from local code". Skip it.
- **Structured outputs:** keep them for extraction and critique (`PatchOp` union). Combining structured outputs with function calling lets the critique call `render_view` and still return a schema-valid patch.
- **Thinking:** use `high` for extraction and critique, and `low` or `medium` for any per-iteration small call. Time all three levels in the Task 2 probe, as Google recommends.
- **`resolution:"high"`** on video keyframes and renders will probably help with door-width reading at modest token cost: about 258 tokens per frame at default, by the static-mode figures above.

### Gaps
- Argon's Maps-grounding support (the docs conflict).
- Whether image zoom inside code execution works on Argon.
- Computer-use latency and accuracy on Argon.
- No `seed` or determinism guidance for Argon was found beyond a `seed` field in the OpenAPI `GenerationConfig`; its behaviour on Argon is undocumented.

---

## 5. Google's 3D worlds guide and the Argon launch blog: what to cite in the pitch

### Takeaway
Google's own 3D guide recommends almost exactly WalkTwin's loop:
- render screenshots from several camera angles and have an adversarial critic score them and send back fixes;
- for multi-room interiors, draw a top-down floorplan in meters first and extrude 3D from it;
- work out the camera pose from a photo first, so the 3D view lines up 1:1.

The launch blog gives a long-video benchmark to cite: LVBench 91.7%, state of the art. Neither source mentions WalkTwin's domain. All benchmark claims are Google's own.

### Cited Findings
- **AI Studio guide** ("Building 3D Games and Procedural Worlds with Gemini 4 Argon"), Geneviève Huskens, published 13 October 2026. Three pillars: "Long-horizon autonomy" (1M-token context and output), "Native multimodality" (photos, sketches, "its own rendered screenshots"), and spatial and mathematical reasoning. — [AI Studio 3D guide](https://aistudio.google.com/learn/building-3d-games-and-worlds-with-gemini-4-argon)
- **Tooling table:**
  - AI Studio Build: three.js / R3F / WebGPU.
  - Antigravity: "long-running /goal loops, parallel subagents, automated browser screenshot checks", with "Vite + Three.js + Headless Blender MCP + headless browser screenshots".
  - Gemini API: "Custom multi-agent harnesses, automated 3D asset pipelines".
  - — [AI Studio 3D guide](https://aistudio.google.com/learn/building-3d-games-and-worlds-with-gemini-4-argon)
- **The six workflows:**
  1. Align on creative direction first (references, Nano Banana mocks, `/grill-me`, a drafted `/goal`). The references can include "a 15-second walkaround video of a real object".
  2. Parallel subagents.
  3. An "Adversarial Critic subagent" after each round. It renders 4 screenshots (a 3/4 overview, a close-up, a low angle for floating objects, a wireframe), lists at least 3 flaws, and rates the scene out of 10; iterate to 9/10 or above. The guide notes that many models "stop after Round 2" without a separate critic.
  4. Human art-direction tools (a `progress.html` screenshot gallery, sliders, "Copy Settings as JSON").
  5. Nano Banana photoreal target renders.
  6. "ground proportions with a 2D plan first". For multi-room interiors, an SVG floorplan in meters and then extrusion. For photos, an X/Y grid overlay. To recreate photos, calculate the camera angle and horizon line first.
  - — [AI Studio 3D guide](https://aistudio.google.com/learn/building-3d-games-and-worlds-with-gemini-4-argon)
- **Desk Racer case study:** desk photos, then Nano Banana mocks, then subagents across Blender MCP and three.js, including "mathematical intersection checks so all 68 coaster pillars landed flush". "Argon verified each iteration with automated screenshots". — [AI Studio 3D guide](https://aistudio.google.com/learn/building-3d-games-and-worlds-with-gemini-4-argon)
- **Launch blog,** 30 September 2026, Koray Kavukcuoglu:
  - LVBench (long video understanding) 91.7%, state of the art; DeepSWE v1.1 77.9%; AutomationBench #1 at 51.3%; CWE-bench v1 tied first at 68%.
  - Argon can "identify details from long videos".
  - 1M output token limit, up from 64K; can "generate hundreds of thousands of tokens in a single trajectory".
  - Migrations on codebases up to "800K+ lines".
  - No mention of 3D, games or Managed Agents.
  - Benchmarks are self-reported, and several "leading" claims have no numbers.
  - (Read via a WebFetch summary, so figures should be rechecked against the page before slides.)
  - — [Argon launch blog](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-4-argon/)
- **Docs-side claims to cite:** agentic video is "Up to 88% more token-efficient and ~7% higher quality on long-form content". This is stated for the agentic mode in general, and the table lists Flash models. — [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding#agentic-video-understanding)
- **Secondary press:** a search returned aggregator and press pages (eesel.ai, cometapi, llmgateway) repeating launch pricing. Not used for any claim. — [secondary: eesel.ai](https://www.eesel.ai/de/blog/gemini-4-argon-benchmarks-preise-zugang)

### Inferences
- **Pitch framing.** "Google's own 3D guide tells you to render, screenshot from several angles, have a critic score it, and fix it, and for interiors to draw the floorplan first. WalkTwin does that loop against a real phone walkthrough instead of an art brief. The critic checks against the video, and the solver and checker are deterministic." This ties PS2, the guide and the 15% originality criterion together.
- **Borrow the guide's critique-view set.** Per iteration, add a top-down orthographic render and a wireframe or outline view alongside the keyframe-matched first-person renders. The top-down view catches zone overlaps and doors off walls, which Argon can compare against its own floorplan SVG.
- **Camera-pose-first (Workflow 6).** Before the critique, ask Argon to estimate each keyframe's camera pose and heading from the video frame. This feeds `cameraFor(k)`, and Google explicitly recommends it to make the 3D view line up 1:1.
- **Human-in-the-loop parallel.** The guide's "progress gallery" and "Copy Settings as JSON" match the plan's iteration timeline and accept-graph step. Show the per-iteration gallery, because Google itself calls it good practice.
- **Benchmarks to cite carefully.** "LVBench 91.7% (Google-reported, state of the art)" for long video. Don't cite the 88% / 7% agentic figures as Argon numbers. Don't claim Argon generated the twin in one pass unless the hybrid dressing module (section 2) is actually built.
- **Workflows to skip.** Nano Banana and Blender MCP add nothing to egress, and Nano Banana is a different model, which dilutes the "Argon only" angle. Parallel subagents can't be nested in managed agents.

### Gaps
- The AI Studio "Gemini 4 Argon showcase" and "Developer Guide" pages were not read; they may include more 3D examples or video benchmarks.
- No official Argon benchmark specific to spatial reconstruction or floorplans was found.
- No published Managed Agents prize criteria.
- The LVBench figure came through a summarising fetch, so verify it on the blog page before it goes on a slide.
