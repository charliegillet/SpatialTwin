# SpatialTwin — Claude parallel-build handoff

Prepared 23 October 2026. This package contains copy-paste instructions and documentation, not an implemented application. The fixed contributors remain **Nihal, Charlie, Codex and Claude**; Claude's teammates are internal coding agents.

## Start

1. This package lives at `/Users/nihalnihalani/Desktop/Github/SpatialTwin/CLAUDE_BUILD_HANDOFF`. The implementation repository and project root are both `/Users/nihalnihalani/Desktop/Github/SpatialTwin`. Read documentation relative to this package; write application code relative to the repository root.
2. Use Claude Code **2.1.284 or newer**, with access to both requested models. Published availability does not establish this account's access.
3. From the intended repository/workspace, start an **interactive** session:

```sh
cd /Users/nihalnihalani/Desktop/Github/SpatialTwin
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 claude --model claude-opus-5-5 --teammate-mode in-process
```

4. Paste **`prompts/00_CLAUDE_TEAM_LEAD.md` once**. The lead creates the team and dispatches prompts 01–05. Do not start five separate leads or paste every prompt into one conversation.
5. If a separate Codex build is starting, paste **`prompts/06_CODEX_PARALLEL.md`** there. Otherwise give its ownership contract to the existing Codex session. This package does not start or message any session automatically.

Agent Teams are experimental. Headless `claude -p` does not spawn teammates. In-process display avoids tmux setup. Only the lead spawns/manages teammates; no nested teams. Requested per-teammate models must be verified against runtime evidence because provider/org settings and hooks can override them. See [official Agent Teams docs](https://code.claude.com/docs/en/agent-teams) and [model configuration](https://code.claude.com/docs/en/model-config).

## Team

| Prompt | Teammate | Requested model | Exclusive scope |
|---|---|---|---|
| 00 | Lead/integration architect | `claude-opus-5-5` | Claude coordination, contract proposals, integration report |
| 01 | Grounding engineer | `claude-sonnet-5-5` | Direct Argon image adapter and its tests |
| 02 | Managed-agent engineer | `claude-opus-5-5` | Stateful bounded tool investigation and its tests |
| 03 | Proposal/evidence UI engineer | `claude-sonnet-5-5` | Isolated review/evidence components and stories |
| 04 | Integration/docs engineer | `claude-sonnet-5-5` | AI-only fakes, smoke probes, setup and source manifest |
| 05 | Devil's advocate | `claude-opus-5-5` | Adversarial tests and independent review; no implementation edits |

Codex reserves backend state, numerical planner/checker, firmware, serial bridge, physical action executor and shared UI shell. Claude teammates must request interface changes through the lead; they must not fill that dependency by implementing a competing planner or actuator.

## Read in this order

- `plans/PHYSICAL_DEMO_BUILD_PLAN.md`: product, hardware, budget, exact ownership, timing and acceptance.
- `plans/PHYSICAL_DEMO_WIRING.md`: matched electronics and independent position confirmation.
- `GOOGLE_API_GUIDE.md`: direct model versus managed-agent integration rules and source map.
- `CONTRACT_PROPOSAL.md`: proposed interface boundary to freeze with Codex before integration.
- `reference/GOOGLE_SOURCES.json`: official URLs, local snapshots, capture dates and hashes.

`reference/google/` contains the task-relevant Google documentation snapshots and API schema. It is not the entire Google documentation corpus and does not prove a request worked. Preserve source/license notices. Check the relevant official page and pinned SDK before copying an example into code. The local Gemini skills' old model/event lists must not override the current Argon docs.

`plans/PHYSICAL_DEMO_BOARD_TEMPLATE.svg` is an original **illustrative fixture**, not a SHACK15 survey. `PHYSICAL_DEMO_DEVICE_MAP.json` intentionally lacks calibrated servo endpoints and reviewed building capacities. Do not accept it as production solver input.

## Parallelism rules

- Prefer a separate Claude worktree from Codex's checkout, based on an agreed contract commit. Teammates do not automatically have isolated worktrees; give each writer exclusive files.
- Teammates receive their complete brief and document paths; they do not inherit this chat's history.
- Do not change shared dependency locks, entrypoints, root config or contracts concurrently. Leaf owners propose dependencies; the designated integrator applies them once.
- Use the existing repository `/Users/nihalnihalani/Desktop/Github/SpatialTwin`, origin `https://github.com/charliegillet/SpatialTwin.git`. The project root is the repository root. The earlier winners repository is historical source material, not the implementation target; do not create a nested spatialtwin_argon_winner application.
- Preserve existing work. No reset/clean/force-push, broad credential search, fabricated passing tests, simulated live calls or hardware movement without the local operator's concrete approval.
- Keep labeled fixture mode and live mode distinct. Credentials stay server-side and are never printed.

## Success and scope cuts

By hour 1, agree on interfaces. By hour 3, show an actual checked local numerical run and real grounding or explicit unavailable status. By hour 5, prove the manual hardware loop. By hour 7, freeze IDs/topology and choose the reliable vision mode. By hour 10, freeze features and rehearse. These are prototype gates within the prior 13-hour event plan, not a guarantee of completion or authorization to build outside event rules.

Read the plan for the two-minute script and full acceptance matrix. The core distinction is **predicted alternative → operator approval → command acknowledged → endpoint observed → new checked result**. An ACK never establishes gate position.

## New repository bootstrap — 24 October 2026

The target repository initially has no HEAD commit. Record “unborn main” instead of inventing a SHA. Before the first project commit, check remote refs and reconcile any existing remote history without force-pushing. Codex is the single bootstrap writer for shared manifests, configuration and central contracts. Other teammates can research, prepare fixtures and work only in disjoint owned paths in the existing checkout. Create separate worktrees only after an agreed committed baseline exists. A worktree does not copy uncommitted work or ignored credentials.

Root BUILD_PLAN.md is the current execution plan. Use geometry_revision and frontend/ as canonical naming; map_revision and app/ in older planning examples are historical aliases, not competing contracts. Google source snapshots remain dated23October and require the documented actual-account/SDK probes.
