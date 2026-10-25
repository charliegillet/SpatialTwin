# Judges, hosts and recent winners: what the Gemini 4 Argon SF Hackathon is likely to reward, and what it means for WalkTwin

Research date: 25 October 2026 (event day). This extends `docs/research/winner-feature-analysis-2026-10-24.md` (355 winners, 63 events, to 17 October 2026) and does not redo it. New material: organizer pages and the public Builder Guide for this event, judge and speaker profiles and posts, the Managed Agents launch posts, and a closer reading of the 3D, video and twin entries at the August–October 2026 galleries, including entries that **did not** place.

Evidence labels used below:
- **[ORG]**: published by Cerebral Valley or Google, such as the event page, Builder Guide, Google blog or gallery award data (ld+json `award` field).
- **[SELF]**: the person's own profile or post.
- **[TEAM]**: a project team's own gallery description. It shows what they claimed to demo, not that it worked.
- **[2ND]**: third-party aggregator, search snippet or local team research.
- **[INF]**: my inference.

Award labels were read from the `award` field in each gallery's ld+json (raw HTML fetched 25 October). The rendered pages show only a "Finalists N" count. Saved copies are in the scratchpad (`.../scratchpad/gal/*.html`, `.../scratchpad/proj/*.html`).

---

## 1. What have the judges and the speaker publicly said, written or built, and what are their roles?

### Takeaway
None of the five has published a scoring rubric for this event. The best signals are each person's role and one explicit post of judging advice from Joana Carrasqueira. The panel covers three lenses: DevRel and storytelling (Carrasqueira), factuality, tool use and evaluation (Sahoo), devices in physical spaces (Jain), and fundability (Yao). Ivan Leo is listed as a **speaker, not a judge**. He led Gemini Managed Agents, so that prize is likely judged against what he built and promotes. That is an inference: the organizers have not named the Managed Agents judges.

### Cited Findings

**Event roles (organizer)**
- The event page lists Ivan Leo "as a speaker". The final-round judges are Joana Carrasqueira, Shudhatma Jain, Subhasmita Sahoo and Oskar Yao, "from Google". Round-one room judges are not named. The prize table is confirmed: $7,500 / $5,000 / $2,500, plus $5,000 for Best use of Managed Agents. [ORG] — [Gemini 4 Argon SF event page](https://cerebralvalley.ai/e/gemini-4-argon-sf)

**Joana Carrasqueira**
- Current X bio: "member of the technical staff @GoogleDeepMind · ex Head of DevRel". [SELF] — [X @jocarrasqueira, posts sampled 10–17 Oct 2026](https://x.com/jocarrasqueira/status/2111241475061321821)
- A Google Cloud Next speaker page lists them as Group Product Manager for 1P Engineering Innovation at Google DeepMind. It says they previously led DeepMind Developer Relations, growing Gemini, Gemma and GenMedia adoption. [ORG] — [Google Cloud Next speaker page](https://www.googlecloudevents.com/next-vegas/speaker/2144496/joana-carrasqueira)
- Earlier roles: DevRel lead for AI/ML at Google, and creator of the Women in ML program. [ORG] — [Google Developers Blog, 2023](https://developers.googleblog.com/en/women-in-ml-symposium-2023-meet-the-presenters/)
- **Their only public judging advice found.** It was posted 9 November 2025, after "yesterday's @cerebral_valley 🤝 @GoogleDeepMind hackathon":
  - judges "primarily focus on the demo";
  - "Pitches should take us on a journey: start with the Why!";
  - if you name a target audience or hook, "deliver on that hook!";
  - keep the demo polished and clear, and if it isn't finished, say how you would take it further;
  - "Storytelling gets you 80% there!"

  [SELF] — [X post, 9 Nov 2025](https://x.com/jocarrasqueira/status/1987577252725543314)
- Recent posts promote Argon. "Gemini 4 Argon is here 🔥" (13 Oct 2026). On 16 Oct 2026, Pro subscribers "can now use Argon" in AI Studio Playground and Build. On 13 Oct they promoted a Google DeepMind × Ruth hackathon in New York on 23 October. [SELF] — [X post 13 Oct](https://x.com/jocarrasqueira/status/2110065213559148981); [X post 16 Oct](https://x.com/jocarrasqueira/status/2111241475061321821); [X post 13 Oct, NYC hackathon](https://x.com/jocarrasqueira/status/2109964348403651010)
- They judged the AI for Social Good Hackathon, held 25 September at Google SF. The recap records no comments from them. [2ND] — [The Ruth Report, 6 Oct 2026](https://ruthai.substack.com/p/what-50-women-built-in-one-day)
- Kaggle lists them as "Vibe Coding Lead" for the Gemini 3 Pro AI Studio vibe-coding competition. [ORG, via search snippet] — [Kaggle Gemini 3 competition](https://www.kaggle.com/competitions/gemini-3/overview)

**Subhasmita Sahoo**
- GitHub bio: "Teaching Gemini to reason, call tools, and stop making things up." [SELF] — [GitHub](https://github.com/subhasmitasahoo)
- Personal site: post-training work on "multi-step reasoning, tool-use, factuality, helpfulness, and long-horizon tasks". Their focus includes synthetic data and "the design of evaluation and benchmarking systems". [SELF] — [subhasmitasahoo.com](https://subhasmitasahoo.com/)
- **Sources disagree on team and title.**
  - The site says "Staff Software Engineer on Google Search".
  - Medium says "working on Gemini post-training".
  - The LinkedIn snippet says "Research @ Google DeepMind" and Staff Research Engineer.

  [SELF] — [subhasmitasahoo.com](https://subhasmitasahoo.com/); [Medium about page](https://medium.com/@subhasmitasahoo.247/about); [LinkedIn (search snippet)](https://www.linkedin.com/in/subhasmitasahoo)
- Their blog favors "clear intuition, practical examples, and only as much depth as the problem needs". [SELF] — [subhasmitasahoo.com](https://subhasmitasahoo.com/)

**Shudhatma Jain**
- LinkedIn snippet: "Building Gemini for Home devices". The role is listed as "Gemini for Home devices Experience Software Engineer, Google DeepMind, Jun 2026 – Present, Mountain View". [SELF, search snippet only; page not fetchable] — [LinkedIn](https://www.linkedin.com/in/shudhatma-jain-4381012a)
- RocketReach lists earlier roles at Google and Microsoft. [2ND] — [RocketReach](https://rocketreach.co/shudhatma-jain-email_192758011)
- No public talks, posts or statements about demos were found.

**Oskar Yao**
- LinkedIn headline: "Investor and Capital Markets at Google". [SELF, snippet] — [LinkedIn](https://www.linkedin.com/in/oskar-yao)
- Listed on the team of Google's **AI Futures Fund**, which invests in AI startups and offers "Equity funding" and early access to DeepMind models. [ORG] — [AI Futures Fund, Google Labs](https://labs.google/aifuturesfund)
- They promoted an "APAC & Bay Area Startup & Investor Connect" mixer after I/O. [SELF, snippet] — [LinkedIn post](https://www.linkedin.com/posts/oskar-yao_apac-bay-area-startup-investor-connect-activity-7327775899016146944-eewi)
- At the May 2026 Google I/O Hackathon (same hosts, same venue and the same prize table), first place also won "a 30-minute virtual call with the deal team of Google's AI Futures Fund". [ORG] — [Google I/O Hackathon page](https://cerebralvalley.ai/e/google-io-hackathon)
- A LinkedIn post by Swaroop Mishra, "Loved judging the Google hackathon", tags Oskar Yao. I could not open it to learn which event it was. [2ND snippet] — [LinkedIn post](https://www.linkedin.com/posts/swarooprm7_loved-judging-the-google-hackathon-the-activity-7467078666687275009-rCAt)

**Ivan Leo (speaker)**
- X bio: "Developer Experience @GoogleDeepMind, Benchmarks @kaggle prev agents @manusai". [SELF] — [X @ivanleomk](https://x.com/ivanleomk/status/2113309071692681634)
- **Podcast "Agent's Hour", 29 July 2026.** As summarized from the podcast page:
  - Managed Agents was the first product they took "from first commit to launch", unveiled at I/O.
  - It gives developers the Antigravity harness Google uses internally.
  - "We give you a sandbox out of the box."
  - Sandboxes persist by default.
  - Their demos included a podcast generator and an agent that used a browser tool to shop for their room.
  - For more control, they suggest moving to a framework.

  [2ND, podcast page summary] — [Mastra podcast page](https://mastra.ai/podcasts/is-gemini-actually-a-coding-model-google-deepminds-ivan-leo-answers)
- Their posts from 22–24 October 2026 are personal. None is about the event. [SELF] — [X @ivanleomk](https://x.com/ivanleomk/status/2114045194064871775)

**What Google itself promotes for Managed Agents**
- The July 2026 expansion added:
  - environment hooks that "block, lint, or audit tool calls inside the sandbox";
  - `max_total_tokens` budget control, returning `status: "incomplete"` and resumable with `previous_interaction_id`;
  - scheduled triggers;
  - an Environments API.

  One customer example is OffDeal, whose `post_tool_execution` hook runs an image-verification pipeline inside the sandbox. [ORG] — [Google blog, 28 Jul 2026](https://blog.google/innovation-and-ai/technology/developers-tools/expanding-managed-agents-gemini-api-3-6-flash-hooks/)
- An earlier expansion added background execution and remote MCP. The launch was 19 May 2026. [ORG] — [Expanding Managed Agents](https://blog.google/innovation-and-ai/technology/developers-tools/expanding-managed-agents-gemini-api/); [Introducing Managed Agents](https://blog.google/innovation-and-ai/technology/developers-tools/managed-agents-gemini-api/)

### Inferences
- [INF] **Carrasqueira**: open with the user and the "why" in about 15 seconds, and make sure the demo pays off the exact hook you promise. If the pitch says "the room you're standing in", the judge's own clip has to produce something visible before time runs out. Otherwise, say in one sentence what the clip will show and switch to the saved live run.
- [INF] **Sahoo**: their stated work is factuality, tool use and evaluation design. Expect: "How do you know Argon didn't invent a door?" and "Is the loop score real?"
  - The plan already has the right answers: evidence timestamps, the "model-reported" label on `discrepancy_count`, and an answer-key benchmark with precision, recall and width MAE.
  - Put the benchmark table one click away, not at the end. Quote one number from memory, for example "exit recall went from X static to Y agentic+loop on three venues".
- [INF] **Jain**: building Gemini for home devices makes them a natural audience for "a phone understands a physical space". Expect "would this work in a home?" A defensible answer is a second benchmark venue that is a domestic-scale space, with the same cannot-measure caveats. Don't drift into medical or elder-care claims; medical advice is banned.
- [INF] **Yao**: an investor at the AI Futures Fund, and I/O's first place included a Fund deal-team call. Prepare a two-sentence market answer: who pays, how often the job recurs, and why existing practice (a manual walk with a clipboard) fails. Don't invent market numbers; use only figures you can source.
- [INF] **Managed Agents prize**: Ivan Leo's framing is the hosted sandbox and harness. Google's own posts stress hooks, budgets, resumption and auditability. WalkTwin's agent currently uses only client-executed function tools.
  - To read as a strong *managed-agent* use, show the call ledger, `max_total_tokens` with an honest `incomplete` path, and resumption via `previous_interaction_id`.
  - Optionally add a `pre_tool_execution` hook in `.agents/hooks.json` that denies any non-whitelisted sandbox action, and show one denial. It must be probed first, and the plan's rule that "the managed agent receives text only" still holds.

### Gaps
- No public statement from Jain, Sahoo or Yao about what makes a good hackathon demo was found.
- Sahoo's exact team (Search vs DeepMind) is unresolved; their own pages conflict.
- Who judges round one in the rooms, and who judges the Managed Agents prize, is not published.
- Ivan Leo's speaker-session content for today was not found.
- I could not identify which Cerebral Valley × Google DeepMind event took place on 8 November 2025, the one Carrasqueira's advice post refers to.

---

## 2. What did recent Cerebral Valley / Google winners build in video, 3D/world, spatial and twin projects, and what did their demos show?

### Takeaway
From August to October 2026 there were no new Google-hosted Cerebral Valley hackathons with published galleries. The most recent Google ones are I/O (23 May), DeepMind Bangalore (11 July) and the Zero to Agent series. The closest recent signals come from OpenAI's GPT-6 Astra events (September), Crusoe (October) and AIEWF (June).

In those galleries, 3D/twin entries placed when the 3D output fed a **measured or actionable verdict**:
- SplatForge: physics success rate;
- Nirman.AI: a costed bill of quantities traced to dimensions;
- Wayfinder: a route;
- Homebuddy: furniture placed in your own home.

The two **render-vs-reference self-critique loops** at GPT-6 Astra SF (Recurse.run, Farallon) **did not place**. A critique loop alone is not a differentiator.

### Cited Findings

**Google-hosted events closest to this one**
- **Google I/O Hackathon** (23 May 2026, SHACK15; same prize table plus the AI Futures Fund call). The award field shows:
  - 1st: Billie Gene (vaccine design);
  - 2nd: #113, the drone rescue entry (Sky Guardian);
  - 3rd: #115, "An RL environment to help train your managed agents in your voice";
  - finalists include #10, the Autonomous Infrastructure Auditor, and Gemini Lifeguard Rescue.

  **No "Managed Agents" track label appears in the award data**, so that track's winner is unverified. [ORG] — [I/O gallery](https://cerebralvalley.ai/e/google-io-hackathon/hackathon/gallery); [I/O event page](https://cerebralvalley.ai/e/google-io-hackathon)
- **Autonomous Infrastructure Auditor** (I/O finalist): a "District Orchestrator" dispatches three specialist agents over real terrain elevation data. Gemini vision confirms hazards in Street View, and findings are "anchored to specific ADA code sections". [TEAM] — [I/O #10](https://cerebralvalley.ai/e/google-io-hackathon/hackathon/gallery/10)
- **Google DeepMind Bangalore** (11 July 2026, 160 projects). The award field shows:
  - 1st: Kahani (browser adventure game);
  - 2nd: Nirman.AI;
  - 3rd: Project Parallax (adaptive cinema).

  About 15 AI-video-studio entries, including Continuity ("verification and version-control layer for AI-generated video"), show no award. [ORG] — [Bangalore gallery](https://cerebralvalley.ai/e/google-deepmind-bangalore-hackathon/hackathon/gallery)
- **Nirman.AI** (Bangalore 2nd). Its demo flow:
  - upload a real government blueprint;
  - click an element and ask a question;
  - "Truth-3D" rebuilds it as a measurable model, with "every solid's size traced to a figured dimension";
  - "If a dimension isn't on the drawing, it says so";
  - a five-agent pipeline writes a costed bill of quantities into a Google Sheet;
  - the headline is "15-day manual takeoff into a 3-minute autonomous one".

  [TEAM] — [Bangalore #9](https://cerebralvalley.ai/e/google-deepmind-bangalore-hackathon/hackathon/gallery/9)
- **Zero to Agent SF**: 1st, blartclaw (watcher subagents per livestream); 2nd, the Adorable World custom-order agent. [ORG] — [Zero to Agent SF gallery](https://cerebralvalley.ai/e/zero-to-agent-sf/hackathon/gallery)

**GPT-6 Astra SF** (8 September 2026, 72 projects)

Judges: Urvashi Barooah, Pranav Reddy, Romain Huet, swyx, Lan Xuezhao. [ORG] — [Astra SF project page header](https://cerebralvalley.ai/e/openai-gpt-6-astra-sf/hackathon/gallery/17)
- **1st, CAD Sandboxes**: Fusion runs in a VM behind an HTTP interface, with a "realtime stream of the workspace state" and a split-screen terminal viewer. [ORG award + TEAM] — [Astra SF #17](https://cerebralvalley.ai/e/openai-gpt-6-astra-sf/hackathon/gallery/17)
- **2nd, Homebuddy**: "creates 3D renders of your living spaces" and furniture models from catalogs, placed "in a simulated version of your home". [ORG award + TEAM] — [Astra SF #41](https://cerebralvalley.ai/e/openai-gpt-6-astra-sf/hackathon/gallery/41)
- **3rd, Pearl Atlas** (immersive travel). **Finalists**: Astra(l) Projection (hardware → interactive 3D explanations) and a surgical-robot data entry. [ORG] — [Astra SF gallery](https://cerebralvalley.ai/e/openai-gpt-6-astra-sf/hackathon/gallery)
- **No award, Recurse.run**: "builds a model, renders it, compares the result with the reference, and tries again". It runs in Blender, with an "inspectable history of its attempts". [TEAM; no award in ld+json] — [Astra SF #47](https://cerebralvalley.ai/e/openai-gpt-6-astra-sf/hackathon/gallery/47)
- **No award, Farallon**: an AI-written geological history generates a 3D model, "visually compares it with ground-truth data" and infers changes. [TEAM; no award] — [Astra SF #2](https://cerebralvalley.ai/e/openai-gpt-6-astra-sf/hackathon/gallery/2)
- **No award**:
  - Safechess: image or splat → segmented 3D → MuJoCo → robot arm → real world;
  - GameScene3D;
  - Robo World;
  - SILTAdesign.

  [TEAM; no award] — [Astra SF #49](https://cerebralvalley.ai/e/openai-gpt-6-astra-sf/hackathon/gallery/49); [Astra SF gallery](https://cerebralvalley.ai/e/openai-gpt-6-astra-sf/hackathon/gallery)

**GPT-6 Astra London and NYC**
- **London 3rd, Wayfinder** (the nearest direct analog):
  - organisers "upload a 3D scan and label destinations";
  - the app compares phone camera images with reference views to locate the user and route them;
  - there are no QR codes or added hardware;
  - the MVP "demonstrates this workflow in the internal event space".

  [ORG award + TEAM] — [Astra London #28](https://cerebralvalley.ai/e/openai-gpt-6-astra-london/hackathon/gallery/28)
- **London finalist, The Object Knows**: it separates "observed, inferred, externally supported and still unknown". When evidence is short, it asks for "the most useful physical observation needed next". It also "refuses to treat proximity as proof". [ORG award + TEAM] — [Astra London #8](https://cerebralvalley.ai/e/openai-gpt-6-astra-london/hackathon/gallery/8)
- **NYC 1st, Astra HQ**: "watch them collaborate, and approve their work". **NYC 2nd**: Counterfactual Worlds. [ORG award + TEAM] — [Astra NYC gallery](https://cerebralvalley.ai/e/openai-gpt-6-astra-nyc/hackathon/gallery)

**Other events**
- **AIEWF Hackathon** (June 2026), **1st SplatForge**:
  - a phone pointed at a tabletop becomes a Gaussian-splat "digital twin";
  - a VLM critic gives pass/fail on each rollout;
  - success is measured in MuJoCo by whether the mug clears a height threshold;
  - "a Gaussian Splat is a renderer, not a physics engine";
  - a live success-rate curve climbs on screen.

  [ORG award + TEAM] — [AIEWF #18](https://cerebralvalley.ai/e/aiewf-hackathon-2026/hackathon/gallery/18)
- **Crusoe Recursive Agents** (October 2026):
  - 1st, Etch (one sentence → real circuit board);
  - 2nd, SPARKLETEAM (self-improving dishwasher-loading team that "measured which" beliefs held);
  - 3rd, AGI Factory (keeps a change "only when unseen factory months prove it better and safer").

  [ORG award + TEAM] — [Crusoe gallery](https://cerebralvalley.ai/e/crusoe-recursive-agents-hackathon/hackathon/gallery)
- **fal × Sequoia virtual** (17 July 2026): finalists are almost all generated short films, plus Formbar (a rough 3D clay scene lifted from a photo to steer video). [ORG] — [fal × Sequoia gallery](https://cerebralvalley.ai/e/fal-x-sequoia-virtual-hackathon/hackathon/gallery)

### Inferences
- [INF] Across these galleries, the 3D twin was rewarded when it was the **setup for a measured answer to a practical question**, not the deliverable itself. SplatForge says this outright: the splat renders and the physics engine measures. WalkTwin has the same split (render critique fixes the graph; solver and checker measure egress), and the pitch should say it in one line: "the twin is how Argon checks its own reading; the solver is how we measure."
- [INF] **Wayfinder** and **Homebuddy** placed with phone and space twins at events judged largely by investors. A "your own room, from your own phone" hook is legible to non-specialists.
- [INF] **Recurse.run** and **Farallon** are the closest precedents for "render, compare, fix" and did not place. WalkTwin should not lead with the loop. Lead with the user's decision (doors tonight), and present the loop as the reason the extraction can be trusted, backed by the static vs agentic vs agentic+loop benchmark.
- [INF] Nirman.AI's mechanics match WalkTwin's plan:
  - dimensions traced to source;
  - "says so" when a dimension is missing;
  - click an element to jump to its source.

  WalkTwin's evidence timestamps that seek the video are the video-native version, and should be shown early (plan step 0:30).

### Gaps
- No Google-hosted Cerebral Valley gallery from August–October 2026 was found in the hackathons list, so "recent Google" evidence stops at July 2026.
- Gallery descriptions are team-written. Whether demos ran live, and what judges said about them, is not recorded.
- I did not watch the YouTube demo videos (Recurse.run, Farallon, Safechess), so I can't say why they didn't place.
- The I/O Managed Agents track winner is not in the award data.

---

## 3. Are there public posts or documents about this event, its problem statements or the Builder Guide that reveal what Google wants?

### Takeaway
Yes, two organizer documents are public, the event page and the Builder Guide, and both are explicit.
- **The event page** asks for "something that wasn't possible last week".
- **The Builder Guide** sets four tests: a named real person, work that needed Argon, humans kept in control of external actions, and a live run with real inputs in under 3 minutes.

The guide explicitly names autonomous verification loops, 3D/WebGPU generation, multi-agent orchestration and **agentic video understanding** as Argon's strengths. I could not find a public copy of the problem statements, including "Problem Statement Two, More Dimensions". They exist locally only as quoted in the team's plan.

### Cited Findings
- **Event page.** The topics are "advanced reasoning and visual coding to robotics and world models". It says: "We're looking for ambitious projects that push Argon to its limits", and "We want to see something that wasn't possible last week." [ORG] — [Event page](https://cerebralvalley.ai/e/gemini-4-argon-sf)
- **Builder Guide (public Google Doc; fetched as text on 25 October), the four tests**:
  - "Judges score working demos, not slide decks."
  - Test 1: "solves a specific problem for a real person you can name".
  - Test 2: it does work that needed Argon. The guide's list: long-horizon coding, autonomous verification loops, multi-file synthesis, 3D and WebGPU generation, or multi-agent orchestration.
  - Test 3: "keeps people in control when taking actions that affect external systems", money or private data.
  - Test 4: "runs live during judging with real inputs in under 3 minutes".

  [ORG] — [Builder Guide](https://docs.google.com/document/d/1kN0n6hPNNTIHMVqf5-hDACrZuIg4KFrWiYpla4WQW8w)
- **Builder Guide, patterns.**
  - Pattern 2, "Give Argon a verification loop": "Argon performs best when it can test its own changes" against a pass or fail signal. It suggests recording a baseline score and iterating "until every check passes with zero regressions".
  - Pattern 3: pass reference images for 3D scenes (Blender, Three.js, WebGPU). Argon's agentic video understanding "scrubs across timestamps, inspects high-resolution frames".
  - Pattern 4: Argon as lead orchestrator, with `gemini-3.8-flash` subagents for parallel leaf tasks.

  [ORG] — [Builder Guide](https://docs.google.com/document/d/1kN0n6hPNNTIHMVqf5-hDACrZuIg4KFrWiYpla4WQW8w)
- **Builder Guide, managed agents.**
  - Managed agent ID `antigravity-preview-09-2026`, with `"model": "gemini-4-argon"`.
  - The sandbox "plans, writes code, verifies its own output, searches the web and calls MCP tools".
  - API tokens go through the Credentials API and a network allowlist, so secrets "never enter the model context".

  [ORG] — [Builder Guide](https://docs.google.com/document/d/1kN0n6hPNNTIHMVqf5-hDACrZuIg4KFrWiYpla4WQW8w)
- **Builder Guide, closing tip.** Before the final demo, have Argon "generate an interactive HTML architecture diagram or pipeline walkthrough". [ORG] — [Builder Guide](https://docs.google.com/document/d/1kN0n6hPNNTIHMVqf5-hDACrZuIg4KFrWiYpla4WQW8w)
- **Argon model page.** "Agentic video understanding" is supported but "defaults to `static`". [ORG] — [Gemini 4 Argon model docs](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon) (local snapshot: `CLAUDE_BUILD_HANDOFF/reference/google/argon-model.md`)
- **Cerebral Valley announcements** on X and LinkedIn: "Gemini 4 Argon just launched." They mention $20,000 in cash prizes and "next weekend on Sunday, October 25th". [ORG] — [CV on X](https://x.com/cerebral_valley/status/2111170787323605298); [CV on LinkedIn](https://www.linkedin.com/posts/cerebralvalley_gemini-4-argon-just-launched-you-know-what-activity-7516935346987667456-fk5G)
- **Launch timing.** Carrasqueira posted "Gemini 4 Argon is here 🔥" on 13 October 2026 [SELF] — [X](https://x.com/jocarrasqueira/status/2110065213559148981). Secondary sources say a restricted preview was announced on 30 September and broad availability came on 13 October. [2ND] — [llmreference](https://www.llmreference.com/model/gemini-4-argon); [mezha.ua](https://mezha.ua/en/news/google-gemini-4-argon-316145/amp/)
- **X search.** A search of X for 15–25 October posts about the event returned nothing. That is not proof that none exist. [2ND] — x-com posts/search via Firecrawl, 25 Oct

### Inferences
- [INF] The guide's test 2 list reads almost like WalkTwin's architecture: agentic video understanding, a verification loop against a pass/fail signal, and 3D/WebGPU. The most direct way to score "only possible with Argon" (15%) is the plan's ablation, **static fps=1 vs `processing: "agentic"` vs agentic+loop on tape-measured answer keys**. It matches Google's own advice to "record a baseline score" and iterate. Put the three numbers on one line in the demo.
- [INF] Test 3 (people in control) is already met by Accept and Approve, `expected_revision` with 409, and "DRAFT — not sent". Say it aloud once: "nothing leaves this laptop; you approve." Don't spend more time on it.
- [INF] "Wasn't possible last week" favors the judge's own fresh clip over the pre-baked venue. If the clip is too slow, say the measured stage time ("this takes about N minutes; here's the run from 9:40 this morning") instead of promising a result in 3 minutes.
- [INF] Optional: an Argon-generated pipeline walkthrough page is a Google-suggested asset. Only use it in Q&A, because "no slides" applies and dashboards as the main feature are banned.

### Gaps
- The participant guide containing the problem statements, the banned-project list and the 50/25/15/10 weights was not found publicly. These come only from the user's brief and the plan's quotation, and I could not verify them.
- No Discord previews were accessible.

---

## 4. What failure modes do Cerebral Valley and Google judges cite?

### Takeaway
Published judge statements about failure modes are sparse. The organizer-stated ones are:
- slides instead of a working demo;
- no specific named user;
- a demo that doesn't run live with real inputs in under 3 minutes;
- not delivering on the hook you set up.

Gallery evidence adds a softer pattern. Broad creative tools (about 15 video studios at Bangalore) and generic 3D generators (Astra SF) were common and mostly unplaced. Narrow, measured, physically grounded projects placed.

### Cited Findings
- "Judges score working demos, not slide decks." The guide also requires a live run "with real inputs in under 3 minutes" and a problem for "a real person you can name". [ORG] — [Builder Guide](https://docs.google.com/document/d/1kN0n6hPNNTIHMVqf5-hDACrZuIg4KFrWiYpla4WQW8w)
- Carrasqueira's post:
  - judges "primarily focus on the demo";
  - "deliver on that hook!";
  - if the demo falls short, share how you'd take it further. This implies an incomplete demo is survivable if handled honestly.

  [SELF] — [X post](https://x.com/jocarrasqueira/status/1987577252725543314)
- Unplaced crowded categories:
  - Bangalore: roughly 15 AI video/film studio entries; only Parallax placed (3rd).
  - Astra SF: about 16 3D/spatial entries; only CAD Sandboxes (1st) and Homebuddy (2nd) placed, plus Astra(l) Projection as a finalist.

  [ORG award data; category counts are my reading of descriptions] — [Bangalore gallery](https://cerebralvalley.ai/e/google-deepmind-bangalore-hackathon/hackathon/gallery); [Astra SF gallery](https://cerebralvalley.ai/e/openai-gpt-6-astra-sf/hackathon/gallery)
- **From a different event (MongoDB/Cerebral Valley, January 2026; local team research).** The first-place JustPrice finals call was pre-recorded, and labelled replay appeared to be tolerated. The same research concludes judges "score what they can see in about 5 minutes". [2ND, local] — `/Users/charlie/hackathons/expunge/RESEARCH-REPORT.md` (lines 125, 375, 416); not organizer-verified

### Inferences
- [INF] The likeliest WalkTwin failure is **latency**. Agentic video extraction plus the critique loop plus a managed agent all have to fit in about 3 minutes in round one. The plan's saved-live-run fallback is right. Label it with its timestamp, and have the judge's clip running in the background from 0:15.
- [INF] A second risk is **scope sprawl**: video → graph → twin → loop → solver → agent → approval → ADA report → ops note. That is nine nouns in 180 seconds.
  - Rehearse a version with three beats: the twin built from this room, fire on the exit, and the agent finds a fix that you approve.
  - Leave the loop rows, the ADA rows and the report for Q&A.
- [INF] A third risk is the **dashboard look**, since dashboard-as-main-feature is banned. Keep the 3D twin and the video as the hero. Show the requirements table for no more than 10 seconds, or only when asked.
- [INF] A fourth risk is **failing to "deliver on the hook"**: if the walkthrough misses an exit, the twin must show "unreachable / not filmed". The plan's review focus #1 covers this. Turn it into a feature by saying "it tells you what it didn't see".

### Gaps
- I found no Cerebral Valley-published list of judge feedback or common failures, and no post-event judge commentary from the August–October 2026 events.

---

## 5. What would most likely be judged "never built before" for video → 3D twin → verified analysis, compared with what has already won?

### Takeaway
Each component has precedent:
- phone scan → twin: SplatForge, Wayfinder, Homebuddy;
- render-vs-reference critique: Recurse.run, Farallon, SplatForge's VLM critic;
- ADA rules with citations: the Infrastructure Auditor and HomeReady;
- "says so when it can't see it": Nirman.AI, The Object Knows.

What has not appeared in the galleries reviewed is the full chain. A **minutes-long handheld walkthrough video**, read with agentic video understanding, becomes a **topological venue graph with timestamped evidence for each door**. The critique corrects **structure** (missing or extra doors and exits), not appearance, against the source frames. The output feeds a **deterministic egress solver with an independent checker** under a hazard the judge places, plus a managed agent that tests only allowed interventions. Finally, an answer-key benchmark shows the agentic loop beats static extraction.

### Cited Findings
- Phone-to-twin precedents:
  - SplatForge (phone → splat twin, then physics-measured success) [ORG+TEAM] — [AIEWF #18](https://cerebralvalley.ai/e/aiewf-hackathon-2026/hackathon/gallery/18);
  - Wayfinder (organiser 3D scan, camera-vs-reference localization, routing) [ORG+TEAM] — [Astra London #28](https://cerebralvalley.ai/e/openai-gpt-6-astra-london/hackathon/gallery/28);
  - Homebuddy (3D renders of your living space) [ORG+TEAM] — [Astra SF #41](https://cerebralvalley.ai/e/openai-gpt-6-astra-sf/hackathon/gallery/41).
- Render-critique-loop precedents (both unplaced): Recurse.run [TEAM] — [Astra SF #47](https://cerebralvalley.ai/e/openai-gpt-6-astra-sf/hackathon/gallery/47); Farallon [TEAM] — [Astra SF #2](https://cerebralvalley.ai/e/openai-gpt-6-astra-sf/hackathon/gallery/2).
- ADA-anchored audit precedent: the Infrastructure Auditor (I/O finalist) [TEAM] — [I/O #10](https://cerebralvalley.ai/e/google-io-hackathon/hackathon/gallery/10).
- Traced-measurement precedent: Nirman.AI's "Truth-3D", with each size traced to a figured dimension (Bangalore 2nd) [TEAM] — [Bangalore #9](https://cerebralvalley.ai/e/google-deepmind-bangalore-hackathon/hackathon/gallery/9).
- Epistemic-separation precedent: The Object Knows (observed / inferred / unknown; asks for the next observation) [TEAM] — [Astra London #8](https://cerebralvalley.ai/e/openai-gpt-6-astra-london/hackathon/gallery/8).
- Argon's agentic video mode defaults to static, so it must be requested. The Builder Guide frames agentic video understanding as scrubbing timestamps and inspecting high-resolution frames. [ORG] — [Argon model docs](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon); [Builder Guide](https://docs.google.com/document/d/1kN0n6hPNNTIHMVqf5-hDACrZuIg4KFrWiYpla4WQW8w)
- The earlier analysis finds 3D/twin as a primary archetype has a 7% first-place rate (1 of 15). Verified engineering artifacts have 33%, and space/plan compliance audits 50% (n=6). [2ND, local] — `docs/research/winner-feature-analysis-2026-10-24.md` §3

### Inferences

**Framing**
- [INF] Pitch WalkTwin as a **space/compliance audit with a measured verdict**, the archetype with the highest first-place rate, whose input happens to be a phone video. Don't pitch it as a "3D twin" project; that archetype rarely won first. Suggested opening, about 12 words: "Every event moves the tables. Nobody re-checks the exits. Film the room."

**The originality claim to say aloud** (15% of the score)
- [INF] "Before Argon, the single-pass reading of this video missed N of M exits. With agentic video understanding and the critique loop, it found M of M, measured against our tape measure." Use the real benchmark numbers only.
- If the loop gives no gain on some venue, show that too. AGI Factory and SPARKLETEAM won with honest measured deltas, and an honest +0 builds trust with an evaluation-minded judge (Sahoo).

**Money shot** (one witnessed state change plus one number)
- [INF] The judge drops Fire on the main exit, and the hero number falls (for example from "120 of 120" to "N of 120 reach a modeled exit in 120 s · checked").
- The agent then proposes opening a specific door seen at a specific video timestamp. The judge clicks that evidence and watches the actual door in their own footage. They approve, and the number recovers.
- That chain is the part no prior winner had: video evidence → structural model → measured consequence → human decision.

**Distinguish the loop from Recurse.run and Farallon**
- [INF] Say it compares the twin with **the source video** and fixes **topology**: a door added, an exit kind corrected. Every patch is validated by local code, and a rejected patch is shown with its reason. Then point to the benchmark rather than the model-reported `discrepancy_count`.

**Managed Agents prize**
- [INF] Make the agent's work visible as checked tool calls: the ledger rows with call IDs, each one solved and then checked. Then one sentence: "the agent investigated; our checker measured; you approved."
- If time allows, after a live probe, demonstrate the Google-promoted controls: the `max_total_tokens` budget with resume, and a hook that denies an out-of-policy action. Ivan Leo's team built and promotes these. Don't claim hooks unless a receipt exists.

**Q&A prep**, one line per judge lens:
- **Sahoo:** "How do you know Argon didn't make up a door?" Answer: every element has a video timestamp, a human accepts the graph, and we report precision and recall against tape-measured keys.
- **Jain:** "Does it generalize beyond this venue?" Answer: the benchmark covers three venues; anything not filmed is reported as unreachable, never assumed.
- **Yao:** "Who pays?" Answer with the named user (event producer or venue ops lead), the recurring trigger (every layout change) and the current practice. Use no unsourced market sizes.
- **Carrasqueira:** "Did you deliver the hook?" Answer: the judge's own clip result appears at about 2:45, or its measured stage time is stated honestly.
- **Anyone:** "Is this safe or compliant?" Answer: the copy rules hold. "Reach a modeled exit in 120 s", "meets ADA §404.2.3 within measured range" or "cannot measure"; never "safe".

### Gaps
- I did not search outside Cerebral Valley (Devpost, ETHGlobal, academic demos) for video → egress-twin projects. "Never built before" is relative to the galleries reviewed here plus the 355-winner dataset.
- Whether judges at this event value the solver and checker depth or mainly the visual twin cannot be known in advance. The panel has no published scoring commentary.
- The real benchmark numbers do not exist yet; the claims above must be filled from `runtime/bench` output.
