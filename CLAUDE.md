# Claude entry point

Read `AGENTS.md`, `README.md` and `docs/plans/demo-v2-contracts.md` first. The original build handoff (`docs/research/build-handoff/START_HERE.md`, `docs/research/build-handoff/plans/BUILD_PLAN.md`) is historical background in `docs/research/`. The implementation root is this repository, not the historical winners source or the documentation package.

Use `docs/research/build-handoff/prompts/00_CLAUDE_TEAM_LEAD.md` when the user asks to start the team. It specifies an Opus 5.5 lead, five Opus/Sonnet 5.5 teammates, exclusive ownership and an independent devil's advocate. Verify actual CLI/model access; do not claim a team exists unless it was created.

The seven prompt files and Google snapshots are already local. Read the relevant docs instead of having every teammate re-fetch the entire corpus. Current examples require actual SDK/account probes before claiming compatibility. Core Google source verification was on 23 October 2026; this repository handoff was prepared 24 October.

Codex owns shared state, central contracts, planner/checker, firmware, serial and shared UI shell. Claude implements bounded AI adapters and isolated review/evidence components. Shared files and lockfiles have one writer. `docs/research/build-handoff/plans/BUILD_PLAN.md` records the original phase gates and bootstrap constraints for the initially empty repository.
