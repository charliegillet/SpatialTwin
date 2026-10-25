# SpatialTwin interface system

This is an operational workspace for reviewing an illustrative tabletop scenario, comparing checked numerical alternatives and inspecting reported hardware state. Preserve the existing dark architectural identity. The spatial model and the operator’s next action carry the visual weight.

## Task and truth

The workflow is **Observe → Review → Compare → Confirm**. Each step has a working navigation target. Image capture, applying a closure, comparing a prediction and approving movement remain separate actions.

**Inspect plan** opens a read-only aggregate schedule; **Scenarios** opens four hypothetical local cases. Both are numerical exploration, never a new observation or a device approval. The printable brief is a saved snapshot, with freshness assessed only at export.

- Demo board means a synthetic image sent to the real Gemini provider when configured.
- Fixture means an explicit offline proposal; Local solver means numerical computation without a Gemini call.
- A completed provider receipt is required for a live-result label. Configuration alone proves no inference.
- Predictions, operator requests, ACK availability and endpoint observations remain visibly distinct.
- Unknown, transit, fault, disconnected and stale states disable unsafe actions; they do not imply a newly checked result.
- Counts describe synthetic modeled floor-transfer crossings. The diagram is not a surveyed venue plan.
- Clear blockages changes scenario availability and preserves P3’s reported position.

## Visual vocabulary

Use the shared tokens in `frontend/src/index.css` rather than adding a separate palette for each panel.

| Role | Value |
| --- | --- |
| Canvas | `#0c0f10` |
| Surface | `#151a1b` |
| Raised surface | `#1c2223` |
| Structural line | `#30383a` |
| Primary text | `#f1f3ef` |
| Secondary text | `#a1ada7` |
| Action / selection / checked flow | `#d3ed9c` |
| Blockage / warning | `#efa28c` |

Use IBM Plex Sans for controls, labels and prose, with IBM Plex Mono for identifiers, times and measured data. Use tabular numerals for changing counts. Main control text is 13–14px, secondary text 12px and metadata generally 11px; tiny legacy labels are removed. Diagram labels may scale with the canvas and have readable native target buttons as an alternative.

Keep panel borders quiet and draw them once. The drawing grid belongs only to the spatial canvas. Accent color communicates actions, selection or status. No decorative motion, staged AI progress, invented occupants or decorative numerical statistics.

## Layout and controls

Desktop uses a labeled side navigation, a compact joined result row, an observation panel beside the larger spatial model, and comparison beside a bounded activity log. The sidebar collapses to icons at intermediate widths and becomes a labeled bottom navigation on narrow screens. Panels stack below 860px; the page supports 320px without a forced body minimum width.

Use consistent 36–40px desktop controls and 44px touch targets. Preserve visible focus. Selecting a model target focuses its review selector; Apply or Cancel returns focus to the triggering target. Escape dismisses the evidence drawer before touching an underlying review or presenter mode.

The primary observation action becomes secondary while a valid proposal awaits Apply. Model thinking settings and raw receipts use progressive disclosure. Critical source, currentness, failure and approval requirements stay visible. Evidence avoids deeply nested disclosures.

Clearing a workflow invalidates outstanding UI request identities. Late responses and errors cannot repopulate the cleared workspace. Preserve a stable analysis action through loading and completion so keyboard focus is not lost.

Capture preparation and provider dispatch use immediate request guards before asynchronous work begins. An earlier completion cannot release a newer request after a source change or reset. Escape acts on the open editor or presenter mode; pressing it elsewhere preserves focus. Pausing the activity stream freezes its displayed snapshot and log announcements while new events remain in the bounded session buffer.

## Research and installed skills

Research used the user-selected Firecrawl CLI on 24 October 2026. The source cache is under ignored `.firecrawl/ui-refresh-*`; the implementation uses these principles rather than copying a product screen.

- [Linear’s interface refresh](https://linear.app/now/behind-the-latest-design-refresh): emphasize the task; quiet navigation and competing chrome.
- [Vercel Geist colors](https://vercel.com/geist/colors): restrained surfaces, consistent interaction states and accessible text roles.
- [IBM Carbon disclosures](https://www.carbondesignsystem.com/building-blocks/core/patterns/disclosures): disclose optional technical detail while retaining required information.
- [Vercel Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines): keyboard, focus, control naming, motion and responsive review.

Installed user-level skills: [Impeccable](https://github.com/pbakaus/impeccable), pinned to `936867543ac2576920d663cc9803597f6044f3ac`, and [web-design-guidelines](https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines). They are development tools, not application runtime dependencies. Impeccable’s Operate guidance applies to this existing workspace; the existing frontend-design skill supplies general craft guidance.

Complementary accessibility, performance and webapp-testing skills, their pins, primary tool sources and the reusable isolated review command are documented in the [UI quality toolkit](docs/ui-toolkit.md).

## Verification

Run `npm test` and `npm run build` in `frontend/`. Native browser review also covers 320/390/768/1440px composition, source selection, narrow camera empty state, keyboard selection/review/apply/cancel, modal Escape, workflow navigation, no-benefit approval blocking and delayed responses arriving after Clear blockages. UI review uses a separate local database with Gemini disabled and simulator hardware; it does not constitute a new live provider or physical-board trial.
