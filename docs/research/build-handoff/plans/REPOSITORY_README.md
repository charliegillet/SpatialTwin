# SpatialTwin

A physical and digital scenario workbench: a judge changes a tabletop floor plan, the system interprets and reviews the change, computes a checked routing result, and demonstrates a sensor-confirmed miniature intervention.

**Implementation repository:** <https://github.com/charliegillet/SpatialTwin>. The project root is this repository. Prepared 24 October 2026 for **Nihal, Charlie, Codex and Claude**.

## Start here

1. Read the current [detailed build plan](BUILD_PLAN.md).
2. Read the [physical demo plan and bill of materials](docs/plans/PHYSICAL_DEMO_BUILD_PLAN.md) and [pin-by-pin wiring guide](docs/plans/PHYSICAL_DEMO_WIRING.md).
3. Start Claude using the [team setup](CLAUDE_BUILD_HANDOFF/START_HERE.md) and [lead prompt](CLAUDE_BUILD_HANDOFF/prompts/00_CLAUDE_TEAM_LEAD.md).
4. Give the parallel Codex session its [build prompt](CLAUDE_BUILD_HANDOFF/prompts/06_CODEX_PARALLEL.md).
5. Freeze shared contracts before either team changes shared application files.

## What is here now

The repository contains planning, hardware fabrication assets, a priced shopping list, separate build prompts and a Google documentation pack. **Application code, firmware, complete solver and live API/device verification have not been implemented here.** The repository initially had no commits; create separate worktrees only after an agreed baseline commit exists.

| Material | Location |
|---|---|
| Current execution plan and phase checks | [BUILD_PLAN.md](BUILD_PLAN.md) |
| Shared agent ownership | [AGENTS.md](AGENTS.md) |
| Claude entry instructions | [CLAUDE.md](CLAUDE.md) |
| Architecture, venue, UI and physical plans | [docs/plans/](docs/plans/) |
| Exact shopping list | [PHYSICAL_DEMO_BOM.csv](docs/plans/PHYSICAL_DEMO_BOM.csv) |
| Printable 24 × 18 inch illustrative board | [SVG template](docs/plans/PHYSICAL_DEMO_BOARD_TEMPLATE.svg) · [preview](docs/plans/PHYSICAL_DEMO_BOARD_PREVIEW.png) |
| Device-map fixture, requiring calibration/review | [PHYSICAL_DEMO_DEVICE_MAP.json](docs/plans/PHYSICAL_DEMO_DEVICE_MAP.json) |
| Seven copy-paste prompts | [CLAUDE_BUILD_HANDOFF/prompts/](CLAUDE_BUILD_HANDOFF/prompts/) |
| Google implementation briefing | [GOOGLE_API_GUIDE.md](CLAUDE_BUILD_HANDOFF/GOOGLE_API_GUIDE.md) |
| 20 official Google pages + OpenAPI | [Source manifest](CLAUDE_BUILD_HANDOFF/reference/GOOGLE_SOURCES.json) · [snapshots](CLAUDE_BUILD_HANDOFF/reference/google/) |
| Portable prompt/documentation package | [CLAUDE_BUILD_HANDOFF.zip](CLAUDE_BUILD_HANDOFF.zip) |
| Imported-file provenance | [IMPORTED_FILES.json](docs/IMPORTED_FILES.json) |

Earlier plans cite `nihalnihalani/winners/spatialtwin_argon_winner` as the original concept source. That is historical reference, not this project's build directory. Root `BUILD_PLAN.md` takes precedence for repository paths and current phase order. Vendor documentation retains its original verification date; compatibility and account access must be tested before implementation claims.

The provided board is explicitly illustrative, not a surveyed SHACK15 blueprint. Synthetic occupants and scenario capacities are separate from venue observations. Results end at finite-rate modeled floor-transfer boundaries; they do not claim full-building evacuation or survival prediction.
