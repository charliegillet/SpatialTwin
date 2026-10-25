# UI quality toolkit

Researched with Firecrawl and installed on 24 October 2026. This extends the existing SpatialTwin interface; it does not replace the application with a template or add a second UI framework.

## Installed skills

These are user-level development instructions in `~/.codex/skills/`, not packages shipped to application users. Restart Codex to have newly installed skills discovered automatically. The complete upstream reference folders were retained.

| Skill | Purpose | Source and installation pin |
| --- | --- | --- |
| Accessibility | Rendered accessibility checks, keyboard, focus, state and live announcements | [Addy Osmani web-quality-skills](https://github.com/addyosmani/web-quality-skills/tree/afa8da942115f2961fdbfa80807ea0b232ff6c00/skills/accessibility), `afa8da942115f2961fdbfa80807ea0b232ff6c00` |
| Performance | Measure loading and interaction costs before optimizing | [Same repository, performance](https://github.com/addyosmani/web-quality-skills/tree/afa8da942115f2961fdbfa80807ea0b232ff6c00/skills/performance), same pin |
| Web application testing | Inspect real rendered states, exercise flows and retain browser evidence | [Anthropic skills](https://github.com/anthropics/skills/tree/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/webapp-testing), `dbd4588f9e1033efb41dad4bef2f7947c8993d44` |

Addy's collection is an unofficial personal project. Anthropic's testing skill is from its official repository. Neither installation is proof that SpatialTwin passes an audit. Existing Impeccable, frontend-design, web-design-guidelines and vercel-react-best-practices cover visual craft, interface conventions and React structure. Their design application is recorded in [DESIGN.md](../DESIGN.md).

The testing skill's generic `networkidle` example needs adaptation: this app keeps an SSE connection open. Wait for the expected checked result and enabled controls instead. Browser actions must follow the available browser tool's rules. No upstream helper script is needed to run the review tool below.

## Repeatable local review

After the standard backend virtual environment and frontend dependencies are installed:

```bash
cd frontend
npm run review:ui
```

Open `http://127.0.0.1:8031/__review`. Use `npm run review:ui -- --help` for options, or `-- --delay-seconds 3` to make fixture/local pending states easier to inspect. The command builds the current frontend first.

The review server runs the actual frontend and local numerical solver with a fresh isolated SQLite database. It binds only to loopback, disables provider credentials in its own process, blocks live AI requests, and uses simulated hardware. It leaves the ordinary backend and its saved state alone. The frame is labeled as a review fixture; a numerical result is still a local checked computation. No physical-board or live-provider verification is implied.

The review page offers 320, 390, 768 and 1440 CSS-pixel frames with realistic viewport heights. Its measurements flag document overflow, small visible text and possible clipped content. Those are inspection aids: intentional diagram clipping and bounded scroll areas need judgment.

**Run accessibility audit** executes the pinned local `axe-core` development dependency against the currently displayed frame, including an open editor or dialog. Reports include violations, checks requiring manual review, the viewport and the checked state. JSON reports are saved under ignored `runtime/ui-toolkit/`; use the export control for a portable copy. Axe is injected only by the review wrapper and is absent from the normal production frontend bundle.

### Review sequence

1. Scan the initial workspace at desktop and narrow widths. Check visible sources and currentness labels.
2. Select P1/P2/B2 by keyboard, review, Apply and Cancel. Confirm focus returns to the triggering control.
3. Open the evidence and device dialogs; exercise Tab and Escape. Escape should dismiss the current layer and preserve accepted scenario state.
4. Load an explicit fixture, then run the local comparison. Scan ready, pending, completed, failed and stale states where available. Clear blockages while delayed work is pending and confirm late responses stay discarded.
5. Pause the activity stream. New events should be recorded without moving the displayed list or producing log announcements; resume to show buffered events.
6. Inspect a no-improvement case and confirm movement approval stays unavailable. Do not use a physical-device approval as a UI test.

A clean automated scan covers only the tested DOM state and axe's rules. Complete keyboard, screen-reader, 200% zoom, reduced-motion, contrast and real touch-device reviews before making accessibility conformance claims.

## Performance tools and limits

[Chrome Lighthouse](https://developer.chrome.com/docs/lighthouse/overview) and Chrome's performance trace are useful optional tools for a local build. No paid service, browser extension or public deployment is necessary. Record the exact route/state, browser/tool version, viewport, network/CPU settings and cache state. Use at least three equivalent runs and report median plus range before claiming a speed improvement.

This localhost project has no production CrUX or aggregated real-user evidence. Treat field performance as unavailable. The build reports compressed bundle sizes; these are asset measurements, not LCP, INP or real-user results. Storybook, a new component library, analytics and a second browser framework were not added without a concrete need.

## Dependency review

`axe-core` is pinned to `4.14.0` as a development dependency. The installation audit reports three moderate findings in the existing Tailwind 3 development chain, all rooted in `postcss-selector-parser <7.1.6`. Tailwind's current `v3-lts` release (`3.4.19`) and `postcss-nested 6.2.0` require parser 6.x; no compatible patched release was found. The [upstream advisory](https://github.com/advisories/GHSA-rj75-hqrm-r3gf) concerns synchronously parsing attacker-controlled CSS selectors and excludes ordinary build-time use of trusted sources. SpatialTwin's frontend build processes repository CSS. No forced parser-major override or Tailwind 4 migration was applied. Recheck upstream before introducing any untrusted CSS parsing.

## Verification on 24 October 2026

The production build and all **23 frontend tests** passed. Ten saved axe scans of the final build returned **zero automated violations**: the initial workspace at 320/390/768/1440px, pending local comparison, pending and completed fixture interpretation, populated activity, the simulator tab and the evidence dialog. The initial four sizes had no measured horizontal overflow or visible clipping warnings. The evidence dialog had no incomplete rules; the other states retained one incomplete color-contrast rule over diagram or image layers, requiring manual inspection.

Browser checks confirmed editor and presenter focus return, no focus jump from an unrelated Escape, actual paused-event buffering/resume, disabled no-benefit approval, fixture source labels and discarded late analysis after clearing. Scan evidence led to fixes for visible-name mismatches, unsupported ARIA labels and keyboard access to a scrollable event log. Synchronous guards cover image preparation and request dispatch; six added behavioral tests cover request ownership and paused activity.

The final index SHA-256 was `1fc41c4a9bd613be1b079700f53f3ee751a962a2dade35e1beb3e1a259cfebdb`. Each report records the actual iframe build hash and timestamp, including after rebuilding and reloading. Local evidence is in `runtime/ui-toolkit/verification.json` and `runtime/ui-toolkit/reports/`. Compressed build assets were 100.44 kB JavaScript and 17.56 kB CSS; these are not speed or real-user measurements.

The running demo retained 117 crossings, three remaining occupants, scenario revision 2 and physical revision 4 with simulated P3 open. This review made no Gemini inference or physical movement requests. Screen-reader, 200% zoom, real touch-device and production field-performance verification remain outside this pass.

## Sources

- [Deque axe-core](https://github.com/dequelabs/axe-core): maintained scanner and rule coverage.
- [Playwright accessibility testing](https://playwright.dev/docs/accessibility-testing): audit the rendered state after interactions and combine automation with manual checks.
- [Lighthouse overview](https://developer.chrome.com/docs/lighthouse/overview): local browser and CLI audits.
- [WCAG 2.2 quick reference](https://www.w3.org/WAI/WCAG22/quickref/): criteria for manual verification.

Firecrawl source snapshots and candidate assessments are cached in ignored `.firecrawl/ui-toolkit-*`. Pins above make the selected instructions reviewable without depending on that local cache.
