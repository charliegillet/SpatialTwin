# SpatialTwin: Gemini Antigravity Managed Agent Documentation

## 1. Overview and Architecture

In SpatialTwin, the **Managed Antigravity Agent** (`antigravity-preview-09-2026` configured with underlying `gemini-4-argon`) performs autonomous multi-turn investigations of physical floor-plan interventions during tabletop incident drills.

```
       ┌───────────────────────────────┐
       │   Google Cloud Interactions   │
       │  antigravity-preview-09-2026  │
       │       (gemini-4-argon)        │
       └──────────────┬────────────────┘
                      │ requires_action (function_call step)
                      ▼
       ┌───────────────────────────────┐
       │  Local Client Tool Executor   │
       │     (ScenarioService Port)    │
       └──────────────┬────────────────┘
                      │
       ┌──────────────┴───────────────┐
       ▼                              ▼
┌──────────────┐              ┌───────────────┐
│ Fixed Flow   │              │ Independent   │
│ Planner      │              │ Checker       │
│ (NetworkX)   │              │ (Conservation)│
└──────────────┘              └───────────────┘
```

### Key Architectural Invariants
1. **Remote Google Sandboxes Cannot Reach Localhost**: The cloud agent environment does not have direct network access to the laptop's `localhost` or serial ports. All tools are defined as client-executed custom functions where the local client dispatches the request to `ScenarioService`, verifies constraints, and returns a `function_result`.
2. **Strictly Read-Only Solver Tools**: The agent receives tools to inspect the scenario (`get_reviewed_scenario`), evaluate candidates (`evaluate_allowed_alternative`), and compare metrics (`get_checked_comparison`). No motor, servo angle, raw firmware write, or arbitrary shell execution tools are exposed to the AI.
3. **Prose vs. Ledger Separation**: Application UI cards and numerical values are populated exclusively from verified local tool results. The agent's prose is treated as narrative commentary and is never parsed for metrics.
4. **Honest No-Improvement Handling**: If downstream boundary `B2` is blocked, opening miniature gate `P3` produces +0 net gain. The agent evaluates the immutable candidate model and confirms that opening the gate does not manufacture exit capacity.

---

## 2. Model & Agent Configuration

```python
interaction = client.interactions.create(
    agent="antigravity-preview-09-2026",
    agent_config={
        "type": "antigravity",
        "model": "gemini-4-argon",
        "max_total_tokens": 20000,
    },
    environment="remote",
    input=[{"type": "text", "text": bounded_investigation_prompt}],
    tools=TOOL_DEFINITIONS,
)
```

| Parameter | Value | Purpose |
|---|---|---|
| `agent` | `antigravity-preview-09-2026` | Published Antigravity managed agent identity |
| `agent_config.type` | `antigravity` | Agent engine type |
| `agent_config.model` | `gemini-4-argon` | Underlying flagship multimodal reasoning model |
| `agent_config.max_total_tokens` | `20000` | Best-effort total token budget across turns |
| `environment` | `remote` | Google managed execution sandbox |

---

## 3. Allowlisted Client Tools

### Tool 1: `get_reviewed_scenario`
Returns active scenario context, blocked targets, and allowed alternatives:
```json
{
  "type": "function",
  "name": "get_reviewed_scenario",
  "description": "Fetch active reviewed scenario context, blocked portals, and allowed alternatives.",
  "parameters": { "type": "object", "properties": {} }
}
```

### Tool 2: `evaluate_allowed_alternative`
Evaluates an immutable copy of the scenario with the requested alternative:
```json
{
  "type": "function",
  "name": "evaluate_allowed_alternative",
  "description": "Evaluates a named alternative (KEEP_CURRENT or OPEN_P3) on the immutable context snapshot.",
  "parameters": {
    "type": "object",
    "properties": {
      "alternative_id": {
        "type": "string",
        "enum": ["KEEP_CURRENT", "OPEN_P3"],
        "description": "The allowed candidate alternative to evaluate."
      }
    },
    "required": ["alternative_id"]
  }
}
```

### Tool 3: `get_checked_comparison`
Executes an independently verified side-by-side comparison between `KEEP_CURRENT` and `OPEN_P3`:
```json
{
  "type": "function",
  "name": "get_checked_comparison",
  "description": "Runs an independently validated side-by-side comparison between KEEP_CURRENT and OPEN_P3.",
  "parameters": { "type": "object", "properties": {} }
}
```

---

## 4. Multi-Turn Continuation Protocol

When the agent requires tool execution, the API returns `status="requires_action"` with one or more `FunctionCallStep` items.

### Step-by-Step Continuation Loop:
1. Inspect `interaction.steps`. Filter for steps where `step.type == "function_call"`.
2. Extract `call_id = step.id`, `fn_name = step.name`, `fn_args = step.arguments`.
3. Dispatch to local `ScenarioService`. Record execution time in `tool_ledger`.
4. Construct continuation payload:
   ```python
   client.interactions.create(
       agent="antigravity-preview-09-2026",
       previous_interaction_id=interaction.id,
       environment=interaction.environment_id,
       input=[{
           "type": "function_result",
           "name": fn_name,
           "call_id": call_id,
           "result": result_dict,
       }],
   )
   ```
5. Loop terminates when `interaction.status == "completed"` or whole-investigation deadline (30s) expires.

---

## 5. Offline and Benchmark Fallback Mode

If the `GEMINI_API_KEY` is omitted or network access is offline during a presentation rehearsal:
- The adapter switches to **Deterministic Tool Loop Mode**.
- The exact same tool definitions are executed in Python against `ScenarioService`.
- A 100% genuine `ToolCallLedgerEntry` list is generated with real solver millisecond timings.
- The UI visibly displays `Argon Fixture` to ensure zero fabrication of provider connectivity.
