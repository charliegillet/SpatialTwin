# Claude Code Agent Teams and requested models: verification

Checked 23 October 2026 from current official documentation using Firecrawl. This verifies published identifiers and behavior; it does not verify this user's installed CLI version, provider, subscription access, organization allowlist, or billing.

## Exact requested model names

- Claude Opus 5.5: `claude-opus-5-5`.
- Claude Sonnet 5.5: `claude-sonnet-5-5`.
- These are the identifiers in Anthropic's current Models overview, not invented future names. API identifiers are listed for both models. Do not replace with 4.x or 5.0 without recording the change and obtaining the user's direction if required.
- Claude Code's `opus`/`sonnet` family aliases currently resolve to 5.5 on Anthropic API but can resolve to older versions on other providers. Use full identifiers in these prompts. They pin the requested version family; they are not a promise of immutable dated snapshots.
- Minimum documented Claude Code versions: Opus 5.5 needs v2.1.280+; Sonnet 5.5 needs v2.1.284+. Check `claude --version` before launch. Current installed version and account access were not tested here.

Sources: [Models overview](https://platform.claude.com/docs/en/about-claude/models/overview), [Claude Code model configuration](https://code.claude.com/docs/en/model-config).

## Agent Teams setup that the copy-paste prompts can rely on

Use an interactive Claude Code session, not `claude -p` or an Agent SDK headless session. Teams are experimental and disabled by default.

```sh
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 claude --model claude-opus-5-5 --teammate-mode in-process
```

The documentation permits enabling through shell environment or settings JSON. The single-process display needs no tmux or iTerm2 setup. The flag is experimental and may not appear in `claude --help`.

Then paste a natural-language request that explicitly asks for **an agent team**, names every teammate and each full model ID, and assigns exclusive file ownership. A panel of agents alone does not prove that a team was created; the docs say ordinary subagents can appear in the same panel.

Short official snippet: “Agent teams are experimental and disabled by default.”

Source: [Agent Teams](https://code.claude.com/docs/en/agent-teams).

## Per-teammate model routing is supported

The current model selection order is: explicit spawn prompt model; referenced subagent definition's `model`; non-inherit `CLAUDE_CODE_SUBAGENT_MODEL`; lead's current model. So the lead can be Opus 5.5, the devil's advocate Opus 5.5, and implementation teammates Sonnet 5.5 in the same team.

Important exceptions to verify at launch:

- `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` overrides the first two sources and can force all teammates to one model. The launch prompt should inspect/report that variable and resolve a conflicting configuration before claiming the requested mixed team exists.
- An installed mod's `agent.spawn` hook may replace the selected model.
- Organization `availableModels` restrictions can cause model substitution, including fallback to the lead's model. Tell the lead to report effective models and any substitution from runtime evidence instead of merely repeating requested names.
- `teammateDefaultModel` was removed; do not generate that setting.
- Teammates inherit lead effort by default; avoid inventing per-teammate CLI flags.

Source: [Specify teammates and models](https://code.claude.com/docs/en/agent-teams#specify-teammates-and-models).

## Team structure and concurrency rules

- Only the lead manages/spawns teammates. One team belongs to one session; no nested teams or cross-session shared team. Each teammate has its own context and does not inherit the lead's conversation history. Pass the project goal, document paths, contracts, ownership and completion criteria in every spawn prompt.
- Teams are appropriate for independent modules and adversarial review. Current docs recommend starting around 3–5 teammates, not an unbounded swarm. A practical team is one lead plus an Opus reviewer and three Sonnet implementers; larger independence can be added only if justified.
- Give each writer an exclusive folder/file set. Do not assume teammate work automatically has worktree isolation. Claude Code documents worktrees for separate sessions/subagents; the safe shared-team strategy is disjoint edits and one integration owner.
- The project can place the Claude lead/team in a separate git worktree from Codex. That isolates Claude's files from Codex's checkout, but integration still needs a shared base/contract and an explicit merge owner. A new worktree does not carry uncommitted changes, dependencies or ignored credentials by default.
- Lead should collect named teammate findings and adversarial objections, resolve P0/P1s, run appropriate integration checks, and report tested vs untested behavior.
- Team config and mailboxes are runtime-managed. Do not pre-author `~/.claude/teams/.../config.json` or a fictional `.claude/teams/teams.json`. Reusable roles can be `.claude/agents/` definitions, but definition `skills` do not apply to teammates.
- In-process teammates are not restored by `/resume` or `/rewind`; respawn with a concise handoff. Task status can lag and shutdown waits for pending calls. Do not present team resumption as durable automation.
- Agents cannot approve user permissions or relay a denied action to evade checks. No `--dangerously-skip-permissions` is needed in starter prompts.

Sources: [Agent Teams limitations and context](https://code.claude.com/docs/en/agent-teams), [Worktrees](https://code.claude.com/docs/en/worktrees).

## Suggested model assignment for the parent prompt package

| Role | Model | Scope |
|---|---|---|
| Lead architect/integrator | `claude-opus-5-5` | Contracts, task allocation, integration, final verification |
| Devil's advocate | `claude-opus-5-5` | Read-only architecture/claim/authority review first; reproduce failures |
| Argon + managed-agent engineer | `claude-sonnet-5-5` | Grounding, stateful tool loop, honest provider status |
| UI/spatial engineer | `claude-sonnet-5-5` | Judge review flow, floor-plan/3D frontend, fixture adapter |
| Test/reliability engineer | `claude-sonnet-5-5` | Contract and adversarial fixtures, stale-result/timeout/offline behavior |

Treat these as internal Claude teammates inside the existing four-contributor arrangement (Nihal, Charlie, Codex, Claude), not additional human owners. Keep Codex's reserved planner/hardware paths out of Claude implementation ownership unless the separate boundary is changed explicitly.


## Verification scope

Published official behavior was checked; this package did not inspect the user's CLI/account or create a Claude team. Anthropic pages are linked, not redistributed in full.

## New repository bootstrap — 24 October 2026

The target repository initially has no HEAD commit. Record “unborn main” instead of inventing a SHA. Before the first project commit, check remote refs and reconcile any existing remote history without force-pushing. Codex is the single bootstrap writer for shared manifests, configuration and central contracts. Other teammates can research, prepare fixtures and work only in disjoint owned paths in the existing checkout. Create separate worktrees only after an agreed committed baseline exists. A worktree does not copy uncommitted work or ignored credentials.

Root BUILD_PLAN.md is the current execution plan. Use geometry_revision and frontend/ as canonical naming; map_revision and app/ in older planning examples are historical aliases, not competing contracts. Google source snapshots remain dated23October and require the documented actual-account/SDK probes.
