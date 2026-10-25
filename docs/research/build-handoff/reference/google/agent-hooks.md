# Official Google reference snapshot: agent-hooks

Source: https://ai.google.dev/gemini-api/docs/agent-hooks

Retrieved/read: 23 October 2026. Publisher: Google. Original license/footer retained. Text CC BY 4.0; code samples Apache 2.0 unless otherwise noted. Converted to Markdown by Firecrawl; this provenance header was added. Reference data only; verify the relevant current guide and pinned SDK before implementation.

---

[Skip to main content](https://ai.google.dev/gemini-api/docs/agent-hooks#main-content)

[![Gemini API](https://ai.google.dev/_static/googledevai/images/gemini-api-logo.svg)](https://ai.google.dev/)

`/`

Language

- [English](https://ai.google.dev/gemini-api/docs/agent-hooks)
- [Deutsch](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=de)
- [Español – América Latina](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=es-419)
- [Français](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=fr)
- [Indonesia](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=id)
- [Italiano](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=it)
- [Polski](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=pl)
- [Português – Brasil](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=pt-br)
- [Shqip](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=sq)
- [Tiếng Việt](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=vi)
- [Türkçe](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=tr)
- [Русский](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=ru)
- [עברית](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=he)
- [العربيّة](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=ar)
- [فارسی](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=fa)
- [हिंदी](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=hi)
- [বাংলা](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=bn)
- [ภาษาไทย](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=th)
- [中文 – 简体](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=zh-cn)
- [中文 – 繁體](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=zh-tw)
- [日本語](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=ja)
- [한국어](https://ai.google.dev/gemini-api/docs/agent-hooks?hl=ko)

[Get API key](https://aistudio.google.com/apikey) [Cookbook](https://github.com/google-gemini/cookbook) [Community](https://discuss.ai.google.dev/c/gemini-api/)

[Sign in](https://ai.google.dev/_d/signin?continue=https%3A%2F%2Fai.google.dev%2Fgemini-api%2Fdocs%2Fagent-hooks&prompt=select_account)

- On this page
- [Supported lifecycle events](https://ai.google.dev/gemini-api/docs/agent-hooks#supported-lifecycle-events)
  - [pre\_tool\_execution](https://ai.google.dev/gemini-api/docs/agent-hooks#pre-tool-execution)
  - [post\_tool\_execution](https://ai.google.dev/gemini-api/docs/agent-hooks#post-tool-execution)
- [Configuration discovery](https://ai.google.dev/gemini-api/docs/agent-hooks#configuration-discovery)
  - [hooks.json schema](https://ai.google.dev/gemini-api/docs/agent-hooks#hooks-json-schema)
  - [Matcher syntax and rules](https://ai.google.dev/gemini-api/docs/agent-hooks#matcher-syntax)
- [Handler types](https://ai.google.dev/gemini-api/docs/agent-hooks#handler-types)
  - [Command hooks](https://ai.google.dev/gemini-api/docs/agent-hooks#command-hooks)
  - [HTTP hooks](https://ai.google.dev/gemini-api/docs/agent-hooks#http-hooks)
- [How the runtime handles decisions and failures](https://ai.google.dev/gemini-api/docs/agent-hooks#execution-and-failure-semantics)
- [Common use cases](https://ai.google.dev/gemini-api/docs/agent-hooks#common-use-cases)
  - [Multi-turn recovery for data privacy and compliance](https://ai.google.dev/gemini-api/docs/agent-hooks#data-privacy-recovery)
  - [External audit logging and telemetry](https://ai.google.dev/gemini-api/docs/agent-hooks#external-audit-logging)
- [Limitations](https://ai.google.dev/gemini-api/docs/agent-hooks#limitations)
- [What's next](https://ai.google.dev/gemini-api/docs/agent-hooks#whats-next)

Gemini 4 Argon is now available. [Try it out](https://aistudio.google.com/prompts/new_chat?model=gemini-4-argon).


- [Home](https://ai.google.dev/)
- [Gemini API](https://ai.google.dev/gemini-api)
- [Docs](https://ai.google.dev/gemini-api/docs)

Was this helpful?



 Send feedback



# Hooks

- On this page
- [Supported lifecycle events](https://ai.google.dev/gemini-api/docs/agent-hooks#supported-lifecycle-events)
  - [pre\_tool\_execution](https://ai.google.dev/gemini-api/docs/agent-hooks#pre-tool-execution)
  - [post\_tool\_execution](https://ai.google.dev/gemini-api/docs/agent-hooks#post-tool-execution)
- [Configuration discovery](https://ai.google.dev/gemini-api/docs/agent-hooks#configuration-discovery)
  - [hooks.json schema](https://ai.google.dev/gemini-api/docs/agent-hooks#hooks-json-schema)
  - [Matcher syntax and rules](https://ai.google.dev/gemini-api/docs/agent-hooks#matcher-syntax)
- [Handler types](https://ai.google.dev/gemini-api/docs/agent-hooks#handler-types)
  - [Command hooks](https://ai.google.dev/gemini-api/docs/agent-hooks#command-hooks)
  - [HTTP hooks](https://ai.google.dev/gemini-api/docs/agent-hooks#http-hooks)
- [How the runtime handles decisions and failures](https://ai.google.dev/gemini-api/docs/agent-hooks#execution-and-failure-semantics)
- [Common use cases](https://ai.google.dev/gemini-api/docs/agent-hooks#common-use-cases)
  - [Multi-turn recovery for data privacy and compliance](https://ai.google.dev/gemini-api/docs/agent-hooks#data-privacy-recovery)
  - [External audit logging and telemetry](https://ai.google.dev/gemini-api/docs/agent-hooks#external-audit-logging)
- [Limitations](https://ai.google.dev/gemini-api/docs/agent-hooks#limitations)
- [What's next](https://ai.google.dev/gemini-api/docs/agent-hooks#whats-next)

Hooks let you run custom scripts or external HTTP requests right before or after the agent executes code or modifies files inside its remote sandbox. Use hooks to extend the agent loop with automated guardrails and background workflows, such as:

- **Enforcing safety and access guardrails** before high-risk shell commands or restricted file reads execute.
- **Automating data pipeline transformations** right after an agent creates or modifies files.
- **Streaming enterprise audit telemetry** to external monitoring systems after tool execution.


[Python](https://ai.google.dev/gemini-api/docs/agent-hooks#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-hooks#javascript)[Java](https://ai.google.dev/gemini-api/docs/agent-hooks#java)[Go](https://ai.google.dev/gemini-api/docs/agent-hooks#go)[REST](https://ai.google.dev/gemini-api/docs/agent-hooks#rest)More

```
import json
from google import genai

client = genai.Client()

hooks_config = {
    "security-gate": {
        "pre_tool_execution": [\
            {\
                "matcher": "code_execution",\
                "hooks": [\
                    {\
                        "type": "command",\
                        "command": "python3 /.agents/hooks-scripts/gate.py",\
                        "timeout": 10,\
                    }\
                ],\
            }\
        ]
    }
}

gate_script = """#!/usr/bin/env python3
import sys, json
data = json.load(sys.stdin)
cmd = str(data.get("tool_call", {}).get("args", {}))
if "rm -rf" in cmd:
    print(json.dumps({"decision": "deny", "reason": "Destructive command blocked by security gate."}))
else:
    print(json.dumps({"decision": "allow"}))
"""

interaction = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="Run `rm -rf /tmp/forbidden` using code_execution.",
    tools=[{"type": "code_execution"}],
    environment={
        "type": "remote",
        "sources": [\
            {\
                "type": "inline",\
                "target": ".agents/hooks.json",\
                "content": json.dumps(hooks_config, indent=2),\
            },\
            {\
                "type": "inline",\
                "target": ".agents/hooks-scripts/gate.py",\
                "content": gate_script,\
            },\
        ],
    },
)
print(interaction.output_text)
```

```
import { GoogleGenAI } from "@google/genai";

const client = new GoogleGenAI({});

const hooksConfig = {
    "security-gate": {
        pre_tool_execution: [\
            {\
                matcher: "code_execution",\
                hooks: [\
                    {\
                        type: "command",\
                        command: "python3 /.agents/hooks-scripts/gate.py",\
                        timeout: 10,\
                    },\
                ],\
            },\
        ],
    },
};

const gateScript = `#!/usr/bin/env python3
import sys, json
data = json.load(sys.stdin)
cmd = str(data.get("tool_call", {}).get("args", {}))
if "rm -rf" in cmd:
    print(json.dumps({"decision": "deny", "reason": "Destructive command blocked by security gate."}))
else:
    print(json.dumps({"decision": "allow"}))
`;

const interaction = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "Run `rm -rf /tmp/forbidden` using code_execution.",
    tools: [{ type: "code_execution" }],
    environment: {
        type: "remote",
        sources: [\
            {\
                type: "inline",\
                target: ".agents/hooks.json",\
                content: JSON.stringify(hooksConfig, null, 2),\
            },\
            {\
                type: "inline",\
                target: ".agents/hooks-scripts/gate.py",\
                content: gateScript,\
            },\
        ],
    },
});
console.log(interaction.output_text);
```

```
import com.google.genai.Client;
import com.google.genai.gaos.models.interactions.AgentOption;
import com.google.genai.gaos.models.interactions.CodeExecution;
import com.google.genai.gaos.models.interactions.CreateAgentInteraction;
import com.google.genai.gaos.models.interactions.CreateAgentInteractionEnvironment;
import com.google.genai.gaos.models.interactions.Environment;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;
import com.google.genai.gaos.models.interactions.Source;
import com.google.genai.gaos.models.interactions.SourceType;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import java.util.List;

Client client = new Client();

String hooksConfig = """
{
  "security-gate": {
    "pre_tool_execution": [\
      {\
        "matcher": "code_execution",\
        "hooks": [\
          {\
            "type": "command",\
            "command": "python3 /.agents/hooks-scripts/gate.py",\
            "timeout": 10\
          }\
        ]\
      }\
    ]
  }
}
""";

String gateScript = "#!/usr/bin/env python3\n"
    + "import sys, json\n"
    + "data = json.load(sys.stdin)\n"
    + "cmd = str(data.get(\"tool_call\", {}).get(\"args\", {}))\n"
    + "if \"rm -rf\" in cmd:\n"
    + "    print(json.dumps({\"decision\": \"deny\", \"reason\": \"Destructive command blocked by security gate.\"}))\n"
    + "else:\n"
    + "    print(json.dumps({\"decision\": \"allow\"}))\n";

Environment env = Environment.builder()
    .sources(List.of(
        Source.builder()
            .type(SourceType.INLINE)
            .target(".agents/hooks.json")
            .content(hooksConfig)
            .build(),
        Source.builder()
            .type(SourceType.INLINE)
            .target(".agents/hooks-scripts/gate.py")
            .content(gateScript)
            .build()
    ))
    .build();

CreateAgentInteraction params = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("Run `rm -rf /tmp/forbidden` using code_execution."))
    .tools(List.of(CodeExecution.builder().build()))
    .environment(CreateAgentInteractionEnvironment.of(env))
    .build();

Interaction interaction = client.interactions.create(CreateInteractionRequestBody.of(params)).interaction().get();
System.out.println(interaction.outputText().orElse(""));
```

```
package main

import (
    "context"
    "fmt"
    "log"

    "google.golang.org/genai"
    "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    hooksConfig := `{
  "security-gate": {
    "pre_tool_execution": [\
      {\
        "matcher": "code_execution",\
        "hooks": [\
          {\
            "type": "command",\
            "command": "python3 /.agents/hooks-scripts/gate.py",\
            "timeout": 10\
          }\
        ]\
      }\
    ]
  }
}`

    gateScript := `#!/usr/bin/env python3
import sys, json
data = json.load(sys.stdin)
cmd = str(data.get("tool_call", {}).get("args", {}))
if "rm -rf" in cmd:
    print(json.dumps({"decision": "deny", "reason": "Destructive command blocked by security gate."}))
else:
    print(json.dumps({"decision": "allow"}))
`

    env := interactions.Environment{
        Sources: []interactions.Source{
            {
                Type:    interactions.SourceTypeInline.ToPointer(),
                Target:  genai.Ptr(".agents/hooks.json"),
                Content: genai.Ptr(hooksConfig),
            },
            {
                Type:    interactions.SourceTypeInline.ToPointer(),
                Target:  genai.Ptr(".agents/hooks-scripts/gate.py"),
                Content: genai.Ptr(gateScript),
            },
        },
    }

    res, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{
        Body: operations.NewCreateInteractionRequestBody(interactions.CreateAgentInteraction{
            Agent:       interactions.AgentOption("antigravity-preview-09-2026"),
            Input:       interactions.NewInteractionsInput("Run `rm -rf /tmp/forbidden` using code_execution."),
            Tools:       []interactions.Tool{interactions.NewTool(interactions.CodeExecution{})},
            Environment: genai.Ptr(interactions.NewCreateAgentInteractionEnvironment(env)),
        }),
    })
    if err != nil {
        log.Fatal(err)
    }
    if res.Interaction.OutputText != nil {
        fmt.Println(*res.Interaction.OutputText)
    }
}
```

```
curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions" \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -d '{
      "agent": "antigravity-preview-09-2026",
      "input": [{"type": "text", "text": "Run `rm -rf /tmp/forbidden` using code_execution."}],
      "tools": [{"type": "code_execution"}],
      "environment": {
          "type": "remote",
          "sources": [\
              {\
                  "type": "inline",\
                  "target": ".agents/hooks.json",\
                  "content": "{\"security-gate\": {\"pre_tool_execution\": [{\"matcher\": \"code_execution\", \"hooks\": [{\"type\": \"command\", \"command\": \"python3 /.agents/hooks-scripts/gate.py\", \"timeout\": 10}]}]}}"\
              },\
              {\
                  "type": "inline",\
                  "target": ".agents/hooks-scripts/gate.py",\
                  "content": "#!/usr/bin/env python3\nimport sys, json\ndata = json.load(sys.stdin)\ncmd = str(data.get(\"tool_call\", {}).get(\"args\", {}))\nif \"rm -rf\" in cmd:\n    print(json.dumps({\"decision\": \"deny\", \"reason\": \"Destructive command blocked by security gate.\"}))\nelse:\n    print(json.dumps({\"decision\": \"allow\"}))\n"\
              }\
          ]
      }
  }'
```

## Supported lifecycle events

Hooks support 2 events inside the sandbox:

| Event | When it fires | What it does |
| --- | --- | --- |
| `pre_tool_execution` | Right before a tool runs | Can approve (`allow`) or block (`deny`) the tool before it executes. When blocked, the model sees your rejection reason and adapts. |
| `post_tool_execution` | Right after a tool finishes | Runs follow-up tasks like formatting code, running unit tests, or logging telemetry. Cannot block or undo completed actions. |

### `pre_tool_execution`

Fires right before a tool executes. Your script reads the tool call details from `stdin` and outputs its decision JSON (`allow` or `deny`) to `stdout`.

**Input payload (`stdin`):**

```
{
  "tool_call": {
    "name": "code_execution",
    "args": {
      "code": "rm -rf /tmp/forbidden",
      "language": "bash"
    }
  },
  "environment_id": "env_xyz789"
}
```

**Output response (`stdout`):**

To approve the tool call:

```
{
  "decision": "allow"
}
```

To block the tool call and return feedback to the model:

```
{
  "decision": "deny",
  "reason": "Destructive command blocked by security gate."
}
```

When a hook denies a command, the tool call is skipped immediately. The agent sees an error result containing your rejection reason right inside its current turn. The model can then self-correct by choosing an alternative command or explaining the block to the user.

If your script outputs unrecognized JSON, plain text, or anything other than `{"decision": "deny"}`, the runtime treats the response as an approval (`allow`).

### `post_tool_execution`

Fires right after a tool completes. Your script reads the execution details and any error status from `stdin`.

**Input payload (`stdin`):**

```
{
  "tool_call": {
    "name": "code_execution",
    "args": {
      "code": "python3 /workspace/app.py",
      "language": "bash"
    }
  },
  "environment_id": "env_xyz789"
}
```

If a shell command prints errors to standard error (`stderr`) or a filesystem operation fails, an `"error"` field containing the error text is included in the payload. When the command succeeds without errors, the `"error"` field is omitted entirely.

**Output response (`stdout`):**

```
{}
```

Because post-tool hooks run strictly for background tasks like code formatting or logging, the runtime ignores any decision values returned on `stdout`.

## Configuration discovery

The runtime automatically discovers hook definitions from `.agents/hooks.json` or `/.agents/hooks.json` inside the sandbox environment. You can provide `hooks.json` alongside your custom scripts using any supported [environment source](https://ai.google.dev/gemini-api/docs/agent-environment#mount_from_a_source):

- **Repository mount**: A Git repository containing `.agents/hooks.json` alongside `AGENTS.md`.
- **Cloud Storage (`gcs`)**: A GCS bucket containing `hooks.json` copied into the environment.
- **Inline sources**: Raw JSON string and script contents passed in `environment.sources` when calling `client.interactions.create`.

### `hooks.json` schema

A `hooks.json` file groups event definitions (`pre_tool_execution` or `post_tool_execution`) under custom names. You can enable or disable each group independently:

```
{
  "security-gate": {
    "enabled": true,
    "pre_tool_execution": [\
      {\
        "matcher": "code_execution",\
        "hooks": [\
          {\
            "type": "command",\
            "command": "python3 /.agents/hooks-scripts/gate.py",\
            "timeout": 10\
          }\
        ]\
      }\
    ]
  },
  "auto-format": {
    "post_tool_execution": [\
      {\
        "matcher": "*",\
        "hooks": [\
          {\
            "type": "command",\
            "command": "python3 /.agents/hooks-scripts/auto_lint.py",\
            "timeout": 15\
          }\
        ]\
      }\
    ]
  }
}
```

### Matcher syntax and rules

Each rule group in `hooks.json` defines when and how handlers fire using the `matcher` and `hooks` properties:

| Field | Type | Description |
| --- | --- | --- |
| `enabled` | `boolean` | Optional. Set to `false` to disable the group (`true` by default). |
| `matcher` | `string` | Regular expression pattern matching target tool names inside the container. |
| `hooks` | `array` | Ordered list of handler definitions (`command` or `http`). Handlers run sequentially in declaration order. |

#### How regex evaluation works

When the agent invokes a tool inside the sandbox, the runtime evaluates the tool's container name against your `matcher` pattern using standard RE2 regular expressions. If the regex matches the tool name, all handlers in the `hooks` array execute in order. If multiple rule groups match the same tool, all corresponding handler arrays run.

You can target any built-in container tool name: code execution (`code_execution`) or filesystem operations (`view_file`, `write_to_file`, `replace_file_content`, `list_dir`, and `delete_file`).

#### Common matcher expressions

- `"code_execution"`: Exact string match for shell commands and script executions.
- `"write_to_file"`: Exact match for filesystem file creation and disk writes.
- `"view_file|write_to_file"`: Pipe separation matches multiple specific tool names in a single rule.
- `".*_file"`: Regex wildcard matching any tool ending in `_file` (such as `view_file`, `write_to_file`, or `delete_file`). This covers only part of the filesystem toolset, `replace_file_content` and `list_dir` do not end in `_file`, so name them explicitly when you need them. Standard RE2 regular expressions require `.*`; simple shell globs like `*_file` are invalid regex syntax and will fail to match.
- `".*"` or `"*"` or `""`: Catch-all pattern that intercepts every single tool call inside the container.

## Handler types

### Command hooks

Command hooks execute a shell command or script inside the sandbox. The script receives the event JSON on `stdin` and outputs its decision JSON on `stdout`.

| Field | Type | Description |
| --- | --- | --- |
| `type` | `string` | Must be `"command"`. |
| `command` | `string` | Command line to run inside the sandbox (for example, `python3 /.agents/hooks-scripts/gate.py`). |
| `timeout` | `integer` | Timeout in seconds. Default: `30`. |

### HTTP hooks

HTTP hooks send the event JSON as a POST request to an external HTTPS URL directly from inside the sandbox network. The target server returns its decision in the HTTP response body using the exact same JSON format (`{"decision": "allow"}` or `{"decision": "deny", "reason": "..."}`).

| Field | Type | Description |
| --- | --- | --- |
| `type` | `string` | Must be `"http"`. |
| `url` | `string` | External HTTPS endpoint to POST the event payload to. |
| `headers` | `object` | Optional key-value pairs for non-sensitive custom headers (such as `{"X-Event-Source": "agent-sandbox"}`). For authentication, use a [credential](https://ai.google.dev/gemini-api/docs/agent-credentials) on the network allowlist instead. |
| `timeout` | `integer` | Timeout in seconds. Default: `30`. |

#### Egress proxy and token transformation

Because HTTP hooks execute directly from inside the sandbox network namespace, outgoing requests pass through the transparent egress proxy. This architecture gives you 2 critical security advantages:

- **Network allowlisting:** Target endpoints must be explicitly permitted in your environment's `network.allowlist`. Loopback traffic (`127.0.0.1` or `localhost`) is blocked by the proxy; always target allowlisted external endpoints.
- **Credential injection:** You do not need to store API keys or secret bearer tokens inside `.agents/hooks.json` or mount them into the container. Store the secret once as a [credential](https://ai.google.dev/gemini-api/docs/agent-credentials) and reference it by ID from your environment's `network.allowlist`. The egress proxy automatically intercepts outgoing HTTP hook traffic and injects the real authentication header on the wire before leaving the sandbox. Inline `transform` rules set headers the same way on the wire, a credential is the one to use when you want to reuse the secret across the project and rotate it in one place. See [network configuration](https://ai.google.dev/gemini-api/docs/agent-environment#network-configuration).

## How the runtime handles decisions and failures

- **Synchronous waiting:** The agent pauses and waits for your hooks to finish before continuing.
- **Blocking tool execution:** If your pre-tool hook returns `{"decision": "deny", "reason": "<your reason>"}`, the runtime immediately cancels the tool call. The model sees your rejection reason in its conversation history and adapts by choosing a safe alternative or explaining the block to the user.
- **Handling script crashes, HTTP errors, and timeouts:** If a command script crashes (non-zero exit status), an HTTP hook returns a non-2xx status code (such as a 4xx or 5xx server error), or an operation times out or returns unrecognized JSON, the runtime treats it as an approval (`allow`). Tool execution continues normally so a broken script or unreachable telemetry server never deadlocks your application.

## Common use cases

### Multi-turn recovery for data privacy and compliance

When a hook blocks access to restricted resources—such as directories containing Personally Identifiable Information (PII) or confidential financial records—you can pass `previous_interaction_id` on the next call to continue the turn in the same environment. The agent reads the denial explanation and automatically recovers by querying approved public tables instead.

[Python](https://ai.google.dev/gemini-api/docs/agent-hooks#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-hooks#javascript)[Java](https://ai.google.dev/gemini-api/docs/agent-hooks#java)[Go](https://ai.google.dev/gemini-api/docs/agent-hooks#go)[REST](https://ai.google.dev/gemini-api/docs/agent-hooks#rest)More

```
import json
from google import genai

client = genai.Client()

hooks_config = {
    "privacy-gate": {
        "pre_tool_execution": [\
            {\
                "matcher": "view_file",\
                "hooks": [\
                    {\
                        "type": "command",\
                        "command": "python3 /.agents/hooks-scripts/check_privacy.py",\
                        "timeout": 5,\
                    }\
                ],\
            }\
        ]
    }
}

check_privacy_script = """#!/usr/bin/env python3
import sys, json
data = json.load(sys.stdin)
path = str(data.get("tool_call", {}).get("args", {}).get("path", ""))

if "/private/" in path:
    resp = {
        "decision": "deny",
        "reason": "Access to confidential `/private/` records is blocked by PII compliance policy. Query approved `/public/` summary tables instead."
    }
else:
    resp = {"decision": "allow"}

print(json.dumps(resp))
"""

# Step 1: Agent attempts to read confidential PII records and is intercepted
int_1 = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="Use your filesystem tool to read `/workspace/private/employees.json` and summarize the employee details.",
    environment={
        "type": "remote",
        "sources": [\
            {\
                "type": "inline",\
                "target": ".agents/hooks.json",\
                "content": json.dumps(hooks_config, indent=2),\
            },\
            {\
                "type": "inline",\
                "target": ".agents/hooks-scripts/check_privacy.py",\
                "content": check_privacy_script,\
            },\
            {\
                "type": "inline",\
                "target": "workspace/private/employees.json",\
                "content": '{"employees": [{"id": 1, "salary": 150000, "ssn": "000-00-0000"}]}',\
            },\
            {\
                "type": "inline",\
                "target": "workspace/public/summary.json",\
                "content": '{"department": "Engineering", "team_size": 42, "status": "active"}',\
            },\
        ],
    },
)
print(int_1.output_text)

# Step 2: Continue in the same environment using previous_interaction_id; agent recovers with public tables
int_2 = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="Understood. Please read the approved `/workspace/public/summary.json` file instead and provide the summary.",
    environment=int_1.environment_id,
    previous_interaction_id=int_1.id,
)
print(int_2.output_text)
```

```
import { GoogleGenAI } from "@google/genai";

const client = new GoogleGenAI({});

const hooksConfig = {
    "privacy-gate": {
        pre_tool_execution: [\
            {\
                matcher: "view_file",\
                hooks: [\
                    {\
                        type: "command",\
                        command: "python3 /.agents/hooks-scripts/check_privacy.py",\
                        timeout: 5,\
                    },\
                ],\
            },\
        ],
    },
};

const checkPrivacyScript = `#!/usr/bin/env python3
import sys, json
data = json.load(sys.stdin)
path = str(data.get("tool_call", {}).get("args", {}).get("path", ""))

if "/private/" in path:
    resp = {
        "decision": "deny",
        "reason": "Access to confidential \`/private/\` records is blocked by PII compliance policy. Query approved \`/public/\` summary tables instead."
    }
else:
    resp = {"decision": "allow"}

print(json.dumps(resp))
`;

const int1 = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "Use your filesystem tool to read `/workspace/private/employees.json` and summarize the employee details.",
    environment: {
        type: "remote",
        sources: [\
            {\
                type: "inline",\
                "target": ".agents/hooks.json",\
                content: JSON.stringify(hooksConfig, null, 2),\
            },\
            {\
                type: "inline",\
                "target": ".agents/hooks-scripts/check_privacy.py",\
                content: checkPrivacyScript,\
            },\
            {\
                type: "inline",\
                "target": "workspace/private/employees.json",\
                content: '{"employees": [{"id": 1, "salary": 150000, "ssn": "000-00-0000"}]}',\
            },\
            {\
                type: "inline",\
                "target": "workspace/public/summary.json",\
                content: '{"department": "Engineering", "team_size": 42, "status": "active"}',\
            },\
        ],
    },
});
console.log(int1.output_text);

const int2 = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "Understood. Please read the approved `/workspace/public/summary.json` file instead and provide the summary.",
    environment: int1.environment_id,
    previous_interaction_id: int1.id,
});
console.log(int2.output_text);
```

```
import com.google.genai.Client;
import com.google.genai.gaos.models.interactions.AgentOption;
import com.google.genai.gaos.models.interactions.CreateAgentInteraction;
import com.google.genai.gaos.models.interactions.CreateAgentInteractionEnvironment;
import com.google.genai.gaos.models.interactions.Environment;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;
import com.google.genai.gaos.models.interactions.Source;
import com.google.genai.gaos.models.interactions.SourceType;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import java.util.List;

Client client = new Client();

String hooksConfig = """
{
  "privacy-gate": {
    "pre_tool_execution": [\
      {\
        "matcher": "read_file",\
        "hooks": [\
          {\
            "type": "command",\
            "command": "python3 /.agents/hooks-scripts/check_privacy.py",\
            "timeout": 5\
          }\
        ]\
      }\
    ]
  }
}
""";

String checkPrivacyScript = "#!/usr/bin/env python3\n"
    + "import sys, json\n"
    + "data = json.load(sys.stdin)\n"
    + "path = str(data.get(\"tool_call\", {}).get(\"args\", {}).get(\"path\", \"\"))\n"
    + "if \"/private/\" in path:\n"
    + "    resp = {\n"
    + "        \"decision\": \"deny\",\n"
    + "        \"reason\": \"Access to confidential `/private/` records is blocked by PII compliance policy. Query approved `/public/` summary tables instead.\"\n"
    + "    }\n"
    + "else:\n"
    + "    resp = {\"decision\": \"allow\"}\n"
    + "print(json.dumps(resp))\n";

Environment env = Environment.builder()
    .sources(List.of(
        Source.builder()
            .type(SourceType.INLINE)
            .target(".agents/hooks.json")
            .content(hooksConfig)
            .build(),
        Source.builder()
            .type(SourceType.INLINE)
            .target(".agents/hooks-scripts/check_privacy.py")
            .content(checkPrivacyScript)
            .build(),
        Source.builder()
            .type(SourceType.INLINE)
            .target("workspace/private/employees.json")
            .content("{\"employees\": [{\"id\": 1, \"salary\": 150000, \"ssn\": \"000-00-0000\"}]}")
            .build(),
        Source.builder()
            .type(SourceType.INLINE)
            .target("workspace/public/summary.json")
            .content("{\"department\": \"Engineering\", \"team_size\": 42, \"status\": \"active\"}")
            .build()
    ))
    .build();

// Step 1: Agent attempts to read confidential PII records and is intercepted
CreateAgentInteraction params1 = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("Use your filesystem tool to read `/workspace/private/employees.json` and summarize the employee details."))
    .environment(CreateAgentInteractionEnvironment.of(env))
    .build();

Interaction int1 = client.interactions.create(CreateInteractionRequestBody.of(params1)).interaction().get();
System.out.println(int1.outputText().orElse(""));

// Step 2: Continue in the same environment using previous_interaction_id; agent recovers with public tables
CreateAgentInteraction params2 = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("Understood. Please read the approved `/workspace/public/summary.json` file instead and provide the summary."))
    .environment(CreateAgentInteractionEnvironment.of(int1.environmentId().orElse("")))
    .previousInteractionId(int1.id().orElse(""))
    .build();

Interaction int2 = client.interactions.create(CreateInteractionRequestBody.of(params2)).interaction().get();
System.out.println(int2.outputText().orElse(""));
```

```
package main

import (
    "context"
    "fmt"
    "log"

    "google.golang.org/genai"
    "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    hooksConfig := `{
  "privacy-gate": {
    "pre_tool_execution": [\
      {\
        "matcher": "read_file",\
        "hooks": [\
          {\
            "type": "command",\
            "command": "python3 /.agents/hooks-scripts/check_privacy.py",\
            "timeout": 5\
          }\
        ]\
      }\
    ]
  }
}`

    checkPrivacyScript := `#!/usr/bin/env python3
import sys, json
data = json.load(sys.stdin)
path = str(data.get("tool_call", {}).get("args", {}).get("path", ""))
if "/private/" in path:
    resp = {
        "decision": "deny",
        "reason": "Access to confidential '/private/' records is blocked by PII compliance policy. Query approved '/public/' summary tables instead."
    }
else:
    resp = {"decision": "allow"}
print(json.dumps(resp))
`

    env := interactions.Environment{
        Sources: []interactions.Source{
            {
                Type:    interactions.SourceTypeInline.ToPointer(),
                Target:  genai.Ptr(".agents/hooks.json"),
                Content: genai.Ptr(hooksConfig),
            },
            {
                Type:    interactions.SourceTypeInline.ToPointer(),
                Target:  genai.Ptr(".agents/hooks-scripts/check_privacy.py"),
                Content: genai.Ptr(checkPrivacyScript),
            },
            {
                Type:    interactions.SourceTypeInline.ToPointer(),
                Target:  genai.Ptr("workspace/private/employees.json"),
                Content: genai.Ptr(`{"employees": [{"id": 1, "salary": 150000, "ssn": "000-00-0000"}]}`),
            },
            {
                Type:    interactions.SourceTypeInline.ToPointer(),
                Target:  genai.Ptr("workspace/public/summary.json"),
                Content: genai.Ptr(`{"department": "Engineering", "team_size": 42, "status": "active"}`),
            },
        },
    }

    // Step 1: Agent attempts to read confidential PII records and is intercepted
    res1, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{
        Body: operations.NewCreateInteractionRequestBody(interactions.CreateAgentInteraction{
            Agent:       interactions.AgentOption("antigravity-preview-09-2026"),
            Input:       interactions.NewInteractionsInput("Use your filesystem tool to read `/workspace/private/employees.json` and summarize the employee details."),
            Environment: genai.Ptr(interactions.NewCreateAgentInteractionEnvironment(env)),
        }),
    })
    if err != nil {
        log.Fatal(err)
    }
    int1 := res1.Interaction
    if int1.OutputText != nil {
        fmt.Println(*int1.OutputText)
    }

    // Step 2: Continue in the same environment using previous_interaction_id; agent recovers with public tables
    res2, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{
        Body: operations.NewCreateInteractionRequestBody(interactions.CreateAgentInteraction{
            Agent:                 interactions.AgentOption("antigravity-preview-09-2026"),
            Input:                 interactions.NewInteractionsInput("Understood. Please read the approved `/workspace/public/summary.json` file instead and provide the summary."),
            Environment:           genai.Ptr(interactions.NewCreateAgentInteractionEnvironment(*int1.EnvironmentID)),
            PreviousInteractionID: int1.ID,
        }),
    })
    if err != nil {
        log.Fatal(err)
    }
    if res2.Interaction.OutputText != nil {
        fmt.Println(*res2.Interaction.OutputText)
    }
}
```

```
# Step 1: Attempt to access restricted PII directory (blocked by hook)
curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions" \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -d '{
      "agent": "antigravity-preview-09-2026",
      "input": [{"type": "text", "text": "Use your filesystem tool to read /workspace/private/employees.json and summarize the employee details."}],
      "environment": {
          "type": "remote",
          "sources": [\
              {\
                  "type": "inline",\
                  "target": ".agents/hooks.json",\
                  "content": "{\"privacy-gate\": {\"pre_tool_execution\": [{\"matcher\": \"view_file\", \"hooks\": [{\"type\": \"command\", \"command\": \"python3 /.agents/hooks-scripts/check_privacy.py\", \"timeout\": 5}]}]}}"\
              },\
              {\
                  "type": "inline",\
                  "target": ".agents/hooks-scripts/check_privacy.py",\
                  "content": "#!/usr/bin/env python3\nimport sys, json\ndata = json.load(sys.stdin)\npath = str(data.get(\"tool_call\", {}).get(\"args\", {}).get(\"path\", \"\"))\nif \"/private/\" in path:\n    resp = {\"decision\": \"deny\", \"reason\": \"Access to confidential `/private/` records is blocked by PII compliance policy. Query approved `/public/` summary tables instead.\"}\nelse:\n    resp = {\"decision\": \"allow\"}\nprint(json.dumps(resp))\n"\
              },\
              {\
                  "type": "inline",\
                  "target": "workspace/private/employees.json",\
                  "content": "{\"employees\": [{\"id\": 1, \"salary\": 150000, \"ssn\": \"000-00-0000\"}]}"\
              },\
              {\
                  "type": "inline",\
                  "target": "workspace/public/summary.json",\
                  "content": "{\"department\": \"Engineering\", \"team_size\": 42, \"status\": \"active\"}"\
              }\
          ]
      }
  }'

# Step 2: Continue in the same environment using $ENV_ID and $INTERACTION_ID from the previous response
# curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions" \
#   -H "Content-Type: application/json" \
#   -H "x-goog-api-key: $GEMINI_API_KEY" \
#   -d '{
#       "agent": "antigravity-preview-09-2026",
#       "input": [{"type": "text", "text": "Understood. Please read the approved /workspace/public/summary.json file instead and provide the summary."}],
#       "environment": "'"$ENV_ID"'",
#       "previous_interaction_id": "'"$INTERACTION_ID"'"
#   }'
```

### External audit logging and telemetry

Send real-time audit events from inside the sandbox to an external monitoring server whenever files are read or modified.

- **Match multiple tools:** Because matchers use standard regex, you can combine multiple tools in a single rule using pipes (`view_file|write_to_file|replace_file_content`) or wildcards (`.*_file`).
- **Keep secrets out of your configuration:** Store the authentication token as a [credential](https://ai.google.dev/gemini-api/docs/agent-credentials) and reference it by ID from your environment's [network configuration](https://ai.google.dev/gemini-api/docs/agent-environment#network-configuration) (`network.allowlist.credential`). The egress proxy injects the real bearer token on outgoing requests. This example sets the header inline with `transform` instead, which is protected by the same proxy and fits when the token belongs to this one configuration.


[Python](https://ai.google.dev/gemini-api/docs/agent-hooks#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-hooks#javascript)[Java](https://ai.google.dev/gemini-api/docs/agent-hooks#java)[Go](https://ai.google.dev/gemini-api/docs/agent-hooks#go)[REST](https://ai.google.dev/gemini-api/docs/agent-hooks#rest)More

```
import json
from google import genai

client = genai.Client()

# Define hook without secrets; the egress proxy injects headers dynamically
hooks_config = {
    "audit-logging": {
        "post_tool_execution": [\
            {\
                "matcher": "view_file|write_to_file|replace_file_content",\
                "hooks": [\
                    {\
                        "type": "http",\
                        "url": "https://telemetry.example.com/api/v1/agent-events",\
                        "timeout": 10,\
                    }\
                ],\
            }\
        ]
    }
}

interaction = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="Use your filesystem tool to create `/workspace/audit.log` containing 'event 1', then immediately read it back using your filesystem read tool.",
    environment={
        "type": "remote",
        "sources": [\
            {\
                "type": "inline",\
                "target": ".agents/hooks.json",\
                "content": json.dumps(hooks_config, indent=2),\
            }\
        ],
        "network": {
            "allowlist": [\
                {\
                    "domain": "telemetry.example.com",\
                    "transform": {\
                        "Authorization": "Bearer telemetry_secret_token_123",\
                    },\
                },\
                {"domain": "*"},\
            ]
        },
    },
)
print(interaction.output_text)
```

```
import { GoogleGenAI } from "@google/genai";

const client = new GoogleGenAI({});

// Define hook without secrets; the egress proxy injects headers dynamically
const hooksConfig = {
    "audit-logging": {
        post_tool_execution: [\
            {\
                matcher: "view_file|write_to_file|replace_file_content",\
                hooks: [\
                    {\
                        type: "http",\
                        url: "https://telemetry.example.com/api/v1/agent-events",\
                        timeout: 10,\
                    },\
                ],\
            },\
        ],
    },
};

const interaction = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "Use your filesystem tool to create `/workspace/audit.log` containing 'event 1', then immediately read it back using your filesystem read tool.",
    environment: {
        type: "remote",
        sources: [\
            {\
                type: "inline",\
                target: ".agents/hooks.json",\
                content: JSON.stringify(hooksConfig, null, 2),\
            },\
        ],
        network: {
            allowlist: [\
                {\
                    domain: "telemetry.example.com",\
                    transform: {\
                        Authorization: "Bearer telemetry_secret_token_123",\
                    },\
                },\
                { domain: "*" },\
            ],
        },
    },
});
console.log(interaction.output_text);
```

```
import com.google.genai.Client;
import com.google.genai.gaos.models.interactions.AgentOption;
import com.google.genai.gaos.models.interactions.Allowlist;
import com.google.genai.gaos.models.interactions.AllowlistEntry;
import com.google.genai.gaos.models.interactions.CreateAgentInteraction;
import com.google.genai.gaos.models.interactions.CreateAgentInteractionEnvironment;
import com.google.genai.gaos.models.interactions.Environment;
import com.google.genai.gaos.models.interactions.EnvironmentNetworkEgressAllowlist;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;
import com.google.genai.gaos.models.interactions.Network;
import com.google.genai.gaos.models.interactions.Source;
import com.google.genai.gaos.models.interactions.SourceType;
import com.google.genai.gaos.models.interactions.Transform;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import java.util.List;
import java.util.Map;

Client client = new Client();

// Define hook without secrets; the egress proxy injects headers dynamically
String hooksConfig = """
{
  "audit-logging": {
    "post_tool_execution": [\
      {\
        "matcher": "read_file|write_file",\
        "hooks": [\
          {\
            "type": "http",\
            "url": "https://telemetry.example.com/api/v1/agent-events",\
            "timeout": 10\
          }\
        ]\
      }\
    ]
  }
}
""";

Environment env = Environment.builder()
    .sources(List.of(
        Source.builder()
            .type(SourceType.INLINE)
            .target(".agents/hooks.json")
            .content(hooksConfig)
            .build()
    ))
    .network(Network.of(
        EnvironmentNetworkEgressAllowlist.builder()
            .allowlist(Allowlist.of(List.of(
                AllowlistEntry.builder()
                    .domain("telemetry.example.com")
                    .transform(Transform.of(Map.of(
                        "Authorization", "Bearer telemetry_secret_token_123"
                    )))
                    .build(),
                AllowlistEntry.builder().domain("*").build()
            )))
            .build()
    ))
    .build();

CreateAgentInteraction params = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("Use your filesystem tool to create `/workspace/audit.log` containing 'event 1', then immediately read it back using your filesystem read tool."))
    .environment(CreateAgentInteractionEnvironment.of(env))
    .build();

Interaction interaction = client.interactions.create(CreateInteractionRequestBody.of(params)).interaction().get();
System.out.println(interaction.outputText().orElse(""));
```

```
package main

import (
    "context"
    "fmt"
    "log"

    "google.golang.org/genai"
    "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    // Define hook without secrets; the egress proxy injects headers dynamically
    hooksConfig := `{
  "audit-logging": {
    "post_tool_execution": [\
      {\
        "matcher": "read_file|write_file",\
        "hooks": [\
          {\
            "type": "http",\
            "url": "https://telemetry.example.com/api/v1/agent-events",\
            "timeout": 10\
          }\
        ]\
      }\
    ]
  }
}`

    env := interactions.Environment{
        Sources: []interactions.Source{
            {
                Type:    interactions.SourceTypeInline.ToPointer(),
                Target:  genai.Ptr(".agents/hooks.json"),
                Content: genai.Ptr(hooksConfig),
            },
        },
        Network: genai.Ptr(interactions.NewNetwork(interactions.EnvironmentNetworkEgressAllowlist{
            Allowlist: genai.Ptr(interactions.NewAllowlist([]interactions.AllowlistEntry{
                {
                    Domain: "telemetry.example.com",
                    Transform: genai.Ptr(interactions.NewTransform(map[string]string{
                        "Authorization": "Bearer telemetry_secret_token_123",
                    })),
                },
                {
                    Domain: "*",
                },
            })),
        })),
    }

    res, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{
        Body: operations.NewCreateInteractionRequestBody(interactions.CreateAgentInteraction{
            Agent:       interactions.AgentOption("antigravity-preview-09-2026"),
            Input:       interactions.NewInteractionsInput("Use your filesystem tool to create `/workspace/audit.log` containing 'event 1', then immediately read it back using your filesystem read tool."),
            Environment: genai.Ptr(interactions.NewCreateAgentInteractionEnvironment(env)),
        }),
    })
    if err != nil {
        log.Fatal(err)
    }
    if res.Interaction.OutputText != nil {
        fmt.Println(*res.Interaction.OutputText)
    }
}
```

```
curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions" \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -d '{
      "agent": "antigravity-preview-09-2026",
      "input": [{"type": "text", "text": "Use your filesystem tool to create /workspace/audit.log containing event 1, then immediately read it back using your filesystem read tool."}],
      "environment": {
          "type": "remote",
          "sources": [\
              {\
                  "type": "inline",\
                  "target": ".agents/hooks.json",\
                  "content": "{\"audit-logging\": {\"post_tool_execution\": [{\"matcher\": \"view_file|write_to_file|replace_file_content\", \"hooks\": [{\"type\": \"http\", \"url\": \"https://telemetry.example.com/api/v1/agent-events\", \"timeout\": 10}]}]}}"\
              }\
          ],
          "network": {
              "allowlist": [\
                  {\
                      "domain": "telemetry.example.com",\
                      "transform": {\
                          "Authorization": "Bearer telemetry_secret_token_123"\
                      }\
                  },\
                  {"domain": "*"}\
              ]
          }
      }
  }'
```

## Limitations

- **Sandbox tool scope:** Hooks intercept built-in tools inside the sandbox: code execution (`code_execution`) and filesystem operations (`view_file`, `write_to_file`, `replace_file_content`, `list_dir`, and `delete_file`). They do not fire for custom function calling (`function`) or external Model Context Protocol (`mcp_server`) tools handled outside the container.
- **Network allowlists:** HTTP hooks run inside the container network. You must explicitly allow target URLs in your environment's `network.allowlist`. Loopback addresses (`localhost`, `127.0.0.1`) are blocked by the proxy.
- **Automatic approval on errors:** If a hook script crashes (non-zero exit status), times out, or fails, the runtime logs the failure and allows the tool call to continue. This ensures broken linter scripts or hanging processes never deadlock your applications.
- **Sandbox configuration protection:** Because hooks execute inside the container sandbox, agents with filesystem write tools or shell code execution permissions can modify local `.agents/hooks.json` or scripts within writable workspaces. Use container hooks as automated policy guidance and operational guardrails; if strict tamper resistance is required against untrusted model executions, mount configuration sources from read-only repositories.

## What's next

- Learn how to configure persistent [remote sandboxes and environments](https://ai.google.dev/gemini-api/docs/agent-environment).
- Explore the capabilities and built-in tools of the [Antigravity agent](https://ai.google.dev/gemini-api/docs/antigravity-agent).
- Review the [Interactions API overview](https://ai.google.dev/gemini-api/docs/interactions-overview) for multi-turn sessions and streaming.

Was this helpful?



 Send feedback



Except as otherwise noted, the content of this page is licensed under the [Creative Commons Attribution 4.0 License](https://creativecommons.org/licenses/by/4.0/), and code samples are licensed under the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0). For details, see the [Google Developers Site Policies](https://developers.google.com/site-policies). Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-10-07 UTC.


Need to tell us more?






\[\[\["Easy to understand","easyToUnderstand","thumb-up"\],\["Solved my problem","solvedMyProblem","thumb-up"\],\["Other","otherUp","thumb-up"\]\],\[\["Missing the information I need","missingTheInformationINeed","thumb-down"\],\["Too complicated / too many steps","tooComplicatedTooManySteps","thumb-down"\],\["Out of date","outOfDate","thumb-down"\],\["Samples / code issue","samplesCodeIssue","thumb-down"\],\["Other","otherDown","thumb-down"\]\],\["Last updated 2026-10-07 UTC."\],\[\],\[\]\]