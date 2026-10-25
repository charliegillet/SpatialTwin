# Official Google reference snapshot: troubleshooting

Source: https://ai.google.dev/gemini-api/docs/troubleshooting

Retrieved/read: 23 October 2026. Publisher: Google. Original license/footer retained. Text CC BY 4.0; code samples Apache 2.0 unless otherwise noted. Converted to Markdown by Firecrawl; this provenance header was added. Reference data only; verify the relevant current guide and pinned SDK before implementation.

---

[Skip to main content](https://ai.google.dev/gemini-api/docs/troubleshooting#main-content)

[![Gemini API](https://ai.google.dev/_static/googledevai/images/gemini-api-logo.svg)](https://ai.google.dev/)

`/`

Language

- [English](https://ai.google.dev/gemini-api/docs/troubleshooting)
- [Deutsch](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=de)
- [Español – América Latina](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=es-419)
- [Français](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=fr)
- [Indonesia](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=id)
- [Italiano](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=it)
- [Polski](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=pl)
- [Português – Brasil](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=pt-br)
- [Shqip](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=sq)
- [Tiếng Việt](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=vi)
- [Türkçe](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=tr)
- [Русский](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=ru)
- [עברית](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=he)
- [العربيّة](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=ar)
- [فارسی](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=fa)
- [हिंदी](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=hi)
- [বাংলা](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=bn)
- [ภาษาไทย](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=th)
- [中文 – 简体](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=zh-cn)
- [中文 – 繁體](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=zh-tw)
- [日本語](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=ja)
- [한국어](https://ai.google.dev/gemini-api/docs/troubleshooting?hl=ko)

[Get API key](https://aistudio.google.com/apikey) [Cookbook](https://github.com/google-gemini/cookbook) [Community](https://discuss.ai.google.dev/c/gemini-api/)

[Sign in](https://ai.google.dev/_d/signin?continue=https%3A%2F%2Fai.google.dev%2Fgemini-api%2Fdocs%2Ftroubleshooting&prompt=select_account)

- On this page
- [Error codes](https://ai.google.dev/gemini-api/docs/troubleshooting#error-codes)
- [Retry strategy](https://ai.google.dev/gemini-api/docs/troubleshooting#retry-strategy)
- [Check your API calls for model parameter errors](https://ai.google.dev/gemini-api/docs/troubleshooting#check-api)
- [Check if you have the right model](https://ai.google.dev/gemini-api/docs/troubleshooting#check-if)
- [Higher latency or token usage with thinking models](https://ai.google.dev/gemini-api/docs/troubleshooting#high-latency-or-token-usage)
- [Safety issues](https://ai.google.dev/gemini-api/docs/troubleshooting#safety-issues)
- [Recitation issue](https://ai.google.dev/gemini-api/docs/troubleshooting#recitation-issue)
- [Repetitive tokens issue](https://ai.google.dev/gemini-api/docs/troubleshooting#repetitive-tokens)
- [Blocked or non-working API keys](https://ai.google.dev/gemini-api/docs/troubleshooting#api-keys-not-working)
  - [Understand why keys are blocked](https://ai.google.dev/gemini-api/docs/troubleshooting#understand_why_keys_are_blocked)
  - [Confirm if your keys are affected](https://ai.google.dev/gemini-api/docs/troubleshooting#confirm_if_your_keys_are_affected)
  - [Action for blocked API keys](https://ai.google.dev/gemini-api/docs/troubleshooting#action_for_blocked_api_keys)
  - [Unexpected charges due to vulnerability](https://ai.google.dev/gemini-api/docs/troubleshooting#unexpected_charges_due_to_vulnerability)
  - [Google's security measures for leaked keys](https://ai.google.dev/gemini-api/docs/troubleshooting#googles_security_measures_for_leaked_keys)
- [Improve model output](https://ai.google.dev/gemini-api/docs/troubleshooting#improve-model)
- [Understand token limits](https://ai.google.dev/gemini-api/docs/troubleshooting#understand-token)
- [Known issues](https://ai.google.dev/gemini-api/docs/troubleshooting#known-issues)
- [File a bug](https://ai.google.dev/gemini-api/docs/troubleshooting#file-bug)

Gemini 4 Argon is now available. [Try it out](https://aistudio.google.com/prompts/new_chat?model=gemini-4-argon).


- [Home](https://ai.google.dev/)
- [Gemini API](https://ai.google.dev/gemini-api)
- [Docs](https://ai.google.dev/gemini-api/docs)

Was this helpful?



 Send feedback



# Troubleshooting guide

- On this page
- [Error codes](https://ai.google.dev/gemini-api/docs/troubleshooting#error-codes)
- [Retry strategy](https://ai.google.dev/gemini-api/docs/troubleshooting#retry-strategy)
- [Check your API calls for model parameter errors](https://ai.google.dev/gemini-api/docs/troubleshooting#check-api)
- [Check if you have the right model](https://ai.google.dev/gemini-api/docs/troubleshooting#check-if)
- [Higher latency or token usage with thinking models](https://ai.google.dev/gemini-api/docs/troubleshooting#high-latency-or-token-usage)
- [Safety issues](https://ai.google.dev/gemini-api/docs/troubleshooting#safety-issues)
- [Recitation issue](https://ai.google.dev/gemini-api/docs/troubleshooting#recitation-issue)
- [Repetitive tokens issue](https://ai.google.dev/gemini-api/docs/troubleshooting#repetitive-tokens)
- [Blocked or non-working API keys](https://ai.google.dev/gemini-api/docs/troubleshooting#api-keys-not-working)
  - [Understand why keys are blocked](https://ai.google.dev/gemini-api/docs/troubleshooting#understand_why_keys_are_blocked)
  - [Confirm if your keys are affected](https://ai.google.dev/gemini-api/docs/troubleshooting#confirm_if_your_keys_are_affected)
  - [Action for blocked API keys](https://ai.google.dev/gemini-api/docs/troubleshooting#action_for_blocked_api_keys)
  - [Unexpected charges due to vulnerability](https://ai.google.dev/gemini-api/docs/troubleshooting#unexpected_charges_due_to_vulnerability)
  - [Google's security measures for leaked keys](https://ai.google.dev/gemini-api/docs/troubleshooting#googles_security_measures_for_leaked_keys)
- [Improve model output](https://ai.google.dev/gemini-api/docs/troubleshooting#improve-model)
- [Understand token limits](https://ai.google.dev/gemini-api/docs/troubleshooting#understand-token)
- [Known issues](https://ai.google.dev/gemini-api/docs/troubleshooting#known-issues)
- [File a bug](https://ai.google.dev/gemini-api/docs/troubleshooting#file-bug)

Use this guide to help you diagnose and resolve common issues that arise when
you call the Gemini API. You may encounter issues from either
the Gemini API backend service or the client SDKs. Our client SDKs are
open sourced in the following repositories:

- [python-genai](https://github.com/googleapis/python-genai)
- [js-genai](https://github.com/googleapis/js-genai)
- [go-genai](https://github.com/googleapis/go-genai)

If you encounter API key issues, verify that you have set up
your API key correctly per the [API key setup guide](https://ai.google.dev/gemini-api/docs/api-key).

## Error codes

For a complete reference of all error codes, including HTTP status codes,
generation blocked codes, and content error codes, see the
[API errors](https://ai.google.dev/gemini-api/docs/api-errors) page.

## Retry strategy

If you receive an error indicating that you should retry your request (such as a `429 RESOURCE_EXHAUSTED` or `503 UNAVAILABLE`), we recommend implementing an exponential backoff strategy. This means you wait a short time before the first retry, and then gradually increase the wait time between subsequent retries.

The official client SDKs for the Gemini API, such as the [Python SDK](https://github.com/googleapis/python-genai), include automatic retry logic with exponential backoff by default for handling transient errors like timeouts, network issues, and rate limits (`429` and `5xx` status codes). For example, the Python SDK automatically retries transient errors up to four times with an initial delay of approximately 1 second and a maximum delay of 60 seconds.

If you are making direct REST API requests or customizing your retry logic, follow these best practices to increase the likelihood of a successful request and prevent overwhelming the service:

- **Use exponential backoff:** Wait a short time before the first retry (for example, 1 second), then increase the delay exponentially (for example, 2s, 4s, 8s).
- **Add jitter:** Add random "jitter" to the delay to help prevent all clients from retrying at the exact same time.
- **Retry on specific errors:** Only retry on transient errors (like `429`, `408`, or `5xx`). Do not retry on client errors (like `400`, `402`, or `403`) as they indicate issues like invalid API keys, depleted Prepay credits, or bad syntax.
- **Set maximum retries:** Define a maximum number of retry attempts to prevent infinite loops.

## Check your API calls for model parameter errors

Verify that your model parameters are within the following values:

|     |     |
| --- | --- |
| **Model parameter** | **Values (range)** |
| Candidate count | 1-8 (integer) |
| Temperature | 0.0-1.0 |
| Max output tokens | Use the [models page](https://ai.google.dev/gemini-api/docs/models/gemini)<br> to determine the maximum number of tokens for the model you are using. |
| TopP | 0.0-1.0 |

In addition to checking parameter values, make sure you're using the correct
[API version](https://ai.google.dev/gemini-api/docs/api-versions) (e.g., `/v1` or `/v1beta`) and
model that supports the features you need. For example, if a feature is in Beta
release, it will only be available in the `/v1beta` API version.

## Check if you have the right model

Verify that you are using a supported model listed on our [models\\
page](https://ai.google.dev/gemini-api/docs/models/gemini).

## Higher latency or token usage with thinking models

Higher latency or token usage often occurs because Gemini 3.x models have
thinking enabled by default. Deprecated Gemini 2.5 models also use default
thinking.

Thinking models generate internal reasoning tokens to improve quality. This
reasoning process increases both response latency and total token consumption.

If you prioritize lower latency or need to minimize costs, you can lower the
thinking level or turn off thinking.

For configuration details and code samples, see the
[thinking guide](https://ai.google.dev/gemini-api/docs/thinking#thinking-levels).

## Safety issues

If you see a prompt was blocked because of a safety setting in your API call,
review the prompt with respect to the filters you set in the API call.

If you see `BlockedReason.OTHER`, the query or response may violate the [terms\\
of service](https://ai.google.dev/terms) or be otherwise unsupported.

## Recitation issue

If you see the model stops generating output due to the RECITATION reason, this
means the model output may resemble certain data. To fix this, try to make
prompt / context as unique as possible and use a higher temperature.

## Repetitive tokens issue

If you see repeated output tokens, try the following suggestions to help
reduce or eliminate them.

| Description | Cause | Suggested workaround |
| --- | --- | --- |
| Repeated hyphens in Markdown tables | This can occur when the contents of the table are long as the model tries<br> to create a visually aligned Markdown table. However, the alignment in<br> Markdown is not necessary for correct rendering. | Add instructions in your prompt to give the model specific guidelines<br>for generating Markdown tables. Provide examples that follow those<br>guidelines. You can also try adjusting the temperature. For generating<br>code or very structured output like Markdown tables,<br>high temperature have shown to work better (>= 0.8).<br>The following is an example set of guidelines you can add to your<br>prompt to prevent this issue:<br> <br>```<br>          # Markdown Table Format<br>          <br>          * Separator line: Markdown tables must include a separator line below<br>            the header row. The separator line must use only 3 hyphens per<br>            column, for example: |---|---|---|. Using more hypens like<br>            ----, -----, ------ can result in errors. Always<br>            use |:---|, |---:|, or |---| in these separator strings.<br>            For example:<br>            | Date | Description | Attendees |<br>            |---|---|---|<br>            | 2024-10-26 | Annual Conference | 500 |<br>            | 2025-01-15 | Q1 Planning Session | 25 |<br>          * Alignment: Do not align columns. Always use |---|.<br>            For three columns, use |---|---|---| as the separator line.<br>            For four columns use |---|---|---|---| and so on.<br>          * Conciseness: Keep cell content brief and to the point.<br>          * Never pad column headers or other cells with lots of spaces to<br>            match with width of other content. Only a single space on each side<br>            is needed. For example, always do "| column name |" instead of<br>            "| column name                |". Extra spaces are wasteful.<br>            A markdown renderer will automatically take care displaying<br>            the content in a visually appealing form.<br>        <br>``` |
| Repeated tokens in Markdown tables | Similar to the repeated hyphens, this occurs when the model tries to<br> visually align the contents of the table. The alignment in Markdown is<br> not required for correct rendering. | - Try adding instructions like the following to your system prompt:<br>   <br>  <br>  <br>  <br>  ```<br>              FOR TABLE HEADINGS, IMMEDIATELY ADD ' |' AFTER THE TABLE HEADING.<br>            <br>  ```<br>  <br>- Try adjusting the temperature. Higher temperatures (>= 0.8)<br>   generally helps to eliminate repetitions or duplication in<br>   the output. |
| Repeated newlines (`\n`) in structured output | When the model input contains unicode or escape sequences like<br> `\u` or `\t`, it can lead to repeated newlines. | - Check for and replace forbidden escape sequences with UTF-8 characters<br>   in your prompt. For example, `\u`<br>   escape sequence in your JSON examples can cause the model to use them<br>   in its output too.<br>   <br>- Instruct the model on allowed escapes. Add a system instruction like<br>   this:<br>  <br>   <br>  <br>  <br>  <br>  ```<br>              In quoted strings, the only allowed escape sequences are \\, \n, and \". Instead of \u escapes, use UTF-8.<br>            <br>  ``` |
| Repeated text in using structured output | When the model output has a different order for the fields than the<br> defined structured schema, this can lead to repeating text. | - Don't specify the order of fields in your prompt.<br>   <br>- Make all output fields required. |
| Repetitive tool calling | This can occur if the model loses the context of previous thoughts and/or<br> call an unavailable endpoint that it's forced to. | Instruct the model to maintain state within its thought process.<br> Add this to the end of your system instructions:<br> <br>```<br>        When thinking silently: ALWAYS start the thought with a brief<br>        (one sentence) recap of the current progress on the task. In<br>        particular, consider whether the task is already done.<br>      <br>``` |
| Repetitive text that's not part of structured output | This can occur if the model gets stuck on a request that it can't resolve. | - If thinking is turned on, avoid giving explicit orders for how to<br>   think through a problem in the instructions. Just ask for the final<br>   output.<br>   <br>- Try a higher temperature >= 0.8.<br>   <br>- Add instructions like "Be concise", "Don't repeat yourself", or<br>   "Provide the answer once". |

## Blocked or non-working API keys

This section describes how to check whether your Gemini API key is blocked
and what to do about it.

### Understand why keys are blocked

We have identified a vulnerability where some API keys may have been publicly
exposed. To protect your data and prevent unauthorized access, we have
proactively blocked these known leaked keys from accessing the Gemini API.

### Confirm if your keys are affected

If your key is known to be leaked, you can no longer use that key with the
Gemini API. You can use [Google AI Studio](https://ai.google.dev/gemini-api/docs/api-key) to see if
any of your API keys are blocked from calling the Gemini API and generate new
keys. You may also see the following error returned when attempting to use
these keys:

```
Your API key was reported as leaked. Please use another API key.
```

### Action for blocked API keys

You should generate new API keys for your Gemini API integrations using [Google\\
AI Studio](https://ai.google.dev/gemini-api/docs/api-key). We strongly recommend reviewing your API
key management practices to ensure that your new keys are kept secure and are
not publicly exposed.

### Unexpected charges due to vulnerability

[Submit a billing support case](https://console.cloud.google.com/support/chat).
Our billing team is working on this, and we will communicate updates as soon as
possible.

### Google's security measures for leaked keys

**How is Google going to help secure my account from cost overrun and abuse if**
**my API keys are leaked?**

- We are moving towards issuing API keys when you request a new key using
[Google AI Studio](https://ai.google.dev/gemini-api/docs/api-key) that will by default be
limited to only Google AI Studio and not accept keys from other services.
This will help prevent any unintended cross-key usage.
- We are defaulting to blocking API keys that are leaked and used with the
Gemini API, helping prevent abuse of cost and your application data.
- You will be able to find the status of your API keys within [Google AI\\
Studio](https://ai.google.dev/gemini-api/docs/api-key) and we will work on communicating
proactively when we identify your API keys are leaked for immediate action.

## Improve model output

For higher quality model outputs, explore writing more structured prompts. The
[prompt engineering guide](https://ai.google.dev/gemini-api/docs/prompting-strategies) page
introduces some basic concepts, strategies, and best practices to get you
started.

## Understand token limits

Read through our [Token guide](https://ai.google.dev/gemini-api/docs/tokens) to better understand how
to count tokens and their limits.

## Known issues

- The API supports only a number of select languages. Submitting prompts in
unsupported languages can produce unexpected or even blocked responses. See
[available languages](https://ai.google.dev/gemini-api/docs/models#supported-languages) for
updates.

## File a bug

Join the discussion on the
[Google AI developer forum](https://discuss.ai.google.dev/)
if you have questions.

Was this helpful?



 Send feedback



Except as otherwise noted, the content of this page is licensed under the [Creative Commons Attribution 4.0 License](https://creativecommons.org/licenses/by/4.0/), and code samples are licensed under the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0). For details, see the [Google Developers Site Policies](https://developers.google.com/site-policies). Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-10-13 UTC.


Need to tell us more?






\[\[\["Easy to understand","easyToUnderstand","thumb-up"\],\["Solved my problem","solvedMyProblem","thumb-up"\],\["Other","otherUp","thumb-up"\]\],\[\["Missing the information I need","missingTheInformationINeed","thumb-down"\],\["Too complicated / too many steps","tooComplicatedTooManySteps","thumb-down"\],\["Out of date","outOfDate","thumb-down"\],\["Samples / code issue","samplesCodeIssue","thumb-down"\],\["Other","otherDown","thumb-down"\]\],\["Last updated 2026-10-13 UTC."\],\[\],\[\]\]