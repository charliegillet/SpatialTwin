# SpatialTwin: Gemini 4 Argon capability audit and venue-plan research

Research date: **24 October 2026**. Repository inspected: `/Users/nihalnihalani/Desktop/Github/SpatialTwin`, HEAD `29b33da149b6c9d7a7e52957079565e8bd202619`.

## Findings

**SpatialTwin has a useful, deliberately narrow Argon integration, but it does not implement all documented capabilities or runtime skills. Its live integration is not established by the existing tests, and a reproducible response-parsing bug prevents the normal managed-agent result from being returned with the installed SDK.** Adding every model feature would not solve these correctness problems.

**Public layouts were found for both SHACK15 and the Ferry Building. No complete, current, coordinated building/tenant as-built drawing set was located.** The best SHACK15 source is a vendor's venue map; the strongest Ferry Building source is an official, 76-page proposed-enhancement drawing package. Neither establishes approved present-day geometry or evacuation capacity for this application.

This was a research and read-only implementation audit. Application code, venue geometry, credentials, provider resources and hardware were not changed. No Gemini model request was made, no physical operation was attempted, and no venue contact or records request was submitted.

## Method and evidence limits

- Read the contributor instructions, `BUILD_PLAN.md`, relevant integration references, current adapters/contracts/service/API, active frontend, tests, installed SDK types and venue model.
- Used the explicitly requested Firecrawl workflow, with agent-reach routing, to search and retrieve Google's official documentation and public venue/Port/architect/vendor sources. Work was divided into AI, SHACK15 and Ferry Building investigations. Search feedback contained source-quality metadata only.
- Compared the model catalog and current release guide with the direct and managed APIs separately. Also checked structured output, background execution, streaming, long decode, video, custom agents and official developer skills.
- Ran the current test suite with provider credentials blank, serial configuration blank, outbound sockets disabled and temporary SQLite storage: **18 passed in 1.18 seconds**. This is offline evidence, not provider access, perception accuracy or physical hardware evidence.
- Inspected request serialization and typed responses through installed **`google-genai 2.33.0`**, using fake HTTP responses and blocked sockets. Additional deterministic adversarial probes exercised deadlines, duplicate calls, lifecycle states and grounding validation. The preserved script assembles individually executed probes; it was not rerun as one combined script.
- Visually inspected the downloaded SHACK15 PDF map. Ferry Building PDFs were text-inspected through Firecrawl; their exact sheet labels were not visually confirmed. Do not infer actual PDF page numbers from Firecrawl text segment numbering.
- Raw web receipts and PDF renders are in the ignored `.firecrawl/` directory. Sanitized probe code/results are preserved alongside this report in `evidence/`. Source URLs and relevant document dates appear below so conclusions can be rechecked.

A configured API client is not proof that the account can access a model or that a response came from that model. A model name in a prompt or result record is also not execution evidence. This report makes no claim that a paid live run failed: the SDK failure was reproduced offline against the actual installed response type.

## 1. What the current Argon release adds

Google's [release guide](https://ai.google.dev/gemini-api/docs/latest-model) highlights a unified million-token context, long decode, agentic video and Argon selection in managed agents. The model page was updated **14 October 2026**; the release guide **16 October 2026**.

| Release capability | SpatialTwin assessment | Practical implication |
|---|---|---|
| Unified 1,048,576-token window, shared by input/thinking/output | Provider capacity; no large-context workflow or measurement in the app | Naming the model does not demonstrate use of the full window. Small token detection does not need it. |
| Long decode beyond the synchronous 65,536-token output ceiling | Absent | No background long-output request, hop/output aggregation, retrieval or resume handling. Optional for long reports, not needed for a small proposal. |
| Agentic video, explicitly selected instead of static processing | Absent | The camera sends a still JPEG. A moving webcam preview is not temporal model analysis. |
| Argon as the managed Antigravity model | Initial request configured; end-to-end execution unverified and parser broken | This is the most relevant existing path to fix before expanding features. |

The exact token limits come from the [Argon model catalog](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon). Long decode requires background stored execution and larger output configuration; see [long decode](https://ai.google.dev/gemini-api/docs/long-decode). Agentic video is opt-in and emits processing steps; see [video understanding](https://ai.google.dev/gemini-api/docs/video-understanding).

These expansion features are not prerequisites of the agreed initial build: [BUILD_PLAN:149](/Users/nihalnihalani/Desktop/Github/SpatialTwin/BUILD_PLAN.md:149) deliberately selects one still, and [BUILD_PLAN:168](/Users/nihalnihalani/Desktop/Github/SpatialTwin/BUILD_PLAN.md:168) selects fixed read-only numerical tools. The required completion gaps are the correctness and orchestration controls described below.

## 2. Direct-model capability matrix

**Implemented** below means a reachable code/request path exists. It does not mean that a real provider run or its accuracy has been verified. **Absent** does not automatically mean required for this demonstrator.

| Capability | Status | Local evidence / limitation |
|---|---|---|
| Explicit `gemini-4-argon` selection | Implemented request | [Grounding adapter:99](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/ai/grounding/adapter.py:99). Returned provider identity is not recorded/checked. |
| Text input | Implemented | A fixed task prompt plus reviewed context is sent. |
| Single captured image | Implemented | Text plus JPEG base64 at [adapter:101](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/ai/grounding/adapter.py:101); explicit connect/capture in [ObservationPanel:100](/Users/nihalnihalani/Desktop/Github/SpatialTwin/frontend/src/components/ObservationPanel.tsx:100). Accuracy/latency on real images remains unmeasured. |
| Multiple images | Absent | Current application intake sends one image. |
| Video input / agentic video | Absent | No video payload, temporal workflow, processing configuration or processing-step evidence. |
| Audio input | Absent | No application intake or interpretation path. |
| PDF/document input | Absent | No provider PDF intake or blueprint-to-reviewed-geometry pipeline. Finding a PDF on the web does not import it into the model. |
| JSON response mode | Implemented request | Uses `type=text` and JSON MIME type. Offline serialization accepted this shape. |
| Provider schema-constrained JSON | Partial | No `schema` is sent at [adapter:106](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/ai/grounding/adapter.py:106). Prompt instructions plus Pydantic parsing are not provider schema enforcement. |
| Local semantic checks and abstention | Partial | Selected target pair/membership and matched/ambiguous/no-match are checked; bounding boxes, all candidate IDs and lifecycle completion are not adequately checked. |
| Low/medium/high thinking | Partial | Backend parameter exists; active UI defaults to low and exposes no selector. [Client:75](/Users/nihalnihalani/Desktop/Github/SpatialTwin/frontend/src/api/client.ts:75). |
| Direct function-calling workflow | Absent | Function calling is used in the separate managed adapter. |
| Google Search grounding | Absent from app | No search tool declaration or source/citation result handling. |
| URL context | Absent from app | No URL tool declaration or URL-context workflow. |
| Maps grounding | Absent from direct path | No Maps tool declaration. Maps cannot substitute for interior architectural drawings. |
| Code execution | Absent from app declarations | Local numerical tools are application code, not the provider's code-execution tool. |
| File search | Absent | No index/store ingestion and retrieval workflow. |
| Computer use | Absent | No provider computer-use integration; desktop tools used during development are separate. |
| Implicit caching | Provider-managed; unmeasured | No cache-token measurement or benchmark. This should not be reported as an explicitly implemented app feature. |
| Batch, flex, priority consumption | Absent | No application routing/configuration/evidence for these modes. Optional operational choices. |
| Background execution | Absent | No stored interaction polling, retrieval/resume or cancellation. |
| Provider streaming | Absent | No provider `stream=True`, delta assembly, reconnect or partial-argument handling. App scenario SSE is a different stream. |
| Native Live API | Not an Argon feature | Google's model page marks this unsupported. A compatible separate model would be required. |
| Native image/audio generation | Not Argon features | Argon output is text. These should not be listed as missing implementations of an available Argon capability. |
| Explicit context caching | Not an Argon feature | The model catalog supports implicit caching only. Do not add explicit-cache calls on the assumption every Gemini model supports them. |

Provider availability in this matrix is grounded in the [model catalog](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon), [structured-output guide](https://ai.google.dev/gemini-api/docs/structured-output), [streaming guide](https://ai.google.dev/gemini-api/docs/streaming) and [background-execution guide](https://ai.google.dev/gemini-api/docs/background-execution). Availability, account entitlement and app implementation are three separate checks.

## 3. Managed-agent and runtime-skill matrix

The [managed-agent guide](https://ai.google.dev/gemini-api/docs/antigravity-agent) describes a different surface from the direct model. Do not transfer direct-model configuration fields or capability claims into the managed call without checking that surface.

| Managed capability/control | Status | Evidence / consequence |
|---|---|---|
| Explicit Antigravity agent plus Argon configuration | Implemented initial request | Agent `antigravity-preview-09-2026`, model `gemini-4-argon`, initial token budget at [adapter:243](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/ai/managed/adapter.py:243). |
| Python budget serialization | Verified offline | Integer `20000` becomes wire `"20000"` through SDK 2.33.0. This is not a type bug. |
| Read-only local function allowlist | Implemented | `get_reviewed_scenario`, `evaluate_allowed_alternative`, `get_checked_comparison`; [definitions:29](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/ai/managed/adapter.py:29). No cloud serial/servo or arbitrary local-execution function. |
| Fixed candidate alternatives | Implemented | `KEEP_CURRENT` and `OPEN_P3`; values derive from the local numerical service. Missing required `alternative_id` silently defaults to KEEP_CURRENT, which should be rejected instead. |
| Function-result correlation | Partial | Uses `function_result.call_id`, prior interaction and initial environment ID at [adapter:290](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/ai/managed/adapter.py:290). |
| Pending-call filtering and duplicate suppression | Absent | Every returned function-call step is executed, without a fulfilled-call set or persistent idempotency key. |
| Durable per-call execution ledger | Absent | In-memory ledger is saved only as part of final investigation JSON. Scenario command idempotency does not deduplicate provider tool calls. |
| Four-tool-call cap | Not enforced | Code limits four continuation turns. One response can contain more than four calls. |
| Whole-investigation deadline | Not enforced | Deadline is returned as metadata but does not bound provider/tool execution. |
| Cancellation/recovery/restart | Absent | No durable interaction/environment resume or cancellation flow. |
| Complete lifecycle treatment | Partial/incorrect | `failed`, `cancelled`, `in_progress` and `incomplete` collapse into incomplete; errors and recommendation availability are not handled distinctly. |
| Response usage parsing | Broken with installed typed response | `Usage.get()` is invalid; see finding A below. |
| Whole-investigation token accounting | Partial/incorrect | Initial budget exists; cumulative local accounting and continuation-wide enforcement do not. Fallback uses constant synthetic usage. |
| Provider streaming and background orchestration | Absent | Scenario SSE does not stream provider execution. |
| Actual execution provenance | Incomplete | `is_live_configured` says only that a client exists. Backend output does not reliably distinguish live, failed-live fallback and local execution. Current UI is appropriately cautious. |
| Remote environment | Configured | `environment="remote"`; no project sources or custom skill files mounted. |
| Runtime `SKILL.md` skills | Absent | No `.agents/skills/<name>/SKILL.md` mount/source packaging in the managed environment. |
| Saved/named custom agent | Absent; optional | Inline configuration is used. No saved-agent creation/version workflow. |
| Search/URL/code-execution builtin integration | Not declared by app | The application supplies its three local function tools. No app workflow or result evidence establishes these builtins were used. |
| Remote MCP | Absent | No remote MCP declarations/connection lifecycle. |
| Hooks, sandbox network/credential policy | No custom implementation | No application-defined hook, mounted-secret or egress-policy workflow. Do not infer arbitrary access to the local host from the provider environment. |
| Scheduled provider triggers | Absent; optional | No trigger resources or unattended workflow. No schedules were created in this audit. |
| Automatic context compaction | Provider behavior; unverified | Not an application feature that the repository can claim to have implemented. |

Managed restrictions matter: schema-constrained output, direct output-limit settings, file search, computer use and Maps are not interchangeable with direct Argon. Managed multimodal intake is limited to text/images; audio/video/documents need a suitable direct path. Background execution requires storage, and custom-function continuations require state. The guide also specifies Streamable HTTP rather than legacy SSE for remote MCP. [Managed limitations](https://ai.google.dev/gemini-api/docs/antigravity-agent#limitations).

The appropriate skill integration mechanism is described in [custom agents](https://ai.google.dev/gemini-api/docs/custom-agents). Existing host-side instructions and global assistant skills are not automatically copied into Google's remote environment.

## 4. What “Gemini skills” means here

There are three separate concepts:

1. **Model capabilities:** image/video understanding, thinking, structured output, tools and so on. These are the matrices above.
2. **Developer skills:** instruction packages used by Codex, Claude Code, Antigravity or another coding assistant while building an app. Google's [coding-agent guide](https://ai.google.dev/gemini-api/docs/coding-agents) lists `gemini-api-dev`, `gemini-live-api-dev` and `gemini-omni-flash-api`, plus its documentation MCP tools. Installing these does not add an endpoint, UI or capability to SpatialTwin.
3. **Runtime managed-agent skills:** files mounted into the remote execution environment and made available to the agent during an investigation. SpatialTwin does not package/mount any.

The current assistant environment advertises Gemini API/Interactions/Live development skills. Their presence establishes neither freshness against the October documentation nor use by the deployed application. No skill installation was performed in this audit. The Live and Omni development skills also concern separate compatible model surfaces; they do not make native Live or generation available in Argon.

If runtime skills are added later, a useful narrow scope would be interpreting the reviewed venue catalog, abstaining on uncertain captures, and requesting only the numerical allowlist. A skill must not become a second route to state acceptance, hardware movement or arbitrary host execution. This is a design suggestion, not an existing feature.

## 5. Reproducible implementation defects

### A. Managed response parsing fails on typed SDK usage

[Managed adapter:321](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/ai/managed/adapter.py:321) evaluates:

```python
getattr(interaction, "usage", {}).get("total_tokens", 0)
```

The installed SDK returns a typed `Usage` object. The offline SDK round trip produced:

```text
SDK_VERSION=2.33.0
USAGE_TYPE=Usage
USAGE_GET_SUPPORTED=False
AttributeError: 'Usage' object has no attribute 'get'
```

The outer catch at [adapter:99](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/ai/managed/adapter.py:99) then returns deterministic local computation. A successful provider completion with ordinary typed usage therefore still fails this application's result parser. Requests and tool continuations may already have executed and incurred usage before this final assembly fails; the probe does not demonstrate denied account/model access. Correct parsing must handle the actual typed field, absent usage and tested SDK version; then record genuine execution provenance instead of disguising a provider error as cloud success.

### B. Deadlines and tool limits are claims rather than enforced controls

The adversarial offline loop executed the same provider call ID **four times**. With `deadline_seconds=0`, it still performed those executions and **five provider creates**. A single turn containing six function calls executed **all six**. See [adapter:258](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/ai/managed/adapter.py:258).

The tools are read-only numerical functions, so this probe did not cause actuation. Repetition nevertheless wastes compute, weakens the ledger and makes later stateful expansion unsafe. Required controls are argument validation, pending-call filtering, durable deduplication, a call cap independent of turn count, a deadline enclosing the entire investigation, and bounded provider retries/cancellation.

### C. Incomplete/failed execution still receives a recommendation

For each simulated provider status `failed`, `cancelled`, `in_progress` and `incomplete`, the adapter reported incomplete with a KEEP_CURRENT recommendation and an empty error list. Its comparison starts missing candidates at zero and synthesizes a recommendation before verifying a completed, valid, current comparison. [Adapter:300](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/ai/managed/adapter.py:300).

Recommendation availability must depend on the required checked evidence, not on zero defaults. Failure, cancellation, exhaustion and active execution need explicit states and recoverable diagnostics. The active frontend already rejects incomplete investigations for comparison display; the backend still needs correct semantics.

### D. Grounding accepts invalid or incomplete response material

An offline response marked `incomplete` still became a `matched`, `live` proposal. A bounding box `[-15, 2000]` and a candidate list containing an invented ID passed the current semantic check. The selected target remained allowlisted; this did **not** demonstrate arbitrary target acceptance or arbitrary local execution.

The request lacks a provider schema; response processing does not first require completed status. [Grounding adapter:109](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/ai/grounding/adapter.py:109). [Contract:115](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/contracts.py:115) permits any integer list for the box. Validation should enforce four coordinates, normalized bounds, coordinate ordering, every candidate's membership, state-dependent nullability and the allowlisted operation. The adapter currently replaces a model-supplied operation with SET_UNAVAILABLE; rejecting unexpected fields/operations would provide clearer evidence than silently repairing them.

### E. Provider errors silently become a matched fixture

Malformed JSON produced a matched P2 fixture unless an override supplied another supported target. The fixture is explicitly labeled, which is useful and should be retained. However, changing a failed live perception into a positive fixture match obscures the distinction between “the model saw this” and “the demo generated this.” [Adapter:135](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/ai/grounding/adapter.py:135).

Use an unavailable/error result for failed live perception, with a separate explicit operator action for a fixture/manual demonstration. Human approval already exists in the active UI; this finding does not claim the fallback automatically changes physical state.

### F. Capture and context identity are weaker in the backend than in the UI

[RunContext.is_current:80](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/contracts.py:80) compares geometry, scenario and physical revision but omits parameter revision, solver version and hash. A mismatch in those omitted fields was accepted offline. An isolated adapter probe supplied older capture geometry, which was rebased into the current context rather than rejected. This is not an HTTP endpoint exploit: the route constructs those fields itself. The concrete endpoint gap is creating capture timestamps/revisions from server receipt state at [main:156](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/main.py:156), without proving when the image was actually captured or which original revision it depicts. The frontend checks returned context before Apply, and the service does reject geometry/scenario/physical mismatches.

Preserve capture-time identity and image digest/source, bind the proposal to it, revalidate the full context at review/apply, and keep a durable capture → proposal → operator review → typed command record. Current frontend revision checks are a meaningful improvement but cannot replace backend admission checks.

### G. Usage/provenance and completion documentation overclaim

The deterministic managed fallback assigns `1420 + 310 = 1730` tokens and an explanation attributing verification to Antigravity. [Adapter:202](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/ai/managed/adapter.py:202), [usage:222](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/ai/managed/adapter.py:222). These are not measured provider usage or proof of managed execution.

[Main:244](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/main.py:244) exposes configuration, not actual successful execution provenance. [Team status:16](/Users/nihalnihalani/Desktop/Github/SpatialTwin/docs/ai/team-status.md:16) claims live integration was verified; this audit found no tracked run artifact sufficient to establish that claim. A previous unrecorded live test is not disproved, but the checked-in evidence and green suite do not prove it.

[Requirements:6](/Users/nihalnihalani/Desktop/Github/SpatialTwin/requirements.txt:6) permits `google-genai>=2.0.0`; the manifest's stated SDK version is not an enforced installation pin. Pin or lock the verified dependency and retain sanitized request/status/model/usage/latency evidence for real smoke tests.

## 6. What the existing UI and tests establish

The active UI is substantially more cautious than some backend/documentation claims:

- [InvestigationPanel:127](/Users/nihalnihalani/Desktop/Github/SpatialTwin/frontend/src/components/InvestigationPanel.tsx:127) explicitly displays **Provider unverified**.
- [InvestigationPanel:85](/Users/nihalnihalani/Desktop/Github/SpatialTwin/frontend/src/components/InvestigationPanel.tsx:85) requires complete investigation evidence, current checked candidates and matching population/horizon/time step for comparison.
- [App:166](/Users/nihalnihalani/Desktop/Github/SpatialTwin/frontend/src/App.tsx:166) requires explicit review before applying a matched, current, canonical proposal.
- The camera captures an explicit still; fixtures are labeled; physical confirmation is distinct from requesting a movement.
- [App:88](/Users/nihalnihalani/Desktop/Github/SpatialTwin/frontend/src/App.tsx:88) consumes real scenario SSE. It should not be advertised as Gemini token/tool streaming.

Older unused components were not treated as active UI behavior. The current entrypoint imports the new panels.

The AI suite consists of three grounding tests and one managed test. Grounding is forced into fixture mode; the managed test uses the truthy string `"none"` as a key and can pass through fallback. [Grounding test:64](/Users/nihalnihalani/Desktop/Github/SpatialTwin/tests/ai_contracts/test_grounding.py:64), [managed test:19](/Users/nihalnihalani/Desktop/Github/SpatialTwin/tests/ai_contracts/test_managed_agent.py:19). The offline 18-test pass confirms that the current suite does not require a working cloud path. It does not measure real-world accuracy, all lifecycle states, deduplication, deadlines, provider identity or physical hardware behavior. The suite does exercise simulated hardware movement and switches.

## 7. SHACK15 plans: what was actually found

The strongest public layout is [Vivas, TEMPLATE Shack15 PDF, page 2](https://vivasinc.com/wp-content/uploads/2026/06/TEMPLATE-Shack15.pdf#page=2), a **32-page event-branding template**.

| Item | Verified scope |
|---|---|
| Page 2 | Labeled SHACK15 floor map: Lounge, Reception, Library, Kilden, Finstua, Hulen, Sanctuary, Gallery, Salon; visible room partitions and furniture. |
| Page 3 | The same layout with 13 event-branding arches marked. |
| Remaining pages | Branding, signs, covers/backdrops and fabrication examples/dimensions. |
| File metadata | Created/modified 25 August 2026, 15:36:53 UTC−07:00; 26 August 04:06:53 IST. The URL's June folder is not a drawing revision date. |
| Drawing quality | Underlying map is a 1486 × 478 JPEG with larger label overlays. Small dimension strings cannot be relied upon. |
| Missing verification | No identifiable architectural sheet/revision block, approval stamp, north arrow or scale bar on the inspected map. No complete structural/MEP/egress/current as-built set. |

Use this to understand room names and an illustrative arrangement. It is insufficient for measured geometry, door widths, current permitted occupancy or approved exit capacity. No dimensions or numerical quotas were imported into SpatialTwin.

Local original: [shack15-vivas-template.pdf](/Users/nihalnihalani/Desktop/Github/SpatialTwin/.firecrawl/shack15-vivas-template.pdf). Inspected render: [page 2](/Users/nihalnihalani/Desktop/Github/SpatialTwin/.firecrawl/shack15-vivas-map-02.png). These are ignored research files, not automatically included in a Git commit.

The venue's [About page](https://www.shack15.com/about) places it on the top floor, approximately 51,000 square feet. Its [terms §01](https://www.shack15.com/terms-and-conditions) say third floor, although that page has no visible effective date and uses prospective wording. A [2 December 2021 Silicon Foundry interview](https://sifoundry.com/shack15-building-community-through-inspired-shared-space/) also says third floor. Some event directions use different elevator numbering; do not infer a precise floor-index convention for an import without confirmation.

The official [private-events page](https://www.shack15.com/events) supplies the venue inquiry route, but no public architectural drawing download was found there. [SF Unique Venues](https://www.sfuva.com/shack15) has room marketing information, not verified model quotas. A [MONDO-DR project entry](https://mondodrawards.com/portfolio/shack15/) credits Hemminger Architects and Global AV Group; these are provenance leads rather than released drawings.

## 8. Ferry Building plans: strongest sources and limitations

| Source | What it contains | What it does not establish |
|---|---|---|
| [Port Exhibit B, 11 March 2024](https://www.sfport.com/media/9504/download?inline) | **76 PDF pages**, approximately 47.21 MB; proposed enhancements by Page & Turnbull / Einwiller Kuehl; existing/proposed site layouts, public access/lease boundaries, seating/circulation, North Arcade/portico configurations, glazing/screens/canopies and sections. | A coordinated current as-built set covering every floor and SHACK15 tenant interiors. No complete second-/third-floor plan headings were found in parsed content. |
| [Port staff report](https://www.sfport.com/media/9511/download) and [official meeting](https://www.sfport.com/meetings/waterfront-design-advisory-committee-wdac-march-11-2024) | Official context and project scope: ground-floor interior and exterior/public spaces. | Approval/construction/as-built status of every depicted condition. |
| [Official marketplace map](https://www.ferrybuildingmarketplace.com/map/) | Ground-level merchant/visitor layout; linked map filename indicates September 2026. | Architectural dimensions, upper floors, approved occupancy or a certified drawing revision. |
| [CBRE/owner brochure](https://images1.showcase.com/d2/g6Tn6jMt0uK7CKuHm7JmiM86gsqRiC5CBGGz8oTEtoI/document.pdf) | Seven-page leasing brochure, second-floor Suite 270, approximately 1,329 rentable square feet; availability 1 June 2024. | Entire second floor or current available/as-built tenant conditions. |
| [BCV architect project](https://bcvarch.com/projects/commercial-community/marketplaces/the-ferry-building-marketplace/) | Marketplace design provenance; page has a floor-plan section. | The actual drawing asset was not extracted/verified in this research. |
| [Places case study](https://placesjournal.org/assets/legacy/pdfs/the-ferry-building-san-francisco-california.pdf) | Seven-page 2007 article with historical illustrative site plan/section credited ©1998. | Current architectural set. |
| [Library of Congress HABS CAL-1910 data](https://tile.loc.gov/storage-services/master/pnp/habshaer/ca/ca0600/ca0641/data/ca0641data.pdf) | Eleven pages of historical/descriptive material prepared in 1964. | Measured drawing sheets; this particular file is written data. |
| [Venue page](https://www.ferrybuildingmarketplace.com/venue-rental-events/) / [Matterport tour](https://my.matterport.com/show/?m=xFpKZWwepfm&ss=323&sr=-.03,.01) | Visual orientation and event-space reference. | A surveyed or dimensionally verified digital twin. |

The Port staff report references Exhibit B printed page groups 10–24 for public/private lease areas, 21–23 for seating, 25–42 for plaza/south work, 43–55 for arcade/portico and 67–71 for details. These are **the report's references**, not independently visually verified PDF indices. The 76-page public package is valuable, but “many drawing pages” must not be described as “complete current building blueprints.”

For this audit, “complete current plans” means a coordinated set with a drawing index, revisions and coverage of all relevant floors/current tenant layouts, dimensions, doors, stairs and egress information. Availability of a historical or proposed design does not establish that such a current package exists or is publicly downloadable.

## 9. Official route to inspect or obtain fuller records

The [Port's published records policy](https://www.sfport.com/recordsrequest) is the most direct next route. It gives `portrecords@sfport.com` for requests identifying the records and relevant dates. Permit files can be inspected at **Pier 1, The Embarcadero, second-floor Permit Desk, Monday–Friday 8:30–11:30 a.m., without an appointment**. The Port says electronic duplication/sharing of permit plans needs the owner's permission. This is the Port's stated process, not a guarantee that a full current as-built set is held.

Its [plan-duplication form](https://www.sfport.com/media/427/download) describes the release/permission workflow; it is an older form, so confirm present requirements with the Port. [San Francisco DBI's plan-copy process](https://www.sf.gov/step-by-step--apply-get-copies-official-building-plans) is a secondary route if records are held there. Do not assume DBI rather than Port custody for this property.

The useful record request is specific: latest available landlord/base-building and SHACK15 tenant plans; drawing index and revision/permit identifiers; dimensioned suite boundaries and openings; stairs/exit discharge; current occupancy/egress documentation; and available CAD/IFC plus permission for prototype use. Structural/MEP sheets are additional records if “complete building blueprint” is meant across all disciplines. Inspection or a request is not evidence of current site conditions; reconcile the drawings with venue staff/site observations before use.

No request or contact was sent. The user authorized searching, not emailing the venue or records office.

## 10. How this affects the existing venue model

[Planner model:45](/Users/nihalnihalani/Desktop/Github/SpatialTwin/backend/app/planner/model.py:45) hardcodes four zones—EVENT, WEST, EAST, RESERVE—with 120 synthetic occupants, a 40-second horizon and a 2-second time step. P1/P2 are declared internal portals; B1/B2 have finite declared rates; P3 is a miniature internal reserve connection. These are demonstrator assumptions, not dimensions/capacities established by the discovered SHACK15 source.

[Reviewed venue JSON](/Users/nihalnihalani/Desktop/Github/SpatialTwin/venue/reviewed_venue.json) describes a six-zone schematic in its provenance string but contains four zones. The `geom-shack15-v1` name does not establish source correspondence. No source-to-room mapping, reviewed drawing index/revision, scale calibration or architectural import pipeline establishes equivalence to the real venue.

There is no need to replace a clear tabletop demonstrator with a falsely precise model. Either continue labeling it illustrative, or create a separate reviewed venue revision after reliable source geometry and site reconciliation. Preserve the allowlisted judge targets, every synthetic occupant and finite boundary capacity. Never turn P3 into an additional real building exit because a diagram happens to show an opening.

AI recommendations also depend on trustworthy numerical checking and observed physical state. This research did not re-audit or certify the full planner/hardware chain; more model features cannot establish those prerequisites.

## 11. Recommended order of work

| Priority | Concrete completion condition |
|---|---|
| **P0 — truthful, working live adapter** | Correct typed usage parsing; lock the tested SDK; distinguish configured/live/local/fixture/replay/error; remove synthetic usage/cloud-verification wording from fallback; retain sanitized real-run identity/status/usage evidence. |
| **P0 — complete admission checks** | Enforce provider completion, schema and semantic checks; reject malformed/stale inputs; preserve capture-time source/context; require full backend context equivalence before accepting reviewed commands. |
| **P0 — bounded orchestration** | Validate required tool arguments; durable exactly-once ledger; cap calls independently of turns; enforce whole-run deadline/cancellation; handle all statuses; recommend only from complete valid checked evidence. |
| **P1 — meaningful validation** | Deterministic SDK-response/lifecycle/adversarial tests, followed by explicit live direct/managed smoke tests and a real capture accuracy/latency trial. Keep those evidence types distinct. |
| **P1 — venue provenance** | Obtain usable current plans/permission if a real-venue claim is needed; record index/revision/units; reconcile layout; create reviewed geometry and validate independently. Otherwise keep the illustrative designation. |
| **P2 — selected feature expansion** | Add provider streaming/background only if it improves the actual investigation flow. Add runtime skills only with explicit mounts/versioning and narrow tool authority. Agentic video is useful only for a temporal product requirement. |
| **Optional — long-form and operational features** | Long decode, giant context workflows, search/file retrieval, batch/flex/priority, saved agents and triggers should each have a concrete user requirement and separate validation. They are not needed merely to claim broad Argon coverage. |

There is no defensible single “percent complete” from counting model features. The meaningful distinction is between working demonstrated paths, partially implemented controls, optional expansion and unsupported features.

## Source register

Google official pages inspected: [model catalog](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon) (14 Oct), [release guide](https://ai.google.dev/gemini-api/docs/latest-model) (16 Oct), [managed agents](https://ai.google.dev/gemini-api/docs/antigravity-agent) (16 Oct), [long decode](https://ai.google.dev/gemini-api/docs/long-decode) (13 Oct), [video understanding](https://ai.google.dev/gemini-api/docs/video-understanding) (13 Oct), [structured output](https://ai.google.dev/gemini-api/docs/structured-output) (21 Oct), [custom agents](https://ai.google.dev/gemini-api/docs/custom-agents) (9 Oct), [coding-agent skills](https://ai.google.dev/gemini-api/docs/coding-agents) (6 Oct), [streaming](https://ai.google.dev/gemini-api/docs/streaming) (23 Sep), [background execution](https://ai.google.dev/gemini-api/docs/background-execution) (21 Oct). Dates are documentation footers, not proof that every account has access.

Venue sources, issuer/date/scope limitations and record-release routes are linked in sections 7–9. Firecrawl can return recently indexed content; successful retrieval is not itself a current-condition certificate. Local SDK/runtime observations were captured on the research date.

Related local specification: [Google API guide](/Users/nihalnihalani/Desktop/Github/SpatialTwin/CLAUDE_BUILD_HANDOFF/GOOGLE_API_GUIDE.md). It already calls for several controls absent from the current implementation; it is guidance, not proof they were executed.
