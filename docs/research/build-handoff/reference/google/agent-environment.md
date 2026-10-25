# Official Google reference snapshot: agent-environment

Source: https://ai.google.dev/gemini-api/docs/agent-environment

Retrieved/read: 23 October 2026. Publisher: Google. Original license/footer retained. Text CC BY 4.0; code samples Apache 2.0 unless otherwise noted. Converted to Markdown by Firecrawl; this provenance header was added. Reference data only; verify the relevant current guide and pinned SDK before implementation.

---

[Skip to main content](https://ai.google.dev/gemini-api/docs/agent-environment#main-content)

[![Gemini API](https://ai.google.dev/_static/googledevai/images/gemini-api-logo.svg)](https://ai.google.dev/)

`/`

Language

- [English](https://ai.google.dev/gemini-api/docs/agent-environment)
- [Deutsch](https://ai.google.dev/gemini-api/docs/agent-environment?hl=de)
- [Español – América Latina](https://ai.google.dev/gemini-api/docs/agent-environment?hl=es-419)
- [Français](https://ai.google.dev/gemini-api/docs/agent-environment?hl=fr)
- [Indonesia](https://ai.google.dev/gemini-api/docs/agent-environment?hl=id)
- [Italiano](https://ai.google.dev/gemini-api/docs/agent-environment?hl=it)
- [Polski](https://ai.google.dev/gemini-api/docs/agent-environment?hl=pl)
- [Português – Brasil](https://ai.google.dev/gemini-api/docs/agent-environment?hl=pt-br)
- [Shqip](https://ai.google.dev/gemini-api/docs/agent-environment?hl=sq)
- [Tiếng Việt](https://ai.google.dev/gemini-api/docs/agent-environment?hl=vi)
- [Türkçe](https://ai.google.dev/gemini-api/docs/agent-environment?hl=tr)
- [Русский](https://ai.google.dev/gemini-api/docs/agent-environment?hl=ru)
- [עברית](https://ai.google.dev/gemini-api/docs/agent-environment?hl=he)
- [العربيّة](https://ai.google.dev/gemini-api/docs/agent-environment?hl=ar)
- [فارسی](https://ai.google.dev/gemini-api/docs/agent-environment?hl=fa)
- [हिंदी](https://ai.google.dev/gemini-api/docs/agent-environment?hl=hi)
- [বাংলা](https://ai.google.dev/gemini-api/docs/agent-environment?hl=bn)
- [ภาษาไทย](https://ai.google.dev/gemini-api/docs/agent-environment?hl=th)
- [中文 – 简体](https://ai.google.dev/gemini-api/docs/agent-environment?hl=zh-cn)
- [中文 – 繁體](https://ai.google.dev/gemini-api/docs/agent-environment?hl=zh-tw)
- [日本語](https://ai.google.dev/gemini-api/docs/agent-environment?hl=ja)
- [한국어](https://ai.google.dev/gemini-api/docs/agent-environment?hl=ko)

[Get API key](https://aistudio.google.com/apikey) [Cookbook](https://github.com/google-gemini/cookbook) [Community](https://discuss.ai.google.dev/c/gemini-api/)

[Sign in](https://ai.google.dev/_d/signin?continue=https%3A%2F%2Fai.google.dev%2Fgemini-api%2Fdocs%2Fagent-environment&prompt=select_account)

- On this page
- [The environment parameter](https://ai.google.dev/gemini-api/docs/agent-environment#the-environment-parameter)
- [Configure an environment](https://ai.google.dev/gemini-api/docs/agent-environment#configure-an-environment)
  - [Mount from a source](https://ai.google.dev/gemini-api/docs/agent-environment#mount_from_a_source)
  - [Hooks](https://ai.google.dev/gemini-api/docs/agent-environment#hooks)
  - [Private sources](https://ai.google.dev/gemini-api/docs/agent-environment#private-sources)
- [Pre-installed software](https://ai.google.dev/gemini-api/docs/agent-environment#pre-installed-software)
- [Environment variables](https://ai.google.dev/gemini-api/docs/agent-environment#environment-variables)
- [Network configuration](https://ai.google.dev/gemini-api/docs/agent-environment#network-configuration)
  - [Credentials](https://ai.google.dev/gemini-api/docs/agent-environment#credentials)
  - [Disable network access](https://ai.google.dev/gemini-api/docs/agent-environment#disable_network_access)
  - [Refresh credentials](https://ai.google.dev/gemini-api/docs/agent-environment#refresh-credentials)
- [Environment lifecycle](https://ai.google.dev/gemini-api/docs/agent-environment#environment-lifecycle)
- [Environments API](https://ai.google.dev/gemini-api/docs/agent-environment#environments-api)
  - [List environments](https://ai.google.dev/gemini-api/docs/agent-environment#list_environments)
  - [Get an environment](https://ai.google.dev/gemini-api/docs/agent-environment#get_an_environment)
  - [Delete an environment](https://ai.google.dev/gemini-api/docs/agent-environment#delete_an_environment)
- [Manage files in the environment](https://ai.google.dev/gemini-api/docs/agent-environment#download-files)
  - [List files in a directory](https://ai.google.dev/gemini-api/docs/agent-environment#list-files)
  - [Get file metadata](https://ai.google.dev/gemini-api/docs/agent-environment#get-file-metadata)
  - [Download a single file](https://ai.google.dev/gemini-api/docs/agent-environment#download-file)
  - [Download a directory as a tar archive](https://ai.google.dev/gemini-api/docs/agent-environment#download-directory)
  - [Upload files to the environment](https://ai.google.dev/gemini-api/docs/agent-environment#upload-file)
  - [Download full snapshot (deprecated)](https://ai.google.dev/gemini-api/docs/agent-environment#download-snapshot-deprecated)
- [Pricing & resources](https://ai.google.dev/gemini-api/docs/agent-environment#pricing-resources)
- [Limitations](https://ai.google.dev/gemini-api/docs/agent-environment#limitations)
- [What's next](https://ai.google.dev/gemini-api/docs/agent-environment#whats-next)

Gemini 4 Argon is now available. [Try it out](https://aistudio.google.com/prompts/new_chat?model=gemini-4-argon).


- [Home](https://ai.google.dev/)
- [Gemini API](https://ai.google.dev/gemini-api)
- [Docs](https://ai.google.dev/gemini-api/docs)

Was this helpful?



 Send feedback



# Environments in managed agents

- On this page
- [The environment parameter](https://ai.google.dev/gemini-api/docs/agent-environment#the-environment-parameter)
- [Configure an environment](https://ai.google.dev/gemini-api/docs/agent-environment#configure-an-environment)
  - [Mount from a source](https://ai.google.dev/gemini-api/docs/agent-environment#mount_from_a_source)
  - [Hooks](https://ai.google.dev/gemini-api/docs/agent-environment#hooks)
  - [Private sources](https://ai.google.dev/gemini-api/docs/agent-environment#private-sources)
- [Pre-installed software](https://ai.google.dev/gemini-api/docs/agent-environment#pre-installed-software)
- [Environment variables](https://ai.google.dev/gemini-api/docs/agent-environment#environment-variables)
- [Network configuration](https://ai.google.dev/gemini-api/docs/agent-environment#network-configuration)
  - [Credentials](https://ai.google.dev/gemini-api/docs/agent-environment#credentials)
  - [Disable network access](https://ai.google.dev/gemini-api/docs/agent-environment#disable_network_access)
  - [Refresh credentials](https://ai.google.dev/gemini-api/docs/agent-environment#refresh-credentials)
- [Environment lifecycle](https://ai.google.dev/gemini-api/docs/agent-environment#environment-lifecycle)
- [Environments API](https://ai.google.dev/gemini-api/docs/agent-environment#environments-api)
  - [List environments](https://ai.google.dev/gemini-api/docs/agent-environment#list_environments)
  - [Get an environment](https://ai.google.dev/gemini-api/docs/agent-environment#get_an_environment)
  - [Delete an environment](https://ai.google.dev/gemini-api/docs/agent-environment#delete_an_environment)
- [Manage files in the environment](https://ai.google.dev/gemini-api/docs/agent-environment#download-files)
  - [List files in a directory](https://ai.google.dev/gemini-api/docs/agent-environment#list-files)
  - [Get file metadata](https://ai.google.dev/gemini-api/docs/agent-environment#get-file-metadata)
  - [Download a single file](https://ai.google.dev/gemini-api/docs/agent-environment#download-file)
  - [Download a directory as a tar archive](https://ai.google.dev/gemini-api/docs/agent-environment#download-directory)
  - [Upload files to the environment](https://ai.google.dev/gemini-api/docs/agent-environment#upload-file)
  - [Download full snapshot (deprecated)](https://ai.google.dev/gemini-api/docs/agent-environment#download-snapshot-deprecated)
- [Pricing & resources](https://ai.google.dev/gemini-api/docs/agent-environment#pricing-resources)
- [Limitations](https://ai.google.dev/gemini-api/docs/agent-environment#limitations)
- [What's next](https://ai.google.dev/gemini-api/docs/agent-environment#whats-next)

Environments are managed Linux sandboxes that give agents an isolated place to
execute code and persist files. They are decoupled from interaction context, so you can reuse the same environment across multiple interactions or start fresh at any time.

The following example demonstrates how to create an interaction with a fresh
remote environment and retrieve its ID:

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[Java](https://ai.google.dev/gemini-api/docs/agent-environment#java)[Go](https://ai.google.dev/gemini-api/docs/agent-environment#go)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="Install pandas and matplotlib, verify the imports, and print the versions.",
    environment="remote",
)

print(f"Environment ID: {interaction.environment_id}")
```

```
import { GoogleGenAI } from "@google/genai";

const client = new GoogleGenAI({});

const interaction = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "Install pandas and matplotlib, verify the imports, and print the versions.",
    environment: "remote",
});

console.log(`Environment ID: ${interaction.environment_id}`);
```

```
import com.google.genai.Client;
import com.google.genai.gaos.models.interactions.AgentOption;
import com.google.genai.gaos.models.interactions.CreateAgentInteraction;
import com.google.genai.gaos.models.interactions.CreateAgentInteractionEnvironment;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;

Client client = new Client();

CreateAgentInteraction params = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("Install pandas and matplotlib, verify the imports, and print the versions."))
    .environment(CreateAgentInteractionEnvironment.of("remote"))
    .build();

Interaction interaction = client.interactions.create(CreateInteractionRequestBody.of(params)).interaction().get();
System.out.println("Environment ID: " + interaction.environmentId().orElse(""));
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

    res, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{
        Body: operations.NewCreateInteractionRequestBody(interactions.CreateAgentInteraction{
            Agent:       interactions.AgentOption("antigravity-preview-09-2026"),
            Input:       interactions.NewInteractionsInput("Install pandas and matplotlib, verify the imports, and print the versions."),
            Environment: genai.Ptr(interactions.NewCreateAgentInteractionEnvironment("remote")),
        }),
    })
    if err != nil {
        log.Fatal(err)
    }

    if res.Interaction.EnvironmentID != nil {
        fmt.Printf("Environment ID: %s\n", *res.Interaction.EnvironmentID)
    }
}
```

```
curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions" \
-H "Content-Type: application/json" \
-H "x-goog-api-key: $GEMINI_API_KEY" \
-d '{
    "agent": "antigravity-preview-09-2026",
    "input": "Install pandas and matplotlib, verify the imports, and print the versions.",
    "environment": "remote"
}'
```

## The `environment` parameter

The `environment` parameter accepts three forms:

| Form | Example | When to use |
| --- | --- | --- |
| `"remote"` | `environment="remote"` | Provision a fresh sandbox. |
| Environment ID | `environment="env_abc123"` | Reuse an existing sandbox with all its files and packages. |
| Config object | `environment={...}` | Provision a new sandbox with sources, network rules, environment variables, or a combination. |

The following examples demonstrate the three ways of using the `environment`
parameter.

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[Java](https://ai.google.dev/gemini-api/docs/agent-environment#java)[Go](https://ai.google.dev/gemini-api/docs/agent-environment#go)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
from google import genai

client = genai.Client()

# Fresh sandbox
interaction = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="Write a hello world script.",
    environment="remote",
)

# Reuse an existing sandbox
interaction_2 = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="Modify the script to accept a name argument.",
    environment=interaction.environment_id,
    previous_interaction_id=interaction.id,
)

# New sandbox with sources
interaction_3 = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="List all files and summarize the project.",
    environment={
        "type": "remote",
        "sources": [\
            {\
                "type": "repository",\
                "source": "https://github.com/octocat/Spoon-Knife",\
                "target": "/workspace/spoon-knife",\
            }\
        ],
    },
)

print(interaction.output_text)
```

```
import { GoogleGenAI } from "@google/genai";

const client = new GoogleGenAI({});

// Fresh sandbox
const interaction = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "Write a hello world script.",
    environment: "remote",
});

// Reuse an existing sandbox
const interaction2 = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "Modify the script to accept a name argument.",
    environment: interaction.environment_id,
    previous_interaction_id: interaction.id,
});

// New sandbox with sources
const interaction3 = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "List all files and summarize the project.",
    environment: {
        type: "remote",
        sources: [\
            {\
                type: "repository",\
                source: "https://github.com/octocat/Spoon-Knife",\
                target: "/workspace/spoon-knife",\
            },\
        ],
    },
});

console.log(interaction.output_text);
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

// Fresh sandbox
CreateAgentInteraction params1 = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("Write a hello world script."))
    .environment(CreateAgentInteractionEnvironment.of("remote"))
    .build();
Interaction interaction = client.interactions.create(CreateInteractionRequestBody.of(params1)).interaction().get();

// Reuse an existing sandbox
CreateAgentInteraction params2 = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("Modify the script to accept a name argument."))
    .environment(CreateAgentInteractionEnvironment.of(interaction.environmentId().orElse("")))
    .previousInteractionId(interaction.id().orElse(""))
    .build();
Interaction interaction2 = client.interactions.create(CreateInteractionRequestBody.of(params2)).interaction().get();

// New sandbox with sources
Environment env3 = Environment.builder()
    .sources(List.of(
        Source.builder()
            .type(SourceType.REPOSITORY)
            .source("https://github.com/octocat/Spoon-Knife")
            .target("/workspace/spoon-knife")
            .build()
    ))
    .build();

CreateAgentInteraction params3 = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("List all files and summarize the project."))
    .environment(CreateAgentInteractionEnvironment.of(env3))
    .build();
Interaction interaction3 = client.interactions.create(CreateInteractionRequestBody.of(params3)).interaction().get();

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

    // Fresh sandbox
    res1, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{
        Body: operations.NewCreateInteractionRequestBody(interactions.CreateAgentInteraction{
            Agent:       interactions.AgentOption("antigravity-preview-09-2026"),
            Input:       interactions.NewInteractionsInput("Write a hello world script."),
            Environment: genai.Ptr(interactions.NewCreateAgentInteractionEnvironment("remote")),
        }),
    })
    if err != nil {
        log.Fatal(err)
    }
    interaction := res1.Interaction

    // Reuse an existing sandbox
    res2, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{
        Body: operations.NewCreateInteractionRequestBody(interactions.CreateAgentInteraction{
            Agent:                 interactions.AgentOption("antigravity-preview-09-2026"),
            Input:                 interactions.NewInteractionsInput("Modify the script to accept a name argument."),
            Environment:           genai.Ptr(interactions.NewCreateAgentInteractionEnvironment(*interaction.EnvironmentID)),
            PreviousInteractionID: interaction.ID,
        }),
    })
    if err != nil {
        log.Fatal(err)
    }
    _ = res2

    // New sandbox with sources
    env3 := interactions.Environment{
        Sources: []interactions.Source{
            {
                Type:   interactions.SourceTypeRepository.ToPointer(),
                Source: genai.Ptr("https://github.com/octocat/Spoon-Knife"),
                Target: genai.Ptr("/workspace/spoon-knife"),
            },
        },
    }

    res3, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{
        Body: operations.NewCreateInteractionRequestBody(interactions.CreateAgentInteraction{
            Agent:       interactions.AgentOption("antigravity-preview-09-2026"),
            Input:       interactions.NewInteractionsInput("List all files and summarize the project."),
            Environment: genai.Ptr(interactions.NewCreateAgentInteractionEnvironment(env3)),
        }),
    })
    if err != nil {
        log.Fatal(err)
    }
    _ = res3

    if interaction.OutputText != nil {
        fmt.Println(*interaction.OutputText)
    }
}
```

```
# Fresh sandbox
curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions" \
-H "Content-Type: application/json" \
-H "x-goog-api-key: $GEMINI_API_KEY" \
-d '{
    "agent": "antigravity-preview-09-2026",
    "input": [{"type": "text", "text": "Write a hello world script."}],
    "environment": "remote"
}'

# Reuse an existing sandbox (replace $ENV_ID and $INTERACTION_ID with values from the previous response)
curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions" \
-H "Content-Type: application/json" \
-H "x-goog-api-key: $GEMINI_API_KEY" \
-d "{
    \"agent\": \"antigravity-preview-09-2026\",
    \"input\": [{\"type\": \"text\", \"text\": \"Modify the script to accept a name argument.\"}],
    \"environment\": \"$ENV_ID\",
    \"previous_interaction_id\": \"$INTERACTION_ID\"
}"

# New sandbox with sources
curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions" \
-H "Content-Type: application/json" \
-H "x-goog-api-key: $GEMINI_API_KEY" \
-d '{
    "agent": "antigravity-preview-09-2026",
    "input": [{"type": "text", "text": "List all files and summarize the project."}],
    "environment": {
        "type": "remote",
        "sources": [\
            {\
                "type": "repository",\
                "source": "https://github.com/octocat/Spoon-Knife",\
                "target": "/workspace/spoon-knife"\
            }\
        ]
    }
}'
```

## Configure an environment

One way to set up an environment is to tell the agent what you need installed.
It handles dependency resolution and troubleshooting. Once the environment is
ready, save the `environment_id` and reuse it.

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[Java](https://ai.google.dev/gemini-api/docs/agent-environment#java)[Go](https://ai.google.dev/gemini-api/docs/agent-environment#go)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="Install pandas, matplotlib, and seaborn. Verify all imports work and print the installed versions.",
    environment="remote",
)

# Reuse the configured environment
interaction_2 = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="Clone https://github.com/octocat/Spoon-Knife into /workspace/tools. Run the test suite and fix any missing dependencies.",
    environment=interaction.environment_id,
    previous_interaction_id=interaction.id,
)

# Reuse the configured environment
interaction_3 = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="Using the tools in /workspace/tools, list the files.",
    environment=interaction.environment_id,
    previous_interaction_id=interaction_2.id,
)

print(interaction.output_text)
```

```
import { GoogleGenAI } from "@google/genai";

const client = new GoogleGenAI({});

const interaction = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "Install pandas, matplotlib, and seaborn. Verify all imports work and print the installed versions.",
    environment: "remote",
});

const interaction2 = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "Clone https://github.com/octocat/Spoon-Knife into /workspace/tools. Run the test suite and fix any missing dependencies.",
    environment: interaction.environment_id,
    previous_interaction_id: interaction.id,
});

const interaction3 = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "Using the tools in /workspace/tools, list the files.",
    environment: interaction.environment_id,
    previous_interaction_id: interaction2.id,
});
console.log(interaction.output_text);
```

```
import com.google.genai.Client;
import com.google.genai.gaos.models.interactions.AgentOption;
import com.google.genai.gaos.models.interactions.CreateAgentInteraction;
import com.google.genai.gaos.models.interactions.CreateAgentInteractionEnvironment;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;

Client client = new Client();

CreateAgentInteraction params1 = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("Install pandas, matplotlib, and seaborn. Verify all imports work and print the installed versions."))
    .environment(CreateAgentInteractionEnvironment.of("remote"))
    .build();
Interaction interaction = client.interactions.create(CreateInteractionRequestBody.of(params1)).interaction().get();

// Reuse the configured environment
CreateAgentInteraction params2 = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("Clone https://github.com/octocat/Spoon-Knife into /workspace/tools. Run the test suite and fix any missing dependencies."))
    .environment(CreateAgentInteractionEnvironment.of(interaction.environmentId().orElse("")))
    .previousInteractionId(interaction.id().orElse(""))
    .build();
Interaction interaction2 = client.interactions.create(CreateInteractionRequestBody.of(params2)).interaction().get();

// Reuse the configured environment
CreateAgentInteraction params3 = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("Using the tools in /workspace/tools, list the files."))
    .environment(CreateAgentInteractionEnvironment.of(interaction.environmentId().orElse("")))
    .previousInteractionId(interaction2.id().orElse(""))
    .build();
Interaction interaction3 = client.interactions.create(CreateInteractionRequestBody.of(params3)).interaction().get();

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

    res1, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{
        Body: operations.NewCreateInteractionRequestBody(interactions.CreateAgentInteraction{
            Agent:       interactions.AgentOption("antigravity-preview-09-2026"),
            Input:       interactions.NewInteractionsInput("Install pandas, matplotlib, and seaborn. Verify all imports work and print the installed versions."),
            Environment: genai.Ptr(interactions.NewCreateAgentInteractionEnvironment("remote")),
        }),
    })
    if err != nil {
        log.Fatal(err)
    }
    interaction := res1.Interaction

    // Reuse the configured environment
    res2, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{
        Body: operations.NewCreateInteractionRequestBody(interactions.CreateAgentInteraction{
            Agent:                 interactions.AgentOption("antigravity-preview-09-2026"),
            Input:                 interactions.NewInteractionsInput("Clone https://github.com/octocat/Spoon-Knife into /workspace/tools. Run the test suite and fix any missing dependencies."),
            Environment:           genai.Ptr(interactions.NewCreateAgentInteractionEnvironment(*interaction.EnvironmentID)),
            PreviousInteractionID: interaction.ID,
        }),
    })
    if err != nil {
        log.Fatal(err)
    }
    interaction2 := res2.Interaction

    // Reuse the configured environment
    res3, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{
        Body: operations.NewCreateInteractionRequestBody(interactions.CreateAgentInteraction{
            Agent:                 interactions.AgentOption("antigravity-preview-09-2026"),
            Input:                 interactions.NewInteractionsInput("Using the tools in /workspace/tools, list the files."),
            Environment:           genai.Ptr(interactions.NewCreateAgentInteractionEnvironment(*interaction.EnvironmentID)),
            PreviousInteractionID: interaction2.ID,
        }),
    })
    if err != nil {
        log.Fatal(err)
    }
    _ = res3

    if interaction.OutputText != nil {
        fmt.Println(*interaction.OutputText)
    }
}
```

```
# Create interaction
curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions" \
-H "Content-Type: application/json" \
-H "x-goog-api-key: $GEMINI_API_KEY" \
-d '{
    "agent": "antigravity-preview-09-2026",
    "input": "Install pandas, matplotlib, and seaborn. Verify all imports work and print the installed versions.",
    "environment": "remote"
}'
```

### Mount from a source

If you know exactly what files the agent needs, mount them in a single call
instead of iterating. The `environment` config object accepts a `sources` array
with three types:

| Source type | `type` value | Description | Limit |
| --- | --- | --- | --- |
| Git repository | `repository` | Clones a repository from a URL into the sandbox at `target`. | 500 MB |
| Cloud Storage | `gcs` | Copies a file or directory from Cloud Storage into the sandbox at `target`. | 2 GB |
| Inline content | `inline` | Writes raw text content to a file in the sandbox at `target`. | 1 MB per file, 2 MB total |

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[Java](https://ai.google.dev/gemini-api/docs/agent-environment#java)[Go](https://ai.google.dev/gemini-api/docs/agent-environment#go)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="List all files under /workspace and describe what you find.",
    environment={
        "type": "remote",
        "sources": [\
            {\
                "type": "repository",\
                "source": "https://github.com/octocat/Spoon-Knife",\
                "target": "/workspace/spoon-knife",\
            },\
            {\
                "type": "gcs",\
                "source": "gs://cloud-samples-data/bigquery/us-states/",\
                "target": "/workspace/gcs-data",\
            },\
            {\
                "type": "inline",\
                "content": "# Project Notes\n\n- Analyze state population data\n- Create visualizations\n",\
                "target": "/workspace/notes/readme.md",\
            },\
        ],
    },
)

print(interaction.output_text)
```

```
import { GoogleGenAI } from "@google/genai";

const client = new GoogleGenAI({});

const interaction = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "List all files under /workspace and describe what you find.",
    environment: {
        type: "remote",
        sources: [\
            {\
                type: "repository",\
                source: "https://github.com/octocat/Spoon-Knife",\
                target: "/workspace/spoon-knife",\
            },\
            {\
                type: "gcs",\
                source: "gs://cloud-samples-data/bigquery/us-states/",\
                target: "/workspace/gcs-data",\
            },\
            {\
                type: "inline",\
                content: "# Project Notes\n\n- Analyze state population data\n- Create visualizations\n",\
                target: "/workspace/notes/readme.md",\
            },\
        ],
    },
});

console.log(interaction.output_text);
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

Environment env = Environment.builder()
    .sources(List.of(
        Source.builder()
            .type(SourceType.REPOSITORY)
            .source("https://github.com/octocat/Spoon-Knife")
            .target("/workspace/spoon-knife")
            .build(),
        Source.builder()
            .type(SourceType.GCS)
            .source("gs://cloud-samples-data/bigquery/us-states/")
            .target("/workspace/gcs-data")
            .build(),
        Source.builder()
            .type(SourceType.INLINE)
            .content("# Project Notes\n\n- Analyze state population data\n- Create visualizations\n")
            .target("/workspace/notes/readme.md")
            .build()
    ))
    .build();

CreateAgentInteraction params = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("List all files under /workspace and describe what you find."))
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

    env := interactions.Environment{
        Sources: []interactions.Source{
            {
                Type:   interactions.SourceTypeRepository.ToPointer(),
                Source: genai.Ptr("https://github.com/octocat/Spoon-Knife"),
                Target: genai.Ptr("/workspace/spoon-knife"),
            },
            {
                Type:   interactions.SourceTypeGcs.ToPointer(),
                Source: genai.Ptr("gs://cloud-samples-data/bigquery/us-states/"),
                Target: genai.Ptr("/workspace/gcs-data"),
            },
            {
                Type:    interactions.SourceTypeInline.ToPointer(),
                Content: genai.Ptr("# Project Notes\n\n- Analyze state population data\n- Create visualizations\n"),
                Target:  genai.Ptr("/workspace/notes/readme.md"),
            },
        },
    }

    res, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{
        Body: operations.NewCreateInteractionRequestBody(interactions.CreateAgentInteraction{
            Agent:       interactions.AgentOption("antigravity-preview-09-2026"),
            Input:       interactions.NewInteractionsInput("List all files under /workspace and describe what you find."),
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
# Create interaction with sources
curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions" \
-H "Content-Type: application/json" \
-H "x-goog-api-key: $GEMINI_API_KEY" \
-d '{
    "agent": "antigravity-preview-09-2026",
    "input": "List all files under /workspace and describe what you find.",
    "environment": {
        "type": "remote",
        "sources": [\
            {\
                "type": "repository",\
                "source": "https://github.com/octocat/Spoon-Knife",\
                "target": "/workspace/spoon-knife"\
            },\
            {\
                "type": "gcs",\
                "source": "gs://cloud-samples-data/bigquery/us-states/",\
                "target": "/workspace/gcs-data"\
            },\
            {\
                "type": "inline",\
                "content": "# Project Notes\n\n- Analyze state population data\n- Create visualizations\n",\
                "target": "/workspace/notes/readme.md"\
            }\
        ]
    }
}'
```

You can combine both approaches: mount known sources declaratively, then iterate
with follow-up interactions to install packages or run setup scripts. You can't
set root (`/`) as target when adding a custom source, you must always specify a
sub-directory.

### Hooks

You can also mount a `.agents/hooks.json` configuration file and custom interception scripts into the sandbox to enforce security guardrails or run automated validations whenever tools execute. For schema definitions and code examples, see [Hooks](https://ai.google.dev/gemini-api/docs/agent-hooks).

### Private sources

You can also download from private GitHub repositories or private Cloud
Storage buckets by authenticating the source domain in the network
configuration.

One option is a stored [credential](https://ai.google.dev/gemini-api/docs/agent-credentials)
referenced by ID, so you store the secret once and every environment that needs
that source can reference it:

```
"network": {
    "allowlist": [\
        { "domain": "github.com", "credential": "github-production" },\
        { "domain": "*" }\
    ]
}
```

You can also set the header inline with `transform`, as the following examples
do. The egress proxy applies both forms the same way, and in neither case does
the secret land inside the sandbox.

For **private Git repositories**, use `Basic` authentication with your
[GitHub Personal Access Token\\
(PAT)](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).
Encode the token using `x-oauth-basic` as the username:

```
echo -n "x-oauth-basic:ghp_YourPATHere" | base64
```

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[Java](https://ai.google.dev/gemini-api/docs/agent-environment#java)[Go](https://ai.google.dev/gemini-api/docs/agent-environment#go)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
interaction = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="Run the test for my backend app and fix any issue.",
    environment={
        "type": "remote",
        "sources": [\
            {\
                "type": "repository",\
                "source": "https://github.com/your-org/backend",\
                "target": "/backend-app"\
            }\
        ],
        "network": {
            "allowlist": [\
                {\
                    "domain": "github.com",\
                    "transform": {\
                        "Authorization": "Basic YOUR_BASE64_TOKEN"\
                    }\
                },\
                {\
                    "domain": "*"\
                }\
            ]
        }
    }
)
```

```
const interaction = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "Run the test for my backend app and fix any issue.",
    environment: {
        type: "remote",
        sources: [\
            {\
                type: "repository",\
                source: "https://github.com/your-org/backend",\
                target: "/backend-app"\
            }\
        ],
        network: {
            allowlist: [\
                {\
                    domain: "github.com",\
                    transform: {\
                        "Authorization": "Basic YOUR_BASE64_TOKEN"\
                    }\
                },\
                {\
                    domain: "*"\
                }\
            ]
        }
    },
});
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

Environment env = Environment.builder()
    .sources(List.of(
        Source.builder()
            .type(SourceType.REPOSITORY)
            .source("https://github.com/your-org/backend")
            .target("/backend-app")
            .build()
    ))
    .network(Network.of(
        EnvironmentNetworkEgressAllowlist.builder()
            .allowlist(Allowlist.of(List.of(
                AllowlistEntry.builder()
                    .domain("github.com")
                    .transform(Transform.of(Map.of(
                        "Authorization", "Basic YOUR_BASE64_TOKEN"
                    )))
                    .build(),
                AllowlistEntry.builder()
                    .domain("*")
                    .build()
            )))
            .build()
    ))
    .build();

CreateAgentInteraction params = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("Run the test for my backend app and fix any issue."))
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

    env := interactions.Environment{
        Sources: []interactions.Source{
            {
                Type:   interactions.SourceTypeRepository.ToPointer(),
                Source: genai.Ptr("https://github.com/your-org/backend"),
                Target: genai.Ptr("/backend-app"),
            },
        },
        Network: genai.Ptr(interactions.NewNetwork(interactions.EnvironmentNetworkEgressAllowlist{
            Allowlist: genai.Ptr(interactions.NewAllowlist([]interactions.AllowlistEntry{
                {
                    Domain: "github.com",
                    Transform: genai.Ptr(interactions.NewTransform(map[string]string{
                        "Authorization": "Basic YOUR_BASE64_TOKEN",
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
            Input:       interactions.NewInteractionsInput("Run the test for my backend app and fix any issue."),
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
    "input": "Run the test for my backend app and fix any issue.",
    "environment": {
        "type": "remote",
        "sources": [\
            {\
                "type": "repository",\
                "source": "https://github.com/your-org/backend",\
                "target": "/backend-app"\
            }\
        ],
        "network": {
            "allowlist": [\
                {\
                    "domain": "github.com",\
                    "transform": {\
                        "Authorization": "Basic YOUR_BASE64_TOKEN"\
                    }\
                },\
                {\
                    "domain": "*"\
                }\
            ]
        }
    }
}'
```

For **private Cloud Storage buckets**, use a standard OAuth 2.0 Bearer token:

```
gcloud auth print-access-token
```

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[Java](https://ai.google.dev/gemini-api/docs/agent-environment#java)[Go](https://ai.google.dev/gemini-api/docs/agent-environment#go)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
interaction = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="Analyze the discrepancies across the data in workspace",
    environment={
        "type": "remote",
        "sources": [\
            {\
                "type": "gcs",\
                "source": "gs://my-private-bucket/data",\
                "target": "/workspace",\
            }\
        ],
        "network": {
            "allowlist": [\
                {\
                    "domain": "*.googleapis.com",\
                    "transform": {\
                        "Authorization": "Bearer YOUR_GCS_TOKEN"\
                    }\
                },\
                {\
                    "domain": "*"\
                }\
            ]
        }
    },
)
```

```
const interaction = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "Analyze the discrepancies across the data in workspace",
    environment: {
        type: "remote",
        sources: [\
            {\
                type: "gcs",\
                source: "gs://my-private-bucket/data",\
                target: "/workspace",\
            }\
        ],
        network: {
            allowlist: [\
                {\
                    domain: "storage.googleapis.com",\
                    transform: {\
                        "Authorization": "Bearer YOUR_GCS_TOKEN"\
                    }\
                },\
                {\
                    domain: "*"\
                }\
            ]
        }
    },
});
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

Environment env = Environment.builder()
    .sources(List.of(
        Source.builder()
            .type(SourceType.GCS)
            .source("gs://my-private-bucket/data")
            .target("/workspace")
            .build()
    ))
    .network(Network.of(
        EnvironmentNetworkEgressAllowlist.builder()
            .allowlist(Allowlist.of(List.of(
                AllowlistEntry.builder()
                    .domain("*.googleapis.com")
                    .transform(Transform.of(Map.of(
                        "Authorization", "Bearer YOUR_GCS_TOKEN"
                    )))
                    .build(),
                AllowlistEntry.builder()
                    .domain("*")
                    .build()
            )))
            .build()
    ))
    .build();

CreateAgentInteraction params = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("Analyze the discrepancies across the data in workspace"))
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

    env := interactions.Environment{
        Sources: []interactions.Source{
            {
                Type:   interactions.SourceTypeGcs.ToPointer(),
                Source: genai.Ptr("gs://my-private-bucket/data"),
                Target: genai.Ptr("/workspace"),
            },
        },
        Network: genai.Ptr(interactions.NewNetwork(interactions.EnvironmentNetworkEgressAllowlist{
            Allowlist: genai.Ptr(interactions.NewAllowlist([]interactions.AllowlistEntry{
                {
                    Domain: "*.googleapis.com",
                    Transform: genai.Ptr(interactions.NewTransform(map[string]string{
                        "Authorization": "Bearer YOUR_GCS_TOKEN",
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
            Input:       interactions.NewInteractionsInput("Analyze the discrepancies across the data in workspace"),
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
    "input": "Analyze the discrepancies across the data in workspace",
    "environment": {
        "type": "remote",
        "sources": [\
            {\
                "type": "gcs",\
                "source": "gs://my-private-bucket/data",\
                "target": "/workspace"\
            }\
        ],
        "network": {
            "allowlist": [\
                {\
                    "domain": "storage.googleapis.com",\
                    "transform": {\
                        "Authorization": "Bearer YOUR_GCS_TOKEN"\
                    }\
                },\
                {\
                    "domain": "*"\
                }\
            ]
        }
    }
}'
```

## Pre-installed software

The sandbox runs on Ubuntu and comes with runtimes and common packages
pre-installed. The agent can install additional packages at runtime using `pip
install` or `npm install`. Packages installed during an interaction persist when
you reuse the same `environment_id`.

| Category | Pre-installed packages |
| --- | --- |
| **UNIX tools** | `curl`, `wget`, `git`, `rsync`, `unzip`, `ripgrep`, `fd-find`, `gawk`, `bc`, `tree`, `which`, `lsof`, `htop`, `jq`, `iproute2`, `procps`, `gcloud CLI` |
| **Python 3.12** | `numpy`, `pandas`, `requests`, `google-genai`, `beautifulsoup4`, `pyyaml`, `ast-grep-cli` |
| **Node.js 22** | `create-next-app`, `create-vite`, `typescript` |

## Environment variables

Use the `env` field to set environment variables inside the sandbox. Each entry
maps a variable name to either a literal string for configuration or a
reference to a stored [credential](https://ai.google.dev/gemini-api/docs/agent-credentials) for a
secret. The agent sees them the way it would in any shell, so tools and scripts
that read from the process environment pick them up without extra wiring.

| Field | Type | Description |
| --- | --- | --- |
| `env` | `object` | Map of variable name to value. A value is either a literal `string` or a credential reference of the form `{"credential": "credential-id"}`. |

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="Build the project and run the test suite.",
    environment={
        "type": "remote",
        "env": {
            "NODE_ENV": "production",
            "LOG_LEVEL": "debug",
            "API_TOKEN": {"credential": "my-api-token"},
        },
    },
)

print(interaction.output_text)
```

```
import { GoogleGenAI } from "@google/genai";

const client = new GoogleGenAI({});

const interaction = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "Build the project and run the test suite.",
    environment: {
        type: "remote",
        env: {
            NODE_ENV: "production",
            LOG_LEVEL: "debug",
            API_TOKEN: { credential: "my-api-token" },
        },
    },
});

console.log(interaction.output_text);
```

```
curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions" \
-H "Content-Type: application/json" \
-H "x-goog-api-key: $GEMINI_API_KEY" \
-d '{
    "agent": "antigravity-preview-09-2026",
    "input": [{"type": "text", "text": "Build the project and run the test suite."}],
    "environment": {
        "type": "remote",
        "env": {
            "NODE_ENV": "production",
            "LOG_LEVEL": "debug",
            "API_TOKEN": {"credential": "my-api-token"}
        }
    }
}'
```

Variables apply to every command the agent runs in that interaction, including
shell commands, build steps, and any process it starts.

The two value types behave differently. A literal string is written into the
container as plain text. A credential reference is not: the variable receives a
placeholder, and the egress proxy substitutes the real secret only on outbound
requests to that credential's trusted domains. See
[Use credentials as environment variables](https://ai.google.dev/gemini-api/docs/agent-credentials#environment-variables)
for how that works.

## Network configuration

By default, environments have unrestricted outbound network access. Use the
`network` field to restrict outbound traffic to specific domains. Each rule
specifies a `domain`, plus an optional `credential` to inject a stored secret
and an optional `transform` object to inject headers into matching requests.
These headers can be unique per interaction, and you can update them for the same environment.

| Field | Type | Description |
| --- | --- | --- |
| `domain` | `string` | Domain to match. Use an exact hostname or `*` for all domains. |
| `credential` | `string` | ID of a stored [credential](https://ai.google.dev/gemini-api/docs/agent-credentials). The egress proxy resolves it and injects the auth header at request time. |
| `transform` | `object` | Object containing flat key-value pairs representing headers to inject into matching requests, e.g. `{"Authorization": "Bearer ..."}`. |

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[Java](https://ai.google.dev/gemini-api/docs/agent-environment#java)[Go](https://ai.google.dev/gemini-api/docs/agent-environment#go)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="Fetch the latest issues from the GitHub API for my-org/my-repo.",
    environment={
        "type": "remote",
        "network": {
            "allowlist": [\
                {\
                    "domain": "api.github.com",\
                    "transform": {\
                        "Authorization": "Bearer ghp_your_github_token"\
                    },\
                },\
                {"domain": "pypi.org"},\
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

const interaction = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "Fetch the latest issues from the GitHub API for my-org/my-repo.",
    environment: {
        type: "remote",
        network: {
            allowlist: [\
                {\
                    domain: "api.github.com",\
                    transform: {\
                        "Authorization": "Bearer ghp_your_github_token"\
                    },\
                },\
                { domain: "pypi.org" },\
                { domain: "*" },\
            ]
        }
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
import com.google.genai.gaos.models.interactions.Transform;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import java.util.List;
import java.util.Map;

Client client = new Client();

Environment env = Environment.builder()
    .network(Network.of(
        EnvironmentNetworkEgressAllowlist.builder()
            .allowlist(Allowlist.of(List.of(
                AllowlistEntry.builder()
                    .domain("api.github.com")
                    .transform(Transform.of(Map.of(
                        "Authorization", "Bearer ghp_your_github_token"
                    )))
                    .build(),
                AllowlistEntry.builder().domain("pypi.org").build(),
                AllowlistEntry.builder().domain("*").build()
            )))
            .build()
    ))
    .build();

CreateAgentInteraction params = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("Fetch the latest issues from the GitHub API for my-org/my-repo."))
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

    env := interactions.Environment{
        Network: genai.Ptr(interactions.NewNetwork(interactions.EnvironmentNetworkEgressAllowlist{
            Allowlist: genai.Ptr(interactions.NewAllowlist([]interactions.AllowlistEntry{
                {
                    Domain: "api.github.com",
                    Transform: genai.Ptr(interactions.NewTransform(map[string]string{
                        "Authorization": "Bearer ghp_your_github_token",
                    })),
                },
                {
                    Domain: "pypi.org",
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
            Input:       interactions.NewInteractionsInput("Fetch the latest issues from the GitHub API for my-org/my-repo."),
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
    "input": [{"type": "text", "text": "Fetch the latest issues from the GitHub API for my-org/my-repo."}],
    "environment": {
        "type": "remote",
        "network": {
            "allowlist": [\
                {\
                    "domain": "api.github.com",\
                    "transform": {\
                        "Authorization": "Bearer ghp_your_github_token"\
                    }\
                },\
                {"domain": "pypi.org"},\
                {"domain": "*"}\
            ]
        }
    }
}'
```

When an allowlist is set, only requests to explicitly listed domains are
permitted. You can use wildcards to match subdomains (e.g., `{"domain":
"*.example.com"}`), but note that this does not match the root domain
`example.com`, which must be added separately. To permit all other traffic, such
as routing unlisted domains without injected headers, add `{"domain": "*"}` as a
catch-all entry.

### Credentials

There are two ways to authenticate outbound traffic, a stored credential
referenced by ID and an inline `transform` on the allowlist rule. The egress
proxy applies both on the wire, so in both cases the secret never enters the
sandbox and never appears in your interaction payloads.

A [managed credential](https://ai.google.dev/gemini-api/docs/agent-credentials) is the one to reach
for when you want to store the secret once and reuse it. Every environment,
agent, and trigger in your project can reference the same ID, and you rotate it
in one place.

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
from google import genai

client = genai.Client()

# Store the secret once
client.credentials.create(
    id="github-production",
    type="bearer_token",
    token="ghp_your_github_token",
)

interaction = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="Fetch the latest issues from the GitHub API for my-org/my-repo.",
    environment={
        "type": "remote",
        "network": {
            "allowlist": [\
                {"domain": "api.github.com", "credential": "github-production"},\
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

// Store the secret once
await client.credentials.create({
    id: "github-production",
    type: "bearer_token",
    token: "ghp_your_github_token",
});

const interaction = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "Fetch the latest issues from the GitHub API for my-org/my-repo.",
    environment: {
        type: "remote",
        network: {
            allowlist: [\
                { domain: "api.github.com", credential: "github-production" },\
                { domain: "*" },\
            ]
        }
    },
});

console.log(interaction.output_text);
```

```
# Store the secret once
curl -X POST "https://generativelanguage.googleapis.com/v1beta/credentials" \
-H "Content-Type: application/json" \
-H "x-goog-api-key: $GEMINI_API_KEY" \
-d '{
    "id": "github-production",
    "type": "bearer_token",
    "token": "ghp_your_github_token"
}'

curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions" \
-H "Content-Type: application/json" \
-H "x-goog-api-key: $GEMINI_API_KEY" \
-d '{
    "agent": "antigravity-preview-09-2026",
    "input": "Fetch the latest issues from the GitHub API for my-org/my-repo.",
    "environment": {
        "type": "remote",
        "network": {
            "allowlist": [\
                { "domain": "api.github.com", "credential": "github-production" },\
                { "domain": "*" }\
            ]
        }
    }
}'
```

An `oauth2` credential also refreshes its access token on its own, so a
long-running interaction does not break when the token expires. See
[Credentials](https://ai.google.dev/gemini-api/docs/agent-credentials) for the full list of
credential types and management operations.

You can also set headers inline with `transform`. This fits when the value
belongs to a single call, for example a token you generate right before creating
the interaction. Headers set this way are injected by the same egress proxy,
they are never exposed inside the sandbox as environment variables or files.

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[Java](https://ai.google.dev/gemini-api/docs/agent-environment#java)[Go](https://ai.google.dev/gemini-api/docs/agent-environment#go)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
import subprocess
from google import genai

# Fetch a short-lived access token from your local gcloud CLI
gcloud_token = subprocess.check_output(
    ["gcloud", "auth", "print-access-token"], text=True
).strip()

client = genai.Client()

interaction = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="List the files in gs://my-bucket/reports/ using the GCS JSON API.",
    environment={
        "type": "remote",
        "network": {
            "allowlist": [\
                {\
                    "domain": "storage.googleapis.com",\
                    "transform": {\
                        "Authorization": f"Bearer {gcloud_token}"\
                    },\
                }\
            ]
        },
    },
)

print(interaction.output_text)
```

```
import { GoogleGenAI } from "@google/genai";

import { execSync } from "child_process";

const gcloudToken = execSync("gcloud auth print-access-token").toString().trim();

const client = new GoogleGenAI({});

const interaction = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "List the files in gs://my-bucket/reports/ using the GCS JSON API.",
    environment: {
        type: "remote",
        network: {
            allowlist: [\
                {\
                    domain: "storage.googleapis.com",\
                    transform: {\
                        "Authorization": `Bearer ${gcloudToken}`\
                    },\
                }\
            ]
        }
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
import com.google.genai.gaos.models.interactions.Transform;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

// Fetch a short-lived access token from your local gcloud CLI
Process process = new ProcessBuilder("gcloud", "auth", "print-access-token").start();
String gcloudToken = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8).trim();

Client client = new Client();

Environment env = Environment.builder()
    .network(Network.of(
        EnvironmentNetworkEgressAllowlist.builder()
            .allowlist(Allowlist.of(List.of(
                AllowlistEntry.builder()
                    .domain("storage.googleapis.com")
                    .transform(Transform.of(Map.of(
                        "Authorization", "Bearer " + gcloudToken
                    )))
                    .build()
            )))
            .build()
    ))
    .build();

CreateAgentInteraction params = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("List the files in gs://my-bucket/reports/ using the GCS JSON API."))
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
    "os/exec"
    "strings"

    "google.golang.org/genai"
    "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()

    // Fetch a short-lived access token from your local gcloud CLI
    out, err := exec.Command("gcloud", "auth", "print-access-token").Output()
    if err != nil {
        log.Fatal(err)
    }
    gcloudToken := strings.TrimSpace(string(out))

    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    env := interactions.Environment{
        Network: genai.Ptr(interactions.NewNetwork(interactions.EnvironmentNetworkEgressAllowlist{
            Allowlist: genai.Ptr(interactions.NewAllowlist([]interactions.AllowlistEntry{
                {
                    Domain: "storage.googleapis.com",
                    Transform: genai.Ptr(interactions.NewTransform(map[string]string{
                        "Authorization": "Bearer " + gcloudToken,
                    })),
                },
            })),
        })),
    }

    res, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{
        Body: operations.NewCreateInteractionRequestBody(interactions.CreateAgentInteraction{
            Agent:       interactions.AgentOption("antigravity-preview-09-2026"),
            Input:       interactions.NewInteractionsInput("List the files in gs://my-bucket/reports/ using the GCS JSON API."),
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
    "input": "List the files in gs://my-bucket/reports/ using the GCS JSON API.",
    "environment": {
        "type": "remote",
        "network": {
            "allowlist": [\
                {\
                    "domain": "storage.googleapis.com",\
                    "transform": {\
                        "Authorization": "Bearer <YOUR_GCLOUD_TOKEN>"\
                    }\
                }\
            ]
        }
    }
}'
```

`credential` and `transform` can appear on the same rule. The credential is
applied first and `transform` merges on top, so an explicit `transform` header
wins if both set the same key. A common pattern is a credential for the
authentication header plus a `transform` for the extra headers the service
expects alongside it.

### Disable network access

To block all outbound network access, set `network` to `disabled`:

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[Java](https://ai.google.dev/gemini-api/docs/agent-environment#java)[Go](https://ai.google.dev/gemini-api/docs/agent-environment#go)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="Analyze the local files only.",
    environment={
        "type": "remote",
        "network": "disabled",
    },
)

print(interaction.output_text)
```

```
import { GoogleGenAI } from "@google/genai";

const client = new GoogleGenAI({});

const interaction = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "Analyze the local files only.",
    environment: {
        type: "remote",
        network: "disabled",
    },
});

console.log(interaction.output_text);
```

```
import com.google.genai.Client;
import com.google.genai.gaos.models.interactions.AgentOption;
import com.google.genai.gaos.models.interactions.CreateAgentInteraction;
import com.google.genai.gaos.models.interactions.CreateAgentInteractionEnvironment;
import com.google.genai.gaos.models.interactions.Environment;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;
import com.google.genai.gaos.models.interactions.Network;
import com.google.genai.gaos.models.interactions.NetworkEnum;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;

Client client = new Client();

Environment env = Environment.builder()
    .network(Network.of(NetworkEnum.DISABLED))
    .build();

CreateAgentInteraction params = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("Analyze the local files only."))
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

    env := interactions.Environment{
        Network: genai.Ptr(interactions.NewNetwork(interactions.NetworkEnumDisabled)),
    }

    res, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{
        Body: operations.NewCreateInteractionRequestBody(interactions.CreateAgentInteraction{
            Agent:       interactions.AgentOption("antigravity-preview-09-2026"),
            Input:       interactions.NewInteractionsInput("Analyze the local files only."),
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
    "input": "Analyze the local files only.",
    "environment": {
        "type": "remote",
        "network": "disabled"
    }
}'
```

### Refresh credentials

Inline tokens such as access tokens and short-lived API keys expire.
You can refresh them by passing the existing `environment_id` together with a
new `network` configuration on the next interaction. The new network rules
fully replace the previous ones, while the environment's file system state
(installed packages, files, repositories) is preserved.

If you use a stored [credential](https://ai.google.dev/gemini-api/docs/agent-credentials) instead,
you don't need this. An `oauth2` credential refreshes itself, and rotating any
credential is a `PATCH` on the credential that leaves every allowlist rule
referencing it untouched.

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[Java](https://ai.google.dev/gemini-api/docs/agent-environment#java)[Go](https://ai.google.dev/gemini-api/docs/agent-environment#go)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
from google import genai

client = genai.Client()

# First interaction: use an initial token
first = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="List the files in gs://my-bucket/reports/ using the GCS JSON API.",
    environment={
        "type": "remote",
        "network": {
            "allowlist": [\
                {\
                    "domain": "storage.googleapis.com",\
                    "transform": {\
                        "Authorization": "Bearer INITIAL_TOKEN"\
                    },\
                }\
            ]
        },
    },
)

# Later: refresh the token on the same environment
result = client.interactions.create(
    agent="antigravity-preview-09-2026",
    input="Now download the file reports/q1.csv from the same bucket.",
    environment={
        "type": "remote",
        "environment_id": first.environment_id,
        "network": {
            "allowlist": [\
                {\
                    "domain": "storage.googleapis.com",\
                    "transform": {\
                        "Authorization": "Bearer REFRESHED_TOKEN"\
                    },\
                }\
            ]
        },
    },
)

print(result.output_text)
```

```
import { GoogleGenAI } from "@google/genai";

const client = new GoogleGenAI({});

// First interaction: use an initial token
const first = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "List the files in gs://my-bucket/reports/ using the GCS JSON API.",
    environment: {
        type: "remote",
        network: {
            allowlist: [\
                {\
                    domain: "storage.googleapis.com",\
                    transform: {\
                        "Authorization": "Bearer INITIAL_TOKEN"\
                    },\
                }\
            ]
        }
    },
});

// Later: refresh the token on the same environment
const result = await client.interactions.create({
    agent: "antigravity-preview-09-2026",
    input: "Now download the file reports/q1.csv from the same bucket.",
    environment: {
        type: "remote",
        environment_id: first.environment_id,
        network: {
            allowlist: [\
                {\
                    domain: "storage.googleapis.com",\
                    transform: {\
                        "Authorization": "Bearer REFRESHED_TOKEN"\
                    },\
                }\
            ]
        }
    },
});

console.log(result.output_text);
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
import com.google.genai.gaos.models.interactions.Transform;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import java.util.List;
import java.util.Map;

Client client = new Client();

// First interaction: use an initial token
Environment initialEnv = Environment.builder()
    .network(Network.of(
        EnvironmentNetworkEgressAllowlist.builder()
            .allowlist(Allowlist.of(List.of(
                AllowlistEntry.builder()
                    .domain("storage.googleapis.com")
                    .transform(Transform.of(Map.of(
                        "Authorization", "Bearer INITIAL_TOKEN"
                    )))
                    .build()
            )))
            .build()
    ))
    .build();

CreateAgentInteraction firstParams = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("List the files in gs://my-bucket/reports/ using the GCS JSON API."))
    .environment(CreateAgentInteractionEnvironment.of(initialEnv))
    .build();

Interaction first = client.interactions.create(CreateInteractionRequestBody.of(firstParams)).interaction().get();

// Later: refresh the token on the same environment
Environment refreshedEnv = Environment.builder()
    .environmentId(first.environmentId().orElse(""))
    .network(Network.of(
        EnvironmentNetworkEgressAllowlist.builder()
            .allowlist(Allowlist.of(List.of(
                AllowlistEntry.builder()
                    .domain("storage.googleapis.com")
                    .transform(Transform.of(Map.of(
                        "Authorization", "Bearer REFRESHED_TOKEN"
                    )))
                    .build()
            )))
            .build()
    ))
    .build();

CreateAgentInteraction secondParams = CreateAgentInteraction.builder()
    .agent(AgentOption.of("antigravity-preview-09-2026"))
    .input(InteractionsInput.of("Now download the file reports/q1.csv from the same bucket."))
    .environment(CreateAgentInteractionEnvironment.of(refreshedEnv))
    .build();

Interaction result = client.interactions.create(CreateInteractionRequestBody.of(secondParams)).interaction().get();
System.out.println(result.outputText().orElse(""));
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

    // First interaction: use an initial token
    initialEnv := interactions.Environment{
        Network: genai.Ptr(interactions.NewNetwork(interactions.EnvironmentNetworkEgressAllowlist{
            Allowlist: genai.Ptr(interactions.NewAllowlist([]interactions.AllowlistEntry{
                {
                    Domain: "storage.googleapis.com",
                    Transform: genai.Ptr(interactions.NewTransform(map[string]string{
                        "Authorization": "Bearer INITIAL_TOKEN",
                    })),
                },
            })),
        })),
    }

    firstRes, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{
        Body: operations.NewCreateInteractionRequestBody(interactions.CreateAgentInteraction{
            Agent:       interactions.AgentOption("antigravity-preview-09-2026"),
            Input:       interactions.NewInteractionsInput("List the files in gs://my-bucket/reports/ using the GCS JSON API."),
            Environment: genai.Ptr(interactions.NewCreateAgentInteractionEnvironment(initialEnv)),
        }),
    })
    if err != nil {
        log.Fatal(err)
    }
    first := firstRes.Interaction

    // Later: refresh the token on the same environment
    refreshedEnv := interactions.Environment{
        EnvironmentID: first.EnvironmentID,
        Network: genai.Ptr(interactions.NewNetwork(interactions.EnvironmentNetworkEgressAllowlist{
            Allowlist: genai.Ptr(interactions.NewAllowlist([]interactions.AllowlistEntry{
                {
                    Domain: "storage.googleapis.com",
                    Transform: genai.Ptr(interactions.NewTransform(map[string]string{
                        "Authorization": "Bearer REFRESHED_TOKEN",
                    })),
                },
            })),
        })),
    }

    secondRes, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{
        Body: operations.NewCreateInteractionRequestBody(interactions.CreateAgentInteraction{
            Agent:       interactions.AgentOption("antigravity-preview-09-2026"),
            Input:       interactions.NewInteractionsInput("Now download the file reports/q1.csv from the same bucket."),
            Environment: genai.Ptr(interactions.NewCreateAgentInteractionEnvironment(refreshedEnv)),
        }),
    })
    if err != nil {
        log.Fatal(err)
    }
    if secondRes.Interaction.OutputText != nil {
        fmt.Println(*secondRes.Interaction.OutputText)
    }
}
```

```
# Use the environment_id from a previous interaction
curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions" \
-H "Content-Type: application/json" \
-H "x-goog-api-key: $GEMINI_API_KEY" \
-d '{
    "agent": "antigravity-preview-09-2026",
    "input": "Now download the file reports/q1.csv from the same bucket.",
    "environment": {
        "type": "remote",
        "environment_id": "<ENVIRONMENT_ID_FROM_PREVIOUS_INTERACTION>",
        "network": {
            "allowlist": [\
                {\
                    "domain": "storage.googleapis.com",\
                    "transform": {\
                        "Authorization": "Bearer REFRESHED_TOKEN"\
                    }\
                }\
            ]
        }
    }
}'
```

## Environment lifecycle

Environments follow this lifecycle:

| State | Behavior |
| --- | --- |
| **Created** | Provisioned when an interaction specifies `environment: "remote"` or a config object. |
| **Active** | Running while an interaction is in progress. |
| **Idle** | Auto-snapshot and stopped after 15 minutes of inactivity. |
| **Offline** | Retained for 7 days since last active. Can be resumed by passing its ID. |
| **Deleted** | Removed from the system automatically after 7-day TTL retention expires or upon manual deletion. |

## Environments API

You can use the Environments API to programmatically manage sandbox sessions.
Enumerating environments lets you discover active session IDs and recover state
if a client connection terminates during a long-running task. You can also
inspect session metadata and explicitly delete environments when workflows
conclude rather than waiting for automatic TTL expiration.

### List environments

List active environments belonging to your project. Use pagination parameters
to control the response batch size.

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[Java](https://ai.google.dev/gemini-api/docs/agent-environment#java)[Go](https://ai.google.dev/gemini-api/docs/agent-environment#go)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
from google import genai

client = genai.Client()

response = client.environments.list(page_size=10)
for env in response.environments:
    print(f"Environment ID: {env.id}, Status: {env.status}")
```

```
import { GoogleGenAI } from "@google/genai";

const client = new GoogleGenAI({});

const response = await client.environments.list({ page_size: 10 });
for (const env of response.environments) {
    console.log(`Environment ID: ${env.id}, Status: ${env.status}`);
}
```

```
import com.google.genai.Client;
import com.google.genai.gaos.models.environments.Environment;
import com.google.genai.gaos.models.environments.ListEnvironmentsResponse;
import java.util.List;

Client client = new Client();

ListEnvironmentsResponse response = client.environments.listEnvironments()
    .pageSize(10)
    .call()
    .listEnvironmentsResponse()
    .get();

for (Environment env : response.environments().orElse(List.of())) {
    System.out.println("Environment ID: " + env.id().orElse("") + ", Status: " + env.status().orElse(null));
}
```

```
package main

import (
    "context"
    "fmt"
    "log"
    "os"

    "google.golang.org/genai"
    interactionssdk "google.golang.org/genai/interactions"
    "google.golang.org/genai/interactions/models/components"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    sdk := interactionssdk.New(interactionssdk.WithSecurity(components.Security{
        APIKey: genai.Ptr(os.Getenv("GEMINI_API_KEY")),
    }))

    res, err := sdk.Environments.ListEnvironments(ctx, operations.ListEnvironmentsRequest{
        PageSize: genai.Ptr(10),
    })
    if err != nil {
        log.Fatal(err)
    }

    if res.ListEnvironmentsResponse != nil {
        for _, env := range res.ListEnvironmentsResponse.Environments {
            fmt.Printf("Environment ID: %s, Status: %v\n", env.ID, env.Status)
        }
    }
}
```

```
curl -X GET "https://generativelanguage.googleapis.com/v1beta/environments?pageSize=10" \
-H "x-goog-api-key: $GEMINI_API_KEY"
```

The response looks similar to the following:

```
{
  "environments": [\
    {\
      "id": "140128b2a13c12c00a5a0d8cf7af9469",\
      "status": "active"\
    },\
    {\
      "id": "362b738275a1d74af6f1c62bc050da73",\
      "status": "active"\
    }\
  ],
  "next_page_token": "Cj...5aE="
}
```

### Get an environment

Retrieve metadata and configuration details for a specific environment by its
resource name.

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[Java](https://ai.google.dev/gemini-api/docs/agent-environment#java)[Go](https://ai.google.dev/gemini-api/docs/agent-environment#go)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
from google import genai

client = genai.Client()

env = client.environments.get(id="YOUR_ENVIRONMENT_ID")
print(f"Environment ID: {env.id}, Status: {env.status}")
```

```
import { GoogleGenAI } from "@google/genai";

const client = new GoogleGenAI({});

const env = await client.environments.get("YOUR_ENVIRONMENT_ID");
console.log(`Environment ID: ${env.id}, Status: ${env.status}`);
```

```
import com.google.genai.Client;
import com.google.genai.gaos.models.environments.Environment;

Client client = new Client();

Environment env = client.environments.getEnvironment("YOUR_ENVIRONMENT_ID").environment().get();
System.out.println("Environment ID: " + env.id().orElse("") + ", Status: " + env.status().orElse(null));
```

```
package main

import (
    "context"
    "fmt"
    "log"
    "os"

    "google.golang.org/genai"
    interactionssdk "google.golang.org/genai/interactions"
    "google.golang.org/genai/interactions/models/components"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    sdk := interactionssdk.New(interactionssdk.WithSecurity(components.Security{
        APIKey: genai.Ptr(os.Getenv("GEMINI_API_KEY")),
    }))

    res, err := sdk.Environments.GetEnvironment(ctx, operations.GetEnvironmentRequest{
        ID: "YOUR_ENVIRONMENT_ID",
    })
    if err != nil {
        log.Fatal(err)
    }

    env := res.Environment
    fmt.Printf("Environment ID: %s, Status: %v\n", env.ID, env.Status)
}
```

```
curl -X GET "https://generativelanguage.googleapis.com/v1beta/environments/YOUR_ENVIRONMENT_ID" \
-H "x-goog-api-key: $GEMINI_API_KEY"
```

The response looks similar to the following:

```
{
  "id": "140128b2a13c12c00a5a0d8cf7af9469",
  "status": "active",
  "sources": [\
    {\
      "type": "repository",\
      "source": "https://github.com/octocat/Spoon-Knife",\
      "target": "/workspace/spoon-knife"\
    }\
  ],
  "network": {
    "allowlist": [\
      {\
        "domain": "api.github.com"\
      },\
      {\
        "domain": "github.com"\
      }\
    ]
  }
}
```

### Delete an environment

Explicitly terminate and delete an environment to clean up sandbox resources
when your tasks or pipelines finish.

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[Java](https://ai.google.dev/gemini-api/docs/agent-environment#java)[Go](https://ai.google.dev/gemini-api/docs/agent-environment#go)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
from google import genai

client = genai.Client()

client.environments.delete(id="YOUR_ENVIRONMENT_ID")
```

```
import { GoogleGenAI } from "@google/genai";

const client = new GoogleGenAI({});

await client.environments.delete("YOUR_ENVIRONMENT_ID");
```

```
import com.google.genai.Client;

Client client = new Client();

client.environments.deleteEnvironment("YOUR_ENVIRONMENT_ID");
```

```
package main

import (
    "context"
    "log"
    "os"

    "google.golang.org/genai"
    interactionssdk "google.golang.org/genai/interactions"
    "google.golang.org/genai/interactions/models/components"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    sdk := interactionssdk.New(interactionssdk.WithSecurity(components.Security{
        APIKey: genai.Ptr(os.Getenv("GEMINI_API_KEY")),
    }))

    _, err := sdk.Environments.DeleteEnvironment(ctx, operations.DeleteEnvironmentRequest{
        ID: "YOUR_ENVIRONMENT_ID",
    })
    if err != nil {
        log.Fatal(err)
    }
}
```

```
curl -X DELETE "https://generativelanguage.googleapis.com/v1beta/environments/YOUR_ENVIRONMENT_ID" \
-H "x-goog-api-key: $GEMINI_API_KEY"
```

## Manage files in the environment

The agent creates and modifies files inside the sandbox during execution. You
can browse directory contents, get file metadata, download individual files or
entire directories as tar archives, and upload files or extract archives
directly into the environment. Storage in sandbox environments is subject to
fair usage limits.

### List files in a directory

List the contents of a directory in the environment. By default, lists the root
directory.

#### Query parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `recursive` | boolean | When `true`, lists all files and directories recursively. Default: `false`. |

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
from google import genai

client = genai.Client()

# List root directory
response = client.environments.files.list(
    environment="YOUR_ENVIRONMENT_ID",
    path="",
)
for file in response.files:
    print(f"{file.name} ({file.type}) - {file.path}")

# List a subdirectory recursively
response = client.environments.files.list(
    environment="YOUR_ENVIRONMENT_ID",
    path="src",
    recursive=True,
)
for file in response.files:
    print(f"{file.name} ({file.type}) - {file.path}")
```

```
import { GoogleGenAI } from "@google/genai";

const client = new GoogleGenAI({});

// List root directory
const response = await client.environments.files.list({
    environment: "YOUR_ENVIRONMENT_ID",
    path: "",
});
for (const file of response.files) {
    console.log(`${file.name} (${file.type}) - ${file.path}`);
}

// List a subdirectory recursively
const srcResponse = await client.environments.files.list({
    environment: "YOUR_ENVIRONMENT_ID",
    path: "src",
    recursive: true,
});
for (const file of srcResponse.files) {
    console.log(`${file.name} (${file.type}) - ${file.path}`);
}
```

```
# List root directory
curl -X GET "https://generativelanguage.googleapis.com/v1beta/environments/$ENV_ID/files" \
  -H "x-goog-api-key: $GEMINI_API_KEY"

# List a subdirectory
curl -X GET "https://generativelanguage.googleapis.com/v1beta/environments/$ENV_ID/files/src" \
  -H "x-goog-api-key: $GEMINI_API_KEY"

# List all files recursively
curl -X GET "https://generativelanguage.googleapis.com/v1beta/environments/$ENV_ID/files?recursive=true" \
  -H "x-goog-api-key: $GEMINI_API_KEY"
```

The response returns a `files` array with metadata for each entry:

```
{
  "files": [\
    {\
      "name": "config",\
      "path": "config",\
      "type": "DIRECTORY",\
      "created": "2026-08-12T07:44:18Z",\
      "modified": "2026-08-12T07:44:18Z"\
    },\
    {\
      "name": "main.py",\
      "path": "src/main.py",\
      "type": "FILE",\
      "size_bytes": "15",\
      "mime_type": "text/x-python; charset=utf-8",\
      "created": "2026-08-12T07:44:20Z",\
      "modified": "2026-08-12T07:44:20Z"\
    }\
  ]
}
```

#### File entry fields

| Field | Type | Description |
| --- | --- | --- |
| `name` | string | The file or directory name. |
| `path` | string | The full path relative to the environment root. |
| `type` | string | Either `FILE` or `DIRECTORY`. |
| `size_bytes` | string | File size in bytes (files only). |
| `mime_type` | string | MIME type (files only). |
| `created` | string | ISO 8601 creation timestamp. |
| `modified` | string | ISO 8601 last-modified timestamp. |

### Get file metadata

Get metadata for a specific file by path.

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
from google import genai

client = genai.Client()

response = client.environments.files.list(
    environment="YOUR_ENVIRONMENT_ID",
    path="src/main.py",
)
file = response.files[0]
print(f"Name: {file.name}, Size: {file.size_bytes} bytes, Type: {file.mime_type}")
```

```
import { GoogleGenAI } from "@google/genai";

const client = new GoogleGenAI({});

const response = await client.environments.files.list({
    environment: "YOUR_ENVIRONMENT_ID",
    path: "src/main.py",
});
const file = response.files[0];
console.log(`Name: ${file.name}, Size: ${file.size_bytes} bytes, Type: ${file.mime_type}`);
```

```
curl -X GET "https://generativelanguage.googleapis.com/v1beta/environments/$ENV_ID/files/src/main.py" \
  -H "x-goog-api-key: $GEMINI_API_KEY"
```

The response returns the file metadata wrapped in a `files` array:

```
{
  "files": [\
    {\
      "name": "main.py",\
      "path": "src/main.py",\
      "type": "FILE",\
      "size_bytes": "15",\
      "mime_type": "text/x-python; charset=utf-8",\
      "created": "2026-08-12T07:44:20Z",\
      "modified": "2026-08-12T07:44:20Z"\
    }\
  ]
}
```

If the file doesn't exist, the API returns a `404` error:

```
{
  "error": {
    "message": "Path 'nonexistent.txt' not found in environment 'ENV_ID'.",
    "code": "not_found"
  }
}
```

### Download a single file

Download the contents of a specific file. In the SDKs, use the `download()`
method. In REST requests, append the `?alt=media` query parameter to the file
path. The server responds with `200 OK` and streams the raw file content.

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
from google import genai

client = genai.Client()

content = client.environments.files.download(
    environment="YOUR_ENVIRONMENT_ID",
    path="src/main.py",
)

with open("main.py", "wb") as f:
    f.write(content)
```

```
import { GoogleGenAI } from "@google/genai";
import * as fs from "fs";

const client = new GoogleGenAI({});

const bytes = await client.environments.files.download({
    environment: "YOUR_ENVIRONMENT_ID",
    path: "src/main.py",
});

fs.writeFileSync("main.py", Buffer.from(bytes));
```

```
curl -L -X GET "https://generativelanguage.googleapis.com/v1beta/environments/$ENV_ID/files/src/main.py?alt=media" \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -o main.py
```

### Download a directory as a tar archive

Download an entire directory as a tar archive by requesting the directory path
with `?alt=media`. This returns a POSIX tar file (not gzipped). Use
`recursive=true` to include nested subdirectories.

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
import tarfile
from google import genai

client = genai.Client()

# Download a subdirectory archive
archive = client.environments.files.download(
    environment="YOUR_ENVIRONMENT_ID",
    path="src",
)

with open("src.tar", "wb") as f:
    f.write(archive)

with tarfile.open("src.tar") as tar:
    tar.extractall(path="./extracted")
```

```
import { GoogleGenAI } from "@google/genai";
import { execSync } from "child_process";
import * as fs from "fs";

const client = new GoogleGenAI({});

// Download a subdirectory archive
const bytes = await client.environments.files.download({
    environment: "YOUR_ENVIRONMENT_ID",
    path: "src",
});

fs.writeFileSync("src.tar", Buffer.from(bytes));
execSync("tar -xf src.tar -C ./extracted");
```

```
# Download a subdirectory (top-level files only)
curl -L -X GET "https://generativelanguage.googleapis.com/v1beta/environments/$ENV_ID/files/src?alt=media" \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -o src.tar

# Download a subdirectory recursively (includes nested directories)
curl -L -X GET "https://generativelanguage.googleapis.com/v1beta/environments/$ENV_ID/files/config?alt=media&recursive=true" \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -o config.tar

# Download root directory
curl -L -X GET "https://generativelanguage.googleapis.com/v1beta/environments/$ENV_ID/files?alt=media" \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -o snapshot.tar

# Extract the archive
tar xf snapshot.tar -C ./extracted
```

#### Behavior matrix

The following behavior matrix summarizes the expected response and archive behavior across file and directory endpoints, HTTP methods, and query parameters:

| Request | `alt` | `recursive` | `extract` | `overwrite` | Response |
| --- | --- | --- | --- | --- | --- |
| `GET /files` | (none) | (none) | - | - | JSON listing of root directory |
| `GET /files/{path}` (file) | (none) | - | - | - | JSON metadata for the file |
| `GET /files/{path}` (dir) | (none) | `false` | - | - | JSON listing of immediate children |
| `GET /files/{path}` (dir) | (none) | `true` | - | - | JSON listing of all descendants |
| `GET /files/{path}?alt=media` (file) | `media` | - | - | - | Raw file content |
| `GET /files/{path}?alt=media` (dir) | `media` | `false` | - | - | Tar archive of immediate files in directory |
| `GET /files/{path}?alt=media` (dir) | `media` | `true` | - | - | Tar archive of all files recursively |
| `GET /files?alt=media` | `media` | `false` | - | - | Tar archive of root-level files only |
| `PUT /files/{path}` (file) | - | - | `false` | `false` | Writes the file at path. Returns `409 Conflict` if it already exists |
| `PUT /files/{path}?overwrite=true` | - | - | `false` | `true` | Writes or overwrites the file at path |
| `PUT /files/{path}?extract=true` | - | - | `true` | `false` | Unpacks archive into destination directory. Returns `409 Conflict` if any target file exists |
| `PUT /files/{path}?extract=true&overwrite=true` | - | - | `true` | `true` | Unpacks archive, replacing any existing files |

### Upload files to the environment

Upload individual files or directory archives directly to an existing environment
sandbox using HTTP `PUT`. Parent directories are created automatically if they
do not exist. Storage in environments is subject to fair usage limits.

#### Upload a single file

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
from google import genai

client = genai.Client()

with open("local_file.txt", "rb") as f:
    result = client.environments.files.upload(
        environment="YOUR_ENVIRONMENT_ID",
        path="workspace/data/file.txt",
        file=f,
        mime_type="text/plain",
        overwrite=True,
    )

file = result.files[0]
print(f"Uploaded: {file.name} ({file.size_bytes} bytes)")
```

```
import { GoogleGenAI } from "@google/genai";
import * as fs from "fs";

const client = new GoogleGenAI({});

const content = fs.readFileSync("local_file.txt");
const result = await client.environments.files.upload({
    environment: "YOUR_ENVIRONMENT_ID",
    path: "workspace/data/file.txt",
    file: content,
    mime_type: "text/plain",
    overwrite: true,
});

const file = result.files[0];
console.log(`Uploaded: ${file.name} (${file.size_bytes} bytes)`);
```

```
curl -X PUT "https://generativelanguage.googleapis.com/upload/v1beta/environments/$ENV_ID/files/workspace/data/file.txt" \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: text/plain" \
  --data-binary @local_file.txt
```

The response returns metadata for the uploaded file, wrapped in a `files` array
for consistency with the list and get endpoints:

```
{
  "files": [\
    {\
      "name": "file.txt",\
      "path": "workspace/data/file.txt",\
      "type": "FILE",\
      "size_bytes": "1024",\
      "mime_type": "text/plain"\
    }\
  ]
}
```

#### Upload and extract a directory archive

To seed an entire codebase or directory structure in a single request, upload a
`.tar` or `.tar.gz` archive with `extract=true`.

[Python](https://ai.google.dev/gemini-api/docs/agent-environment#python)[JavaScript](https://ai.google.dev/gemini-api/docs/agent-environment#javascript)[REST](https://ai.google.dev/gemini-api/docs/agent-environment#rest)More

```
from google import genai

client = genai.Client()

with open("source.tar.gz", "rb") as f:
    result = client.environments.files.upload(
        environment="YOUR_ENVIRONMENT_ID",
        path="workspace/src/",
        file=f,
        extract=True,
    )

for entry in result.files:
    print(f"Extracted: {entry.path}")
```

```
import { GoogleGenAI } from "@google/genai";
import * as fs from "fs";

const client = new GoogleGenAI({});

const archive = fs.readFileSync("source.tar.gz");
const result = await client.environments.files.upload({
    environment: "YOUR_ENVIRONMENT_ID",
    path: "workspace/src/",
    file: archive,
    extract: true,
});

for (const entry of result.files) {
    console.log(`Extracted: ${entry.path}`);
}
```

```
curl -X PUT "https://generativelanguage.googleapis.com/upload/v1beta/environments/$ENV_ID/files/workspace/src/?extract=true" \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/x-tar" \
  --data-binary @source.tar.gz
```

The response lists every file written by the archive:

```
{
  "files": [\
    {\
      "name": "app.py",\
      "path": "workspace/src/app.py",\
      "type": "FILE",\
      "size_bytes": "15",\
      "mime_type": "text/x-python"\
    },\
    {\
      "name": "requirements.txt",\
      "path": "workspace/src/requirements.txt",\
      "type": "FILE",\
      "size_bytes": "17",\
      "mime_type": "text/plain"\
    }\
  ]
}
```

#### Upload large files with a resumable session

For large payloads, or when uploading over an unreliable connection, use a
resumable session instead of sending the whole body in one request. A resumable
upload splits the transfer into chunks that can be retried individually, so a
failure part way through does not force you to start over.

Start by initiating the session with `uploadType=resumable`. Send an empty body
and use the `X-Upload-Content-Type` and `X-Upload-Content-Length` headers to
declare the media type and total size of the payload you intend to upload:

```
PUT /upload/v1beta/environments/$ENV_ID/files/workspace/data/large_dataset.bin?uploadType=resumable HTTP/1.1
Host: generativelanguage.googleapis.com
X-Upload-Content-Type: application/octet-stream
X-Upload-Content-Length: 20971520
Content-Length: 0
x-goog-api-key: $GEMINI_API_KEY
```

The response carries the session URL in the `Location` header. This URL already
contains an `upload_id`, so it does not need the API key again:

```
HTTP/1.1 200 OK
Location: https://generativelanguage.googleapis.com/upload/v1beta/environments/$ENV_ID/files/workspace/data/large_dataset.bin?uploadType=resumable&upload_id=AJjja9bfHjiYlGi60pUazCaTuPY
Content-Length: 0
```

Upload the payload to that URL in chunks. Each chunk declares its byte range and
the total size with a `Content-Range` header:

```
PUT /upload/v1beta/environments/$ENV_ID/files/workspace/data/large_dataset.bin?uploadType=resumable&upload_id=AJjja9bfHjiYlGi60pUazCaTuPY HTTP/1.1
Host: generativelanguage.googleapis.com
Content-Type: application/octet-stream
Content-Range: bytes 0-10485759/20971520
Content-Length: 10485760

<10 MB binary payload>
```

Every chunk except the last returns `308 Resume Incomplete`. The `Range` header
tells you how many bytes the server has committed, which is where you resume
from if a chunk fails:

```
HTTP/1.1 308 Resume Incomplete
Range: bytes=0-10485759
Content-Length: 0
```

Send the remaining chunks the same way:

```
PUT /upload/v1beta/environments/$ENV_ID/files/workspace/data/large_dataset.bin?uploadType=resumable&upload_id=AJjja9bfHjiYlGi60pUazCaTuPY HTTP/1.1
Host: generativelanguage.googleapis.com
Content-Type: application/octet-stream
Content-Range: bytes 10485760-20971519/20971520
Content-Length: 10485760

<remaining 10 MB binary payload>
```

The final chunk completes the upload and returns the file metadata, in the same
`files` envelope as a single-shot upload:

```
{
  "files": [\
    {\
      "name": "large_dataset.bin",\
      "path": "workspace/data/large_dataset.bin",\
      "type": "FILE",\
      "size_bytes": "20971520",\
      "mime_type": "application/octet-stream"\
    }\
  ]
}
```

Resumable sessions work with `extract` and `overwrite` as well. Set those query
parameters on the initiating request, not on the individual chunks.

#### Overwrite protection

By default, `overwrite` is `false`. If the destination path already exists, the
request returns a `409 Conflict` error and nothing is written:

```
{
  "error": {
    "message": "Requested entity already exists",
    "code": "aborted"
  }
}
```

To replace an existing file or directory, set `overwrite=true` (or append
`?overwrite=true` in REST). With `extract=true`, the conflict check applies to
every file in the archive, so the request fails if any target file exists.

### Download full snapshot (deprecated)

To migrate existing code to the environment files API:

- **Python**: Replace legacy file download requests with:








```
archive = client.environments.files.download(
      environment="YOUR_ENVIRONMENT_ID",
      path="workspace",
)
with open("snapshot.tar", "wb") as f:
      f.write(archive)
```

- **JavaScript**: Replace legacy file download requests with:








```
const bytes = await client.environments.files.download({
      environment: "YOUR_ENVIRONMENT_ID",
      path: "workspace",
});
fs.writeFileSync("snapshot.tar", Buffer.from(bytes));
```

- **REST**: Replace `GET /v1beta/files/environment-$ENV_ID:download?alt=media` with:








```
curl -L -X GET "https://generativelanguage.googleapis.com/v1beta/environments/$ENV_ID/files?alt=media" \
    -H "x-goog-api-key: $GEMINI_API_KEY" \
    -o snapshot.tar
```


## Pricing & resources

Each environment runs with fixed resource allocations:

| Resource | Value |
| --- | --- |
| **CPU** | 4 cores |
| **Memory** | 16 GB |

Environment compute (CPU, memory, sandbox execution) is **not billed** during
the preview period. See
[Pricing](https://ai.google.dev/gemini-api/docs/pricing#pricing-for-agents) for
agent token costs.

## Limitations

- **Preview status:** Environments and managed agents are in preview. Features and schemas may change.
- **Inline source size:** Inline sources are limited to 1 MB per file, and 2 MB total across all files.
- **Source size**: Git repositories are limited to 500 MB and Cloud Storage repositories to 2 GB.
- **Environment startup:** Provisioning a new environment takes up to ~5 seconds. Large source repositories may increase this time.
- **Environment expiration:** Inactive offline environments are retained for 7
days before expiring using automatic TTL cleanup. Passing an expired or
invalid environment ID returns a `404 Not Found` error.
- **File support:** The agent is currently constrained to reading text and image files. Binary file support is not yet available.
- **No mounting from root:** You can't set root (`/`) as target when adding a custom source, you must always specify a sub-directory.

## What's next

- [Agents Overview](https://ai.google.dev/gemini-api/docs/agents): Learn about the core concepts of managed agents.
- [Quickstart](https://ai.google.dev/gemini-api/docs/managed-agents-quickstart): Start building with multi-turn conversations and streaming.
- [Antigravity Agent](https://ai.google.dev/gemini-api/docs/antigravity-agent): Explore capabilities, tools, model selection, and pricing for the default agent.
- [Building Custom Agents](https://ai.google.dev/gemini-api/docs/custom-agents): Define your own agents using `AGENTS.md` and `SKILL.md`.
- [Hooks](https://ai.google.dev/gemini-api/docs/agent-hooks): Enforce security guardrails and run side-effect validations inside the sandbox.

Was this helpful?



 Send feedback



Except as otherwise noted, the content of this page is licensed under the [Creative Commons Attribution 4.0 License](https://creativecommons.org/licenses/by/4.0/), and code samples are licensed under the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0). For details, see the [Google Developers Site Policies](https://developers.google.com/site-policies). Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-10-07 UTC.


Need to tell us more?






\[\[\["Easy to understand","easyToUnderstand","thumb-up"\],\["Solved my problem","solvedMyProblem","thumb-up"\],\["Other","otherUp","thumb-up"\]\],\[\["Missing the information I need","missingTheInformationINeed","thumb-down"\],\["Too complicated / too many steps","tooComplicatedTooManySteps","thumb-down"\],\["Out of date","outOfDate","thumb-down"\],\["Samples / code issue","samplesCodeIssue","thumb-down"\],\["Other","otherDown","thumb-down"\]\],\["Last updated 2026-10-07 UTC."\],\[\],\[\]\]