# Official Google reference snapshot: argon-model

Source: https://ai.google.dev/gemini-api/docs/models/gemini-4-argon

Retrieved/read: 23 October 2026. Publisher: Google. Original license/footer retained. Text CC BY 4.0; code samples Apache 2.0 unless otherwise noted. Converted to Markdown by Firecrawl; this provenance header was added. Reference data only; verify the relevant current guide and pinned SDK before implementation.

---

[Skip to main content](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon#main-content)

[![Gemini API](https://ai.google.dev/_static/googledevai/images/gemini-api-logo.svg)](https://ai.google.dev/)

`/`

Language

- [English](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon)
- [Deutsch](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=de)
- [Español – América Latina](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=es-419)
- [Français](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=fr)
- [Indonesia](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=id)
- [Italiano](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=it)
- [Polski](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=pl)
- [Português – Brasil](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=pt-br)
- [Shqip](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=sq)
- [Tiếng Việt](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=vi)
- [Türkçe](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=tr)
- [Русский](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=ru)
- [עברית](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=he)
- [العربيّة](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=ar)
- [فارسی](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=fa)
- [हिंदी](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=hi)
- [বাংলা](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=bn)
- [ภาษาไทย](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=th)
- [中文 – 简体](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=zh-cn)
- [中文 – 繁體](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=zh-tw)
- [日本語](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=ja)
- [한국어](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon?hl=ko)

[Get API key](https://aistudio.google.com/apikey) [Cookbook](https://github.com/google-gemini/cookbook) [Community](https://discuss.ai.google.dev/c/gemini-api/)

[Sign in](https://ai.google.dev/_d/signin?continue=https%3A%2F%2Fai.google.dev%2Fgemini-api%2Fdocs%2Fmodels%2Fgemini-4-argon&prompt=select_account)

- On this page
- [Documentation](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon#documentation)
- [gemini-4-argon](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon#gemini-4-argon)

Gemini 4 Argon is now available. [Try it out](https://aistudio.google.com/prompts/new_chat?model=gemini-4-argon).


- [Home](https://ai.google.dev/)
- [Gemini API](https://ai.google.dev/gemini-api)
- [Docs](https://ai.google.dev/gemini-api/docs)

Was this helpful?



 Send feedback



# Gemini 4 Argon

- On this page
- [Documentation](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon#documentation)
- [gemini-4-argon](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon#gemini-4-argon)

Gemini 4 Argon (`gemini-4-argon`) is our flagship reasoning model, built for complex software engineering, deep mathematical and scientific problem solving, autonomous multi-step agents, and long decode up to 1M tokens.

[Try in Google AI Studio](https://aistudio.google.com/prompts/new_chat?model=gemini-4-argon)

## Documentation

Visit the [Latest model](https://ai.google.dev/gemini-api/docs/latest-model) page for full coverage of features, API changes, and migration guidance.

## gemini-4-argon

| Property | Description |
| --- | --- |
| id\_cardModel code | `gemini-4-argon` |
| saveSupported data types | **Inputs**<br>Text, Image, Video, Audio, and PDF<br>**Output**<br>Text |
| token\_autoToken limits[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens) | **Context window (unified input and output token limit)**<br>1,048,576<br>**Max output**<br>65,536 (default synchronous) / up to 1,048,576 (with [long decode](https://ai.google.dev/gemini-api/docs/long-decode)) |
| handymanCapabilities | **[Agentic video understanding](https://ai.google.dev/gemini-api/docs/video-understanding#agentic-video-understanding)**<br>Supported (defaults to `static`)<br>**[Audio generation](https://ai.google.dev/gemini-api/docs/speech-generation)**<br>Not supported<br>**[Caching](https://ai.google.dev/gemini-api/docs/caching)**<br>Supported (Implicit only)<br>Note: Explicit caching is not supported.<br>**[Code execution](https://ai.google.dev/gemini-api/docs/code-execution)**<br>Supported<br>**[Computer use](https://ai.google.dev/gemini-api/docs/computer-use)**<br>Supported (Preview)<br>**[File search](https://ai.google.dev/gemini-api/docs/file-search)**<br>Supported<br>**[Function calling](https://ai.google.dev/gemini-api/docs/function-calling)**<br>Supported<br>**[Grounding with Google Maps](https://ai.google.dev/gemini-api/docs/maps-grounding)**<br>Supported<br>**[Image generation](https://ai.google.dev/gemini-api/docs/image-generation)**<br>Not supported<br>**[Live API](https://ai.google.dev/gemini-api/docs/live-api)**<br>Not supported<br>**[Search grounding](https://ai.google.dev/gemini-api/docs/google-search)**<br>Supported<br>**[Structured outputs](https://ai.google.dev/gemini-api/docs/structured-output)**<br>Supported<br>**[Thinking](https://ai.google.dev/gemini-api/docs/thinking)**<br>Supported (low, medium, high)<br>**[URL context](https://ai.google.dev/gemini-api/docs/url-context)**<br>Supported |
| speedConsumption options | **[Batch API](https://ai.google.dev/gemini-api/docs/batch-api)**<br>Supported<br>**[Flex inference](https://ai.google.dev/gemini-api/docs/flex-inference)**<br>Supported<br>**[Priority inference](https://ai.google.dev/gemini-api/docs/priority-inference)**<br>Supported |
| 123Versions | Read the [model version\<br>patterns](https://ai.google.dev/gemini-api/docs/models#model-versions) for more details.<br>- Stable: `gemini-4-argon` |
| calendar\_monthLatest update | October 2026 |
| id\_cardModel card | [Model card](https://deepmind.google/models/model-cards/gemini-4-argon/) |

Was this helpful?



 Send feedback



Except as otherwise noted, the content of this page is licensed under the [Creative Commons Attribution 4.0 License](https://creativecommons.org/licenses/by/4.0/), and code samples are licensed under the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0). For details, see the [Google Developers Site Policies](https://developers.google.com/site-policies). Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-10-14 UTC.


Need to tell us more?






\[\[\["Easy to understand","easyToUnderstand","thumb-up"\],\["Solved my problem","solvedMyProblem","thumb-up"\],\["Other","otherUp","thumb-up"\]\],\[\["Missing the information I need","missingTheInformationINeed","thumb-down"\],\["Too complicated / too many steps","tooComplicatedTooManySteps","thumb-down"\],\["Out of date","outOfDate","thumb-down"\],\["Samples / code issue","samplesCodeIssue","thumb-down"\],\["Other","otherDown","thumb-down"\]\],\["Last updated 2026-10-14 UTC."\],\[\],\[\]\]
