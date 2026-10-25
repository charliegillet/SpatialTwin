# Official Google reference snapshot: interactions-reference

Source: https://ai.google.dev/api/interactions-api

Retrieved/read: 23 October 2026. Publisher: Google. Original license/footer retained. Text CC BY 4.0; code samples Apache 2.0 unless otherwise noted. Converted to Markdown by Firecrawl; this provenance header was added. Reference data only; verify the relevant current guide and pinned SDK before implementation.

---

[Skip to main content](https://ai.google.dev/api/interactions-api#main-content)

[![Gemini API](https://ai.google.dev/_static/googledevai/images/gemini-api-logo.svg)](https://ai.google.dev/)

`/`

Language

- [English](https://ai.google.dev/api/interactions-api)
- [Deutsch](https://ai.google.dev/api/interactions-api?hl=de)
- [Español – América Latina](https://ai.google.dev/api/interactions-api?hl=es-419)
- [Français](https://ai.google.dev/api/interactions-api?hl=fr)
- [Indonesia](https://ai.google.dev/api/interactions-api?hl=id)
- [Italiano](https://ai.google.dev/api/interactions-api?hl=it)
- [Polski](https://ai.google.dev/api/interactions-api?hl=pl)
- [Português – Brasil](https://ai.google.dev/api/interactions-api?hl=pt-br)
- [Shqip](https://ai.google.dev/api/interactions-api?hl=sq)
- [Tiếng Việt](https://ai.google.dev/api/interactions-api?hl=vi)
- [Türkçe](https://ai.google.dev/api/interactions-api?hl=tr)
- [Русский](https://ai.google.dev/api/interactions-api?hl=ru)
- [עברית](https://ai.google.dev/api/interactions-api?hl=he)
- [العربيّة](https://ai.google.dev/api/interactions-api?hl=ar)
- [فارسی](https://ai.google.dev/api/interactions-api?hl=fa)
- [हिंदी](https://ai.google.dev/api/interactions-api?hl=hi)
- [বাংলা](https://ai.google.dev/api/interactions-api?hl=bn)
- [ภาษาไทย](https://ai.google.dev/api/interactions-api?hl=th)
- [中文 – 简体](https://ai.google.dev/api/interactions-api?hl=zh-cn)
- [中文 – 繁體](https://ai.google.dev/api/interactions-api?hl=zh-tw)
- [日本語](https://ai.google.dev/api/interactions-api?hl=ja)
- [한국어](https://ai.google.dev/api/interactions-api?hl=ko)

[Get API key](https://aistudio.google.com/apikey) [Cookbook](https://github.com/google-gemini/cookbook) [Community](https://discuss.ai.google.dev/c/gemini-api/)

[Sign in](https://ai.google.dev/_d/signin?continue=https%3A%2F%2Fai.google.dev%2Fapi%2Finteractions-api&prompt=select_account)

- On this page
- [Creating an interaction](https://ai.google.dev/api/interactions-api#CreateInteraction)
  - [Request body](https://ai.google.dev/api/interactions-api#request-body)
  - [Response](https://ai.google.dev/api/interactions-api#response)
- [Canceling an interaction](https://ai.google.dev/api/interactions-api#cancelInteractionById)
  - [Path / Query Parameters](https://ai.google.dev/api/interactions-api#path-query-parameters)
  - [Response](https://ai.google.dev/api/interactions-api#response_1)
- [Retrieving an interaction](https://ai.google.dev/api/interactions-api#getInteractionById)
  - [Path / Query Parameters](https://ai.google.dev/api/interactions-api#path-query-parameters_1)
  - [Response](https://ai.google.dev/api/interactions-api#response_2)
- [Deleting an interaction](https://ai.google.dev/api/interactions-api#deleteInteraction)
  - [Path / Query Parameters](https://ai.google.dev/api/interactions-api#path-query-parameters_2)
  - [Response](https://ai.google.dev/api/interactions-api#response_3)
- [Resources](https://ai.google.dev/api/interactions-api#resources)
  - [Interaction](https://ai.google.dev/api/interactions-api#Resource:Interaction)
  - [Examples](https://ai.google.dev/api/interactions-api#examples)
- [Data Models](https://ai.google.dev/api/interactions-api#data-models)
  - [Content](https://ai.google.dev/api/interactions-api#Resource:Content)
  - [Possible Types](https://ai.google.dev/api/interactions-api#possible-types_1)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_1)
  - [Tool](https://ai.google.dev/api/interactions-api#Resource:Tool)
  - [Possible Types](https://ai.google.dev/api/interactions-api#possible-types_3)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_2)
  - [InteractionSseEvent](https://ai.google.dev/api/interactions-api#Resource:InteractionSseEvent)
  - [Possible Types](https://ai.google.dev/api/interactions-api#possible-types_4)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_3)
  - [ResponseFormat](https://ai.google.dev/api/interactions-api#Resource:ResponseFormat)
  - [Possible Types](https://ai.google.dev/api/interactions-api#possible-types_7)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_4)
  - [Step](https://ai.google.dev/api/interactions-api#Resource:Step)
  - [Possible Types](https://ai.google.dev/api/interactions-api#possible-types_8)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_5)
  - [EnvironmentConfig](https://ai.google.dev/api/interactions-api#Resource:EnvironmentConfig)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_6)
  - [EnvironmentNetworkEgressAllowlist](https://ai.google.dev/api/interactions-api#Resource:EnvironmentNetworkEgressAllowlist)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_7)
  - [ToolChoiceConfig](https://ai.google.dev/api/interactions-api#Resource:ToolChoiceConfig)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_8)
  - [ImageContent](https://ai.google.dev/api/interactions-api#Resource:ImageContent)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_9)
  - [TextContent](https://ai.google.dev/api/interactions-api#Resource:TextContent)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_10)

Gemini 4 Argon is now available. [Try it out](https://aistudio.google.com/prompts/new_chat?model=gemini-4-argon).


- [Home](https://ai.google.dev/)
- [Gemini API](https://ai.google.dev/gemini-api)
- [API reference](https://ai.google.dev/api)

Was this helpful?



 Send feedback



# Gemini Interactions API

- On this page
- [Creating an interaction](https://ai.google.dev/api/interactions-api#CreateInteraction)
  - [Request body](https://ai.google.dev/api/interactions-api#request-body)
  - [Response](https://ai.google.dev/api/interactions-api#response)
- [Canceling an interaction](https://ai.google.dev/api/interactions-api#cancelInteractionById)
  - [Path / Query Parameters](https://ai.google.dev/api/interactions-api#path-query-parameters)
  - [Response](https://ai.google.dev/api/interactions-api#response_1)
- [Retrieving an interaction](https://ai.google.dev/api/interactions-api#getInteractionById)
  - [Path / Query Parameters](https://ai.google.dev/api/interactions-api#path-query-parameters_1)
  - [Response](https://ai.google.dev/api/interactions-api#response_2)
- [Deleting an interaction](https://ai.google.dev/api/interactions-api#deleteInteraction)
  - [Path / Query Parameters](https://ai.google.dev/api/interactions-api#path-query-parameters_2)
  - [Response](https://ai.google.dev/api/interactions-api#response_3)
- [Resources](https://ai.google.dev/api/interactions-api#resources)
  - [Interaction](https://ai.google.dev/api/interactions-api#Resource:Interaction)
  - [Examples](https://ai.google.dev/api/interactions-api#examples)
- [Data Models](https://ai.google.dev/api/interactions-api#data-models)
  - [Content](https://ai.google.dev/api/interactions-api#Resource:Content)
  - [Possible Types](https://ai.google.dev/api/interactions-api#possible-types_1)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_1)
  - [Tool](https://ai.google.dev/api/interactions-api#Resource:Tool)
  - [Possible Types](https://ai.google.dev/api/interactions-api#possible-types_3)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_2)
  - [InteractionSseEvent](https://ai.google.dev/api/interactions-api#Resource:InteractionSseEvent)
  - [Possible Types](https://ai.google.dev/api/interactions-api#possible-types_4)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_3)
  - [ResponseFormat](https://ai.google.dev/api/interactions-api#Resource:ResponseFormat)
  - [Possible Types](https://ai.google.dev/api/interactions-api#possible-types_7)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_4)
  - [Step](https://ai.google.dev/api/interactions-api#Resource:Step)
  - [Possible Types](https://ai.google.dev/api/interactions-api#possible-types_8)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_5)
  - [EnvironmentConfig](https://ai.google.dev/api/interactions-api#Resource:EnvironmentConfig)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_6)
  - [EnvironmentNetworkEgressAllowlist](https://ai.google.dev/api/interactions-api#Resource:EnvironmentNetworkEgressAllowlist)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_7)
  - [ToolChoiceConfig](https://ai.google.dev/api/interactions-api#Resource:ToolChoiceConfig)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_8)
  - [ImageContent](https://ai.google.dev/api/interactions-api#Resource:ImageContent)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_9)
  - [TextContent](https://ai.google.dev/api/interactions-api#Resource:TextContent)
  - [Examples](https://ai.google.dev/api/interactions-api#examples_10)

The Gemini Interactions API allows developers to build generative AI applications using Gemini models. Gemini is our most capable model, built from the ground up to be multimodal. It can generalize and seamlessly understand, operate across, and combine different types of information including language, images, audio, video, and code. You can use the Gemini API for use cases like reasoning across text and images, content generation, dialogue agents, summarization and classification systems, and more.

[View as markdown](https://ai.google.dev/static/api/interactions.md.txt) [View the OpenAPI Spec](https://ai.google.dev/static/api/interactions.openapi.json)

API version:v1beta [v1](https://ai.google.dev/api/interactions-api-v1)

## Creating an interaction

post

https://generativelanguage.googleapis.com/v1beta/interactions


Creates a new interaction.

- [Request body](https://ai.google.dev/api/interactions-api#CreateInteraction.request_body)
- [Response](https://ai.google.dev/api/interactions-api#CreateInteraction.response)

### Request body

The request body contains data with the following structure:

modelModelOption (optional)

The name of the \`Model\` used for generating the interaction.

**Required if \`agent\` is not provided.**

The model that will complete your prompt.\\n\\nSee \[models\](https://ai.google.dev/gemini-api/docs/models) for additional details.

#### Possible values

- `gemma-4-26b-a4b-it`
Gemma 4 26B A4B IT

- `gemma-4-31b-it`
Gemma 4 31B IT

- `gemini-flash-latest`
Latest release of Gemini Flash

- `gemini-flash-lite-latest`
Latest release of Gemini Flash-Lite

- `gemini-pro-latest`
Latest release of Gemini Pro

- `gemini-2.5-flash`
Our first hybrid reasoning model which supports a 1M token context window and has thinking budgets.

- `gemini-2.5-pro`
Our state-of-the-art multipurpose model, which excels at coding and complex reasoning tasks.

- `gemini-2.5-flash-lite`
Our smallest and most cost effective model, built for at scale usage.

- `gemini-3.5-flash-lite`
Gemini 3.5 Flash-Lite - Our fastest, most cost-effective 3.5 model for high-throughput execution.

- `gemini-2.5-flash-image`
Our native image generation model, optimized for speed, flexibility, and contextual understanding. Text input and output is priced the same as 2.5 Flash.

- `gemini-3-flash-preview`
Our most intelligent model built for speed, combining frontier intelligence with superior search and grounding.

- `gemini-3.1-pro-preview`
Our latest SOTA reasoning model with unprecedented depth and nuance, and powerful multimodal understanding and coding capabilities.

- `gemini-3.1-pro-preview-customtools`
Gemini 3.1 Pro Preview optimized for custom tool usage

- `gemini-3.1-flash-lite`
Our most cost-efficient model, optimized for high-volume agentic tasks, translation, and simple data processing.

- `gemini-3.1-flash-lite-image`
Gemini 3.1 Flash Lite Image.

- `gemini-3-pro-image`
Gemini 3 Pro Image

- `nano-banana-pro-preview`
Gemini 3 Pro Image Preview

- `gemini-3.1-flash-image`
Gemini 3.1 Flash Image.

- `gemini-nano-banana-2.1`
Gemini Nano Banana 2.1.

- `gemini-3.1-flash-tts-preview`
Gemini 3.1 Flash TTS: Powerful, low-latency speech generation. Enjoy natural outputs, steerable prompts, and new expressive audio tags for precise narration control.

- `gemini-3.5-flash`
Gemini 3.5 Flash - Our earlier Flash model, built for speed and foundational performance across routine, high-throughput workloads.

- `gemini-3.6-flash`
Gemini 3.6 Flash - Our previous generation Flash model, balancing speed and multimodal capabilities across general agentic and everyday tasks.

- `gemini-3.7-flash`
Gemini 3.7 Flash - Our high-speed, efficient Flash model built for everyday coding, agentic tool use, and reliable multi-step execution.

- `gemini-3.8-flash`
Gemini 3.8 Flash - Our most intelligent Flash model, engineered for long-horizon software engineering, autonomous agents, and complex enterprise workflows.

- `gemini-3.8-flash-tts`
Gemini 3.8 Flash TTS - Flagship TTS model for Voice Design and dual-speaker screenplay control. Prompt custom vocal personas, direct line-by-line delivery, and add vocal bursts.

- `gemini-3.8-flash-lite-tts`
Gemini 3.8 Flash Lite TTS - High-speed and cost-efficient, ideal for rapid dubbing, media localization, and high-throughput voice agents. Direct replacement for gemini-3.1-flash-tts-preview.

- `lyria-3-clip-preview`
Our low-latency, music generation model optimized for high-fidelity audio clips and precise rhythmic control.

- `lyria-3-pro-preview`
Our advanced, full-song generative model with deep compositional understanding, optimized for precise structural control and complex transitions across diverse musical styles.

- `gemini-robotics-er-1.6-preview`
Gemini Robotics-ER 1.6 Preview

- `gemini-robotics-er-2-preview`
Gemini Robotics Embodied Reasoning 2 Preview

- `lyria-3.5`
Our flagship music generation model, optimized for full-length songs with complex structural coherence.

- `gemini-omni-1.1-flash`
Our high-performance multimodal model designed for fast, conversational video generation, editing, and cinematic control.

- `gemini-omni-flash-preview`
Preview release of our multimodal model for conversational video generation, editing, and cinematic control.


agentAgentOption (optional)

The name of the \`Agent\` used for generating the interaction.

**Required if \`model\` is not provided.**

The agent to interact with.

#### Possible values

- `deep-research-pro-preview-12-2025`
Gemini Deep Research Agent

- `deep-research-preview-04-2026`
Gemini Deep Research Agent

- `deep-research-max-preview-04-2026`
Gemini Deep Research Max Agent

- `antigravity-preview-05-2026`
Use the Antigravity managed agent to perform multi-step tasks that require reasoning, file operations, and tool use.


input[Content](https://ai.google.dev/api/interactions-api#Resource:Content) or array ( [Content](https://ai.google.dev/api/interactions-api#Resource:Content)) or array ( [Step](https://ai.google.dev/api/interactions-api#Resource:Step)) or string (required)

The inputs for the interaction (common to both Model and Agent).

generation\_configGenerationConfig (optional)

**Model Configuration**

Configuration parameters for the model interaction.

_Alternative to \`agent\_config\`. Only applicable when \`model\` is set._

Configuration parameters for model interactions.

#### Fields

tool\_choice[ToolChoiceConfig](https://ai.google.dev/api/interactions-api#Resource:ToolChoiceConfig) or enum (string) (optional)

The tool choice configuration.

Possible
values:

- `auto`
Auto tool choice.

- `any`
Any tool choice.

- `none`
No tool choice.

- `validated`
Validated tool choice.


seedinteger (optional)

Seed used in decoding for reproducibility.

stop\_sequencesarray (string) (optional)

A list of character sequences that will stop output interaction.

thinking\_levelThinkingLevel (optional)

The level of thought tokens that the model should generate.

#### Possible values

- `minimal`
Little to no thinking.

- `low`
Low thinking level.

- `medium`
Medium thinking level.

- `high`
High thinking level.


thinking\_summariesThinkingSummaries (optional)

Whether to include thought summaries in the response.

#### Possible values

- `auto`
Auto thinking summaries.

- `none`
No thinking summaries.


max\_output\_tokensinteger (optional)

The maximum number of tokens to include in the response.

video\_configVideoConfig (optional)

Configuration for video generation.

Configuration options for video generation.

#### Fields

taskenum (string) (optional)

Optional task mode for video generation. If not specified, the model
automatically determines the appropriate mode based on the provided text
prompt and input media.

Possible
values:

- `text_to_video`
Generates video solely from a text prompt.

- `image_to_video`
Generates video from one or two source images. The first image defines
the starting frame, and the optional second image defines the ending
frame.

- `reference_to_video`
Generates video using reference media (such as images, audio, or video).

- `edit`
Modifies an existing input video.

- `extend`
Extends an existing input video.


transcription\_configTranscriptionConfig (optional)

Optional. Configuration for speech recognition (transcription). If present, ASR is
enabled.

Configuration for speech recognition (transcription).

#### Fields

modeTranscriptionMode or enum (string) (optional)

Discriminated transcription mode options or enum.

Configuration for transcription mode.

#### Possible Types

SmartTranscriptionMode

Configuration for smart transcription mode.

typeobject (required)

No description provided.

Always set to `"smart"`.

VerbatimTranscriptionMode

Configuration for verbatim transcription mode.

typeobject (required)

No description provided.

Always set to `"verbatim"`.

timestamp\_granularitiesarray (string) (optional)

Optional. The granularity of timestamps to include in the transcription output.
Supported values: "word". If empty, no timestamps are generated.

diarization\_modestring (optional)

Optional. Configures speaker diarization. Supported values: "speaker".

language\_codesarray (string) (optional)

Optional. BCP-47 language codes providing hints about the languages present in the
audio. If omitted or empty, defaults to automatic language detection.

custom\_vocabularyarray (string) (optional)

Optional. A list of custom vocabulary phrases to bias the speech recognition model
toward recognizing specific terms.

structured\_speech\_configSpeakerConfig or array (SpeechConfig) (optional)

Speech and multi-speaker configuration.

Configuration for multi-speaker and speech generation.

#### Fields

speakersarray (SpeechConfig) (optional)

Individual speaker configurations.

The configuration for speech interaction.

#### Fields

voicestring (optional)

The voice of the speaker.

languagestring (optional)

The language of the speech.

speakerstring (optional)

The speaker's name, it should match the speaker name given in the prompt.

agent\_configAntigravityAgentConfig or DeepResearchAgentConfig or DynamicAgentConfig (optional)

**Agent Configuration**

Configuration for the agent.

_Alternative to \`generation\_config\`. Only applicable when \`agent\` is set._

response\_format[ResponseFormat](https://ai.google.dev/api/interactions-api#Resource:ResponseFormat) or array ( [ResponseFormat](https://ai.google.dev/api/interactions-api#Resource:ResponseFormat)) (optional)

Enforces that the generated response is a JSON object that complies with
the JSON schema specified in this field.

environment[EnvironmentConfig](https://ai.google.dev/api/interactions-api#Resource:EnvironmentConfig) or string (optional)

The environment configuration for the interaction. Can be an object
specifying remote environment sources or a string referencing an existing
environment ID.

system\_instructionstring (optional)

System instruction for the interaction.

toolsarray ( [Tool](https://ai.google.dev/api/interactions-api#Resource:Tool)) (optional)

A list of tool declarations the model may call during interaction.

previous\_interaction\_idstring (optional)

The ID of the previous interaction, if any.

service\_tierServiceTier (optional)

The service tier for the interaction.

#### Possible values

- `flex`
Flex service tier.

- `standard`
Standard service tier.

- `priority`
Priority service tier.


webhook\_configWebhookConfig (optional)

Optional. Webhook configuration for receiving notifications when the
interaction completes.

Message for configuring webhook events for a request.

#### Fields

urisarray (string) (optional)

Optional. If set, these webhook URIs will be used for webhook events instead of the
registered webhooks.

user\_metadataobject (optional)

Optional. The user metadata that will be returned on each event emission to the
webhooks.

safety\_settingsarray (SafetySetting) (optional)

Safety settings for the interaction.

A safety setting that affects the safety-blocking behavior.

A SafetySetting consists of a
harm category and a
threshold for that
category.

#### Fields

typeHarmCategory (required)

Required. The type of harm category to be blocked.

#### Possible values

- `hate_speech`
Content that promotes violence or incites hatred against individuals or
groups based on certain attributes.

- `dangerous_content`
Content that promotes, facilitates, or enables dangerous activities.

- `harassment`
Abusive, threatening, or content intended to bully, torment, or ridicule.

- `sexually_explicit`
Content that contains sexually explicit material.

- `jailbreak`
Prompts designed to bypass safety filters.


thresholdenum (string) (required)

Required. The threshold for blocking content. If the harm probability
exceeds this threshold, the content will be blocked.

Possible
values:

- `block_low_and_above`
Block content with a low harm probability or higher.

- `block_medium_and_above`
Block content with a medium harm probability or higher.

- `block_only_high`
Block content with a high harm probability.

- `off`
Turn off the safety filter entirely.


methodenum (string) (optional)

Optional. The method for blocking content. If not specified, the default
behavior is to use the probability score.

Possible
values:

- `severity`
The harm block method uses both probability and severity scores.

- `probability`
The harm block method uses the probability score.


labelsobject (optional)

The labels with user-defined metadata for the request.

Label keys and values can be no longer than 63 characters
(Unicode codepoints) and can only contain lowercase letters, numeric
characters, underscores, and dashes. International characters are allowed.
Label values are optional. Label keys must start with a letter.

streamboolean (optional)

Input only. Whether the interaction will be streamed.

storeboolean (optional)

Input only. Whether to store the response and request for later retrieval.

backgroundboolean (optional)

Input only. Whether to run the model interaction in the background.

### Response

Returns an [Interaction](https://ai.google.dev/api/interactions-api#Resource:Interaction) resource.

[Simple Request](https://ai.google.dev/api/interactions-api#simple-request)[Multi-turn](https://ai.google.dev/api/interactions-api#multi-turn)[Image Input](https://ai.google.dev/api/interactions-api#image-input)[Function Calling](https://ai.google.dev/api/interactions-api#function-calling)[Deep Research](https://ai.google.dev/api/interactions-api#deep-research)[Antigravity Agent](https://ai.google.dev/api/interactions-api#antigravity-agent)[Reuse Environment](https://ai.google.dev/api/interactions-api#reuse-environment)[With Sources](https://ai.google.dev/api/interactions-api#with-sources)[Custom Agent](https://ai.google.dev/api/interactions-api#custom-agent)More

Google AI for Developers

#### Example Request

RESTPythonJavaScriptJavaGo

```sh
curl -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-flash-latest",
    "input": "Hello, how are you?"
  }'
```

```python
from google import genai

client = genai.Client()
interaction = client.interactions.create(
    model="gemini-flash-latest",
    input="Hello, how are you?",
)
print(interaction.output_text)
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});
const interaction = await ai.interactions.create({
  model: 'gemini-flash-latest',
  input: 'Hello, how are you?',
});
console.log(interaction.output_text);
```

```java
import com.google.genai.Client;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.gaos.models.operations.CreateInteractionResponse;
import com.google.genai.gaos.models.interactions.CreateModelInteraction;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;

Client client = new Client();
CreateModelInteraction params =
    CreateModelInteraction.builder()
        .model("gemini-flash-latest")
        .input(InteractionsInput.of("Hello, how are you?"))
        .build();
CreateInteractionResponse response =
    client.interactions.create(CreateInteractionRequestBody.of(params));
Interaction interaction =
    response.interaction().orElseThrow(() -> new RuntimeException("No interaction returned"));
System.out.println(interaction.outputText().orElse(""));
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "google.golang.org/genai"
    gaos_interactions "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    body := operations.NewCreateInteractionRequestBody(gaos_interactions.CreateModelInteraction{
        Model: gaos_interactions.Model("gemini-flash-latest"),
        Input: genai.Ptr(gaos_interactions.NewInteractionsInput("Hello, how are you?")),
    })

    res, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{Body: body})
    if err != nil {
        log.Fatal(err)
    }

    if res.Interaction != nil && res.Interaction.OutputText != nil {
        fmt.Println(*res.Interaction.OutputText)
    }
}
```

#### Example Response

```
{
  "created": "2025-11-26T12:25:15Z",
  "id": "v1_ChdPU0F4YWFtNkFwS2kxZThQZ05lbXdROBIXT1NBeGFhbTZBcEtpMWU4UGdOZW13UTg",
  "model": "gemini-3.6-flash",
  "object": "interaction",
  "status": "completed",
  "steps": [\
    {\
      "type": "model_output",\
      "content": [\
        {\
          "type": "text",\
          "text": "Hello! I'm functioning perfectly and ready to assist you.\n\nHow are you doing today?"\
        }\
      ]\
    }\
  ],
  "updated": "2025-11-26T12:25:15Z",
  "usage": {
    "input_tokens_by_modality": [\
      {\
        "modality": "text",\
        "tokens": 7\
      }\
    ],
    "total_cached_tokens": 0,
    "total_input_tokens": 7,
    "total_output_tokens": 20,
    "total_thought_tokens": 22,
    "total_tokens": 49,
    "total_tool_use_tokens": 0
  }
}
```

Google AI for Developers

#### Example Request

RESTPythonJavaScriptJavaGo

```sh
curl -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-flash-latest",
    "input": [\
      { "type": "user_input", "content": [{ "type": "text", "text": "Hello!" }] },\
      { "type": "model_output", "content": [{ "type": "text", "text": "Hi there! How can I help you today?" }] },\
      { "type": "user_input", "content": [{ "type": "text", "text": "What is the capital of France?" }] }\
    ]
  }'
```

```python
from google import genai

client = genai.Client()
response = client.interactions.create(
    model="gemini-flash-latest",
    input=[\
        {\
            "type": "user_input",\
            "content": [{"type": "text", "text": "Hello!"}],\
        },\
        {\
            "type": "model_output",\
            "content": [{\
                "type": "text",\
                "text": "Hi there! How can I help you today?",\
            }],\
        },\
        {\
            "type": "user_input",\
            "content": [\
                {"type": "text", "text": "What is the capital of France?"}\
            ],\
        },\
    ],
)
print(response.output_text)
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});
const interaction = await ai.interactions.create({
  model: 'gemini-flash-latest',
  input: [\
    {type: 'user_input', content: [{type: 'text', text: 'Hello'}]},\
    {\
      type: 'model_output',\
      content: [\
        {type: 'text', text: 'Hi there! How can I help you today?'},\
      ],\
    },\
    {\
      type: 'user_input',\
      content: [{type: 'text', text: 'What is the capital of France?'}],\
    },\
  ],
});
console.log(interaction.output_text);
```

```java
import com.google.genai.Client;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.gaos.models.operations.CreateInteractionResponse;
import com.google.genai.gaos.models.interactions.CreateModelInteraction;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;
import com.google.genai.gaos.models.interactions.ModelOutputStep;
import com.google.genai.gaos.models.interactions.Step;
import com.google.genai.gaos.models.interactions.TextContent;
import com.google.genai.gaos.models.interactions.UserInputStep;

Client client = new Client();
List conversation =
    List.of(
        UserInputStep.builder()
            .content(List.of(TextContent.builder().text("Hello!").build()))
            .build(),
        ModelOutputStep.builder()
            .content(
                List.of(
                    TextContent.builder().text("Hi there! How can I help you today?").build()))
            .build(),
        UserInputStep.builder()
            .content(
                List.of(TextContent.builder().text("What is the capital of France?").build()))
            .build());
CreateModelInteraction params =
    CreateModelInteraction.builder()
        .model("gemini-flash-latest")
        .input(InteractionsInput.ofStep(conversation))
        .build();
CreateInteractionResponse response =
    client.interactions.create(CreateInteractionRequestBody.of(params));
Interaction interaction =
    response.interaction().orElseThrow(() -> new RuntimeException("No interaction returned"));
System.out.println(interaction.outputText().orElse(""));
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "google.golang.org/genai"
    gaos_interactions "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    history := []gaos_interactions.Step{
        gaos_interactions.NewStep(gaos_interactions.UserInputStep{
            Content: []gaos_interactions.Content{
                gaos_interactions.NewContent(gaos_interactions.TextContent{
                    Text: "Hello!",
                }),
            },
        }),
        gaos_interactions.NewStep(gaos_interactions.ModelOutputStep{
            Content: []gaos_interactions.Content{
                gaos_interactions.NewContent(gaos_interactions.TextContent{
                    Text: "Hi there! How can I help you today?",
                }),
            },
        }),
        gaos_interactions.NewStep(gaos_interactions.UserInputStep{
            Content: []gaos_interactions.Content{
                gaos_interactions.NewContent(gaos_interactions.TextContent{
                    Text: "What is the capital of France?",
                }),
            },
        }),
    }

    body := operations.NewCreateInteractionRequestBody(gaos_interactions.CreateModelInteraction{
        Model: gaos_interactions.Model("gemini-flash-latest"),
        Input: genai.Ptr(gaos_interactions.NewInteractionsInput(history)),
    })

    res, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{Body: body})
    if err != nil {
        log.Fatal(err)
    }

    if res.Interaction != nil && res.Interaction.OutputText != nil {
        fmt.Println(*res.Interaction.OutputText)
    }
}
```

#### Example Response

```
{
  "created": "2025-11-26T12:22:47Z",
  "id": "v1_ChdPU0F4YWFtNkFwS2kxZThQZ05lbXdROBIXT1NBeGFhbTZBcEtpMWU4UGdOZW13UTg",
  "model": "gemini-3.6-flash",
  "object": "interaction",
  "status": "completed",
  "steps": [\
    {\
      "type": "model_output",\
      "content": [\
        {\
          "type": "text",\
          "text": "The capital of France is Paris."\
        }\
      ]\
    }\
  ],
  "updated": "2025-11-26T12:22:47Z",
  "usage": {
    "input_tokens_by_modality": [\
      {\
        "modality": "text",\
        "tokens": 50\
      }\
    ],
    "total_cached_tokens": 0,
    "total_input_tokens": 50,
    "total_output_tokens": 10,
    "total_thought_tokens": 0,
    "total_tokens": 60,
    "total_tool_use_tokens": 0
  }
}
```

Google AI for Developers

#### Example Request

RESTPythonJavaScriptJavaGo

```sh
curl -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-flash-latest",
    "input": [\
      {\
        "type": "text",\
        "text": "What is in this picture?"\
      },\
      {\
        "type": "image",\
        "data": "BASE64_ENCODED_IMAGE",\
        "mime_type": "image/png"\
      }\
    ]
  }'
```

```python
from google import genai

client = genai.Client()
response = client.interactions.create(
    model="gemini-flash-latest",
    input=[\
        {"type": "text", "text": "What is in this picture?"},\
        {\
            "type": "image",\
            "data": "BASE64_ENCODED_IMAGE",\
            "mime_type": "image/png",\
        },\
    ],
)
print(response.output_text)
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});
const interaction = await ai.interactions.create({
  model: 'gemini-flash-latest',
  input: [\
    {type: 'text', text: 'What is in this picture?'},\
    {type: 'image', data: 'BASE64_ENCODED_IMAGE', mime_type: 'image/png'},\
  ],
});
console.log(interaction.output_text);
```

```java
import com.google.genai.Client;
import com.google.genai.gaos.models.interactions.Content;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.gaos.models.operations.CreateInteractionResponse;
import com.google.genai.gaos.models.interactions.CreateModelInteraction;
import com.google.genai.gaos.models.interactions.ImageContent;
import com.google.genai.gaos.models.interactions.ImageContentMimeType;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;
import com.google.genai.gaos.models.interactions.TextContent;

Client client = new Client();
List content =
    List.of(
        TextContent.builder().text("What is in this picture?").build(),
        ImageContent.builder()
            .data("BASE64_ENCODED_IMAGE")
            .mimeType(ImageContentMimeType.IMAGE_PNG)
            .build());
CreateModelInteraction params =
    CreateModelInteraction.builder()
        .model("gemini-flash-latest")
        .input(InteractionsInput.ofContent(content))
        .build();
CreateInteractionResponse response =
    client.interactions.create(CreateInteractionRequestBody.of(params));
Interaction interaction =
    response.interaction().orElseThrow(() -> new RuntimeException("No interaction returned"));
System.out.println(interaction.outputText().orElse(""));
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "google.golang.org/genai"
    gaos_interactions "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    contents := []gaos_interactions.Content{
        gaos_interactions.NewContent(gaos_interactions.TextContent{
            Text: "What is in this picture?",
        }),
        gaos_interactions.NewContent(gaos_interactions.ImageContent{
            Data:     genai.Ptr("BASE64_ENCODED_IMAGE"),
            MimeType: gaos_interactions.ImageContentMimeTypeImagePng.ToPointer(),
        }),
    }

    body := operations.NewCreateInteractionRequestBody(gaos_interactions.CreateModelInteraction{
        Model: gaos_interactions.Model("gemini-flash-latest"),
        Input: genai.Ptr(gaos_interactions.NewInteractionsInput(contents)),
    })

    res, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{Body: body})
    if err != nil {
        log.Fatal(err)
    }

    if res.Interaction != nil && res.Interaction.OutputText != nil {
        fmt.Println(*res.Interaction.OutputText)
    }
}
```

#### Example Response

```
{
  "created": "2025-11-26T12:22:47Z",
  "id": "v1_ChdPU0F4YWFtNkFwS2kxZThQZ05lbXdROBIXT1NBeGFhbTZBcEtpMWU4UGdOZW13UTg",
  "model": "gemini-3.6-flash",
  "object": "interaction",
  "status": "completed",
  "steps": [\
    {\
      "type": "model_output",\
      "content": [\
        {\
          "type": "text",\
          "text": "A white humanoid robot with glowing blue eyes stands holding a red skateboard."\
        }\
      ]\
    }\
  ],
  "updated": "2025-11-26T12:22:47Z",
  "usage": {
    "input_tokens_by_modality": [\
      {\
        "modality": "text",\
        "tokens": 10\
      },\
      {\
        "modality": "image",\
        "tokens": 258\
      }\
    ],
    "total_cached_tokens": 0,
    "total_input_tokens": 268,
    "total_output_tokens": 20,
    "total_thought_tokens": 0,
    "total_tokens": 288,
    "total_tool_use_tokens": 0
  }
}
```

Google AI for Developers

#### Example Request

RESTPythonJavaScriptJavaGo

```sh
curl -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-flash-latest",
    "tools": [\
      {\
        "type": "function",\
        "name": "get_weather",\
        "description": "Get the current weather in a given location",\
        "parameters": {\
          "type": "object",\
          "properties": {\
            "location": {\
              "type": "string",\
              "description": "The city and state, e.g. San Francisco, CA"\
            }\
          },\
          "required": [\
            "location"\
          ]\
        }\
      }\
    ],
    "input": "What is the weather like in Boston, MA?"
  }'
```

```python
from google import genai

client = genai.Client()
response = client.interactions.create(
    model="gemini-flash-latest",
    tools=[{\
        "type": "function",\
        "name": "get_weather",\
        "description": "Get the current weather in a given location",\
        "parameters": {\
            "type": "object",\
            "properties": {\
                "location": {\
                    "type": "string",\
                    "description": (\
                        "The city and state, e.g. San Francisco, CA"\
                    ),\
                }\
            },\
            "required": ["location"],\
        },\
    }],
    input="What is the weather like in Boston, MA?",
)
print(response.steps[-1])
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});
const interaction = await ai.interactions.create({
  model: 'gemini-flash-latest',
  tools: [\
    {\
      type: 'function',\
      name: 'get_weather',\
      description: 'Get the current weather in a given location',\
      parameters: {\
        type: 'object',\
        properties: {\
          location: {\
            type: 'string',\
            description: 'The city and state, e.g. San Francisco, CA',\
          },\
        },\
        required: ['location'],\
      },\
    },\
  ],
  input: 'What is the weather like in Boston, MA?',
});
console.log(interaction.steps.at(-1));
```

```java
import com.google.genai.Client;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.gaos.models.operations.CreateInteractionResponse;
import com.google.genai.gaos.models.interactions.CreateModelInteraction;
import com.google.genai.gaos.models.interactions.Function;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;
import com.google.genai.gaos.models.interactions.Step;

Client client = new Client();
Map parameters =
    Map.of(
        "type", "object",
        "properties",
            Map.of(
                "location",
                Map.of(
                    "type", "string",
                    "description", "The city and state, e.g. San Francisco, CA")),
        "required", List.of("location"));
Function functionTool =
    Function.builder()
        .name("get_weather")
        .description("Get the current weather in a given location")
        .parameters(parameters)
        .build();
CreateModelInteraction params =
    CreateModelInteraction.builder()
        .model("gemini-flash-latest")
        .tools(List.of(functionTool))
        .input(InteractionsInput.of("What is the weather like in Boston, MA?"))
        .build();
CreateInteractionResponse response =
    client.interactions.create(CreateInteractionRequestBody.of(params));
Interaction interaction =
    response.interaction().orElseThrow(() -> new RuntimeException("No interaction returned"));
List steps = interaction.steps().orElse(List.of());
if (!steps.isEmpty()) {
  System.out.println(steps.get(steps.size() - 1));
}
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "google.golang.org/genai"
    gaos_interactions "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    function := gaos_interactions.Function{
        Name:        genai.Ptr("get_weather"),
        Description: genai.Ptr("Get the current weather in a given location"),
        Parameters: map[string]any{
            "type": "object",
            "properties": map[string]any{
                "location": map[string]any{
                    "type":        "string",
                    "description": "The city and state, e.g. San Francisco, CA",
                },
            },
            "required": []string{"location"},
        },
    }

    tool := gaos_interactions.NewTool(function)

    body := operations.NewCreateInteractionRequestBody(gaos_interactions.CreateModelInteraction{
        Model: gaos_interactions.Model("gemini-flash-latest"),
        Input: genai.Ptr(gaos_interactions.NewInteractionsInput("What is the weather like in Boston, MA?")),
        Tools: []gaos_interactions.Tool{tool},
    })

    res, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{Body: body})
    if err != nil {
        log.Fatal(err)
    }

    if res.Interaction != nil {
        for _, step := range res.Interaction.Steps {
            if step.FunctionCallStep != nil {
                fmt.Println("Function Call:", step.FunctionCallStep.Name)
                fmt.Println("Arguments:", step.FunctionCallStep.Arguments)
            }
        }
    }
}
```

#### Example Response

```
{
  "created": "2025-11-26T12:22:47Z",
  "id": "v1_ChdPU0F4YWFtNkFwS2kxZThQZ05lbXdROBIXT1NBeGFhbTZBcEtpMWU4UGdOZW13UTg",
  "model": "gemini-3.6-flash",
  "object": "interaction",
  "status": "requires_action",
  "steps": [\
    {\
      "name": "get_weather",\
      "type": "function_call",\
      "arguments": {\
        "location": "Boston, MA"\
      },\
      "id": "gth23981"\
    }\
  ],
  "updated": "2025-11-26T12:22:47Z",
  "usage": {
    "input_tokens_by_modality": [\
      {\
        "modality": "text",\
        "tokens": 100\
      }\
    ],
    "total_cached_tokens": 0,
    "total_input_tokens": 100,
    "total_output_tokens": 25,
    "total_thought_tokens": 0,
    "total_tokens": 125,
    "total_tool_use_tokens": 50
  }
}
```

Google AI for Developers

#### Example Request

RESTPythonJavaScriptJavaGo

```sh
curl -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "deep-research-pro-preview-12-2025",
    "input": "Find a cure to cancer",
    "background": true
  }'
```

```python
from google import genai

client = genai.Client()
interaction = client.interactions.create(
    agent="deep-research-pro-preview-12-2025",
    input="find a cure to cancer",
    background=True,
)
print(interaction.status)
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});
const interaction = await ai.interactions.create({
  agent: 'deep-research-pro-preview-12-2025',
  input: 'find a cure to cancer',
  background: true,
});
console.log(interaction.status);
```

```java
import com.google.genai.gaos.models.interactions.AgentOption;
import com.google.genai.Client;
import com.google.genai.gaos.models.interactions.CreateAgentInteraction;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.gaos.models.operations.CreateInteractionResponse;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionStatus;
import com.google.genai.gaos.models.interactions.InteractionsInput;

Client client = new Client();
CreateAgentInteraction params =
    CreateAgentInteraction.builder()
        .agent(AgentOption.of("deep-research-pro-preview-12-2025"))
        .input(InteractionsInput.of("find a cure to cancer"))
        .background(true)
        .build();
CreateInteractionResponse response =
    client.interactions.create(CreateInteractionRequestBody.of(params));
Interaction interaction =
    response.interaction().orElseThrow(() -> new RuntimeException("No interaction returned"));
System.out.println(interaction.status().map(InteractionStatus::value).orElse(""));
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "google.golang.org/genai"
    gaos_interactions "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    body := operations.NewCreateInteractionRequestBody(gaos_interactions.CreateAgentInteraction{
        Agent:      gaos_interactions.AgentOption("deep-research-pro-preview-12-2025"),
        Input:      genai.Ptr(gaos_interactions.NewInteractionsInput("find a cure to cancer")),
        Background: genai.Ptr(true),
    })

    req := operations.CreateInteractionRequest{
        Body: body,
    }

    res, err := client.Interactions.Create(ctx, req)
    if err != nil {
        log.Fatal(err)
    }

    if res.Interaction != nil {
        fmt.Println(res.Interaction.Status)
    }
}
```

#### Example Response

```
{
  "agent": "deep-research-pro-preview-12-2025",
  "created": "2025-11-26T12:22:47Z",
  "id": "v1_ChdPU0F4YWFtNkFwS2kxZThQZ05lbXdROBIXT1NBeGFhbTZBcEtpMWU4UGdOZW13UTg",
  "object": "interaction",
  "status": "completed",
  "steps": [\
    {\
      "type": "model_output",\
      "content": [\
        {\
          "type": "text",\
          "text": "Here is a comprehensive research report on the current state of cancer research..."\
        }\
      ]\
    }\
  ],
  "updated": "2025-11-26T12:22:47Z",
  "usage": {
    "input_tokens_by_modality": [\
      {\
        "modality": "text",\
        "tokens": 20\
      }\
    ],
    "total_cached_tokens": 0,
    "total_input_tokens": 20,
    "total_output_tokens": 1000,
    "total_thought_tokens": 500,
    "total_tokens": 1520,
    "total_tool_use_tokens": 0
  }
}
```

Google AI for Developers

#### Example Request

RESTPythonJavaScriptJavaGo

```sh
curl -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "antigravity-preview-05-2026",
    "input": "Read Hacker News, summarize the top 5 stories, and save results as a markdown file.",
    "environment": "remote"
  }'
```

```python
from google import genai

client = genai.Client()
interaction = client.interactions.create(
    agent="antigravity-preview-05-2026",
    input=(
        "Read Hacker News, summarize the top 5 stories, and save results as"
        " a markdown file."
    ),
    environment="remote",
)
print(interaction.output_text)
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});
const interaction = await ai.interactions.create({
  agent: 'antigravity-preview-05-2026',
  input:
    'Read Hacker News, summarize the top 5 stories, and save results as a markdown file.',
  environment: 'remote',
});
console.log(interaction.output_text);
```

```java
import com.google.genai.gaos.models.interactions.AgentOption;
import com.google.genai.Client;
import com.google.genai.gaos.models.interactions.CreateAgentInteraction;
import com.google.genai.gaos.models.interactions.CreateAgentInteractionEnvironment;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.gaos.models.operations.CreateInteractionResponse;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;

Client client = new Client();
CreateAgentInteraction params =
    CreateAgentInteraction.builder()
        .agent(AgentOption.of("antigravity-preview-05-2026"))
        .input(
            InteractionsInput.of(
                "Read Hacker News, summarize the top 5 stories, and save results as a markdown"
                    + " file."))
        .environment(CreateAgentInteractionEnvironment.of("remote"))
        .build();
CreateInteractionResponse response =
    client.interactions.create(CreateInteractionRequestBody.of(params));
Interaction interaction =
    response.interaction().orElseThrow(() -> new RuntimeException("No interaction returned"));
System.out.println(interaction.outputText().orElse(""));
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "google.golang.org/genai"
    gaos_interactions "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    body := operations.NewCreateInteractionRequestBody(gaos_interactions.CreateAgentInteraction{
        Agent:       gaos_interactions.AgentOption("antigravity-preview-05-2026"),
        Input:       genai.Ptr(gaos_interactions.NewInteractionsInput("Read Hacker News, summarize the top 5 stories, and save results as a markdown file.")),
        Environment: genai.Ptr(gaos_interactions.NewCreateAgentInteractionEnvironment("remote")),
    })

    res, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{Body: body})
    if err != nil {
        log.Fatal(err)
    }

    if res.Interaction != nil && res.Interaction.OutputText != nil {
        fmt.Println(*res.Interaction.OutputText)
    }
}
```

#### Example Response

```
{
  "agent": "antigravity-preview-05-2026",
  "created": "2025-11-26T12:22:47Z",
  "environment_id": "env_abc123",
  "id": "v1_ChdPU0F4YWFtNkFwS2kxZThQZ05lbXdROBIXT1NBeGFhbTZBcEtpMWU4UGdOZW13UTg",
  "object": "interaction",
  "status": "completed",
  "steps": [\
    {\
      "type": "model_output",\
      "content": [\
        {\
          "type": "text",\
          "text": "I've summarized the top 5 Hacker News stories and saved the results to /workspace/summary.md."\
        }\
      ]\
    }\
  ],
  "updated": "2025-11-26T12:22:47Z",
  "usage": {
    "input_tokens_by_modality": [\
      {\
        "modality": "text",\
        "tokens": 50\
      }\
    ],
    "total_cached_tokens": 0,
    "total_input_tokens": 50,
    "total_output_tokens": 500,
    "total_thought_tokens": 200,
    "total_tokens": 750,
    "total_tool_use_tokens": 0
  }
}
```

Google AI for Developers

#### Example Request

RESTPythonJavaScriptJavaGo

```sh
# Step 1: Create an interaction with a fresh remote environment.
RESPONSE=$(curl -s -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "antigravity-preview-05-2026",
    "input": "Write a hello world script at /workspace/hello.py.",
    "environment": "remote"
  }')
INTERACTION_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
ENV_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['environment_id'])")

# Step 2: Reuse the same environment in a follow-up interaction.
curl -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent\": \"antigravity-preview-05-2026\",
    \"input\": \"Modify the script to accept a name argument and greet the user.\",
    \"environment\": \"$ENV_ID\",
    \"previous_interaction_id\": \"$INTERACTION_ID\"
  }"
```

```python
from google import genai

client = genai.Client()

# Step 1: Create an interaction with a fresh remote environment.
interaction = client.interactions.create(
    agent="antigravity-preview-05-2026",
    input="Write a hello world script at /workspace/hello.py.",
    environment="remote",
)
print(f"Environment ID: {interaction.environment_id}")

# Step 2: Reuse the same environment in a follow-up interaction.
interaction_2 = client.interactions.create(
    agent="antigravity-preview-05-2026",
    input="Modify the script to accept a name argument and greet the user.",
    environment=interaction.environment_id,
    previous_interaction_id=interaction.id,
)
print(interaction_2.output_text)
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});

// Step 1: Create an interaction with a fresh remote environment.
const interaction = await ai.interactions.create({
  agent: 'antigravity-preview-05-2026',
  input: 'Write a hello world script at /workspace/hello.py.',
  environment: 'remote',
});
console.log(`Environment ID: ${interaction.environment_id}`);

// Step 2: Reuse the same environment in a follow-up interaction.
const interaction2 = await ai.interactions.create({
  agent: 'antigravity-preview-05-2026',
  input: 'Modify the script to accept a name argument and greet the user.',
  environment: interaction.environment_id,
  previous_interaction_id: interaction.id,
});
console.log(interaction2.output_text);
```

```java
import com.google.genai.gaos.models.interactions.AgentOption;
import com.google.genai.Client;
import com.google.genai.gaos.models.interactions.CreateAgentInteraction;
import com.google.genai.gaos.models.interactions.CreateAgentInteractionEnvironment;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.gaos.models.operations.CreateInteractionResponse;
import com.google.genai.gaos.models.environments.Environment;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;
import com.google.genai.gaos.models.interactions.Step;

Client client = new Client();

// Step 1: Create an interaction with a fresh remote environment.
CreateAgentInteraction params1 =
    CreateAgentInteraction.builder()
        .agent(AgentOption.of("antigravity-preview-05-2026"))
        .input(InteractionsInput.of("Write a hello world script at /workspace/hello.py."))
        .environment(CreateAgentInteractionEnvironment.of("remote"))
        .build();
CreateInteractionResponse response1 =
    client.interactions.create(CreateInteractionRequestBody.of(params1));
Interaction interaction1 =
    response1.interaction().orElseThrow(() -> new RuntimeException("No interaction returned"));
System.out.println("Environment ID: " + interaction1.environmentId().orElse(""));

// Step 2: Reuse the same environment in a follow-up interaction.
CreateAgentInteraction params2 =
    CreateAgentInteraction.builder()
        .agent(AgentOption.of("antigravity-preview-05-2026"))
        .input(
            InteractionsInput.of(
                "Modify the script to accept a name argument and greet the user."))
        .environment(
            CreateAgentInteractionEnvironment.of(interaction1.environmentId().orElse("")))
        .previousInteractionId(interaction1.id().orElse(null))
        .build();
CreateInteractionResponse response2 =
    client.interactions.create(CreateInteractionRequestBody.of(params2));
Interaction interaction2 =
    response2.interaction().orElseThrow(() -> new RuntimeException("No interaction returned"));
System.out.println(interaction2.outputText().orElse(""));
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "google.golang.org/genai"
    gaos_interactions "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    // Step 1: Create an interaction with a fresh remote environment.
    body1 := operations.NewCreateInteractionRequestBody(gaos_interactions.CreateAgentInteraction{
        Agent:       gaos_interactions.AgentOption("antigravity-preview-05-2026"),
        Input:       genai.Ptr(gaos_interactions.NewInteractionsInput("Write a hello world script at /workspace/hello.py.")),
        Environment: genai.Ptr(gaos_interactions.NewCreateAgentInteractionEnvironment("remote")),
    })

    res1, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{Body: body1})
    if err != nil {
        log.Fatal(err)
    }

    if res1.Interaction == nil || res1.Interaction.EnvironmentID == nil {
        log.Fatal("No environment ID returned")
    }
    fmt.Printf("Environment ID: %s\n", *res1.Interaction.EnvironmentID)

    // Step 2: Reuse the same environment in a follow-up interaction.
    body2 := operations.NewCreateInteractionRequestBody(gaos_interactions.CreateAgentInteraction{
        Agent:                 gaos_interactions.AgentOption("antigravity-preview-05-2026"),
        Input:                 genai.Ptr(gaos_interactions.NewInteractionsInput("Modify the script to accept a name argument and greet the user.")),
        Environment:           genai.Ptr(gaos_interactions.NewCreateAgentInteractionEnvironment(*res1.Interaction.EnvironmentID)),
        PreviousInteractionID: res1.Interaction.ID,
    })

    res2, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{Body: body2})
    if err != nil {
        log.Fatal(err)
    }

    if res2.Interaction != nil && res2.Interaction.OutputText != nil {
        fmt.Println(*res2.Interaction.OutputText)
    }
}
```

#### Example Response

```
{
  "agent": "antigravity-preview-05-2026",
  "created": "2025-11-26T12:23:00Z",
  "environment_id": "env_abc123",
  "id": "v1_Chd2ZTJhYmNkZWZnaGlqa2xtbm9wcXJzdHV2d3h5ejAxMjM0NTY3ODkwMTIzNDU2Nzg",
  "object": "interaction",
  "status": "completed",
  "steps": [\
    {\
      "type": "model_output",\
      "content": [\
        {\
          "type": "text",\
          "text": "I've updated /workspace/hello.py to accept a name argument and greet the user."\
        }\
      ]\
    }\
  ],
  "updated": "2025-11-26T12:23:00Z",
  "usage": {
    "input_tokens_by_modality": [\
      {\
        "modality": "text",\
        "tokens": 80\
      }\
    ],
    "total_cached_tokens": 0,
    "total_input_tokens": 80,
    "total_output_tokens": 200,
    "total_thought_tokens": 100,
    "total_tokens": 380,
    "total_tool_use_tokens": 0
  }
}
```

Google AI for Developers

#### Example Request

RESTPythonJavaScriptJavaGo

```sh
curl -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "antigravity-preview-05-2026",
    "input": "List all files under /workspace and summarize what you find.",
    "environment": {
      "type": "remote",
      "sources": [\
        {\
          "type": "repository",\
          "source": "https://github.com/octocat/Spoon-Knife",\
          "target": "/workspace/repo"\
        },\
        {\
          "type": "inline",\
          "content": "Focus on Python files only.",\
          "target": "/workspace/notes.txt"\
        }\
      ]
    }
  }'
```

```python
from google import genai

client = genai.Client()
interaction = client.interactions.create(
    agent="antigravity-preview-05-2026",
    input="List all files under /workspace and summarize what you find.",
    environment={
        "type": "remote",
        "sources": [\
            {\
                "type": "repository",\
                "source": "https://github.com/octocat/Spoon-Knife",\
                "target": "/workspace/repo",\
            },\
            {\
                "type": "inline",\
                "content": "Focus on Python files only.",\
                "target": "/workspace/notes.txt",\
            },\
        ],
    },
)
print(interaction.output_text)
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});
const interaction = await ai.interactions.create({
  agent: 'antigravity-preview-05-2026',
  input: 'List all files under /workspace and summarize what you find.',
  environment: {
    type: 'remote',
    sources: [\
      {\
        type: 'repository',\
        source: 'https://github.com/octocat/Spoon-Knife',\
        target: '/workspace/repo',\
      },\
      {\
        type: 'inline',\
        content: 'Focus on Python files only.',\
        target: '/workspace/notes.txt',\
      },\
    ],
  },
});
console.log(interaction.output_text);
```

```java
import com.google.genai.gaos.models.interactions.AgentOption;
import com.google.genai.Client;
import com.google.genai.gaos.models.interactions.CreateAgentInteraction;
import com.google.genai.gaos.models.interactions.CreateAgentInteractionEnvironment;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.gaos.models.operations.CreateInteractionResponse;
import com.google.genai.gaos.models.environments.Environment;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;
import com.google.genai.gaos.models.interactions.Source;
import com.google.genai.gaos.models.interactions.SourceType;

Client client = new Client();
com.google.genai.gaos.models.interactions.Environment env =
    com.google.genai.gaos.models.interactions.Environment.builder()
        .sources(
            List.of(
                Source.builder()
                    .type(SourceType.REPOSITORY)
                    .source("https://github.com/octocat/Spoon-Knife")
                    .target("/workspace/repo")
                    .build(),
                Source.builder()
                    .type(SourceType.INLINE)
                    .content("Focus on Python files only.")
                    .target("/workspace/notes.txt")
                    .build()))
        .build();
CreateAgentInteraction params =
    CreateAgentInteraction.builder()
        .agent(AgentOption.of("antigravity-preview-05-2026"))
        .input(
            InteractionsInput.of(
                "List all files under /workspace and summarize what you find."))
        .environment(CreateAgentInteractionEnvironment.of(env))
        .build();
CreateInteractionResponse response =
    client.interactions.create(CreateInteractionRequestBody.of(params));
Interaction interaction =
    response.interaction().orElseThrow(() -> new RuntimeException("No interaction returned"));
System.out.println(interaction.outputText().orElse(""));
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "google.golang.org/genai"
    gaos_interactions "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    env := gaos_interactions.Environment{
        Sources: []gaos_interactions.Source{
            {
                Type:   genai.Ptr(gaos_interactions.SourceTypeRepository),
                Source: genai.Ptr("https://github.com/octocat/Spoon-Knife"),
                Target: genai.Ptr("/workspace/repo"),
            },
            {
                Type:    genai.Ptr(gaos_interactions.SourceTypeInline),
                Content: genai.Ptr("Focus on Python files only."),
                Target:  genai.Ptr("/workspace/notes.txt"),
            },
        },
    }

    body := operations.NewCreateInteractionRequestBody(gaos_interactions.CreateAgentInteraction{
        Agent:       gaos_interactions.AgentOption("antigravity-preview-05-2026"),
        Input:       genai.Ptr(gaos_interactions.NewInteractionsInput("List all files under /workspace and summarize what you find.")),
        Environment: genai.Ptr(gaos_interactions.NewCreateAgentInteractionEnvironment(env)),
    })

    res, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{Body: body})
    if err != nil {
        log.Fatal(err)
    }

    if res.Interaction != nil && res.Interaction.OutputText != nil {
        fmt.Println(*res.Interaction.OutputText)
    }
}
```

Google AI for Developers

#### Example Request

RESTPythonJavaScriptJavaGo

```sh
# Step 1: Create a custom agent.
curl -X POST https://generativelanguage.googleapis.com/v1beta/agents \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "code-reviewer",
    "base_agent": "antigravity-preview-05-2026",
    "system_instruction": "You are a senior code reviewer. Check every file for bugs, style issues, and security vulnerabilities.",
    "base_environment": {
      "type": "remote",
      "sources": [{\
        "type": "repository",\
        "source": "https://github.com/octocat/Spoon-Knife",\
        "target": "/workspace/repo"\
      }]
    }
  }'

# Step 2: Use the custom agent.
curl -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "code-reviewer",
    "input": "Review the latest changes in /workspace/repo/src and file a summary.",
    "environment": "remote"
  }'
```

```python
import uuid
from google import genai

client = genai.Client()

# Step 1: Create a custom agent.
agent_id = f"code-reviewer-{uuid.uuid4().hex[:8]}"
client.agents.create(
    id=agent_id,
    base_agent="antigravity-preview-05-2026",
    system_instruction=(
        "You are a senior code reviewer. Check every file for bugs, style"
        " issues, and security vulnerabilities."
    ),
    base_environment={
        "type": "remote",
        "sources": [{\
            "type": "repository",\
            "source": "https://github.com/octocat/Spoon-Knife",\
            "target": "/workspace/repo",\
        }],
    },
)

# Step 2: Use the custom agent.
result = client.interactions.create(
    agent=agent_id,
    input=(
        "Review the latest changes in /workspace/repo/src and file a"
        " summary."
    ),
    environment="remote",
)
print(result.output_text)
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});

// Step 1: Create a custom agent.
const agentId = `code-reviewer-${crypto.randomUUID().slice(0, 8)}`;
await ai.agents.create({
  id: agentId,
  base_agent: 'antigravity-preview-05-2026',
  system_instruction:
    'You are a senior code reviewer. Check every file for bugs, style issues, and security vulnerabilities.',
  base_environment: {
    type: 'remote',
    sources: [\
      {\
        type: 'repository',\
        source: 'https://github.com/octocat/Spoon-Knife',\
        target: '/workspace/repo',\
      },\
    ],
  },
});

// Step 2: Use the custom agent.
const result = await ai.interactions.create({
  agent: agentId,
  input:
    'Review the latest changes in /workspace/repo/src and file a summary.',
  environment: 'remote',
});
console.log(result.output_text);
```

```java
import com.google.genai.gaos.models.agents.Agent;
import com.google.genai.gaos.models.interactions.AgentOption;
import com.google.genai.gaos.models.agents.BaseEnvironment;
import com.google.genai.Client;
import com.google.genai.gaos.models.interactions.CreateAgentInteraction;
import com.google.genai.gaos.models.interactions.CreateAgentInteractionEnvironment;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.gaos.models.operations.CreateInteractionResponse;
import com.google.genai.gaos.models.environments.Environment;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;
import com.google.genai.gaos.models.interactions.Source;
import com.google.genai.gaos.models.interactions.SourceType;
import com.google.genai.gaos.models.interactions.Step;

Client client = new Client();

// Step 1: Create a custom agent.
String agentId = "code-reviewer-" + UUID.randomUUID().toString().substring(0, 8);
com.google.genai.gaos.models.interactions.Environment baseEnv =
    com.google.genai.gaos.models.interactions.Environment.builder()
        .sources(
            List.of(
                Source.builder()
                    .type(SourceType.REPOSITORY)
                    .source("https://github.com/octocat/Spoon-Knife")
                    .target("/workspace/repo")
                    .build()))
        .build();
Agent customAgent =
    Agent.builder()
        .id(agentId)
        .baseAgent("antigravity-preview-05-2026")
        .systemInstruction(
            "You are a senior code reviewer. Check every file for bugs, style issues, and"
                + " security vulnerabilities.")
        .baseEnvironment(BaseEnvironment.of(baseEnv))
        .build();
client.agents.create(customAgent);

// Step 2: Use the custom agent.
CreateAgentInteraction params =
    CreateAgentInteraction.builder()
        .agent(AgentOption.of(agentId))
        .input(
            InteractionsInput.of(
                "Review the latest changes in /workspace/repo/src and file a summary."))
        .environment(CreateAgentInteractionEnvironment.of("remote"))
        .build();
CreateInteractionResponse response =
    client.interactions.create(CreateInteractionRequestBody.of(params));
Interaction interaction =
    response.interaction().orElseThrow(() -> new RuntimeException("No interaction returned"));
System.out.println(interaction.outputText().orElse(""));
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "time"
    "google.golang.org/genai"
    gaos_agents "google.golang.org/genai/interactions/models/agents"
    gaos_interactions "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    // Step 1: Create a custom agent.
    agentID := fmt.Sprintf("code-reviewer-%d", time.Now().UnixNano())
    baseEnv := gaos_interactions.Environment{
        Sources: []gaos_interactions.Source{
            {
                Type:   genai.Ptr(gaos_interactions.SourceTypeRepository),
                Source: genai.Ptr("https://github.com/octocat/Spoon-Knife"),
                Target: genai.Ptr("/workspace/repo"),
            },
        },
    }

    _, err = client.Agents.Create(ctx, operations.CreateAgentRequest{
        Body: gaos_agents.Agent{
            ID:                genai.Ptr(agentID),
            BaseAgent:         genai.Ptr("antigravity-preview-05-2026"),
            SystemInstruction: genai.Ptr("You are a senior code reviewer. Check every file for bugs, style issues, and security vulnerabilities."),
            BaseEnvironment:   genai.Ptr(gaos_agents.NewBaseEnvironment(baseEnv)),
        },
    })
    if err != nil {
        log.Fatal(err)
    }

    // Step 2: Use the custom agent.
    body := operations.NewCreateInteractionRequestBody(gaos_interactions.CreateAgentInteraction{
        Agent:       gaos_interactions.AgentOption(agentID),
        Input:       genai.Ptr(gaos_interactions.NewInteractionsInput("Review the latest changes in /workspace/repo/src and file a summary.")),
        Environment: genai.Ptr(gaos_interactions.NewCreateAgentInteractionEnvironment("remote")),
    })

    res, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{Body: body})
    if err != nil {
        log.Fatal(err)
    }

    if res.Interaction != nil && res.Interaction.OutputText != nil {
        fmt.Println(*res.Interaction.OutputText)
    }
}
```

## Canceling an interaction

post

https://generativelanguage.googleapis.com/v1beta/interactions/{id}/cancel


Cancels an interaction by id. This only applies to background interactions that are still running.

- [Path / Query parameters](https://ai.google.dev/api/interactions-api#cancelInteractionById.PATH_PARAMETERS)
- [Response](https://ai.google.dev/api/interactions-api#cancelInteractionById.response)

### Path / Query Parameters

api\_versionstring (required)

API version for request routing.

idstring (required)

The unique identifier of the interaction to cancel.

### Response

Returns an [Interaction](https://ai.google.dev/api/interactions-api#Resource:Interaction) resource.

[Cancel Interaction](https://ai.google.dev/api/interactions-api#cancel-interaction)More

Google AI for Developers

#### Example Request

RESTPythonJavaScriptJavaGo

```sh
curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions/$INTERACTION_ID/cancel" \
  -H "x-goog-api-key: $GEMINI_API_KEY"
```

```python
from google import genai

client = genai.Client()

# Start a background interaction so it stays in-progress.
created = client.interactions.create(
    model="gemini-flash-latest",
    input="Write a long essay about the history of computing.",
    tools=[{"type": "computer_use"}],
    background=True,
)

# Cancel the in-progress interaction.
interaction = client.interactions.cancel(id=created.id)
print(interaction.status)
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});

// Start a background interaction so it stays in-progress.
const created = await ai.interactions.create({
  model: 'gemini-flash-latest',
  input: 'Write a long essay about the history of computing.',
  tools: [{type: 'computer_use'}],
  background: true,
});

// Cancel the in-progress interaction.
const interaction = await ai.interactions.cancel(created.id);
console.log(interaction.status);
```

```java
import com.google.genai.gaos.models.operations.CancelInteractionByIdResponse;
import com.google.genai.Client;
import com.google.genai.gaos.models.interactions.ComputerUse;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.gaos.models.operations.CreateInteractionResponse;
import com.google.genai.gaos.models.interactions.CreateModelInteraction;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionStatus;
import com.google.genai.gaos.models.interactions.InteractionsInput;

Client client = new Client();

// Start a background interaction so it stays in-progress.
CreateModelInteraction params =
    CreateModelInteraction.builder()
        .model("gemini-flash-latest")
        .input(InteractionsInput.of("Write a long essay about the history of computing."))
        .tools(List.of(new ComputerUse()))
        .background(true)
        .build();
CreateInteractionResponse created =
    client.interactions.create(CreateInteractionRequestBody.of(params));
String interactionId = created.interaction().flatMap(Interaction::id).orElseThrow();

// Cancel the in-progress interaction.
CancelInteractionByIdResponse cancelResponse = client.interactions.cancel(interactionId);
Interaction interaction =
    cancelResponse
        .interaction()
        .orElseThrow(() -> new RuntimeException("No interaction returned"));
System.out.println(interaction.status().map(InteractionStatus::value).orElse(""));
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "google.golang.org/genai"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    req := operations.CancelInteractionByIDRequest{
        ID: interactionID,
    }

    res, err := client.Interactions.Cancel(
        ctx,
        req,
    )
    if err != nil {
        log.Fatal(err)
    }

    if res.Interaction != nil {
        fmt.Println(res.Interaction.Status)
    }
}
```

#### Example Response

```
{
  "created": "2025-11-26T12:25:15Z",
  "id": "v1_ChdPU0F4YWFtNkFwS2kxZThQZ05lbXdROBIXT1NBeGFhbTZBcEtpMWU4UGdOZW13UTg",
  "model": "gemini-3.6-flash",
  "object": "interaction",
  "status": "cancelled",
  "updated": "2025-11-26T12:25:15Z"
}
```

## Retrieving an interaction

get

https://generativelanguage.googleapis.com/v1beta/interactions/{id}


Retrieves the full details of a single interaction based on its \`Interaction.id\`.

- [Path / Query parameters](https://ai.google.dev/api/interactions-api#getInteractionById.PATH_PARAMETERS)
- [Response](https://ai.google.dev/api/interactions-api#getInteractionById.response)

### Path / Query Parameters

api\_versionstring (required)

API version for request routing.

idstring (required)

The unique identifier of the interaction to retrieve.

last\_event\_idstring (optional)

Optional. If set, resumes the interaction stream from the next chunk after the event marked by the event id. Can only be used if \`stream\` is true.

streamboolean (optional)

If set to true, the generated content will be streamed incrementally.

_Defaults to: `False`_

### Response

Returns an [Interaction](https://ai.google.dev/api/interactions-api#Resource:Interaction) resource.

[Get Interaction](https://ai.google.dev/api/interactions-api#get-interaction)More

Google AI for Developers

#### Example Request

RESTPythonJavaScriptJavaGo

```sh
curl -X GET "https://generativelanguage.googleapis.com/v1beta/interactions/$INTERACTION_ID" \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
```

```python
from google import genai

client = genai.Client()

interaction = client.interactions.get(id=created.id)
print(interaction.status)
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});

const interaction = await ai.interactions.get(created.id);
console.log(interaction.status);
```

```java
import com.google.genai.Client;
import com.google.genai.gaos.models.operations.GetInteractionByIdRequest;
import com.google.genai.gaos.models.operations.GetInteractionByIdResponse;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionStatus;

Client client = new Client();

GetInteractionByIdResponse getResponse =
    client.interactions.get(new GetInteractionByIdRequest(interactionId));
Interaction interaction =
    getResponse
        .interaction()
        .orElseThrow(() -> new RuntimeException("No interaction returned"));
System.out.println(interaction.status().map(InteractionStatus::value).orElse(""));
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "google.golang.org/genai"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    interaction, err := client.Interactions.Get(ctx, operations.GetInteractionByIDRequest{
        ID: *created.Interaction.ID,
    })
    if err != nil {
        log.Fatal(err)
    }

    if interaction.Interaction != nil {
        fmt.Println(interaction.Interaction.Status)
    }
}
```

#### Example Response

```
{
  "created": "2025-11-26T12:25:15Z",
  "id": "v1_ChdPU0F4YWFtNkFwS2kxZThQZ05lbXdROBIXT1NBeGFhbTZBcEtpMWU4UGdOZW13UTg",
  "model": "gemini-3.6-flash",
  "object": "interaction",
  "status": "completed",
  "steps": [\
    {\
      "type": "model_output",\
      "content": [\
        {\
          "type": "text",\
          "text": "I'm doing great, thank you for asking! How can I help you today?"\
        }\
      ]\
    }\
  ],
  "updated": "2025-11-26T12:25:15Z"
}
```

## Deleting an interaction

delete

https://generativelanguage.googleapis.com/v1beta/interactions/{id}


Deletes the interaction by id.

- [Path / Query parameters](https://ai.google.dev/api/interactions-api#deleteInteraction.PATH_PARAMETERS)
- [Response](https://ai.google.dev/api/interactions-api#deleteInteraction.response)

### Path / Query Parameters

api\_versionstring (required)

API version for request routing.

idstring (required)

The unique identifier of the interaction to delete.

interactionsIdstring (required)

Required. The name of the interaction to delete.

### Response

If successful, the response is empty.

[Delete](https://ai.google.dev/api/interactions-api#delete)More

Google AI for Developers

#### Example Request

RESTPythonJavaScriptJavaGo

```sh
curl -X DELETE "https://generativelanguage.googleapis.com/v1beta/interactions/$INTERACTION_ID" \
  -H "x-goog-api-key: $GEMINI_API_KEY"
```

```python
from google import genai

client = genai.Client()

client.interactions.delete(id=created.id)
print("Interaction deleted successfully.")
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});

await ai.interactions.delete(created.id);
console.log('Interaction deleted successfully.');
```

```java
import com.google.genai.Client;
import com.google.genai.gaos.models.interactions.Interaction;

Client client = new Client();

client.interactions.delete(interactionId);
System.out.println("Interaction deleted successfully.");
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "google.golang.org/genai"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    req := operations.DeleteInteractionRequest{
        ID: interactionID,
    }

    _, err = client.Interactions.Delete(
        ctx,
        req,
    )
    if err != nil {
        log.Fatal(err)
    }

    fmt.Println("Interaction deleted successfully.")
}
```

## Resources

### Interaction

The Interaction resource.

#### Fields

idstring (required)

Required. Output only. A unique identifier for the interaction completion.

statusenum (string) (required)

Required. Output only. The status of the interaction.

Possible
values:

- `in_progress`
The interaction is in progress.

- `requires_action`
The interaction requires action/input from the user.

- `completed`
The interaction is completed.

- `failed`
The interaction failed.

- `cancelled`
The interaction was cancelled.

- `incomplete`
The interaction is completed, but contains incomplete results (e.g.
hitting max\_tokens).


createdstring (required)

Required. Output only. The time at which the response was created in ISO 8601 format
(YYYY-MM-DDThh:mm:ssZ).

updatedstring (required)

Required. Output only. The time at which the response was last updated in ISO 8601 format
(YYYY-MM-DDThh:mm:ssZ).

stepsarray ( [Step](https://ai.google.dev/api/interactions-api#Resource:Step)) (required)

Required. Output only. The steps that make up the interaction, when included in the response.

modelModelOption (optional)

The name of the \`Model\` used for generating the interaction.

The model that will complete your prompt.\\n\\nSee \[models\](https://ai.google.dev/gemini-api/docs/models) for additional details.

#### Possible values

- `gemma-4-26b-a4b-it`
Gemma 4 26B A4B IT

- `gemma-4-31b-it`
Gemma 4 31B IT

- `gemini-flash-latest`
Latest release of Gemini Flash

- `gemini-flash-lite-latest`
Latest release of Gemini Flash-Lite

- `gemini-pro-latest`
Latest release of Gemini Pro

- `gemini-2.5-flash`
Our first hybrid reasoning model which supports a 1M token context window and has thinking budgets.

- `gemini-2.5-pro`
Our state-of-the-art multipurpose model, which excels at coding and complex reasoning tasks.

- `gemini-2.5-flash-lite`
Our smallest and most cost effective model, built for at scale usage.

- `gemini-3.5-flash-lite`
Gemini 3.5 Flash-Lite - Our fastest, most cost-effective 3.5 model for high-throughput execution.

- `gemini-2.5-flash-image`
Our native image generation model, optimized for speed, flexibility, and contextual understanding. Text input and output is priced the same as 2.5 Flash.

- `gemini-3-flash-preview`
Our most intelligent model built for speed, combining frontier intelligence with superior search and grounding.

- `gemini-3.1-pro-preview`
Our latest SOTA reasoning model with unprecedented depth and nuance, and powerful multimodal understanding and coding capabilities.

- `gemini-3.1-pro-preview-customtools`
Gemini 3.1 Pro Preview optimized for custom tool usage

- `gemini-3.1-flash-lite`
Our most cost-efficient model, optimized for high-volume agentic tasks, translation, and simple data processing.

- `gemini-3.1-flash-lite-image`
Gemini 3.1 Flash Lite Image.

- `gemini-3-pro-image`
Gemini 3 Pro Image

- `nano-banana-pro-preview`
Gemini 3 Pro Image Preview

- `gemini-3.1-flash-image`
Gemini 3.1 Flash Image.

- `gemini-nano-banana-2.1`
Gemini Nano Banana 2.1.

- `gemini-3.1-flash-tts-preview`
Gemini 3.1 Flash TTS: Powerful, low-latency speech generation. Enjoy natural outputs, steerable prompts, and new expressive audio tags for precise narration control.

- `gemini-3.5-flash`
Gemini 3.5 Flash - Our earlier Flash model, built for speed and foundational performance across routine, high-throughput workloads.

- `gemini-3.6-flash`
Gemini 3.6 Flash - Our previous generation Flash model, balancing speed and multimodal capabilities across general agentic and everyday tasks.

- `gemini-3.7-flash`
Gemini 3.7 Flash - Our high-speed, efficient Flash model built for everyday coding, agentic tool use, and reliable multi-step execution.

- `gemini-3.8-flash`
Gemini 3.8 Flash - Our most intelligent Flash model, engineered for long-horizon software engineering, autonomous agents, and complex enterprise workflows.

- `gemini-3.8-flash-tts`
Gemini 3.8 Flash TTS - Flagship TTS model for Voice Design and dual-speaker screenplay control. Prompt custom vocal personas, direct line-by-line delivery, and add vocal bursts.

- `gemini-3.8-flash-lite-tts`
Gemini 3.8 Flash Lite TTS - High-speed and cost-efficient, ideal for rapid dubbing, media localization, and high-throughput voice agents. Direct replacement for gemini-3.1-flash-tts-preview.

- `lyria-3-clip-preview`
Our low-latency, music generation model optimized for high-fidelity audio clips and precise rhythmic control.

- `lyria-3-pro-preview`
Our advanced, full-song generative model with deep compositional understanding, optimized for precise structural control and complex transitions across diverse musical styles.

- `gemini-robotics-er-1.6-preview`
Gemini Robotics-ER 1.6 Preview

- `gemini-robotics-er-2-preview`
Gemini Robotics Embodied Reasoning 2 Preview

- `lyria-3.5`
Our flagship music generation model, optimized for full-length songs with complex structural coherence.

- `gemini-omni-1.1-flash`
Our high-performance multimodal model designed for fast, conversational video generation, editing, and cinematic control.

- `gemini-omni-flash-preview`
Preview release of our multimodal model for conversational video generation, editing, and cinematic control.


input[Content](https://ai.google.dev/api/interactions-api#Resource:Content) or array ( [Content](https://ai.google.dev/api/interactions-api#Resource:Content)) or array ( [Step](https://ai.google.dev/api/interactions-api#Resource:Step)) or string (optional)

The input for the interaction.

response\_format[ResponseFormat](https://ai.google.dev/api/interactions-api#Resource:ResponseFormat) or array ( [ResponseFormat](https://ai.google.dev/api/interactions-api#Resource:ResponseFormat)) (optional)

Enforces that the generated response is a JSON object that complies with
the JSON schema specified in this field.

environment[EnvironmentConfig](https://ai.google.dev/api/interactions-api#Resource:EnvironmentConfig) or string (optional)

The environment configuration for the interaction. Can be an object
specifying remote environment sources or a string referencing an existing
environment ID.

system\_instructionstring (optional)

System instruction for the interaction.

toolsarray ( [Tool](https://ai.google.dev/api/interactions-api#Resource:Tool)) (optional)

A list of tool declarations the model may call during interaction.

usageUsage (optional)

Output only. Statistics on the interaction request's token usage.

Statistics on the interaction request's token usage.

#### Fields

total\_input\_tokensinteger (optional)

Number of tokens in the prompt (context).

input\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of input token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_cached\_tokensinteger (optional)

Number of tokens in the cached part of the prompt (the cached content).

cached\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of cached token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_output\_tokensinteger (optional)

Total number of tokens across all the generated responses.

output\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of output token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_tool\_use\_tokensinteger (optional)

Number of tokens present in tool-use prompt(s).

tool\_use\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of tool-use token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_thought\_tokensinteger (optional)

Number of tokens of thoughts for thinking models.

total\_tokensinteger (optional)

Total token count for the interaction request (prompt + responses + other
internal tokens).

grounding\_tool\_countarray (GroundingToolCount) (optional)

Grounding tool count.

The number of grounding tool counts.

#### Fields

typeenum (string) (optional)

The grounding tool type associated with the count.

Possible
values:

- `google_search`
Grounding with Google Web Search and Image Search, & Web Grounding
for Enterprise.

- `google_maps`
Grounding with Google Maps.


countinteger (optional)

The number of grounding tool counts.

previous\_interaction\_idstring (optional)

The ID of the previous interaction, if any.

environment\_idstring (optional)

Output only. The environment ID for the interaction. Only populated if environment
config is set in the request.

service\_tierServiceTier (optional)

The service tier for the interaction.

#### Possible values

- `flex`
Flex service tier.

- `standard`
Standard service tier.

- `priority`
Priority service tier.


webhook\_configWebhookConfig (optional)

Optional. Webhook configuration for receiving notifications when the
interaction completes.

Message for configuring webhook events for a request.

#### Fields

urisarray (string) (optional)

Optional. If set, these webhook URIs will be used for webhook events instead of the
registered webhooks.

user\_metadataobject (optional)

Optional. The user metadata that will be returned on each event emission to the
webhooks.

safety\_settingsarray (SafetySetting) (optional)

Safety settings for the interaction.

A safety setting that affects the safety-blocking behavior.

A SafetySetting consists of a
harm category and a
threshold for that
category.

#### Fields

typeHarmCategory (required)

Required. The type of harm category to be blocked.

#### Possible values

- `hate_speech`
Content that promotes violence or incites hatred against individuals or
groups based on certain attributes.

- `dangerous_content`
Content that promotes, facilitates, or enables dangerous activities.

- `harassment`
Abusive, threatening, or content intended to bully, torment, or ridicule.

- `sexually_explicit`
Content that contains sexually explicit material.

- `jailbreak`
Prompts designed to bypass safety filters.


thresholdenum (string) (required)

Required. The threshold for blocking content. If the harm probability
exceeds this threshold, the content will be blocked.

Possible
values:

- `block_low_and_above`
Block content with a low harm probability or higher.

- `block_medium_and_above`
Block content with a medium harm probability or higher.

- `block_only_high`
Block content with a high harm probability.

- `off`
Turn off the safety filter entirely.


methodenum (string) (optional)

Optional. The method for blocking content. If not specified, the default
behavior is to use the probability score.

Possible
values:

- `severity`
The harm block method uses both probability and severity scores.

- `probability`
The harm block method uses the probability score.


labelsobject (optional)

The labels with user-defined metadata for the request.

Label keys and values can be no longer than 63 characters
(Unicode codepoints) and can only contain lowercase letters, numeric
characters, underscores, and dashes. International characters are allowed.
Label values are optional. Label keys must start with a letter.

errorsarray (Error) (optional)

Output only. Diagnostic faults / platform errors recorded on the interaction.

Error message from an interaction.

#### Fields

codestring (optional)

A URI that identifies the error type.

messagestring (optional)

A human-readable error message.

agentAgentOption (optional)

The name of the \`Agent\` used for generating the interaction.

The agent to interact with.

#### Possible values

- `deep-research-pro-preview-12-2025`
Gemini Deep Research Agent

- `deep-research-preview-04-2026`
Gemini Deep Research Agent

- `deep-research-max-preview-04-2026`
Gemini Deep Research Max Agent

- `antigravity-preview-05-2026`
Use the Antigravity managed agent to perform multi-step tasks that require reasoning, file operations, and tool use.


agent\_configAntigravityAgentConfig or DeepResearchAgentConfig or DynamicAgentConfig (optional)

Configuration parameters for the agent interaction.

max\_total\_tokensstring (optional)

Max total tokens for the agent run.

### Examples

[Example](https://ai.google.dev/api/interactions-api#example)More

```
{
  "created": "2025-12-04T15:01:45Z",
  "id": "v1_ChdXS0l4YWZXTk9xbk0xZThQczhEcmlROBIXV0tJeGFmV05PcW5NMWU4UHM4RHJpUTg",
  "model": "gemini-3.6-flash",
  "object": "interaction",
  "status": "completed",
  "steps": [\
    {\
      "type": "model_output",\
      "content": [\
        {\
          "type": "text",\
          "text": "Hello! I'm doing well, functioning as expected. Thank you for asking! How are you doing today?"\
        }\
      ]\
    }\
  ],
  "updated": "2025-12-04T15:01:45Z",
  "usage": {
    "input_tokens_by_modality": [\
      {\
        "modality": "text",\
        "tokens": 7\
      }\
    ],
    "total_cached_tokens": 0,
    "total_input_tokens": 7,
    "total_output_tokens": 23,
    "total_thought_tokens": 49,
    "total_tokens": 79,
    "total_tool_use_tokens": 0
  }
}
```

## Data Models

### Content

The content of the response.

### Possible Types

AudioContent

An audio content block.

typeobject (required)

No description provided.

Always set to `"audio"`.

datastring (optional)

The audio content.

uristring (optional)

The URI of the audio.

channelsinteger (optional)

The number of audio channels.

sample\_rateinteger (optional)

The sample rate of the audio.

mime\_typeenum (string) (optional)

The mime type of the audio.

Possible
values:

- `audio/wav`
WAV audio format

- `audio/mp3`
MP3 audio format

- `audio/aiff`
AIFF audio format

- `audio/aac`
AAC audio format

- `audio/ogg`
OGG audio format

- `audio/flac`
FLAC audio format

- `audio/mpeg`
MPEG audio format

- `audio/m4a`
M4A audio format

- `audio/l16`
L16 audio format

- `audio/opus`
OPUS audio format

- `audio/alaw`
ALAW audio format

- `audio/mulaw`
MULAW audio format

- `audio/webm`
WEBM audio format


DocumentContent

A document content block.

typeobject (required)

No description provided.

Always set to `"document"`.

datastring (optional)

The document content.

uristring (optional)

The URI of the document.

mime\_typeenum (string) (optional)

The mime type of the document.

Possible
values:

- `application/pdf`
PDF document format

- `text/csv`
CSV document format


ImageContent

An image content block.

typeobject (required)

No description provided.

Always set to `"image"`.

datastring (optional)

The image content.

uristring (optional)

The URI of the image.

resolutionMediaResolution (optional)

The resolution of the media.

#### Possible values

- `low`
Low resolution.

- `medium`
Medium resolution.

- `high`
High resolution.

- `ultra_high`
Ultra high resolution.


mime\_typeenum (string) (optional)

The mime type of the image.

Possible
values:

- `image/png`
PNG image format

- `image/jpeg`
JPEG image format

- `image/webp`
WebP image format

- `image/heic`
HEIC image format

- `image/heif`
HEIF image format

- `image/gif`
GIF image format

- `image/bmp`
BMP image format

- `image/tiff`
TIFF image format


TextContent

A text content block.

textstring (required)

Required. The text content.

typeobject (required)

No description provided.

Always set to `"text"`.

annotationsarray (Annotation) (optional)

Citation information for model-generated content.

Citation information for model-generated content.

#### Possible Types

FileCitation

A file citation annotation.

typeobject (required)

No description provided.

Always set to `"file_citation"`.

document\_uristring (optional)

The URI of the file.

file\_namestring (optional)

The name of the file.

sourcestring (optional)

Source attributed for a portion of the text.

custom\_metadataobject (optional)

User provided metadata about the retrieved context.

page\_numberinteger (optional)

Page number of the cited document, if applicable.

media\_idstring (optional)

Media ID in-case of image citations, if applicable.

start\_indexinteger (optional)

Start of segment of the response that is attributed to this source.

Index indicates the start of the segment, measured in bytes.

end\_indexinteger (optional)

End of the attributed segment, exclusive.

PlaceCitation

A place citation annotation.

typeobject (required)

No description provided.

Always set to `"place_citation"`.

place\_idstring (optional)

The ID of the place, in \`places/{place\_id}\` format.

namestring (optional)

Title of the place.

urlstring (optional)

URI reference of the place.

review\_snippetsarray (ReviewSnippet) (optional)

Snippets of reviews that are used to generate answers about the
features of a given place in Google Maps.

Encapsulates a snippet of a user review that answers a question about
the features of a specific place in Google Maps.

#### Fields

titlestring (optional)

Title of the review.

urlstring (optional)

A link that corresponds to the user review on Google Maps.

review\_idstring (optional)

The ID of the review snippet.

start\_indexinteger (optional)

Start of segment of the response that is attributed to this source.

Index indicates the start of the segment, measured in bytes.

end\_indexinteger (optional)

End of the attributed segment, exclusive.

SpeechAnnotation

Speech annotation for text content.

typeobject (required)

No description provided.

Always set to `"speech_metadata"`.

speakerstring (optional)

The speaker to associate with this turn.

stylestring (optional)

Style instruction for the speech synthesis.

start\_indexinteger (optional)

Start of segment of the response that is attributed to this source.

Index indicates the start of the segment, measured in bytes.

end\_indexinteger (optional)

End of the attributed segment, exclusive.

UrlCitation

A URL citation annotation.

typeobject (required)

No description provided.

Always set to `"url_citation"`.

urlstring (optional)

The URL.

titlestring (optional)

The title of the URL.

start\_indexinteger (optional)

Start of segment of the response that is attributed to this source.

Index indicates the start of the segment, measured in bytes.

end\_indexinteger (optional)

End of the attributed segment, exclusive.

WordInfo

Word-level ASR annotation for transcription output.
Carries the word text, optional timing, and optional speaker attribution.

typeobject (required)

No description provided.

Always set to `"word_info"`.

textstring (optional)

The transcribed word.

start\_offsetstring (optional)

Start offset in time of the word relative to the start of the audio.
Present when timestamp\_granularities contains "word".

end\_offsetstring (optional)

End offset in time of the word relative to the start of the audio.
Present when timestamp\_granularities contains "word".

speakerstring (optional)

Optional. Speaker label for this word (e.g. "spk\_1", "spk\_2").
Present when diarization\_mode is set in TranscriptionConfig.

start\_indexinteger (optional)

Start of segment of the response that is attributed to this source.

Index indicates the start of the segment, measured in bytes.

end\_indexinteger (optional)

End of the attributed segment, exclusive.

VideoContent

A video content block.

typeobject (required)

No description provided.

Always set to `"video"`.

datastring (optional)

The video content.

uristring (optional)

The URI of the video.

processingMediaProcessing or enum (string) (optional)

How the model processes this video for understanding.

Can be a string (`"static"` \| `"agentic"`) or a `StaticMediaProcessing` object:

- `agentic`: Model-driven dynamic navigation.

- `static`: Fixed-rate frame extraction. All frames placed in context. Can be passed as the string `"static"`, or as an object with the following fields:





typestring (required)





No description provided.



Always set to `"static"`.









start\_offsetstring (optional)





Optional. Segment start time. Specified as a decimal number of seconds followed
by an 's' suffix, e.g., "10.5s". Must be non-negative.









end\_offsetstring (optional)





Optional. Segment end time. Specified as a decimal number of seconds followed
by an 's' suffix, e.g., "30s". Must be non-negative and greater than
\`start\_offset\` if \`start\_offset\` is set.









fpsnumber (optional)





Optional. Video frame-rate sampling density.


resolutionMediaResolution (optional)

The resolution of the media.

#### Possible values

- `low`
Low resolution.

- `medium`
Medium resolution.

- `high`
High resolution.

- `ultra_high`
Ultra high resolution.


namestring (optional)

A user-defined name for this content block. Can be referenced by the model
in the final response.

mime\_typeenum (string) (optional)

The mime type of the video.

Possible
values:

- `video/mp4`
MP4 video format

- `video/mpeg`
MPEG video format

- `video/mpg`
MPG video format

- `video/mov`
MOV video format

- `video/avi`
AVI video format

- `video/x-flv`
FLV video format

- `video/webm`
WebM video format

- `video/wmv`
WMV video format

- `video/3gpp`
3GPP video format


### Examples

[Audio](https://ai.google.dev/api/interactions-api#audio)[Document](https://ai.google.dev/api/interactions-api#document)[Image](https://ai.google.dev/api/interactions-api#image)[Text](https://ai.google.dev/api/interactions-api#text)[Video](https://ai.google.dev/api/interactions-api#video)More

```
{
  "type": "audio",
  "data": "BASE64_ENCODED_AUDIO",
  "mime_type": "audio/wav"
}
```

```
{
  "type": "document",
  "data": "BASE64_ENCODED_DOCUMENT",
  "mime_type": "application/pdf"
}
```

```
{
  "type": "image",
  "data": "BASE64_ENCODED_IMAGE",
  "mime_type": "image/png"
}
```

```
{
  "type": "text",
  "text": "Hello, how are you?"
}
```

```
{
  "type": "video",
  "uri": "https://www.youtube.com/watch?v=9hE5-98ZeCg"
}
```

### Tool

A tool that can be used by the model.

### Possible Types

CodeExecution

A tool that can be used by the model to execute code.

typeobject (required)

No description provided.

Always set to `"code_execution"`.

ComputerUse

A tool that can be used by the model to interact with the computer.

typeobject (required)

No description provided.

Always set to `"computer_use"`.

environmentenum (string) (optional)

The environment being operated.

Possible
values:

- `browser`
Operates in a web browser.

- `mobile`
Operates in a mobile environment.

- `desktop`
Operates in a desktop environment.


excluded\_predefined\_functionsarray (string) (optional)

The list of predefined functions that are excluded from the model call.

enable\_prompt\_injection\_detectionboolean (optional)

Whether enable the prompt injection detection check on computer-use
request.

disabled\_safety\_policiesarray (enum (string)) (optional)

Optional. Disabled safety policies for computer use.

Possible
values:

- `financial_transactions`
Safety policy for financial transactions.

- `sensitive_data_modification`
Safety policy for sensitive data modification.

- `communication_tool`
Safety policy for communication tools (e.g. Gmail, Chat, Meet).

- `account_creation`
Safety policy for account creation.

- `data_modification`
Safety policy for data modification.

- `user_consent_management`
Safety policy for user consent management.

- `legal_terms_and_agreements`
Safety policy for legal terms and agreements.


FileSearch

A tool that can be used by the model to search files.

typeobject (required)

No description provided.

Always set to `"file_search"`.

file\_search\_store\_namesarray (string) (optional)

The file search store names to search.

top\_kinteger (optional)

The number of semantic retrieval chunks to retrieve.

metadata\_filterstring (optional)

Metadata filter to apply to the semantic retrieval documents and chunks.

Function

A tool that can be used by the model.

typeobject (required)

No description provided.

Always set to `"function"`.

namestring (optional)

The name of the function.

descriptionstring (optional)

A description of the function.

parametersobject (optional)

The JSON Schema for the function's parameters.

Supports a subset of JSON Schema. \`minLength\`, \`maxLength\`,
\`minProperties\`, \`maxProperties\`, \`uniqueItems\`, \`contains\`,
\`minContains\`, and \`maxContains\` are ignored and not enforced.

GoogleMaps

A tool that can be used by the model to call Google Maps.

typeobject (required)

No description provided.

Always set to `"google_maps"`.

enable\_widgetboolean (optional)

Whether to return a widget context token in the tool call result of the
response.

latitudenumber (optional)

The latitude of the user's location.

longitudenumber (optional)

The longitude of the user's location.

GoogleSearch

A tool that can be used by the model to search Google.

typeobject (required)

No description provided.

Always set to `"google_search"`.

search\_typesarray (enum (string)) (optional)

The types of search grounding to enable.

Possible
values:

- `web_search`
Setting this field enables web search. Only text results are returned.

- `image_search`
Setting this field enables image search. Image bytes are returned.


McpServer

A MCPServer is a server that can be called by the model to perform actions.

typeobject (required)

No description provided.

Always set to `"mcp_server"`.

urlstring (optional)

The full URL for the MCPServer endpoint.
Example: "https://api.example.com/mcp"

namestring (optional)

The name of the MCPServer.

headersobject (optional)

Optional: Fields for authentication headers, timeouts, etc., if needed.

allowed\_toolsarray (AllowedTools) (optional)

The allowed tools.

The configuration for allowed tools.

#### Fields

modeenum (string) (optional)

The mode of the tool choice.

Possible
values:

- `auto`
Auto tool choice.

- `any`
Any tool choice.

- `none`
No tool choice.

- `validated`
Validated tool choice.


toolsarray (string) (optional)

The names of the allowed tools.

UrlContext

A tool that can be used by the model to fetch URL context.

typeobject (required)

No description provided.

Always set to `"url_context"`.

### Examples

[CodeExecution](https://ai.google.dev/api/interactions-api#codeexecution)[ComputerUse](https://ai.google.dev/api/interactions-api#computeruse)[FileSearch](https://ai.google.dev/api/interactions-api#filesearch)[Function](https://ai.google.dev/api/interactions-api#function)[GoogleMaps](https://ai.google.dev/api/interactions-api#googlemaps)[GoogleSearch](https://ai.google.dev/api/interactions-api#googlesearch)[McpServer](https://ai.google.dev/api/interactions-api#mcpserver)[UrlContext](https://ai.google.dev/api/interactions-api#urlcontext)More

Google AI for Developers

#### Example

RESTPythonJavaScriptJavaGo

```sh
curl -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-flash-latest",
    "tools": [{\
      "type": "code_execution"\
    }],
    "input": "Calculate the first 10 Fibonacci numbers"
  }'
```

```python
from google import genai

client = genai.Client()
response = client.interactions.create(
    model="gemini-flash-latest",
    tools=[{"type": "code_execution"}],
    input="Calculate the first 10 Fibonacci numbers",
)
print(response.output_text)
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});
const interaction = await ai.interactions.create({
  model: 'gemini-flash-latest',
  tools: [{type: 'code_execution'}],
  input: 'Calculate the first 10 Fibonacci numbers',
});
console.log(interaction.output_text);
```

```java
import com.google.genai.Client;
import com.google.genai.gaos.models.interactions.CodeExecution;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.gaos.models.operations.CreateInteractionResponse;
import com.google.genai.gaos.models.interactions.CreateModelInteraction;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;

Client client = new Client();
CreateModelInteraction params =
    CreateModelInteraction.builder()
        .model("gemini-flash-latest")
        .tools(List.of(new CodeExecution()))
        .input(InteractionsInput.of("Calculate the first 10 Fibonacci numbers"))
        .build();
CreateInteractionResponse response =
    client.interactions.create(CreateInteractionRequestBody.of(params));
Interaction interaction =
    response.interaction().orElseThrow(() -> new RuntimeException("No interaction returned"));
System.out.println(interaction.outputText().orElse(""));
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "google.golang.org/genai"
    gaos_interactions "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    tool := gaos_interactions.NewTool(gaos_interactions.CodeExecution{})

    body := operations.NewCreateInteractionRequestBody(gaos_interactions.CreateModelInteraction{
        Model: gaos_interactions.Model("gemini-flash-latest"),
        Input: genai.Ptr(gaos_interactions.NewInteractionsInput("Calculate the first 10 Fibonacci numbers")),
        Tools: []gaos_interactions.Tool{tool},
    })

    req := operations.CreateInteractionRequest{
        Body: body,
    }

    res, err := client.Interactions.Create(ctx, req)
    if err != nil {
        log.Fatal(err)
    }

    if res.Interaction != nil && res.Interaction.OutputText != nil {
        fmt.Println(*res.Interaction.OutputText)
    }
}
```

Google AI for Developers

#### Example

RESTPythonJavaScriptJavaGo

```sh
curl -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-2.5-computer-use-preview-10-2025",
    "tools": [{\
      "type": "computer_use"\
    }],
    "input": "Find a flight to Tokyo"
  }'
```

```python
from google import genai

client = genai.Client()
response = client.interactions.create(
    model="gemini-2.5-computer-use-preview-10-2025",
    tools=[{"type": "computer_use"}],
    input="Find a flight to Tokyo",
)
print(response.output_text)
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});
const interaction = await ai.interactions.create({
  model: 'gemini-2.5-computer-use-preview-10-2025',
  tools: [{type: 'computer_use'}],
  input: 'Find a flight to Tokyo',
});
console.log(interaction.output_text);
```

```java
import com.google.genai.Client;
import com.google.genai.gaos.models.interactions.ComputerUse;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.gaos.models.operations.CreateInteractionResponse;
import com.google.genai.gaos.models.interactions.CreateModelInteraction;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;

Client client = new Client();
CreateModelInteraction params =
    CreateModelInteraction.builder()
        .model("gemini-2.5-computer-use-preview-10-2025")
        .tools(List.of(new ComputerUse()))
        .input(InteractionsInput.of("Find a flight to Tokyo"))
        .build();
CreateInteractionResponse response =
    client.interactions.create(CreateInteractionRequestBody.of(params));
Interaction interaction =
    response.interaction().orElseThrow(() -> new RuntimeException("No interaction returned"));
System.out.println(interaction.outputText().orElse(""));
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "google.golang.org/genai"
    gaos_interactions "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    tool := gaos_interactions.NewTool(gaos_interactions.ComputerUse{})

    body := operations.NewCreateInteractionRequestBody(gaos_interactions.CreateModelInteraction{
        Model: gaos_interactions.Model("gemini-2.5-computer-use-preview-10-2025"),
        Input: genai.Ptr(gaos_interactions.NewInteractionsInput("Find a flight to Tokyo")),
        Tools: []gaos_interactions.Tool{tool},
    })

    req := operations.CreateInteractionRequest{
        Body: body,
    }

    res, err := client.Interactions.Create(ctx, req)
    if err != nil {
        log.Fatal(err)
    }

    if res.Interaction != nil && res.Interaction.OutputText != nil {
        fmt.Println(*res.Interaction.OutputText)
    }
}
```

Google AI for Developers

#### Example

RESTPythonJavaScriptJavaGo

```sh
curl -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-flash-latest",
    "tools": [{\
      "type": "file_search",\
      "file_search_store_names": ["fileSearchStores/m64d1sevsr4y-xfyawui3fxqg"]\
    }],
    "input": "Who is the author of the book?"
  }'
```

```python
from google import genai

client = genai.Client()

# Create a file search store so we have a valid one to use.
store = client.file_search_stores.create()

response = client.interactions.create(
    model="gemini-flash-latest",
    tools=[\
        {"type": "file_search", "file_search_store_names": [store.name]}\
    ],
    input="What documents are available?",
)
print(response.output_text)
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});

// Create a file search store so we have a valid one to use.
const store = await ai.fileSearchStores.create({});
if (!store.name) {
  throw new Error('Store creation failed: Name is undefined');
}

const interaction = await ai.interactions.create({
  model: 'gemini-flash-latest',
  tools: [\
    {\
      type: 'file_search',\
      file_search_store_names: [store.name],\
    },\
  ],
  input: 'What documents are available?',
});
console.log(interaction.output_text);
```

```java
import com.google.genai.Client;
import com.google.genai.types.CreateFileSearchStoreConfig;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.gaos.models.operations.CreateInteractionResponse;
import com.google.genai.gaos.models.interactions.CreateModelInteraction;
import com.google.genai.gaos.models.interactions.FileSearch;
import com.google.genai.types.FileSearchStore;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;

Client client = new Client();

// Create a file search store so we have a valid one to use.
FileSearchStore store =
    client.fileSearchStores.create(CreateFileSearchStoreConfig.builder().build());
String storeName = store.name().orElseThrow();

FileSearch tool = FileSearch.builder().fileSearchStoreNames(List.of(storeName)).build();
CreateModelInteraction params =
    CreateModelInteraction.builder()
        .model("gemini-flash-latest")
        .tools(List.of(tool))
        .input(InteractionsInput.of("What documents are available?"))
        .build();
CreateInteractionResponse response =
    client.interactions.create(CreateInteractionRequestBody.of(params));
Interaction interaction =
    response.interaction().orElseThrow(() -> new RuntimeException("No interaction returned"));
System.out.println(interaction.outputText().orElse(""));
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "google.golang.org/genai"
    gaos_interactions "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    tool := gaos_interactions.NewTool(gaos_interactions.FileSearch{
        FileSearchStoreNames: []string{store.Name},
    })

    body := operations.NewCreateInteractionRequestBody(gaos_interactions.CreateModelInteraction{
        Model: gaos_interactions.Model("gemini-flash-latest"),
        Input: genai.Ptr(gaos_interactions.NewInteractionsInput("What documents are available?")),
        Tools: []gaos_interactions.Tool{tool},
    })

    req := operations.CreateInteractionRequest{
        Body: body,
    }

    res, err := client.Interactions.Create(ctx, req)
    if err != nil {
        log.Fatal(err)
    }

    if res.Interaction != nil && res.Interaction.OutputText != nil {
        fmt.Println(*res.Interaction.OutputText)
    }
}
```

Google AI for Developers

#### Example

RESTPythonJavaScriptJavaGo

```sh
curl -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-flash-latest",
    "tools": [{\
      "type": "function",\
      "name": "get_weather",\
      "description": "Get the current weather in a given location",\
      "parameters": {\
        "type": "object",\
        "properties": {\
          "location": {\
            "type": "string",\
            "description": "The city and state, e.g. San Francisco, CA"\
          }\
        },\
        "required": ["location"]\
      }\
    }],
    "input": "What is the weather like in Boston, MA?"
  }'
```

```python
from google import genai

client = genai.Client()
response = client.interactions.create(
    model="gemini-flash-latest",
    tools=[{\
        "type": "function",\
        "name": "get_weather",\
        "description": "Get the current weather in a given location",\
        "parameters": {\
            "type": "object",\
            "properties": {\
                "location": {\
                    "type": "string",\
                    "description": (\
                        "The city and state, e.g. San Francisco, CA"\
                    ),\
                }\
            },\
            "required": ["location"],\
        },\
    }],
    input="What is the weather like in Boston?",
)
print(response.steps[-1])
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});
const interaction = await ai.interactions.create({
  model: 'gemini-flash-latest',
  tools: [\
    {\
      type: 'function',\
      name: 'get_weather',\
      description: 'Get the current weather in a given location',\
      parameters: {\
        type: 'object',\
        properties: {\
          location: {\
            type: 'string',\
            description: 'The city and state, e.g. San Francisco, CA',\
          },\
        },\
        required: ['location'],\
      },\
    },\
  ],
  input: 'What is the weather like in Boston?',
});
console.log(interaction.steps.at(-1));
```

```java
import com.google.genai.Client;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.gaos.models.operations.CreateInteractionResponse;
import com.google.genai.gaos.models.interactions.CreateModelInteraction;
import com.google.genai.gaos.models.interactions.Function;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;
import com.google.genai.gaos.models.interactions.Step;

Client client = new Client();
Map parameters =
    Map.of(
        "type", "object",
        "properties",
            Map.of(
                "location",
                Map.of(
                    "type", "string",
                    "description", "The city and state, e.g. San Francisco, CA")),
        "required", List.of("location"));
Function functionTool =
    Function.builder()
        .name("get_weather")
        .description("Get the current weather in a given location")
        .parameters(parameters)
        .build();
CreateModelInteraction params =
    CreateModelInteraction.builder()
        .model("gemini-flash-latest")
        .tools(List.of(functionTool))
        .input(InteractionsInput.of("What is the weather like in Boston?"))
        .build();
CreateInteractionResponse response =
    client.interactions.create(CreateInteractionRequestBody.of(params));
Interaction interaction =
    response.interaction().orElseThrow(() -> new RuntimeException("No interaction returned"));
List steps = interaction.steps().orElse(List.of());
if (!steps.isEmpty()) {
  System.out.println(steps.get(steps.size() - 1));
}
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "google.golang.org/genai"
    gaos_interactions "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    function := gaos_interactions.Function{
        Name:        genai.Ptr("get_weather"),
        Description: genai.Ptr("Get the current weather in a given location"),
        Parameters: map[string]any{
            "type": "object",
            "properties": map[string]any{
                "location": map[string]any{
                    "type":        "string",
                    "description": "The city and state, e.g. San Francisco, CA",
                },
            },
            "required": []string{"location"},
        },
    }

    tool := gaos_interactions.NewTool(function)

    body := operations.NewCreateInteractionRequestBody(gaos_interactions.CreateModelInteraction{
        Model: gaos_interactions.Model("gemini-flash-latest"),
        Input: genai.Ptr(gaos_interactions.NewInteractionsInput("What is the weather like in Boston, MA?")),
        Tools: []gaos_interactions.Tool{tool},
    })

    req := operations.CreateInteractionRequest{
        Body: body,
    }

    res, err := client.Interactions.Create(ctx, req)
    if err != nil {
        log.Fatal(err)
    }

    if res.Interaction != nil {
        for _, step := range res.Interaction.Steps {
            if step.FunctionCallStep != nil {
                fmt.Println("Function Call:", step.FunctionCallStep.Name)
                fmt.Println("Arguments:", step.FunctionCallStep.Arguments)
            }
        }
    }
}
```

Google AI for Developers

#### Example

RESTPythonJavaScriptJavaGo

```sh
curl -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-flash-latest",
    "tools": [{\
      "type": "google_maps",\
      "latitude": 37.7749,\
      "longitude": -122.4194\
    }],
    "input": "What is the best food near me?"
  }'
```

```python
from google import genai

client = genai.Client()
response = client.interactions.create(
    model="gemini-flash-latest",
    tools=[\
        {"type": "google_maps", "latitude": 37.7749, "longitude": -122.4194}\
    ],
    input="What is the best food near me?",
)
print(response.output_text)
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});
const interaction = await ai.interactions.create({
  model: 'gemini-flash-latest',
  tools: [\
    {\
      type: 'google_maps',\
      latitude: 37.7749,\
      longitude: -122.4194,\
    },\
  ],
  input: 'What is the best food near me?',
});
console.log(interaction.output_text);
```

```java
import com.google.genai.Client;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.gaos.models.operations.CreateInteractionResponse;
import com.google.genai.gaos.models.interactions.CreateModelInteraction;
import com.google.genai.gaos.models.interactions.GoogleMaps;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;

Client client = new Client();
GoogleMaps tool = GoogleMaps.builder().latitude(37.7749).longitude(-122.4194).build();
CreateModelInteraction params =
    CreateModelInteraction.builder()
        .model("gemini-flash-latest")
        .tools(List.of(tool))
        .input(InteractionsInput.of("What is the best food near me?"))
        .build();
CreateInteractionResponse response =
    client.interactions.create(CreateInteractionRequestBody.of(params));
Interaction interaction =
    response.interaction().orElseThrow(() -> new RuntimeException("No interaction returned"));
System.out.println(interaction.outputText().orElse(""));
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "google.golang.org/genai"
    gaos_interactions "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    tool := gaos_interactions.NewTool(gaos_interactions.GoogleMaps{
        Latitude:  genai.Ptr(37.7749),
        Longitude: genai.Ptr(-122.4194),
    })

    body := operations.NewCreateInteractionRequestBody(gaos_interactions.CreateModelInteraction{
        Model: gaos_interactions.Model("gemini-flash-latest"),
        Input: genai.Ptr(gaos_interactions.NewInteractionsInput("What is the best food near me?")),
        Tools: []gaos_interactions.Tool{tool},
    })

    req := operations.CreateInteractionRequest{
        Body: body,
    }

    res, err := client.Interactions.Create(ctx, req)
    if err != nil {
        log.Fatal(err)
    }

    if res.Interaction != nil && res.Interaction.OutputText != nil {
        fmt.Println(*res.Interaction.OutputText)
    }
}
```

Google AI for Developers

#### Example

RESTPythonJavaScriptJavaGo

```sh
curl -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-flash-latest",
    "tools": [{\
      "type": "google_search"\
    }],
    "input": "Who is the current president of France?"
  }'
```

```python
from google import genai

client = genai.Client()
response = client.interactions.create(
    model="gemini-flash-latest",
    tools=[{"type": "google_search"}],
    input="Who is the current president of France?",
)
print(response.output_text)
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});
const interaction = await ai.interactions.create({
  model: 'gemini-flash-latest',
  tools: [{type: 'google_search'}],
  input: 'Who is the current president of France?',
});
console.log(interaction.output_text);
```

```java
import com.google.genai.Client;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.gaos.models.operations.CreateInteractionResponse;
import com.google.genai.gaos.models.interactions.CreateModelInteraction;
import com.google.genai.gaos.models.interactions.GoogleSearch;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;

Client client = new Client();
CreateModelInteraction params =
    CreateModelInteraction.builder()
        .model("gemini-flash-latest")
        .tools(List.of(new GoogleSearch()))
        .input(InteractionsInput.of("Who is the current president of France?"))
        .build();
CreateInteractionResponse response =
    client.interactions.create(CreateInteractionRequestBody.of(params));
Interaction interaction =
    response.interaction().orElseThrow(() -> new RuntimeException("No interaction returned"));
System.out.println(interaction.outputText().orElse(""));
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "google.golang.org/genai"
    gaos_interactions "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    tool := gaos_interactions.NewTool(gaos_interactions.GoogleSearch{})

    body := operations.NewCreateInteractionRequestBody(gaos_interactions.CreateModelInteraction{
        Model: gaos_interactions.Model("gemini-flash-latest"),
        Input: genai.Ptr(gaos_interactions.NewInteractionsInput("Who is the current president of France?")),
        Tools: []gaos_interactions.Tool{tool},
    })

    req := operations.CreateInteractionRequest{
        Body: body,
    }

    res, err := client.Interactions.Create(ctx, req)
    if err != nil {
        log.Fatal(err)
    }

    if res.Interaction != nil && res.Interaction.OutputText != nil {
        fmt.Println(*res.Interaction.OutputText)
    }
}
```

Google AI for Developers

#### Example

RESTPythonJavaScriptJavaGo

```sh
curl -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-flash-latest",
    "tools": [{\
      "type": "mcp_server",\
      "name": "weather_service",\
      "url": "https://gemini-api-demos.uc.r.appspot.com/mcp"\
    }],
    "input": "Today is 12-05-2025, what is the temperature today in London?"
  }'
```

```python
import os

from google import genai

client = genai.Client()
response = client.interactions.create(
    model="gemini-flash-latest",
    tools=[{\
        "type": "mcp_server",\
        "name": "weather_service",\
        "url": "https://gemini-api-demos.uc.r.appspot.com/mcp",\
    }],
    input="Today is 12-05-2025, what is the temperature today in London?",
)
print(response.output_text)
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});
const interaction = await ai.interactions.create({
  model: 'gemini-flash-latest',
  tools: [\
    {\
      type: 'mcp_server',\
      name: 'weather_service',\
      url: 'https://gemini-api-demos.uc.r.appspot.com/mcp',\
    },\
  ],
  input: 'Today is 12-05-2025, what is the temperature today in London?',
});
console.log(interaction.output_text);
```

```java
import com.google.genai.Client;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.gaos.models.operations.CreateInteractionResponse;
import com.google.genai.gaos.models.interactions.CreateModelInteraction;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;
import com.google.genai.gaos.models.interactions.MCPServer;

Client client = new Client();
MCPServer mcpTool =
    MCPServer.builder()
        .name("weather_service")
        .url("https://gemini-api-demos.uc.r.appspot.com/mcp")
        .build();
CreateModelInteraction params =
    CreateModelInteraction.builder()
        .model("gemini-flash-latest")
        .tools(List.of(mcpTool))
        .input(
            InteractionsInput.of(
                "Today is 12-05-2025, what is the temperature today in London?"))
        .build();
CreateInteractionResponse response =
    client.interactions.create(CreateInteractionRequestBody.of(params));
Interaction interaction =
    response.interaction().orElseThrow(() -> new RuntimeException("No interaction returned"));
System.out.println(interaction.outputText().orElse(""));
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "os"
    "google.golang.org/genai"
    gaos_interactions "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    mcpServer := gaos_interactions.MCPServer{
        Name: genai.Ptr("weather_service"),
        URL:  genai.Ptr("https://gemini-api-demos.uc.r.appspot.com/mcp"),
    }
    tool := gaos_interactions.NewTool(mcpServer)

    body := operations.NewCreateInteractionRequestBody(gaos_interactions.CreateModelInteraction{
        Model: gaos_interactions.Model("gemini-flash-latest"),
        Input: genai.Ptr(gaos_interactions.NewInteractionsInput("Today is 12-05-2025, what is the temperature today in London?")),
        Tools: []gaos_interactions.Tool{tool},
    })

    req := operations.CreateInteractionRequest{
        Body: body,
    }

    res, err := client.Interactions.Create(ctx, req)
    if err != nil {
        log.Fatal(err)
    }

    if res.Interaction != nil && res.Interaction.OutputText != nil {
        fmt.Println(*res.Interaction.OutputText)
    }
}
```

Google AI for Developers

#### Example

RESTPythonJavaScriptJavaGo

```sh
curl -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-flash-latest",
    "tools": [{\
      "type": "url_context"\
    }],
    "input": "Summarize https://www.example.com"
  }'
```

```python
from google import genai

client = genai.Client()
response = client.interactions.create(
    model="gemini-flash-latest",
    tools=[{"type": "url_context"}],
    input="Summarize https://www.example.com",
)
print(response.output_text)
```

```javascript
import {GoogleGenAI} from '@google/genai';

const ai = new GoogleGenAI({});
const interaction = await ai.interactions.create({
  model: 'gemini-flash-latest',
  tools: [{type: 'url_context'}],
  input: 'Summarize https://www.example.com',
});
console.log(interaction.output_text);
```

```java
import com.google.genai.Client;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.gaos.models.operations.CreateInteractionResponse;
import com.google.genai.gaos.models.interactions.CreateModelInteraction;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;
import com.google.genai.gaos.models.interactions.URLContext;

Client client = new Client();
CreateModelInteraction params =
    CreateModelInteraction.builder()
        .model("gemini-flash-latest")
        .tools(List.of(new URLContext()))
        .input(InteractionsInput.of("Summarize https://www.example.com"))
        .build();
CreateInteractionResponse response =
    client.interactions.create(CreateInteractionRequestBody.of(params));
Interaction interaction =
    response.interaction().orElseThrow(() -> new RuntimeException("No interaction returned"));
System.out.println(interaction.outputText().orElse(""));
```

```go
package main

import (
    "context"
    "fmt"
    "log"
    "google.golang.org/genai"
    gaos_interactions "google.golang.org/genai/interactions/models/interactions"
    "google.golang.org/genai/interactions/models/operations"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    tool := gaos_interactions.NewTool(gaos_interactions.URLContext{})

    body := operations.NewCreateInteractionRequestBody(gaos_interactions.CreateModelInteraction{
        Model: gaos_interactions.Model("gemini-flash-latest"),
        Input: genai.Ptr(gaos_interactions.NewInteractionsInput("Summarize https://www.example.com")),
        Tools: []gaos_interactions.Tool{tool},
    })

    req := operations.CreateInteractionRequest{
        Body: body,
    }

    res, err := client.Interactions.Create(ctx, req)
    if err != nil {
        log.Fatal(err)
    }

    if res.Interaction != nil && res.Interaction.OutputText != nil {
        fmt.Println(*res.Interaction.OutputText)
    }
}
```

### InteractionSseEvent

### Possible Types

ErrorEvent

event\_typeobject (required)

No description provided.

Always set to `"error"`.

errorError (optional)

No description provided.

Error message from an interaction.

#### Fields

codestring (optional)

A URI that identifies the error type.

messagestring (optional)

A human-readable error message.

event\_idstring (optional)

The event\_id token to be used to resume the interaction stream, from
this event.

InteractionCompletedEvent

Signals that the Interaction completed. Sent when the Interaction receives
Complete/Cancel or naturally terminates. No more input can be sent to the
Interaction after this.

interactionInteractionSseEventInteraction (required)

Required. Partial completed interaction resource emitted at the end of the stream.

Partial interaction resource emitted by interaction lifecycle SSE events.
Streaming lifecycle payloads may omit fields that are only available on
full non-streaming Interaction responses.

#### Fields

idstring (required)

Required. Output only. A unique identifier for the interaction completion.

statusenum (string) (required)

Required. Output only. The status of the interaction.

Possible
values:

- `in_progress`
The interaction is in progress.

- `requires_action`
The interaction requires action/input from the user.

- `completed`
The interaction is completed.

- `failed`
The interaction failed.

- `cancelled`
The interaction was cancelled.

- `incomplete`
The interaction is completed, but contains incomplete results (e.g. hitting max\_tokens).


modelstring (optional)

The model that will complete your prompt.

createdstring (optional)

Output only. The time at which the response was created in ISO 8601 format.

updatedstring (optional)

Output only. The time at which the response was last updated in ISO 8601 format.

usageUsage (optional)

Output only. Statistics on the interaction request's token usage.

Statistics on the interaction request's token usage.

#### Fields

total\_input\_tokensinteger (optional)

Number of tokens in the prompt (context).

input\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of input token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_cached\_tokensinteger (optional)

Number of tokens in the cached part of the prompt (the cached content).

cached\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of cached token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_output\_tokensinteger (optional)

Total number of tokens across all the generated responses.

output\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of output token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_tool\_use\_tokensinteger (optional)

Number of tokens present in tool-use prompt(s).

tool\_use\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of tool-use token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_thought\_tokensinteger (optional)

Number of tokens of thoughts for thinking models.

total\_tokensinteger (optional)

Total token count for the interaction request (prompt + responses + other
internal tokens).

grounding\_tool\_countarray (GroundingToolCount) (optional)

Grounding tool count.

The number of grounding tool counts.

#### Fields

typeenum (string) (optional)

The grounding tool type associated with the count.

Possible
values:

- `google_search`
Grounding with Google Web Search and Image Search, & Web Grounding
for Enterprise.

- `google_maps`
Grounding with Google Maps.


countinteger (optional)

The number of grounding tool counts.

service\_tierServiceTier (optional)

The service tier for the interaction.

#### Possible values

- `flex`
Flex service tier.

- `standard`
Standard service tier.

- `priority`
Priority service tier.


stepsarray ( [Step](https://ai.google.dev/api/interactions-api#Resource:Step)) (optional)

Output only. The steps that make up the interaction, if included in this event.

agentstring (optional)

The agent to interact with.

continuation\_tokenstring (optional)

Opaque token to resume a long decode.
Output: set when status is INCOMPLETE and decoding can be resumed.
Input: pass the latest token back unchanged in CreateInteraction to
continue decoding.

objectstring (optional)

Output only. The resource type.

event\_typeobject (required)

No description provided.

Always set to `"interaction.completed"`.

event\_idstring (optional)

The event\_id token to be used to resume the interaction stream, from
this event.

InteractionCreatedEvent

Server response confirming that a new interaction was created.

interactionInteractionSseEventInteraction (required)

Required. Partial interaction resource emitted when the stream is created.

Partial interaction resource emitted by interaction lifecycle SSE events.
Streaming lifecycle payloads may omit fields that are only available on
full non-streaming Interaction responses.

#### Fields

idstring (required)

Required. Output only. A unique identifier for the interaction completion.

statusenum (string) (required)

Required. Output only. The status of the interaction.

Possible
values:

- `in_progress`
The interaction is in progress.

- `requires_action`
The interaction requires action/input from the user.

- `completed`
The interaction is completed.

- `failed`
The interaction failed.

- `cancelled`
The interaction was cancelled.

- `incomplete`
The interaction is completed, but contains incomplete results (e.g. hitting max\_tokens).


modelstring (optional)

The model that will complete your prompt.

createdstring (optional)

Output only. The time at which the response was created in ISO 8601 format.

updatedstring (optional)

Output only. The time at which the response was last updated in ISO 8601 format.

usageUsage (optional)

Output only. Statistics on the interaction request's token usage.

Statistics on the interaction request's token usage.

#### Fields

total\_input\_tokensinteger (optional)

Number of tokens in the prompt (context).

input\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of input token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_cached\_tokensinteger (optional)

Number of tokens in the cached part of the prompt (the cached content).

cached\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of cached token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_output\_tokensinteger (optional)

Total number of tokens across all the generated responses.

output\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of output token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_tool\_use\_tokensinteger (optional)

Number of tokens present in tool-use prompt(s).

tool\_use\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of tool-use token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_thought\_tokensinteger (optional)

Number of tokens of thoughts for thinking models.

total\_tokensinteger (optional)

Total token count for the interaction request (prompt + responses + other
internal tokens).

grounding\_tool\_countarray (GroundingToolCount) (optional)

Grounding tool count.

The number of grounding tool counts.

#### Fields

typeenum (string) (optional)

The grounding tool type associated with the count.

Possible
values:

- `google_search`
Grounding with Google Web Search and Image Search, & Web Grounding
for Enterprise.

- `google_maps`
Grounding with Google Maps.


countinteger (optional)

The number of grounding tool counts.

service\_tierServiceTier (optional)

The service tier for the interaction.

#### Possible values

- `flex`
Flex service tier.

- `standard`
Standard service tier.

- `priority`
Priority service tier.


stepsarray ( [Step](https://ai.google.dev/api/interactions-api#Resource:Step)) (optional)

Output only. The steps that make up the interaction, if included in this event.

agentstring (optional)

The agent to interact with.

continuation\_tokenstring (optional)

Opaque token to resume a long decode.
Output: set when status is INCOMPLETE and decoding can be resumed.
Input: pass the latest token back unchanged in CreateInteraction to
continue decoding.

objectstring (optional)

Output only. The resource type.

event\_typeobject (required)

No description provided.

Always set to `"interaction.created"`.

event\_idstring (optional)

The event\_id token to be used to resume the interaction stream, from
this event.

InteractionStatusUpdate

interaction\_idstring (required)

No description provided.

statusenum (string) (required)

No description provided.

Possible
values:

- `in_progress`
The interaction is in progress.

- `requires_action`
The interaction requires action/input from the user.

- `completed`
The interaction is completed.

- `failed`
The interaction failed.

- `cancelled`
The interaction was cancelled.

- `incomplete`
The interaction is completed, but contains incomplete results (e.g.
hitting max\_tokens).


event\_typeobject (required)

No description provided.

Always set to `"interaction.status_update"`.

continuation\_tokenstring (optional)

An optional opaque continuation token used to resume decoding from the
latest checkpoint after a disconnected stream.

usageUsage (optional)

Model usage statistics up to this checkpoint.

Statistics on the interaction request's token usage.

#### Fields

total\_input\_tokensinteger (optional)

Number of tokens in the prompt (context).

input\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of input token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_cached\_tokensinteger (optional)

Number of tokens in the cached part of the prompt (the cached content).

cached\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of cached token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_output\_tokensinteger (optional)

Total number of tokens across all the generated responses.

output\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of output token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_tool\_use\_tokensinteger (optional)

Number of tokens present in tool-use prompt(s).

tool\_use\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of tool-use token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_thought\_tokensinteger (optional)

Number of tokens of thoughts for thinking models.

total\_tokensinteger (optional)

Total token count for the interaction request (prompt + responses + other
internal tokens).

grounding\_tool\_countarray (GroundingToolCount) (optional)

Grounding tool count.

The number of grounding tool counts.

#### Fields

typeenum (string) (optional)

The grounding tool type associated with the count.

Possible
values:

- `google_search`
Grounding with Google Web Search and Image Search, & Web Grounding
for Enterprise.

- `google_maps`
Grounding with Google Maps.


countinteger (optional)

The number of grounding tool counts.

event\_idstring (optional)

The event\_id token to be used to resume the interaction stream, from
this event.

StepDelta

indexinteger (required)

No description provided.

deltaStepDeltaData (required)

No description provided.

#### Possible Types

ArgumentsDelta

typeobject (required)

No description provided.

Always set to `"arguments_delta"`.

argumentsstring (optional)

No description provided.

AudioDelta

typeobject (required)

No description provided.

Always set to `"audio"`.

datastring (optional)

No description provided.

uristring (optional)

No description provided.

mime\_typeenum (string) (optional)

No description provided.

Possible
values:

- `audio/wav`
WAV audio format

- `audio/mp3`
MP3 audio format

- `audio/aiff`
AIFF audio format

- `audio/aac`
AAC audio format

- `audio/ogg`
OGG audio format

- `audio/flac`
FLAC audio format

- `audio/mpeg`
MPEG audio format

- `audio/m4a`
M4A audio format

- `audio/l16`
L16 audio format

- `audio/opus`
OPUS audio format

- `audio/alaw`
ALAW audio format

- `audio/mulaw`
MULAW audio format

- `audio/webm`
WEBM audio format


sample\_rateinteger (optional)

The sample rate of the audio.

channelsinteger (optional)

The number of audio channels.

CodeExecutionCallDelta

argumentsCodeExecutionCallArguments (required)

No description provided.

The arguments to pass to the code execution.

#### Fields

languageenum (string) (optional)

Programming language of the \`code\`.

Possible
values:

- `python`
Python >= 3.10, with numpy and simpy available.

- `bash`
Bash. Only available for Gemini 3.0 model or above.


codestring (optional)

The code to be executed.

typeobject (required)

No description provided.

Always set to `"code_execution_call"`.

signaturestring (optional)

A signature hash for backend validation.

CodeExecutionResultDelta

resultstring (required)

No description provided.

typeobject (required)

No description provided.

Always set to `"code_execution_result"`.

is\_errorboolean (optional)

No description provided.

signaturestring (optional)

A signature hash for backend validation.

DocumentDelta

typeobject (required)

No description provided.

Always set to `"document"`.

datastring (optional)

No description provided.

uristring (optional)

No description provided.

mime\_typeenum (string) (optional)

No description provided.

Possible
values:

- `application/pdf`
PDF document format

- `text/csv`
CSV document format


FileSearchCallDelta

typeobject (required)

No description provided.

Always set to `"file_search_call"`.

signaturestring (optional)

A signature hash for backend validation.

FileSearchResultDelta

resultarray (FileSearchResult) (required)

No description provided.

The result of the File Search.

typeobject (required)

No description provided.

Always set to `"file_search_result"`.

signaturestring (optional)

A signature hash for backend validation.

FunctionResultDelta

resultarray ( [ImageContent](https://ai.google.dev/api/interactions-api#Resource:ImageContent) or [TextContent](https://ai.google.dev/api/interactions-api#Resource:TextContent)) or object or string (required)

No description provided.

typeobject (required)

No description provided.

Always set to `"function_result"`.

namestring (optional)

No description provided.

is\_errorboolean (optional)

No description provided.

GoogleMapsCallDelta

typeobject (required)

No description provided.

Always set to `"google_maps_call"`.

argumentsGoogleMapsCallArguments (optional)

The arguments to pass to the Google Maps tool.

The arguments to pass to the Google Maps tool.

#### Fields

queriesarray (string) (optional)

The queries to be executed.

signaturestring (optional)

A signature hash for backend validation.

GoogleMapsResultDelta

typeobject (required)

No description provided.

Always set to `"google_maps_result"`.

resultarray (GoogleMapsResult) (optional)

The results of the Google Maps.

The result of the Google Maps.

#### Fields

placesarray (Places) (optional)

The places that were found.

#### Fields

place\_idstring (optional)

The ID of the place, in \`places/{place\_id}\` format.

namestring (optional)

Title of the place.

urlstring (optional)

URI reference of the place.

review\_snippetsarray (ReviewSnippet) (optional)

Snippets of reviews that are used to generate answers about the
features of a given place in Google Maps.

Encapsulates a snippet of a user review that answers a question about
the features of a specific place in Google Maps.

#### Fields

titlestring (optional)

Title of the review.

urlstring (optional)

A link that corresponds to the user review on Google Maps.

review\_idstring (optional)

The ID of the review snippet.

widget\_context\_tokenstring (optional)

Resource name of the Google Maps widget context token.

signaturestring (optional)

A signature hash for backend validation.

GoogleSearchCallDelta

argumentsGoogleSearchCallArguments (required)

No description provided.

The arguments to pass to Google Search.

#### Fields

queriesarray (string) (optional)

Web search queries for the following-up web search.

typeobject (required)

No description provided.

Always set to `"google_search_call"`.

signaturestring (optional)

A signature hash for backend validation.

GoogleSearchResultDelta

resultarray (GoogleSearchResult) (required)

No description provided.

The result of the Google Search.

#### Fields

search\_suggestionsstring (optional)

Web content snippet that can be embedded in a web page or an app webview.

typeobject (required)

No description provided.

Always set to `"google_search_result"`.

is\_errorboolean (optional)

No description provided.

signaturestring (optional)

A signature hash for backend validation.

ImageDelta

typeobject (required)

No description provided.

Always set to `"image"`.

datastring (optional)

No description provided.

uristring (optional)

No description provided.

mime\_typeenum (string) (optional)

No description provided.

Possible
values:

- `image/png`
PNG image format

- `image/jpeg`
JPEG image format

- `image/webp`
WebP image format

- `image/heic`
HEIC image format

- `image/heif`
HEIF image format

- `image/gif`
GIF image format

- `image/bmp`
BMP image format

- `image/tiff`
TIFF image format


resolutionMediaResolution (optional)

The resolution of the media.

#### Possible values

- `low`
Low resolution.

- `medium`
Medium resolution.

- `high`
High resolution.

- `ultra_high`
Ultra high resolution.


McpServerToolCallDelta

namestring (required)

No description provided.

server\_namestring (required)

No description provided.

argumentsobject (required)

No description provided.

typeobject (required)

No description provided.

Always set to `"mcp_server_tool_call"`.

McpServerToolResultDelta

resultarray ( [ImageContent](https://ai.google.dev/api/interactions-api#Resource:ImageContent) or [TextContent](https://ai.google.dev/api/interactions-api#Resource:TextContent)) or object or string (required)

No description provided.

typeobject (required)

No description provided.

Always set to `"mcp_server_tool_result"`.

namestring (optional)

No description provided.

server\_namestring (optional)

No description provided.

ProcessingCallDelta

Streaming delta for a server-initiated media processing step.

typeobject (required)

No description provided.

Always set to `"processing_call"`.

signaturestring (optional)

A signature hash for backend validation.

ProcessingResultDelta

Streaming delta for the result of a server-initiated media processing step.

typeobject (required)

No description provided.

Always set to `"processing_result"`.

signaturestring (optional)

A signature hash for backend validation.

TextAnnotationDelta

typeobject (required)

No description provided.

Always set to `"text_annotation_delta"`.

annotationsarray (Annotation) (optional)

Citation information for model-generated content.

Citation information for model-generated content.

#### Possible Types

FileCitation

A file citation annotation.

typeobject (required)

No description provided.

Always set to `"file_citation"`.

document\_uristring (optional)

The URI of the file.

file\_namestring (optional)

The name of the file.

sourcestring (optional)

Source attributed for a portion of the text.

custom\_metadataobject (optional)

User provided metadata about the retrieved context.

page\_numberinteger (optional)

Page number of the cited document, if applicable.

media\_idstring (optional)

Media ID in-case of image citations, if applicable.

start\_indexinteger (optional)

Start of segment of the response that is attributed to this source.

Index indicates the start of the segment, measured in bytes.

end\_indexinteger (optional)

End of the attributed segment, exclusive.

PlaceCitation

A place citation annotation.

typeobject (required)

No description provided.

Always set to `"place_citation"`.

place\_idstring (optional)

The ID of the place, in \`places/{place\_id}\` format.

namestring (optional)

Title of the place.

urlstring (optional)

URI reference of the place.

review\_snippetsarray (ReviewSnippet) (optional)

Snippets of reviews that are used to generate answers about the
features of a given place in Google Maps.

Encapsulates a snippet of a user review that answers a question about
the features of a specific place in Google Maps.

#### Fields

titlestring (optional)

Title of the review.

urlstring (optional)

A link that corresponds to the user review on Google Maps.

review\_idstring (optional)

The ID of the review snippet.

start\_indexinteger (optional)

Start of segment of the response that is attributed to this source.

Index indicates the start of the segment, measured in bytes.

end\_indexinteger (optional)

End of the attributed segment, exclusive.

SpeechAnnotation

Speech annotation for text content.

typeobject (required)

No description provided.

Always set to `"speech_metadata"`.

speakerstring (optional)

The speaker to associate with this turn.

stylestring (optional)

Style instruction for the speech synthesis.

start\_indexinteger (optional)

Start of segment of the response that is attributed to this source.

Index indicates the start of the segment, measured in bytes.

end\_indexinteger (optional)

End of the attributed segment, exclusive.

UrlCitation

A URL citation annotation.

typeobject (required)

No description provided.

Always set to `"url_citation"`.

urlstring (optional)

The URL.

titlestring (optional)

The title of the URL.

start\_indexinteger (optional)

Start of segment of the response that is attributed to this source.

Index indicates the start of the segment, measured in bytes.

end\_indexinteger (optional)

End of the attributed segment, exclusive.

WordInfo

Word-level ASR annotation for transcription output.
Carries the word text, optional timing, and optional speaker attribution.

typeobject (required)

No description provided.

Always set to `"word_info"`.

textstring (optional)

The transcribed word.

start\_offsetstring (optional)

Start offset in time of the word relative to the start of the audio.
Present when timestamp\_granularities contains "word".

end\_offsetstring (optional)

End offset in time of the word relative to the start of the audio.
Present when timestamp\_granularities contains "word".

speakerstring (optional)

Optional. Speaker label for this word (e.g. "spk\_1", "spk\_2").
Present when diarization\_mode is set in TranscriptionConfig.

start\_indexinteger (optional)

Start of segment of the response that is attributed to this source.

Index indicates the start of the segment, measured in bytes.

end\_indexinteger (optional)

End of the attributed segment, exclusive.

TextDelta

textstring (required)

No description provided.

typeobject (required)

No description provided.

Always set to `"text"`.

ThoughtSignatureDelta

typeobject (required)

No description provided.

Always set to `"thought_signature"`.

signaturestring (optional)

Signature to match the backend source to be part of the generation.

ThoughtSummaryDelta

typeobject (required)

No description provided.

Always set to `"thought_summary"`.

content[Content](https://ai.google.dev/api/interactions-api#Resource:Content) (optional)

A new summary item to be added to the thought.

UrlContextCallDelta

argumentsUrlContextCallArguments (required)

No description provided.

The arguments to pass to the URL context.

#### Fields

urlsarray (string) (optional)

The URLs to fetch.

typeobject (required)

No description provided.

Always set to `"url_context_call"`.

signaturestring (optional)

A signature hash for backend validation.

UrlContextResultDelta

resultarray (UrlContextResult) (required)

No description provided.

The result of the URL context.

#### Fields

urlstring (optional)

The URL that was fetched.

statusenum (string) (optional)

The status of the URL retrieval.

Possible
values:

- `success`
Url retrieval is successful.

- `error`
Url retrieval is failed due to error.

- `paywall`
Url retrieval is failed because the content is behind paywall.

- `unsafe`
Url retrieval is failed because the content is unsafe.


typeobject (required)

No description provided.

Always set to `"url_context_result"`.

is\_errorboolean (optional)

No description provided.

signaturestring (optional)

A signature hash for backend validation.

VideoDelta

typeobject (required)

No description provided.

Always set to `"video"`.

datastring (optional)

No description provided.

uristring (optional)

No description provided.

mime\_typeenum (string) (optional)

No description provided.

Possible
values:

- `video/mp4`
MP4 video format

- `video/mpeg`
MPEG video format

- `video/mpg`
MPG video format

- `video/mov`
MOV video format

- `video/avi`
AVI video format

- `video/x-flv`
FLV video format

- `video/webm`
WebM video format

- `video/wmv`
WMV video format

- `video/3gpp`
3GPP video format

- `video/jpeg2000`
JPEG 2000 video format


resolutionMediaResolution (optional)

The resolution of the media.

#### Possible values

- `low`
Low resolution.

- `medium`
Medium resolution.

- `high`
High resolution.

- `ultra_high`
Ultra high resolution.


event\_typeobject (required)

No description provided.

Always set to `"step.delta"`.

event\_idstring (optional)

The event\_id token to be used to resume the interaction stream, from
this event.

metadataStepDeltaMetadata (optional)

No description provided.

Optional metadata accompanying ANY streamed event.

#### Fields

total\_usageUsage (optional)

Statistics on the interaction request's token usage.

Statistics on the interaction request's token usage.

#### Fields

total\_input\_tokensinteger (optional)

Number of tokens in the prompt (context).

input\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of input token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_cached\_tokensinteger (optional)

Number of tokens in the cached part of the prompt (the cached content).

cached\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of cached token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_output\_tokensinteger (optional)

Total number of tokens across all the generated responses.

output\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of output token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_tool\_use\_tokensinteger (optional)

Number of tokens present in tool-use prompt(s).

tool\_use\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of tool-use token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_thought\_tokensinteger (optional)

Number of tokens of thoughts for thinking models.

total\_tokensinteger (optional)

Total token count for the interaction request (prompt + responses + other
internal tokens).

grounding\_tool\_countarray (GroundingToolCount) (optional)

Grounding tool count.

The number of grounding tool counts.

#### Fields

typeenum (string) (optional)

The grounding tool type associated with the count.

Possible
values:

- `google_search`
Grounding with Google Web Search and Image Search, & Web Grounding
for Enterprise.

- `google_maps`
Grounding with Google Maps.


countinteger (optional)

The number of grounding tool counts.

StepStart

indexinteger (required)

No description provided.

step[Step](https://ai.google.dev/api/interactions-api#Resource:Step) (required)

No description provided.

event\_typeobject (required)

No description provided.

Always set to `"step.start"`.

event\_idstring (optional)

The event\_id token to be used to resume the interaction stream, from
this event.

StepStop

indexinteger (required)

No description provided.

event\_typeobject (required)

No description provided.

Always set to `"step.stop"`.

usageUsage (optional)

Cumulative model usage stats from the start of the session.

Statistics on the interaction request's token usage.

#### Fields

total\_input\_tokensinteger (optional)

Number of tokens in the prompt (context).

input\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of input token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_cached\_tokensinteger (optional)

Number of tokens in the cached part of the prompt (the cached content).

cached\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of cached token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_output\_tokensinteger (optional)

Total number of tokens across all the generated responses.

output\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of output token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_tool\_use\_tokensinteger (optional)

Number of tokens present in tool-use prompt(s).

tool\_use\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of tool-use token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_thought\_tokensinteger (optional)

Number of tokens of thoughts for thinking models.

total\_tokensinteger (optional)

Total token count for the interaction request (prompt + responses + other
internal tokens).

grounding\_tool\_countarray (GroundingToolCount) (optional)

Grounding tool count.

The number of grounding tool counts.

#### Fields

typeenum (string) (optional)

The grounding tool type associated with the count.

Possible
values:

- `google_search`
Grounding with Google Web Search and Image Search, & Web Grounding
for Enterprise.

- `google_maps`
Grounding with Google Maps.


countinteger (optional)

The number of grounding tool counts.

step\_usageUsage (optional)

Model usage stats for this specific step.

Statistics on the interaction request's token usage.

#### Fields

total\_input\_tokensinteger (optional)

Number of tokens in the prompt (context).

input\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of input token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_cached\_tokensinteger (optional)

Number of tokens in the cached part of the prompt (the cached content).

cached\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of cached token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_output\_tokensinteger (optional)

Total number of tokens across all the generated responses.

output\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of output token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_tool\_use\_tokensinteger (optional)

Number of tokens present in tool-use prompt(s).

tool\_use\_tokens\_by\_modalityarray (ModalityTokens) (optional)

A breakdown of tool-use token usage by modality.

The token count for a single response modality.

#### Fields

modalityResponseModality (optional)

The modality associated with the token count.

#### Possible values

- `text`
Indicates the model should return text.

- `image`
Indicates the model should return images.

- `audio`
Indicates the model should return audio.

- `video`
Indicates the model should return video.

- `document`
Indicates the model should return documents.


tokensinteger (optional)

Number of tokens for the modality.

total\_thought\_tokensinteger (optional)

Number of tokens of thoughts for thinking models.

total\_tokensinteger (optional)

Total token count for the interaction request (prompt + responses + other
internal tokens).

grounding\_tool\_countarray (GroundingToolCount) (optional)

Grounding tool count.

The number of grounding tool counts.

#### Fields

typeenum (string) (optional)

The grounding tool type associated with the count.

Possible
values:

- `google_search`
Grounding with Google Web Search and Image Search, & Web Grounding
for Enterprise.

- `google_maps`
Grounding with Google Maps.


countinteger (optional)

The number of grounding tool counts.

event\_idstring (optional)

The event\_id token to be used to resume the interaction stream, from
this event.

### Examples

[Error Event](https://ai.google.dev/api/interactions-api#error-event)[Interaction Completed](https://ai.google.dev/api/interactions-api#interaction-completed)[Interaction Completed](https://ai.google.dev/api/interactions-api#interaction-completed)[Interaction Created](https://ai.google.dev/api/interactions-api#interaction-created)[Interaction Created](https://ai.google.dev/api/interactions-api#interaction-created)[Interaction Status Update](https://ai.google.dev/api/interactions-api#interaction-status-update)[Step Delta](https://ai.google.dev/api/interactions-api#step-delta)[Step Start](https://ai.google.dev/api/interactions-api#step-start)[Step Stop](https://ai.google.dev/api/interactions-api#step-stop)More

```
{
  "error": {
    "code": "not_found",
    "message": "Failed to get completed interaction: Result not found."
  },
  "event_type": "error"
}
```

```
{
  "event_id": "evt_123",
  "event_type": "interaction.completed",
  "interaction": {
    "created": "2025-12-04T15:01:45Z",
    "id": "v1_ChdXS0l4YWZXTk9xbk0xZThQczhEcmlROBIXV0tJeGFmV05PcW5NMWU4UHM4RHJpUTg",
    "model": "gemini-3.6-flash",
    "status": "completed",
    "updated": "2025-12-04T15:01:45Z"
  }
}
```

```
{
  "event_id": "evt_123",
  "event_type": "interaction.completed",
  "interaction": {
    "created": "2025-12-04T15:01:45Z",
    "id": "v1_ChdXS0l4YWZXTk9xbk0xZThQczhEcmlROBIXV0tJeGFmV05PcW5NMWU4UHM4RHJpUTg",
    "model": "gemini-3-flash-preview",
    "object": "interaction",
    "status": "completed",
    "updated": "2025-12-04T15:01:45Z"
  }
}
```

```
{
  "event_id": "evt_123",
  "event_type": "interaction.created",
  "interaction": {
    "created": "2025-12-04T15:01:45Z",
    "id": "v1_ChdXS0l4YWZXTk9xbk0xZThQczhEcmlROBIXV0tJeGFmV05PcW5NMWU4UHM4RHJpUTg",
    "model": "gemini-3.6-flash",
    "status": "in_progress",
    "updated": "2025-12-04T15:01:45Z"
  }
}
```

```
{
  "event_id": "evt_123",
  "event_type": "interaction.created",
  "interaction": {
    "id": "v1_ChdXS0l4YWZXTk9xbk0xZThQczhEcmlROBIXV0tJeGFmV05PcW5NMWU4UHM4RHJpUTg",
    "model": "gemini-3-flash-preview",
    "object": "interaction",
    "status": "in_progress"
  }
}
```

```
{
  "event_type": "interaction.status_update",
  "interaction_id": "v1_ChdTMjQ0YWJ5TUF1TzcxZThQdjRpcnFRcxIXUzI0NGFieU1BdU83MWU4UHY0aXJxUXM",
  "status": "in_progress"
}
```

```
{
  "delta": {
    "type": "text",
    "text": "Hello"
  },
  "event_type": "step.delta",
  "index": 0
}
```

```
{
  "event_type": "step.start",
  "index": 0,
  "step": {
    "type": "model_output"
  }
}
```

```
{
  "event_type": "step.stop",
  "index": 0
}
```

### ResponseFormat

### Possible Types

AudioResponseFormat

Configuration for audio output format.

typeobject (required)

No description provided.

Always set to `"audio"`.

mime\_typeenum (string) (optional)

The MIME type of the audio output.

Possible
values:

- `audio/mp3`
MP3 audio format.

- `audio/ogg_opus`
OGG Opus audio format.

- `audio/l16`
Raw PCM (L16) audio format.

- `audio/wav`
WAV audio format.

- `audio/alaw`
A-law audio format.

- `audio/mulaw`
Mu-law audio format.


deliveryenum (string) (optional)

The delivery mode for the audio output.

Possible
values:

- `inline`
Audio data is returned inline in the response.

- `uri`
Audio data is returned as a URI.


sample\_rateinteger (optional)

Sample rate in Hz.

bit\_rateinteger (optional)

Bit rate in bits per second (bps). Only applicable for compressed formats
(MP3, Opus).

ImageResponseFormat

Configuration for image output format.

typeobject (required)

No description provided.

Always set to `"image"`.

mime\_typeenum (string) (optional)

The MIME type of the image output.

Possible
values:

- `image/jpeg`
JPEG image format.


deliveryenum (string) (optional)

The delivery mode for the image output.

Possible
values:

- `inline`
Image data is returned inline in the response.

- `uri`
Image data is returned as a URI.


aspect\_ratioenum (string) (optional)

The aspect ratio for the image output.

Possible
values:

- `1:1`
1:1 aspect ratio.

- `2:3`
2:3 aspect ratio.

- `3:2`
3:2 aspect ratio.

- `3:4`
3:4 aspect ratio.

- `4:3`
4:3 aspect ratio.

- `4:5`
4:5 aspect ratio.

- `5:4`
5:4 aspect ratio.

- `9:16`
9:16 aspect ratio.

- `16:9`
16:9 aspect ratio.

- `21:9`
21:9 aspect ratio.

- `1:8`
1:8 aspect ratio.

- `8:1`
8:1 aspect ratio.

- `1:4`
1:4 aspect ratio.

- `4:1`
4:1 aspect ratio.


image\_sizeenum (string) (optional)

The size of the image output.

Possible
values:

- `512`
512px image size.

- `1K`
1K image size.

- `2K`
2K image size.

- `4K`
4K image size.


TextResponseFormat

Configuration for text output format.

typeobject (required)

No description provided.

Always set to `"text"`.

mime\_typeenum (string) (optional)

The MIME type of the text output.

Possible
values:

- `application/json`
JSON output format.

- `text/plain`
Plain text output format.


schemaobject (optional)

The JSON schema that the output should conform to. Only applicable when
mime\_type is application/json.

Supports a subset of JSON Schema. \`minLength\`, \`maxLength\`,
\`minProperties\`, \`maxProperties\`, \`uniqueItems\`, \`contains\`,
\`minContains\`, and \`maxContains\` are ignored and not enforced; validate
these in your application. \`minItems\` and \`maxItems\` are enforced. Schemas
that are too complex to enforce (for example, large \`maxItems\` on nested
arrays) return a 400 INVALID\_ARGUMENT error.

VideoResponseFormat

Configuration for video output format.

typeobject (required)

No description provided.

Always set to `"video"`.

deliveryenum (string) (optional)

The delivery mode for the video output.

Possible
values:

- `inline`
Video data is returned inline in the response.

- `uri`
Video data is returned as a URI.


aspect\_ratioenum (string) (optional)

The aspect ratio for the video output.

Possible
values:

- `16:9`
16:9 aspect ratio.

- `9:16`
9:16 aspect ratio.


durationstring (optional)

The duration for the video output.

resolutionenum (string) (optional)

The video output resolution. Defaults to 720p.

Possible
values:

- `360p`
360p resolution.

- `720p`
720p resolution.

- `1080p`
1080p resolution.

- `4k`
4K resolution.


### Examples

[Audio Output](https://ai.google.dev/api/interactions-api#audio-output)[Image Output](https://ai.google.dev/api/interactions-api#image-output)[Text Output (JSON Schema)](https://ai.google.dev/api/interactions-api#text-output-json-schema)[Video Output](https://ai.google.dev/api/interactions-api#video-output)More

```
{
  "type": "audio",
  "sample_rate": 24000
}
```

```
{
  "type": "image",
  "aspect_ratio": "16:9",
  "image_size": "1K",
  "mime_type": "image/jpeg"
}
```

```
{
  "type": "text",
  "mime_type": "application/json",
  "schema": {
    "type": "object",
    "properties": {
      "ingredients": {
        "type": "array",
        "items": {
          "type": "string"
        }
      },
      "recipe_name": {
        "type": "string"
      }
    },
    "required": [\
      "ingredients",\
      "recipe_name"\
    ]
  }
}
```

```
{
  "type": "video",
  "aspect_ratio": "16:9",
  "delivery": "inline"
}
```

### Step

A step in the interaction.

### Possible Types

CodeExecutionCallStep

Code execution call step.

argumentsCodeExecutionCallStepArguments (required)

Required. The arguments to pass to the code execution.

The arguments to pass to the code execution.

#### Fields

languageenum (string) (optional)

Programming language of the \`code\`.

Possible
values:

- `python`
Python >= 3.10, with numpy and simpy available.

- `bash`
Bash. Only available for Gemini 3.0 model or above.


codestring (optional)

The code to be executed.

idstring (required)

Required. A unique ID for this specific tool call.

typeobject (required)

No description provided.

Always set to `"code_execution_call"`.

signaturestring (optional)

A signature hash for backend validation.

CodeExecutionResultStep

Code execution result step.

resultstring (required)

Required. The output of the code execution.

call\_idstring (required)

Required. ID to match the ID from the function call block.

typeobject (required)

No description provided.

Always set to `"code_execution_result"`.

is\_errorboolean (optional)

Whether the code execution resulted in an error.

signaturestring (optional)

A signature hash for backend validation.

FileSearchCallStep

File Search call step.

idstring (required)

Required. A unique ID for this specific tool call.

typeobject (required)

No description provided.

Always set to `"file_search_call"`.

signaturestring (optional)

A signature hash for backend validation.

FileSearchResultStep

File Search result step.

call\_idstring (required)

Required. ID to match the ID from the function call block.

typeobject (required)

No description provided.

Always set to `"file_search_result"`.

signaturestring (optional)

A signature hash for backend validation.

FunctionCallStep

A function tool call step.

namestring (required)

Required. The name of the tool to call.

argumentsobject (required)

Required. The arguments to pass to the function.

idstring (required)

Required. A unique ID for this specific tool call.

typeobject (required)

No description provided.

Always set to `"function_call"`.

FunctionResultStep

Result of a function tool call.

resultarray ( [ImageContent](https://ai.google.dev/api/interactions-api#Resource:ImageContent) or [TextContent](https://ai.google.dev/api/interactions-api#Resource:TextContent)) or object or string (required)

Required. The result of the tool call.

call\_idstring (required)

Required. ID to match the ID from the function call block.

typeobject (required)

No description provided.

Always set to `"function_result"`.

namestring (optional)

The name of the tool that was called.

is\_errorboolean (optional)

Whether the tool call resulted in an error.

GoogleMapsCallStep

Google Maps call step.

idstring (required)

Required. A unique ID for this specific tool call.

typeobject (required)

No description provided.

Always set to `"google_maps_call"`.

argumentsGoogleMapsCallStepArguments (optional)

The arguments to pass to the Google Maps tool.

The arguments to pass to the Google Maps tool.

#### Fields

queriesarray (string) (optional)

The queries to be executed.

signaturestring (optional)

A signature hash for backend validation.

GoogleMapsResultStep

Google Maps result step.

resultarray (GoogleMapsResultItem) (required)

No description provided.

The result of the Google Maps.

#### Fields

placesarray (GoogleMapsResultPlaces) (optional)

No description provided.

#### Fields

place\_idstring (optional)

No description provided.

namestring (optional)

No description provided.

urlstring (optional)

No description provided.

review\_snippetsarray (ReviewSnippet) (optional)

No description provided.

Encapsulates a snippet of a user review that answers a question about
the features of a specific place in Google Maps.

#### Fields

titlestring (optional)

Title of the review.

urlstring (optional)

A link that corresponds to the user review on Google Maps.

review\_idstring (optional)

The ID of the review snippet.

widget\_context\_tokenstring (optional)

No description provided.

call\_idstring (required)

Required. ID to match the ID from the function call block.

typeobject (required)

No description provided.

Always set to `"google_maps_result"`.

signaturestring (optional)

A signature hash for backend validation.

GoogleSearchCallStep

Google Search call step.

argumentsGoogleSearchCallStepArguments (required)

Required. The arguments to pass to Google Search.

The arguments to pass to Google Search.

#### Fields

queriesarray (string) (optional)

Web search queries for the following-up web search.

idstring (required)

Required. A unique ID for this specific tool call.

typeobject (required)

No description provided.

Always set to `"google_search_call"`.

search\_typeenum (string) (optional)

The type of search grounding enabled.

Possible
values:

- `web_search`
Setting this field enables web search. Only text results are returned.

- `image_search`
Setting this field enables image search. Image bytes are returned.


signaturestring (optional)

A signature hash for backend validation.

GoogleSearchResultStep

Google Search result step.

resultarray (GoogleSearchResultItem) (required)

Required. The results of the Google Search.

The result of the Google Search.

#### Fields

search\_suggestionsstring (optional)

Web content snippet that can be embedded in a web page or an app webview.

call\_idstring (required)

Required. ID to match the ID from the function call block.

typeobject (required)

No description provided.

Always set to `"google_search_result"`.

is\_errorboolean (optional)

Whether the Google Search resulted in an error.

signaturestring (optional)

A signature hash for backend validation.

McpServerToolCallStep

MCPServer tool call step.

namestring (required)

Required. The name of the tool which was called.

server\_namestring (required)

Required. The name of the used MCP server.

argumentsobject (required)

Required. The JSON object of arguments for the function.

idstring (required)

Required. A unique ID for this specific tool call.

typeobject (required)

No description provided.

Always set to `"mcp_server_tool_call"`.

McpServerToolResultStep

MCPServer tool result step.

resultarray ( [ImageContent](https://ai.google.dev/api/interactions-api#Resource:ImageContent) or [TextContent](https://ai.google.dev/api/interactions-api#Resource:TextContent)) or object or string (required)

Required. The output from the MCP server call. Can be simple text or rich content.

call\_idstring (required)

Required. ID to match the ID from the function call block.

typeobject (required)

No description provided.

Always set to `"mcp_server_tool_result"`.

namestring (optional)

Name of the tool which is called for this specific tool call.

server\_namestring (optional)

The name of the used MCP server.

ModelOutputStep

Output generated by the model.

typeobject (required)

No description provided.

Always set to `"model_output"`.

contentarray ( [Content](https://ai.google.dev/api/interactions-api#Resource:Content)) (optional)

No description provided.

ProcessingCallStep

A server-initiated processing step for media analysis (e.g. video
understanding).

idstring (required)

Required. A unique ID for this specific tool call.

typeobject (required)

No description provided.

Always set to `"processing_call"`.

signaturestring (optional)

A signature hash for backend validation.

ProcessingResultStep

The result of a server-initiated media processing step.

call\_idstring (required)

Required. ID to match the ID from the function call block.

typeobject (required)

No description provided.

Always set to `"processing_result"`.

signaturestring (optional)

A signature hash for backend validation.

ThoughtStep

A thought step.

typeobject (required)

No description provided.

Always set to `"thought"`.

signaturestring (optional)

A signature hash for backend validation.

summaryarray ( [Content](https://ai.google.dev/api/interactions-api#Resource:Content)) (optional)

A summary of the thought.

UrlContextCallStep

URL context call step.

argumentsUrlContextCallArguments (required)

Required. The arguments to pass to the URL context.

The arguments to pass to the URL context.

#### Fields

urlsarray (string) (optional)

The URLs to fetch.

idstring (required)

Required. A unique ID for this specific tool call.

typeobject (required)

No description provided.

Always set to `"url_context_call"`.

signaturestring (optional)

A signature hash for backend validation.

UrlContextResultStep

URL context result step.

resultarray (UrlContextResult) (required)

Required. The results of the URL context.

The result of the URL context.

#### Fields

urlstring (optional)

The URL that was fetched.

statusenum (string) (optional)

The status of the URL retrieval.

Possible
values:

- `success`
Url retrieval is successful.

- `error`
Url retrieval is failed due to error.

- `paywall`
Url retrieval is failed because the content is behind paywall.

- `unsafe`
Url retrieval is failed because the content is unsafe.


call\_idstring (required)

Required. ID to match the ID from the function call block.

typeobject (required)

No description provided.

Always set to `"url_context_result"`.

is\_errorboolean (optional)

Whether the URL context resulted in an error.

signaturestring (optional)

A signature hash for backend validation.

UserInputStep

Input provided by the user.

typeobject (required)

No description provided.

Always set to `"user_input"`.

contentarray ( [Content](https://ai.google.dev/api/interactions-api#Resource:Content)) (optional)

No description provided.

### Examples

[CodeExecutionCallStep](https://ai.google.dev/api/interactions-api#codeexecutioncallstep)[CodeExecutionResultStep](https://ai.google.dev/api/interactions-api#codeexecutionresultstep)[FileSearchCallStep](https://ai.google.dev/api/interactions-api#filesearchcallstep)[FileSearchResultStep](https://ai.google.dev/api/interactions-api#filesearchresultstep)[FunctionCallStep](https://ai.google.dev/api/interactions-api#functioncallstep)[FunctionResultStep](https://ai.google.dev/api/interactions-api#functionresultstep)[GoogleMapsCallStep](https://ai.google.dev/api/interactions-api#googlemapscallstep)[GoogleMapsResultStep](https://ai.google.dev/api/interactions-api#googlemapsresultstep)[GoogleSearchCallStep](https://ai.google.dev/api/interactions-api#googlesearchcallstep)[GoogleSearchResultStep](https://ai.google.dev/api/interactions-api#googlesearchresultstep)[McpServerToolCallStep](https://ai.google.dev/api/interactions-api#mcpservertoolcallstep)[McpServerToolResultStep](https://ai.google.dev/api/interactions-api#mcpservertoolresultstep)[ModelOutputStep](https://ai.google.dev/api/interactions-api#modeloutputstep)[ProcessingCallStep](https://ai.google.dev/api/interactions-api#processingcallstep)[ProcessingResultStep](https://ai.google.dev/api/interactions-api#processingresultstep)[ThoughtStep](https://ai.google.dev/api/interactions-api#thoughtstep)[UrlContextCallStep](https://ai.google.dev/api/interactions-api#urlcontextcallstep)[UrlContextResultStep](https://ai.google.dev/api/interactions-api#urlcontextresultstep)[UserInputStep](https://ai.google.dev/api/interactions-api#userinputstep)More

```
{
  "type": "code_execution_call",
  "arguments": {
    "code": "print(sum(range(1, 11)))"
  },
  "id": "code_call_71021"
}
```

```
{
  "type": "code_execution_result",
  "call_id": "code_call_71021",
  "result": "55\n"
}
```

```
{
  "type": "file_search_call",
  "id": "file_call_88192"
}
```

```
{
  "type": "file_search_result",
  "call_id": "file_call_88192"
}
```

```
{
  "name": "get_weather",
  "type": "function_call",
  "arguments": {
    "location": "Boston, MA"
  },
  "id": "call_98231"
}
```

```
{
  "name": "get_weather",
  "type": "function_result",
  "call_id": "call_98231",
  "result": [\
    {\
      "type": "text",\
      "text": "{\"weather\":\"sunny\"}"\
    }\
  ]
}
```

```
{
  "type": "google_maps_call",
  "arguments": {
    "latitude": 37.7749,
    "longitude": -122.4194
  },
  "id": "maps_call_39201"
}
```

```
{
  "type": "google_maps_result",
  "call_id": "maps_call_39201",
  "result": [\
    {\
      "name": "Golden Gate Park",\
      "place_id": "ChIJIQBpAG2ahYAR9R7bNdTLg8M",\
      "rating": 4.8\
    }\
  ]
}
```

```
{
  "type": "google_search_call",
  "arguments": {
    "query": "Who won the men's 100m in Paris 2024?"
  },
  "id": "search_call_19201"
}
```

```
{
  "type": "google_search_result",
  "call_id": "search_call_19201",
  "result": [\
    {\
      "title": "Paris 2024 Olympics: Noah Lyles wins men's 100m gold",\
      "url": "https://olympics.com/en/news/paris-2024-noah-lyles-wins-mens-100m-gold",\
      "snippet": "American Noah Lyles won the Olympic men's 100m gold medal in a photo finish."\
    }\
  ]
}
```

```
{
  "name": "calculate_tax",
  "type": "mcp_server_tool_call",
  "arguments": {
    "income": 120000,
    "state": "CA"
  },
  "id": "mcp_call_29012",
  "server_name": "financial_mcp_server"
}
```

```
{
  "name": "calculate_tax",
  "type": "mcp_server_tool_result",
  "call_id": "mcp_call_29012",
  "result": {
    "tax_due": 32400
  },
  "server_name": "financial_mcp_server"
}
```

```
{
  "type": "model_output",
  "content": [\
    {\
      "type": "text",\
      "text": "The capital of France is Paris."\
    }\
  ]
}
```

No examples available for this type.

No examples available for this type.

```
{
  "type": "thought",
  "signature": "thought_sig_abcd1234",
  "summary": [\
    {\
      "type": "text",\
      "text": "The model is searching Google for the capital of France."\
    }\
  ]
}
```

```
{
  "type": "url_context_call",
  "arguments": {
    "urls": [\
      "https://www.example.com"\
    ]
  },
  "id": "url_call_10219"
}
```

```
{
  "type": "url_context_result",
  "call_id": "url_call_10219",
  "result": [\
    {\
      "title": "Example Domain",\
      "url": "https://www.example.com",\
      "snippet": "This domain is for use in illustrative examples in documents."\
    }\
  ]
}
```

```
{
  "type": "user_input",
  "content": [\
    {\
      "type": "text",\
      "text": "What is the capital of France?"\
    }\
  ]
}
```

### EnvironmentConfig

Configuration for a custom environment.

#### Fields

typeobject (required)

No description provided.

Always set to `"remote"`.

network[EnvironmentNetworkEgressAllowlist](https://ai.google.dev/api/interactions-api#Resource:EnvironmentNetworkEgressAllowlist) or enum (string) (optional)

Network configuration for the environment.

Possible
values:

- `disabled`
All network egress is blocked.


sourcesarray (Source) (optional)

No description provided.

A source to be mounted into the environment.

#### Fields

typeenum (string) (optional)

No description provided.

Possible
values:

- `gcs`
A Cloud Storage bucket.

- `inline`
Inline content.

- `repository`
A generic repository. The protocol prefix in the source URL
identifies the provider (e.g., github://, gcs://).


sourcestring (optional)

The source of the environment.
For Cloud Storage, this is the Cloud Storage path.
For GitHub, this is the GitHub path.

targetstring (optional)

Where the source should appear in the environment.

contentstring (optional)

The inline content if \`type\` is \`INLINE\`.

encodingstring (optional)

Optional encoding for inline content (e.g. \`base64\`).

environment\_idstring (optional)

Optional. The environment ID for the interaction. If specified, the request will
update the existing environment instead of creating a new one.

envobject or string (optional)

Environment variables to set in the sandbox environment.

#### Possible Types

object

string

A direct string value.

### Examples

[Inline Sources](https://ai.google.dev/api/interactions-api#inline-sources)[External Sources](https://ai.google.dev/api/interactions-api#external-sources)[Network Allowlist](https://ai.google.dev/api/interactions-api#network-allowlist)[Proxy Credentials](https://ai.google.dev/api/interactions-api#proxy-credentials)More

```
{
  "type": "remote",
  "sources": [\
    {\
      "type": "inline",\
      "content": "You are a data analyst. Always include visualizations and export results as PDF.",\
      "target": ".agents/AGENTS.md"\
    },\
    {\
      "type": "inline",\
      "content": "---\nname: slide-maker\ndescription: Create HTML slide decks\n---\n# Slide Maker\n\nWhen asked to create a presentation:\n1. Analyze the input data\n2. Create an HTML slide deck with reveal.js\n3. Save to /workspace/output/slides.html",\
      "target": ".agents/skills/slide-maker/SKILL.md"\
    }\
  ]
}
```

```
{
  "type": "remote",
  "sources": [\
    {\
      "type": "repository",\
      "source": "https://github.com/my-org/my-skills.git",\
      "target": ".agents/skills"\
    },\
    {\
      "type": "gcs",\
      "source": "gs://my-bucket/my-folder",\
      "target": "/workspace/data"\
    }\
  ]
}
```

```
{
  "type": "remote",
  "network": {
    "allowlist": [\
      {\
        "domain": "pypi.org"\
      },\
      {\
        "domain": "*.github.com"\
      }\
    ]
  }
}
```

```
{
  "type": "remote",
  "network": {
    "allowlist": [\
      {\
        "domain": "api.github.com",\
        "transform": {\
          "Authorization": "Bearer YOUR_GITHUB_TOKEN"\
        }\
      }\
    ]
  }
}
```

### EnvironmentNetworkEgressAllowlist

Network egress configuration for the environment.

#### Fields

allowlistarray (EgressRule) or enum (string) (optional)

List of allowed domains and their configurations. Set to \`"disabled"\`
to block all network egress.

Possible
values:

- `disabled`
All network egress is blocked.


### Examples

[Network Allowlist](https://ai.google.dev/api/interactions-api#network-allowlist)More

```
{
  "allowlist": [\
    {\
      "domain": "github.com",\
      "transform": [\
        {\
          "Authorization": "Bearer your-token"\
        }\
      ]\
    },\
    {\
      "domain": "*.googleapis.com"\
    }\
  ]
}
```

### ToolChoiceConfig

The tool choice configuration containing allowed tools.

#### Fields

allowed\_toolsAllowedTools (optional)

The allowed tools.

The configuration for allowed tools.

#### Fields

modeenum (string) (optional)

The mode of the tool choice.

Possible
values:

- `auto`
Auto tool choice.

- `any`
Any tool choice.

- `none`
No tool choice.

- `validated`
Validated tool choice.


toolsarray (string) (optional)

The names of the allowed tools.

### Examples

[Example](https://ai.google.dev/api/interactions-api#example)More

```
{
  "allowed_tools": {
    "mode": "any",
    "tools": [\
      "my_tool"\
    ]
  }
}
```

### ImageContent

An image content block.

#### Fields

typeobject (required)

No description provided.

Always set to `"image"`.

datastring (optional)

The image content.

uristring (optional)

The URI of the image.

resolutionMediaResolution (optional)

The resolution of the media.

#### Possible values

- `low`
Low resolution.

- `medium`
Medium resolution.

- `high`
High resolution.

- `ultra_high`
Ultra high resolution.


mime\_typeenum (string) (optional)

The mime type of the image.

Possible
values:

- `image/png`
PNG image format

- `image/jpeg`
JPEG image format

- `image/webp`
WebP image format

- `image/heic`
HEIC image format

- `image/heif`
HEIF image format

- `image/gif`
GIF image format

- `image/bmp`
BMP image format

- `image/tiff`
TIFF image format


### Examples

[Image](https://ai.google.dev/api/interactions-api#image)More

```
{
  "type": "image",
  "data": "BASE64_ENCODED_IMAGE",
  "mime_type": "image/png"
}
```

### TextContent

A text content block.

#### Fields

textstring (required)

Required. The text content.

typeobject (required)

No description provided.

Always set to `"text"`.

annotationsarray (Annotation) (optional)

Citation information for model-generated content.

Citation information for model-generated content.

#### Possible Types

FileCitation

A file citation annotation.

typeobject (required)

No description provided.

Always set to `"file_citation"`.

document\_uristring (optional)

The URI of the file.

file\_namestring (optional)

The name of the file.

sourcestring (optional)

Source attributed for a portion of the text.

custom\_metadataobject (optional)

User provided metadata about the retrieved context.

page\_numberinteger (optional)

Page number of the cited document, if applicable.

media\_idstring (optional)

Media ID in-case of image citations, if applicable.

start\_indexinteger (optional)

Start of segment of the response that is attributed to this source.

Index indicates the start of the segment, measured in bytes.

end\_indexinteger (optional)

End of the attributed segment, exclusive.

PlaceCitation

A place citation annotation.

typeobject (required)

No description provided.

Always set to `"place_citation"`.

place\_idstring (optional)

The ID of the place, in \`places/{place\_id}\` format.

namestring (optional)

Title of the place.

urlstring (optional)

URI reference of the place.

review\_snippetsarray (ReviewSnippet) (optional)

Snippets of reviews that are used to generate answers about the
features of a given place in Google Maps.

Encapsulates a snippet of a user review that answers a question about
the features of a specific place in Google Maps.

#### Fields

titlestring (optional)

Title of the review.

urlstring (optional)

A link that corresponds to the user review on Google Maps.

review\_idstring (optional)

The ID of the review snippet.

start\_indexinteger (optional)

Start of segment of the response that is attributed to this source.

Index indicates the start of the segment, measured in bytes.

end\_indexinteger (optional)

End of the attributed segment, exclusive.

SpeechAnnotation

Speech annotation for text content.

typeobject (required)

No description provided.

Always set to `"speech_metadata"`.

speakerstring (optional)

The speaker to associate with this turn.

stylestring (optional)

Style instruction for the speech synthesis.

start\_indexinteger (optional)

Start of segment of the response that is attributed to this source.

Index indicates the start of the segment, measured in bytes.

end\_indexinteger (optional)

End of the attributed segment, exclusive.

UrlCitation

A URL citation annotation.

typeobject (required)

No description provided.

Always set to `"url_citation"`.

urlstring (optional)

The URL.

titlestring (optional)

The title of the URL.

start\_indexinteger (optional)

Start of segment of the response that is attributed to this source.

Index indicates the start of the segment, measured in bytes.

end\_indexinteger (optional)

End of the attributed segment, exclusive.

WordInfo

Word-level ASR annotation for transcription output.
Carries the word text, optional timing, and optional speaker attribution.

typeobject (required)

No description provided.

Always set to `"word_info"`.

textstring (optional)

The transcribed word.

start\_offsetstring (optional)

Start offset in time of the word relative to the start of the audio.
Present when timestamp\_granularities contains "word".

end\_offsetstring (optional)

End offset in time of the word relative to the start of the audio.
Present when timestamp\_granularities contains "word".

speakerstring (optional)

Optional. Speaker label for this word (e.g. "spk\_1", "spk\_2").
Present when diarization\_mode is set in TranscriptionConfig.

start\_indexinteger (optional)

Start of segment of the response that is attributed to this source.

Index indicates the start of the segment, measured in bytes.

end\_indexinteger (optional)

End of the attributed segment, exclusive.

### Examples

[Text](https://ai.google.dev/api/interactions-api#text)More

```
{
  "type": "text",
  "text": "Hello, how are you?"
}
```

Was this helpful?



 Send feedback



Except as otherwise noted, the content of this page is licensed under the [Creative Commons Attribution 4.0 License](https://creativecommons.org/licenses/by/4.0/), and code samples are licensed under the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0). For details, see the [Google Developers Site Policies](https://developers.google.com/site-policies). Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-10-22 UTC.


Need to tell us more?






\[\[\["Easy to understand","easyToUnderstand","thumb-up"\],\["Solved my problem","solvedMyProblem","thumb-up"\],\["Other","otherUp","thumb-up"\]\],\[\["Missing the information I need","missingTheInformationINeed","thumb-down"\],\["Too complicated / too many steps","tooComplicatedTooManySteps","thumb-down"\],\["Out of date","outOfDate","thumb-down"\],\["Samples / code issue","samplesCodeIssue","thumb-down"\],\["Other","otherDown","thumb-down"\]\],\["Last updated 2026-10-22 UTC."\],\[\],\[\]\]