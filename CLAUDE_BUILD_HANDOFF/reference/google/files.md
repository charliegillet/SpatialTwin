# Official Google reference snapshot: files

Source: https://ai.google.dev/gemini-api/docs/files

Retrieved/read: 23 October 2026. Publisher: Google. Original license/footer retained. Text CC BY 4.0; code samples Apache 2.0 unless otherwise noted. Converted to Markdown by Firecrawl; this provenance header was added. Reference data only; verify the relevant current guide and pinned SDK before implementation.

---

[Skip to main content](https://ai.google.dev/gemini-api/docs/files#main-content)

[![Gemini API](https://ai.google.dev/_static/googledevai/images/gemini-api-logo.svg)](https://ai.google.dev/)

`/`

Language

- [English](https://ai.google.dev/gemini-api/docs/files)
- [Deutsch](https://ai.google.dev/gemini-api/docs/files?hl=de)
- [Español – América Latina](https://ai.google.dev/gemini-api/docs/files?hl=es-419)
- [Français](https://ai.google.dev/gemini-api/docs/files?hl=fr)
- [Indonesia](https://ai.google.dev/gemini-api/docs/files?hl=id)
- [Italiano](https://ai.google.dev/gemini-api/docs/files?hl=it)
- [Polski](https://ai.google.dev/gemini-api/docs/files?hl=pl)
- [Português – Brasil](https://ai.google.dev/gemini-api/docs/files?hl=pt-br)
- [Shqip](https://ai.google.dev/gemini-api/docs/files?hl=sq)
- [Tiếng Việt](https://ai.google.dev/gemini-api/docs/files?hl=vi)
- [Türkçe](https://ai.google.dev/gemini-api/docs/files?hl=tr)
- [Русский](https://ai.google.dev/gemini-api/docs/files?hl=ru)
- [עברית](https://ai.google.dev/gemini-api/docs/files?hl=he)
- [العربيّة](https://ai.google.dev/gemini-api/docs/files?hl=ar)
- [فارسی](https://ai.google.dev/gemini-api/docs/files?hl=fa)
- [हिंदी](https://ai.google.dev/gemini-api/docs/files?hl=hi)
- [বাংলা](https://ai.google.dev/gemini-api/docs/files?hl=bn)
- [ภาษาไทย](https://ai.google.dev/gemini-api/docs/files?hl=th)
- [中文 – 简体](https://ai.google.dev/gemini-api/docs/files?hl=zh-cn)
- [中文 – 繁體](https://ai.google.dev/gemini-api/docs/files?hl=zh-tw)
- [日本語](https://ai.google.dev/gemini-api/docs/files?hl=ja)
- [한국어](https://ai.google.dev/gemini-api/docs/files?hl=ko)

[Get API key](https://aistudio.google.com/apikey) [Cookbook](https://github.com/google-gemini/cookbook) [Community](https://discuss.ai.google.dev/c/gemini-api/)

[Sign in](https://ai.google.dev/_d/signin?continue=https%3A%2F%2Fai.google.dev%2Fgemini-api%2Fdocs%2Ffiles&prompt=select_account)

- On this page
- [Upload a file](https://ai.google.dev/gemini-api/docs/files#upload-audio)
- [Get metadata for a file](https://ai.google.dev/gemini-api/docs/files#get-metadata)
- [List uploaded files](https://ai.google.dev/gemini-api/docs/files#list-uploaded)
- [Delete uploaded files](https://ai.google.dev/gemini-api/docs/files#delete-uploaded)
- [Usage information](https://ai.google.dev/gemini-api/docs/files#usage-info)
- [File prompting strategies](https://ai.google.dev/gemini-api/docs/files#prompt-guide)
  - [Be specific in your instructions](https://ai.google.dev/gemini-api/docs/files#specific-instructions)
  - [Add a few examples](https://ai.google.dev/gemini-api/docs/files#add_a_few_examples)
  - [Break it down step-by-step](https://ai.google.dev/gemini-api/docs/files#break_it_down_step-by-step)
  - [Specify the output format](https://ai.google.dev/gemini-api/docs/files#specify_the_output_format)
  - [Put your image first for single-image prompts](https://ai.google.dev/gemini-api/docs/files#single-image-prompts)
  - [Troubleshooting your multimodal prompt](https://ai.google.dev/gemini-api/docs/files#troubleshooting)
- [What's next](https://ai.google.dev/gemini-api/docs/files#whats-next)

Gemini 4 Argon is now available. [Try it out](https://aistudio.google.com/prompts/new_chat?model=gemini-4-argon).


- [Home](https://ai.google.dev/)
- [Gemini API](https://ai.google.dev/gemini-api)
- [Docs](https://ai.google.dev/gemini-api/docs)

Was this helpful?

Interactions API (Recommended)generateContent APILearn more

Select an optionInteractions API (Recommended)

- [Interactions API (Recommended)](https://ai.google.dev/gemini-api/docs/files)
- [generateContent API](https://ai.google.dev/gemini-api/docs/generate-content/files)
- [Learn more](https://ai.google.dev/gemini-api/docs/interactions)



 Send feedback



# Files API

- On this page
- [Upload a file](https://ai.google.dev/gemini-api/docs/files#upload-audio)
- [Get metadata for a file](https://ai.google.dev/gemini-api/docs/files#get-metadata)
- [List uploaded files](https://ai.google.dev/gemini-api/docs/files#list-uploaded)
- [Delete uploaded files](https://ai.google.dev/gemini-api/docs/files#delete-uploaded)
- [Usage information](https://ai.google.dev/gemini-api/docs/files#usage-info)
- [File prompting strategies](https://ai.google.dev/gemini-api/docs/files#prompt-guide)
  - [Be specific in your instructions](https://ai.google.dev/gemini-api/docs/files#specific-instructions)
  - [Add a few examples](https://ai.google.dev/gemini-api/docs/files#add_a_few_examples)
  - [Break it down step-by-step](https://ai.google.dev/gemini-api/docs/files#break_it_down_step-by-step)
  - [Specify the output format](https://ai.google.dev/gemini-api/docs/files#specify_the_output_format)
  - [Put your image first for single-image prompts](https://ai.google.dev/gemini-api/docs/files#single-image-prompts)
  - [Troubleshooting your multimodal prompt](https://ai.google.dev/gemini-api/docs/files#troubleshooting)
- [What's next](https://ai.google.dev/gemini-api/docs/files#whats-next)

Gemini can handle various types of input data, including text, images, and
audio, at the same time.

This guide shows you how to work with media files using the Files API. The
basic operations are the same for audio files, images, videos, documents, and
other supported file types.

For file prompting guidance, check out the [File prompt guide](https://ai.google.dev/gemini-api/docs/files#prompt-guide) section.

## Upload a file

You can use the Files API to upload a media file. Always use the Files API when
the total request size (including the files, text prompt, system instructions,
etc.) is larger than 100 MB. For PDF files, the limit is 50 MB.

The following code uploads a file and then uses the file in a call to
`interactions.create`.

[Python](https://ai.google.dev/gemini-api/docs/files#python)[JavaScript](https://ai.google.dev/gemini-api/docs/files#javascript)[Java](https://ai.google.dev/gemini-api/docs/files#java)[Go](https://ai.google.dev/gemini-api/docs/files#go)[REST](https://ai.google.dev/gemini-api/docs/files#rest)More

```
from google import genai

client = genai.Client()

myfile = client.files.upload(file="path/to/sample.mp3")

interaction = client.interactions.create(
    model="gemini-3.8-flash",
    input=[\
        {"type": "text", "text": "Describe this audio clip"},\
        {"type": "audio", "uri": myfile.uri, "mime_type": myfile.mime_type}\
    ]
)

print(interaction.output_text)
```

```
import { GoogleGenAI } from "@google/genai";

const client = new GoogleGenAI({});

async function main() {
  const myfile = await client.files.upload({
    file: "path/to/sample.mp3",
    config: { mime_type: "audio/mpeg" },
  });

  const interaction = await client.interactions.create({
    model: "gemini-3.8-flash",
    input: [\
      { type: "text", text: "Describe this audio clip" },\
      { type: "audio", uri: myfile.uri, mime_type: myfile.mimeType }\
    ]
  });
  console.log(interaction.output_text);
}

await main();
```

```
import com.google.genai.Client;
import com.google.genai.gaos.models.interactions.AudioContent;
import com.google.genai.gaos.models.interactions.AudioContentMimeType;
import com.google.genai.gaos.models.interactions.Content;
import com.google.genai.gaos.models.interactions.CreateModelInteraction;
import com.google.genai.gaos.models.interactions.Interaction;
import com.google.genai.gaos.models.interactions.InteractionsInput;
import com.google.genai.gaos.models.interactions.Model;
import com.google.genai.gaos.models.interactions.TextContent;
import com.google.genai.gaos.models.operations.CreateInteractionRequestBody;
import com.google.genai.types.File;
import com.google.genai.types.UploadFileConfig;
import java.util.Arrays;
import java.util.List;

Client client = new Client();

File myFile =
    client.files.upload(
        new java.io.File("path/to/sample.mp3"),
        UploadFileConfig.builder().mimeType("audio/mp3").build());

Content textContent = TextContent.builder().text("Describe this audio clip").build();
Content audioContent =
    AudioContent.builder()
        .uri(myFile.uri().orElse(""))
        .mimeType(AudioContentMimeType.of(myFile.mimeType().orElse("audio/mp3")))
        .build();

List<Content> contents = Arrays.asList(textContent, audioContent);

CreateModelInteraction params =
    CreateModelInteraction.builder()
        .model(Model.of("gemini-3.8-flash"))
        .input(InteractionsInput.ofContent(contents))
        .build();

Interaction interaction =
    client.interactions.create(CreateInteractionRequestBody.of(params)).interaction().get();

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

    myFile, err := client.Files.UploadFromPath(ctx, "path/to/sample.mp3", &genai.UploadFileConfig{
        MIMEType: "audio/mp3",
    })
    if err != nil {
        log.Fatal(err)
    }

    res, err := client.Interactions.Create(ctx, operations.CreateInteractionRequest{
        Body: operations.NewCreateInteractionRequestBody(interactions.CreateModelInteraction{
            Model: interactions.Model("gemini-3.8-flash"),
            Input: interactions.NewInteractionsInput([]interactions.Content{
                interactions.NewContent(interactions.TextContent{
                    Text: "Describe this audio clip",
                }),
                interactions.NewContent(interactions.AudioContent{
                    URI:      genai.Ptr(myFile.URI),
                    MimeType: interactions.AudioContentMimeType(myFile.MIMEType).ToPointer(),
                }),
            }),
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
AUDIO_PATH="path/to/sample.mp3"
MIME_TYPE=$(file -b --mime-type "${AUDIO_PATH}")
NUM_BYTES=$(wc -c < "${AUDIO_PATH}")
DISPLAY_NAME=AUDIO

tmp_header_file=upload-header.tmp

# Initial resumable request defining metadata.
# The upload url is in the response headers dump them to a file.
curl "${BASE_URL}/upload/v1beta/files" \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -D "${tmp_header_file}" \
  -H "X-Goog-Upload-Protocol: resumable" \
  -H "X-Goog-Upload-Command: start" \
  -H "X-Goog-Upload-Header-Content-Length: ${NUM_BYTES}" \
  -H "X-Goog-Upload-Header-Content-Type: ${MIME_TYPE}" \
  -H "Content-Type: application/json" \
  -d "{'file': {'display_name': '${DISPLAY_NAME}'}}" 2> /dev/null

upload_url=$(grep -i "x-goog-upload-url: " "${tmp_header_file}" | cut -d" " -f2 | tr -d "\r")
rm "${tmp_header_file}"

# Upload the actual bytes.
curl "${upload_url}" \
  -H "Content-Length: ${NUM_BYTES}" \
  -H "X-Goog-Upload-Offset: 0" \
  -H "X-Goog-Upload-Command: upload, finalize" \
  --data-binary "@${AUDIO_PATH}" 2> /dev/null > file_info.json

file_uri=$(jq ".file.uri" file_info.json)
echo file_uri=$file_uri

# Now create an interaction using the Interactions API
curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions" \
    -H "x-goog-api-key: $GEMINI_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{
      "model": "gemini-3.8-flash",
      "input": [\
        {"type": "text", "text": "Describe this audio clip"},\
        {"type": "audio", "uri": '$file_uri', "mime_type": "'${MIME_TYPE}'"}\
      ]
    }' 2> /dev/null > response.json

cat response.json
echo

jq ".outputs[] | select(.type == \"text\") | .text" response.json
```

## Get metadata for a file

You can verify that the API successfully stored the uploaded file and get its
metadata by calling `files.get`.

[Python](https://ai.google.dev/gemini-api/docs/files#python)[JavaScript](https://ai.google.dev/gemini-api/docs/files#javascript)[Java](https://ai.google.dev/gemini-api/docs/files#java)[Go](https://ai.google.dev/gemini-api/docs/files#go)[REST](https://ai.google.dev/gemini-api/docs/files#rest)More

```
from google import genai

client = genai.Client()

myfile = client.files.upload(file='path/to/sample.mp3')
file_name = myfile.name
myfile = client.files.get(name=file_name)
print(myfile)
```

```
import {
  GoogleGenAI,
} from "@google/genai";

const client = new GoogleGenAI({});

async function main() {
  const myfile = await client.files.upload({
    file: "path/to/sample.mp3",
    config: { mime_type: "audio/mpeg" },
  });

  const fileName = myfile.name;
  const fetchedFile = await client.files.get({ name: fileName });
  console.log(fetchedFile);
}

await main();
```

```
import com.google.genai.Client;
import com.google.genai.types.File;
import com.google.genai.types.UploadFileConfig;

Client client = new Client();

File myFile =
    client.files.upload(
        new java.io.File("path/to/sample.mp3"),
        UploadFileConfig.builder().mimeType("audio/mp3").build());

String fileName = myFile.name().orElse("");
File fileMetadata = client.files.get(fileName, null);
System.out.println(fileMetadata);
```

```
package main

import (
    "context"
    "fmt"
    "log"

    "google.golang.org/genai"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    myFile, err := client.Files.UploadFromPath(ctx, "path/to/sample.mp3", &genai.UploadFileConfig{
        MIMEType: "audio/mp3",
    })
    if err != nil {
        log.Fatal(err)
    }

    fileMetadata, err := client.Files.Get(ctx, myFile.Name, nil)
    if err != nil {
        log.Fatal(err)
    }
    fmt.Println(fileMetadata)
}
```

```
# file_info.json was created in the upload example
name=$(jq -r ".file.name" file_info.json)
# Get the file of interest to check state
curl https://generativelanguage.googleapis.com/v1beta/$name \
-H "x-goog-api-key: $GEMINI_API_KEY" > file_info.json
# Print some information about the file you got
name=$(jq -r ".name" file_info.json)
echo name=$name
file_uri=$(jq -r ".uri" file_info.json)
echo file_uri=$file_uri
```

## List uploaded files

The following code gets a list of all the files uploaded:

[Python](https://ai.google.dev/gemini-api/docs/files#python)[JavaScript](https://ai.google.dev/gemini-api/docs/files#javascript)[Java](https://ai.google.dev/gemini-api/docs/files#java)[Go](https://ai.google.dev/gemini-api/docs/files#go)[REST](https://ai.google.dev/gemini-api/docs/files#rest)More

```
from google import genai

client = genai.Client()

print('My files:')
for f in client.files.list():
    print(' ', f.name)
```

```
import {
  GoogleGenAI,
} from "@google/genai";

const client = new GoogleGenAI({});

async function main() {
  const listResponse = await client.files.list({ config: { pageSize: 10 } });
  for await (const file of listResponse) {
    console.log(file.name);
  }
}

await main();
```

```
import com.google.genai.Client;
import com.google.genai.types.File;

Client client = new Client();

System.out.println("My files:");
for (File f : client.files.list(null)) {
  System.out.println("  " + f.name().orElse(""));
}
```

```
package main

import (
    "context"
    "fmt"
    "log"

    "google.golang.org/genai"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    fmt.Println("My files:")
    for f, err := range client.Files.All(ctx) {
        if err != nil {
            log.Fatal(err)
        }
        fmt.Println(" ", f.Name)
    }
}
```

```
echo "My files: "

curl "https://generativelanguage.googleapis.com/v1beta/files" \
  -H "x-goog-api-key: $GEMINI_API_KEY"
```

## Delete uploaded files

Files are automatically deleted after 48 hours. You can also manually delete an
uploaded file:

[Python](https://ai.google.dev/gemini-api/docs/files#python)[JavaScript](https://ai.google.dev/gemini-api/docs/files#javascript)[Java](https://ai.google.dev/gemini-api/docs/files#java)[Go](https://ai.google.dev/gemini-api/docs/files#go)[REST](https://ai.google.dev/gemini-api/docs/files#rest)More

```
from google import genai

client = genai.Client()

myfile = client.files.upload(file='path/to/sample.mp3')
client.files.delete(name=myfile.name)
```

```
import {
  GoogleGenAI,
} from "@google/genai";

const client = new GoogleGenAI({});

async function main() {
  const myfile = await client.files.upload({
    file: "path/to/sample.mp3",
    config: { mime_type: "audio/mpeg" },
  });

  const fileName = myfile.name;
  await client.files.delete({ name: fileName });
}

await main();
```

```
import com.google.genai.Client;
import com.google.genai.types.File;
import com.google.genai.types.UploadFileConfig;

Client client = new Client();

File myFile =
    client.files.upload(
        new java.io.File("path/to/sample.mp3"),
        UploadFileConfig.builder().mimeType("audio/mp3").build());

client.files.delete(myFile.name().orElse(""), null);
```

```
package main

import (
    "context"
    "log"

    "google.golang.org/genai"
)

func main() {
    ctx := context.Background()
    client, err := genai.NewClient(ctx, nil)
    if err != nil {
        log.Fatal(err)
    }

    myFile, err := client.Files.UploadFromPath(ctx, "path/to/sample.mp3", &genai.UploadFileConfig{
        MIMEType: "audio/mp3",
    })
    if err != nil {
        log.Fatal(err)
    }

    if _, err := client.Files.Delete(ctx, myFile.Name, nil); err != nil {
        log.Fatal(err)
    }
}
```

```
curl --request "DELETE" https://generativelanguage.googleapis.com/v1beta/$name \
  -H "x-goog-api-key: $GEMINI_API_KEY"
```

## Usage information

You can use the Files API to upload and interact with media files. The Files API
lets you store up to 20 GB of files per project, with a per-file maximum
size of 2 GB. Files are stored for 48 hours.

During that time, you can use the API to get metadata about the files. However,
you can't download user-uploaded files. You can download files generated by
models, such as videos, using the `files.download` method. The Files API is
available at no cost in all regions where the Gemini API is available.

## File prompting strategies

This section provides guidance and best practices for using media files with
prompts for the Gemini API.

Being able to use various types of data in your prompts gives you more
flexibility in terms of what tasks you can tackle with the Gemini API. For
example, you can send the model a photo of a delicious meal and ask it to write
a short blog about the meal.

|     |     |
| --- | --- |
| **Prompt** | **Response** |
| Write a short, engaging blog post based on this picture. It should<br>include a description of the meal in the photo and talk about my journey<br>meal prepping.<br>![Cookies](https://ai.google.dev/static/gemini-api/docs/images/image_prompt.png) | Meal prepping is a great way to save time and money, and it can also<br>help you to eat healthier. This meal is a great example of a healthy<br>and delicious meal that can be prepped ahead of time.<br>This meal features brown rice, roasted vegetables, and chicken teriyaki.<br>The brown rice is a healthy and complex carbohydrate that will give you<br>sustained energy. The roasted vegetables are a great way to get your daily<br>dose of vitamins and minerals, and the chicken teriyaki is a delicious and<br>protein-rich option.<br>This meal is also straightforward to prepare. Simply cook the brown rice, roast<br>the vegetables, and cook the chicken teriyaki. Once everything is cooked,<br>divide it into meal prep containers and store them in the refrigerator.<br>You can then grab a container and go on busy mornings!<br>If you're looking for a healthy and delicious meal that can be<br>prepped ahead of time, this meal is a great option. It's packed with<br>nutrients and flavor, and it's sure to keep you feeling full and satisfied.<br>Here's to healthy and delicious meal prepping! |

If you are having trouble getting the output you want from prompts that use
media files, there are some strategies that can help you get the results you
want. The following sections provide design approaches and troubleshooting
tips for improving prompts that use multimodal input.

You can improve your multimodal prompts by following these best practices:

- ### [Prompt design fundamentals](https://ai.google.dev/gemini-api/docs/files\#specific-instructions)

  - **Be specific in your instructions**: Craft clear and concise instructions that leave minimal room for misinterpretation.
  - **Add a few examples to your prompt:** Use realistic few-shot examples to illustrate what you want to achieve.
  - **Break it down step-by-step**: Divide complex tasks into manageable sub-goals, guiding the model through the process.
  - **Specify the output format**: In your prompt, ask for the output to be in the format you want, like Markdown, JSON, HTML and more.
  - **Put your image first for single-image prompts**: While Gemini can handle image and text inputs in any order, for prompts containing a single image, it might perform better if that image (or video) is placed before the text prompt. However, for prompts that require images to be highly interleaved with texts to make sense, use whatever order is most natural.
- ### [Troubleshooting your multimodal prompt](https://ai.google.dev/gemini-api/docs/files\#troubleshooting)

  - **If the model is not drawing information from the relevant part of the image:** Drop hints with which aspects of the image you want the prompt to draw information from.
  - **If the model output is too generic (not tailored enough to the image/video input):** At the start of the prompt, try asking the model to describe the image(s) or video before providing the task instruction, or try asking the model to refer to what's in the image.
  - **To troubleshoot which part failed:** Ask the model to describe the image, or ask the model to explain its reasoning, to gauge the model's initial understanding.
  - **If your prompt results in hallucinated content:** Try dialing down the temperature setting or asking the model for shorter descriptions so that it's less likely to extrapolate additional details.
  - **Tuning the sampling parameters:** Experiment with different temperature settings and top-k selections to adjust the model's creativity.

### Be specific in your instructions

Prompts have the most success when they are clear and detailed. If you have a
specific output in mind, it's better to include that requirement in the prompt
to ensure you get the output you want.

For this image of an airport board, asking the model to just "describe this
image" could generate a general description. If you need the model to parse the
time and city from the image, you can include that request directly in your
prompt.

| Prompt | Model response |
| --- | --- |
| ![](https://ai.google.dev/static/gemini-api/docs/images/timetable.png)<br>Describe this image. | The image shows an airport arrivals and departures board. |

| **Updated prompt** | **Improved response** |
| --- | --- |
| ![Travel timetable](https://ai.google.dev/static/gemini-api/docs/images/timetable.png)<br>Parse the time and city from the airport board shown in this image into a list. | 10:50 Moscow<br>11:05 Edinburgh<br>11:05 London<br>11:10 Bucharest<br>11:30 Kiev<br>11:35 Dublin<br>11:45 East Midlands<br>12:15 Sofia<br>12:30 London<br>12:30 Newcastle<br>12:40 St Petersburg<br>12:40 London<br>12:45 Manchester |

### Add a few examples

The Gemini model can accept multiple inputs which it can use as examples to
understand the output you want. Adding these examples can help the model
identify the patterns and apply the relationship between the given images and
responses to the new example. This is also called "few-shot" learning.

In the following example, the initial output is written in sentence form,
and also contains the country (Brazil). Suppose you want the output in a
different format or style, and you want only the city, not the country. Adding
few-shot examples to your prompt can steer the model to respond in the way you
want.

| **Prompt** | **Model response** |
| --- | --- |
| ![Travel timetable](https://ai.google.dev/static/gemini-api/docs/images/redeemer.png)<br>Determine the city along with the landmark. | The landmark is the Christ the Redeemer statue in Rio de Janeiro, Brazil. |

| **Updated prompt** | **Improved response** |
| --- | --- |
| Determine the city along with the landmark.<br>![colosseum](https://ai.google.dev/static/gemini-api/docs/images/colosseum.png) | city: Rome, landmark: the Colosseum. |
| ![Forbidden City](https://ai.google.dev/static/gemini-api/docs/images/forbidden-city.png) | city: Beijing, landmark: Forbidden City |
| ![forbidden-city](https://ai.google.dev/static/gemini-api/docs/images/redeemer.png) | city: Rio de Janeiro, landmark: Christ the Redeemer statue |

### Break it down step-by-step

For complex tasks like the ones that require both visual understanding and
reasoning, it can be helpful to split the task into smaller, more
straightforward steps. Alternatively, it could also be effective if you
directly ask the model to "think step by step" in your prompt.

| Prompt | Model response |
| --- | --- |
| ![](https://ai.google.dev/static/gemini-api/docs/images/toilet-paper.jpg)<br>When will I run out of toilet paper? | Soon, you only have 3 rolls left. |

| **Updated prompt** | **Improved response** |
| --- | --- |
| ![](https://ai.google.dev/static/gemini-api/docs/images/toilet-paper.jpg)<br>1. First, count how many toilet paper rolls are in this picture.<br>2. Then, determine how much toilet paper a typical person uses per day.<br>3. Calculate how long these rolls of toilet paper will last. | 1. There are 3 rolls of toilet paper in this picture.<br>2. A typical person uses about 20 sheets of toilet paper per day.<br>3. If each roll contains 200 sheets, then each roll will last for about 10 days. Therefore, the 3 rolls will last for about a month. |

Math problems or other types of word problems are great candidates for asking
the model to think step-by-step.

| **Prompt** | **Response** |
| --- | --- |
| ![](https://ai.google.dev/static/gemini-api/docs/images/math.jpg)<br>What is the 4th term in the sequence? | -135 |

The response from the model is incorrect. Some ways to improve this is to ask
the model to parse the problem before answering the prompt.

| **Prompt** | **Response** |
| --- | --- |
| ![](https://ai.google.dev/static/gemini-api/docs/images/math.jpg)<br>Parse the formula in the image first.<br>Then based on the formula, answer "what's the 4th term in the sequence?". | _Click to expand the result_<br>$$ b(n) = b(n-1) \* (-3) $$<br>$$ b(1) = 15 $$<br>1. Substitute n = 4 into the formula:<br>   <br>   $$ b(4) = b(4-1) \* (-3) $$<br>   <br>   $$ b(4) = b(3) \* (-3) $$<br>   <br>2. We don't know the value of b(3), so substitute n = 3 into the formula:<br>   <br>   $$ b(3) = b(3-1) \* (-3) $$<br>   <br>   $$ b(3) = b(2) \* (-3) $$<br>   <br>3. We don't know the value of b(2), so substitute n = 2 into the formula:<br>   <br>   $$ b(2) = b(2-1) \* (-3) $$<br>   <br>   $$ b(2) = b(1) \* (-3) $$<br>   <br>4. We know the value of b(1) is 15, so substitute it into the formula:<br>   <br>   $$ b(2) = 15 \* (-3) $$<br>   <br>   $$ b(2) = -45 $$<br>   <br>5. Now that we know the value of b(2), substitute it into the formula for b(3):<br>   <br>   $$ b(3) = b(2) \* (-3) $$<br>   <br>   $$ b(3) = -45 \* (-3) $$<br>   <br>   $$ b(3) = 135 $$<br>   <br>6. Now that we know the value of b(3), substitute it into the formula for b(4):<br>   <br>   $$ b(4) = b(3) \* (-3) $$<br>   <br>   $$ b(4) = 135 \* (-3) $$<br>   <br>   $$ b(4) = -405 $$<br>   <br>Therefore, the 4th term in the sequence is -405. |

This model response is correct - now to make the response even more streamlined,
you can ask the model to think step-by-step.

| **Updated prompt** | **Improved response** |
| --- | --- |
| ![](https://ai.google.dev/static/gemini-api/docs/images/math.jpg)<br>What is the 4th term in the sequence? Think step by step. | The first term is 15.<br>The second term is b(1) \* (-3) = 15 \* (-3) = -45.<br>The third term is b(2) \* (-3) = -45 \* (-3) = 135.<br>The fourth term is b(3) \* (-3) = 135 \* (-3) = -405. |

### Specify the output format

A common problem is the need for model output to be in a certain format
(e.g. Markdown, JSON, HTML), especially if the model output needs to
be ingested by a downstream task. You can try to produce output in that format
by instructing the model to do so within the prompt. The following are two
examples:

| Prompt | Model response |
| --- | --- |
| ![](https://ai.google.dev/static/gemini-api/docs/images/excel-example.png)<br>Parse the table in this image into Markdown format | \`\`\`none<br>\| Subject \| Status \| Time \| Start date \| Due on \|<br>\| \-\-\-\-\-\-\- \| \-\-\-\-\-\- \| \-\-\-\- \| \-\-\-\-\-\-\-\-\-\- \| \-\-\-\-\-\- \|<br>\| Math \| Done \| 1.5 hrs \| 11/29/2023 \| 12/1/2023 \|<br>\| Geography \| Done \| 30 min \| 12/2/2023 \| 12/4/2023 \|<br>\| Physics \| In progress \| 2 hrs \| 12/3/2023 \| 12/5/2023 \|<br>\| Biology \| Not started \| 6 hrs \| 11/2/2016 \| 12/6/2023 \|<br>\`\`\` |

| **Prompt** | **Model response** |
| --- | --- |
| ![](https://ai.google.dev/static/gemini-api/docs/images/spanish-meal.png)<br>Provide a list of all the following attributes:<br>ingredients, type of cuisine, vegetarian or not, in JSON format | \`\`\`json<br>{<br>"ingredients": \[<br>"rice",<br>"shrimp",<br>"clams",<br>"mussels",<br>"peas",<br>"tomatoes",<br>"onions",<br>"garlic",<br>"olive oil",<br>"paprika",<br>"salt",<br>"pepper"<br>\],<br>"type of cuisine": "Spanish",<br>"vegetarian": false<br>}<br>\`\`\` |

### Put your image first for single-image prompts

While Gemini can interpret image and text in any order within a prompt, placing
a single image before the text prompt might lead to better results.
In the following samples, you'll notice the image comes first before the text in
each prompt.

### Troubleshooting your multimodal prompt

You might need to troubleshoot your prompt if you are not getting a helpful
response. Here are a few strategies you could try.

#### If the model is not drawing information from the relevant part of the image

To get a more specific response, you can point out which aspects of the image
you want the prompt to draw information from to inform its response.

| Prompt | Model response |
| --- | --- |
| ![](https://ai.google.dev/static/gemini-api/docs/images/diapers.png)<br>How many days will these diapers last a baby? | The diapers will last for 198 days before they run out. |

| **Updated prompt** | **Improved response** |
| --- | --- |
| ![](https://ai.google.dev/static/gemini-api/docs/images/diapers.png)<br>How long will these diapers last before I run out?<br>Use the weight shown on the box to determine the child's age, and use the total number of diapers in the box.<br>Divide the total number by how many diapers the child goes through per day. | The box contains 198 diapers. The box states the diapers are for a child weighing 22-37 lbs.<br>The average child in this weight range is likely between 1 and 2 years old.<br>A 2-year-old typically goes through 6 diapers per day, therefore, the diapers will last around 33 days (198/6). |

#### If the model output is too generic and not tailored enough to the image input

To help the model tailor its response to the image(s), try asking it to describe
the images before performing its reasoning task.

| Prompt | Model response |
| --- | --- |
| ![](https://ai.google.dev/static/gemini-api/docs/images/packing.jpg)![](https://ai.google.dev/static/gemini-api/docs/images/mall.jpg)![](https://ai.google.dev/static/gemini-api/docs/images/toilet-paper.jpg)![](https://ai.google.dev/static/gemini-api/docs/images/ocean.jpg)<br>What is in common between these images? | All four images are examples of landscape photography. |

| **Updated prompt** | **Improved response** |
| --- | --- |
| ![](https://ai.google.dev/static/gemini-api/docs/images/packing.jpg)![](https://ai.google.dev/static/gemini-api/docs/images/mall.jpg)![](https://ai.google.dev/static/gemini-api/docs/images/toilet-paper.jpg)![](https://ai.google.dev/static/gemini-api/docs/images/ocean.jpg)<br>First, describe what's in each image in detail. What's in common between these images? | The first image shows a person packing a suitcase. The second image shows an empty hallway in a shopping mall. The third image shows a roll of toilet paper. The fourth image shows a dark and stormy sea.<br>The commonality between these images is that they are all examples of liminal spaces. Liminal spaces are places or situations that are in between two other places or situations. They are often characterized by a sense of uncertainty or ambiguity.<br>The first image shows the person in between being at home and being on a trip. The second image shows the hallway in between two stores. The third image is of toilet paper, which can represent a bathroom. A bathroom is a transitional space between private<br>and public realms. It's a place where we prepare ourselves to enter or leave the outside world.<br>The fourth image shows the sea in between being calm and being stormy.<br>Liminal spaces can be both exciting and unsettling. They can be a place of new beginning or a place of endings. They can be a place of reflection or a place of action. |

You can also try explicitly asking the model to refer to what's in the image.

| **Updated prompt** | **Improved response** |
| --- | --- |
| ![](https://ai.google.dev/static/gemini-api/docs/images/packing.jpg)![](https://ai.google.dev/static/gemini-api/docs/images/mall.jpg)![](https://ai.google.dev/static/gemini-api/docs/images/toilet-paper.jpg)![](https://ai.google.dev/static/gemini-api/docs/images/ocean.jpg)<br>What is in common between these images? Refer to what's in the images in your response. | All of the images are related to travel. The first image shows a person packing a suitcase, the second image shows<br>an empty hallway in a shopping mall, the third image shows a stack of toilet paper, and the fourth image shows a<br>dark and stormy sea.<br>These images are all related to travel because they are all things that people need or use when<br>they travel. The first image shows a person packing a suitcase, which is<br>something that people do when they are going on a trip. The second image<br>shows an empty hallway in a shopping mall, which is a place where people<br>often go to buy things for their trips. The third image shows a stack of<br>toilet paper, which is something that people often use when they are<br>traveling. The fourth image shows a dark and stormy sea, which is<br>something that people often encounter when they are traveling. |

The same tips work for creative output from images. In the following example with
the rabbit, explicitly asking the model to include aspects from the image can
improve the output.

| Prompt | Model response |
| --- | --- |
| ![](https://ai.google.dev/static/gemini-api/docs/images/rabbit.jpg)<br>Can you write me a poem about this image? | Little bunny, so soft and brown,<br>Hopping through the field, up and down.<br>Your ears so long, your tail so small,<br>You're the cutest creature of them all.<br>You nibble on the grass, so green and sweet,<br>And hop away when you see me.<br>But I'll always be your friend,<br>Little bunny, until the very end. |

| **Updated prompt** | **Improved response** |
| --- | --- |
| ![](https://ai.google.dev/static/gemini-api/docs/images/rabbit.jpg)<br>Can you write me a descriptive and dramatic poem about this image and include the location? | Little bunny on the green,<br>Ears so long, so keen.<br>What do you see out there,<br>In the distance, where you stare?<br>Is it the ocean blue,<br>Sparkling in the sun's hue?<br>Or the waves that crash and roar,<br>A rhythm that you adore?<br>Little bunny, tell me true,<br>What captures your attention so?<br>Is it the salty breeze,<br>Or the seagulls' cries that please?<br>Perhaps it's the vastness of it all,<br>A world so big and small.<br>A place where dreams can roam,<br>And adventures can be sown.<br>Little bunny, I wonder what you dream,<br>As you sit on the grass, so serene.<br>Do you yearn to explore the deep,<br>Or stay on land, where you can leap?<br>Whatever it may be, little bunny,<br>Keep that spark of wonder burning brightly.<br>For in your dreams and aspirations,<br>Lies a world waiting for your creation. |

#### Troubleshooting which part of the prompt failed

It can be hard to know whether a prompt failed because the model
didn't **understand the image** to begin with, or if it did understand the image
but did not perform the correct **reasoning steps** afterward.
To disambiguate between those reasons, ask the model to describe what's in the image.

In the following example, if the model responds with a snack that seems surprising
when paired with tea (e.g. popcorn), you can first troubleshoot to determine
whether the model correctly recognized that the image contains tea.

| Prompt | Prompt for troubleshooting |
| --- | --- |
| ![](https://ai.google.dev/static/gemini-api/docs/images/tea-set.png)<br>What's a snack I can make in 1 minute that would go well with this? | ![](https://ai.google.dev/static/gemini-api/docs/images/tea-set.png)<br>Describe what's in this image. |

Another strategy is to ask the model to explain its reasoning. That can help you
narrow down which part of the reasoning broke down, if any.

| Prompt | Prompt for troubleshooting |
| --- | --- |
| ![](https://ai.google.dev/static/gemini-api/docs/images/tea-set.png)<br>What's a snack I can make in 1 minute that would go well with this? | ![](https://ai.google.dev/static/gemini-api/docs/images/tea-set.png)<br>What's a snack I can make in 1 minute that would go well with this? Please explain why. |

## What's next

- Try writing your own multimodal prompts using [Google AI\\
Studio](http://aistudio.google.com/).
- For information on using the Gemini Files API for
uploading media files and including them in your prompts, see the
[Vision](https://ai.google.dev/gemini-api/docs/vision), [Audio](https://ai.google.dev/gemini-api/docs/audio), and
[Document processing](https://ai.google.dev/gemini-api/docs/document-processing) guides.
- For more guidance on prompt design, like tuning sampling parameters, see the
[Prompt strategies](https://ai.google.dev/gemini-api/docs/prompting-strategies) page.

Was this helpful?



 Send feedback



Except as otherwise noted, the content of this page is licensed under the [Creative Commons Attribution 4.0 License](https://creativecommons.org/licenses/by/4.0/), and code samples are licensed under the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0). For details, see the [Google Developers Site Policies](https://developers.google.com/site-policies). Java is a registered trademark of Oracle and/or its affiliates.

Last updated 2026-10-14 UTC.


Need to tell us more?






\[\[\["Easy to understand","easyToUnderstand","thumb-up"\],\["Solved my problem","solvedMyProblem","thumb-up"\],\["Other","otherUp","thumb-up"\]\],\[\["Missing the information I need","missingTheInformationINeed","thumb-down"\],\["Too complicated / too many steps","tooComplicatedTooManySteps","thumb-down"\],\["Out of date","outOfDate","thumb-down"\],\["Samples / code issue","samplesCodeIssue","thumb-down"\],\["Other","otherDown","thumb-down"\]\],\["Last updated 2026-10-14 UTC."\],\[\],\[\]\]