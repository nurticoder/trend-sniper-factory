# Trend Sniper Factory — product direction

## What we are building

A local-first browser platform for a solo creator. It discovers opportunities, develops original concepts and scripts, produces videos from a structured edit plan, places audio deliberately, and manages review, scheduling and results. The platform runs the factory; the development chat builds the platform. The user should not need to ask the chat to make each individual video.

The existing Python renderer is an experimental production component, not the finished product. Its fictional pool puzzle is a technical fixture, not proof that this format attracts viewers. Do not use the demonstration's creative quality as the target for the platform.

First audience: one student creator with little time and almost no budget. Start with gaming Shorts, but model niches and formats independently of specific games. DONT SPLASH and Poppy Playtime are possible subjects, not hardcoded business assumptions. No income or virality guarantees.

## Essential parts, in build order

| Part | What the user gets | Required result |
| --- | --- | --- |
| 1. Discover & analyze | A watchlist of niches, games, channels and breakout videos, with dated evidence and clear uncertainty | An opportunity brief: who watches, what is growing, what smaller channels can enter, how crowded it is and whether we can produce original work cheaply |
| 2. Ideas & scripts | Distinct video concepts with a hook, original angle, payoff and source-backed claims | A selected concept becomes a timed script, shot list and audio cue sheet, ready for production |
| 3. Asset & sound library | Searchable approved visuals, voices, sound effects, meme-style stings and music, with usable license records | Every chosen asset has permission evidence, attribution where needed, allowed platforms and commercial-use status |
| 4. Production factory | Jobs that create/gather permitted visuals, synthesize narration if enabled, assemble scenes, place audio, add captions and render | A preview, MP4, metadata, cost record, provenance manifest and actionable error/retry state |
| 5. Review & publishing | One review screen for the exact final video, title, rights, audience and schedule | Approved files can be privately uploaded and scheduled through the owner's OAuth connection; edited files require another review |
| 6. Results & learning | Same-age performance comparisons, watch-time/retention where available, and cost per output | Evidence about which niche, concept and format to try next, without inventing causal conclusions or earnings |

The dashboard is the shared workspace across all six parts. It shows real saved state: backlog, selected idea, script, production, review, scheduled, published, failed. Each stage links to its inputs and outputs, so failures do not require starting over.

## The decision loop

Discover → collect evidence → choose an opportunity → develop a concept → generate a script and edit plan → render → review → schedule → measure → improve the next opportunity.

An idea is not just a title. It contains a target viewer, original promise, hook, payoff, format, required visuals, rights risk and rough production cost. A script is not just narration: it also specifies what appears and what the viewer hears at each moment.

Discovery should distinguish:

- **Niche:** a repeatable viewer need, such as quick co-op horror challenges.
- **Topic:** a specific game, update, mechanic or community question.
- **Format:** a repeatable editorial structure, such as an explained challenge or original animated scenario.

A game can be popular while a particular format is saturated. A small niche can have a usable entry point even when it is not globally trending.

## How discovery earns trust

Start with seed games/channels/keywords, permitted API data and user-provided reference URLs. A saved report must show its source URLs, observation times, data coverage and missing fields. Comments/transcripts may supply research context where permitted; they are not raw material to copy into finished videos.

Look at multiple signals separately: recent velocity, video age, performance relative to a channel's usual reach, multiple independent breakout channels, smaller-channel access, search demand where available, competition, freshness, production feasibility and asset rights. Use observed histories; do not infer acceleration from one count. Show confidence and explanations before introducing a numerical ranking.

Keep public data distinct from owner-only analytics. Never present competitors' private retention, precise revenue or subscriber conversions as known. Do not require a paid intelligence subscription for the basic workflow. Optional provider adapters can enrich a report when authorized, available and within budget.

## Audio should be directed, not randomly sprinkled

The script/edit plan provides cues such as `reveal`, `mistake`, `tension_build`, `punchline`, `transition` and `silence`. Each cue records its timestamp or linked spoken word, intensity, maximum duration and whether narration is active.

The sound library stores tags for mood, comic function, tempo, intensity, length, loudness and license. A deterministic first version matches cue tags to eligible assets, offers a preview and records the selection. Later ranking can use semantic similarity, but permission checks always happen before ranking.

The editor trims and fades clips, avoids unwanted overlaps, ducks music under speech and checks peaks. A punchline cue lands on the intended event, not at an arbitrary scene boundary. The user can swap a cue's sound and rerender only the affected job.

“Meme sound” describes an editorial function, not a copyright exception. Do not extract commercial songs, film/TV dialogue or viral clips from other videos. Use owned recordings, clearly licensed assets, permitted library music or original synthesized alternatives. If a sound is licensed only inside YouTube's native Shorts tools, it cannot automatically be embedded into a standalone FFmpeg export. Retain track-specific permission evidence; do not assume every library item has the same terms.

## Platform shape and costs

Current first slice: buildless HTML/CSS/JavaScript browser interface, a Python FastAPI service, SQLite persistence and an independent local Python render worker using FFmpeg. One repository and one user first. React + TypeScript remains a possible later frontend migration; the initial interface needs no Node setup. No Redis, Kubernetes, paid database or subscription is required for the first slice.

SQLite stores opportunities, ideas, scripts, asset records, jobs, review decisions and results. Large media stays on disk outside Git. The database holds durable queued/running/completed/failed jobs with attempts and errors; an independent worker resumes or reconciles interrupted jobs. Heavy renders must not depend on an in-request background task staying alive.

Store a versioned edit plan linking shots, narration, captions, source references and audio cues. The UI and worker use the same validated contract. Keep provider adapters behind it so a local text model, optional paid model, licensed visual generator or alternate speech engine can be added without rewriting the factory. Chat subscriptions do not automatically supply application API access.

Rendering on the user's computer keeps initial hosting costs low, but the machine must be awake. Unattended production while it is off needs an always-on host and a separate cost decision. No always-on service, paid model call or publishing job is enabled during planning. Show estimated costs before paid jobs and measured spend afterward; allow per-job and daily limits.

## First platform milestone

Build the **control room and opportunity-to-script workflow** before extending video generation:

1. A locally running browser dashboard with persistent opportunities, ideas and job stages.
2. Add a niche/topic/reference URL; save real evidence and distinguish manual/imported/automatically fetched data.
3. Inspect a concise opportunity brief and select one concept.
4. Produce and edit a structured script, storyboard and audio cue sheet through a configurable provider. If no model is connected, say so and offer manual entry; do not return a fake “AI generated” success.
5. Persist the selected version and its links to evidence. Reloading the browser preserves work.

Acceptance: a creator can progress from a topic to an editable, saved production brief in the browser without asking the development chat to create a video. Empty and disconnected states are honest. This milestone does not need YouTube OAuth or a paid API.

Then connect the production worker, approved media/sound library and preview/review screen. Connect YouTube only after the platform can reliably manage its own inputs, outputs, failures and costs. Add the analytics feedback loop after the first real publication.

## Development sequence

| Branch | Deliverable | Completion evidence |
| --- | --- | --- |
| `docs/platform-foundation` | Product scope, prioritized milestones, contributor workflow | Clear platform direction and a reviewable PR |
| `feat/control-room` | Browser app, Python service, SQLite records and pipeline board | Create/edit/reload records; honest empty/error states |
| `feat/opportunity-analysis` | Source adapters, dated snapshots and evidence-backed briefs | Reproducible analysis with missing-data handling |
| `feat/script-studio` | Concept development, provider interface, versioned storyboard/audio contract | Editable saved script tied to evidence; no fabricated claims |
| `feat/media-library` | Rights records and cue-based sound/asset selection | Ineligible assets cannot enter a render plan |
| `feat/render-worker` | Durable jobs, assembly, timing, mix, preview and measured cost | Interrupted-job recovery and playable synchronized output |
| `feat/youtube-publishing` | Owner OAuth, private upload, approval-bound scheduling and recovery | Verified remote video ID without duplicate uploads |
| `feat/performance-feedback` | Dated analytics snapshots and equal-age comparisons | Real owner data and documented API coverage |

These are ordered slices, not a promise to build all modules in one chat. Split them further when a smaller change can be tested and reviewed independently. During exam season, prefer a completed useful slice over parallel unfinished subsystems.

## Intentionally postponed

Multi-user accounts, billing, mobile apps, a public hosted service, a visual editing suite, universal game simulators and autonomous mass publishing. The first format must still be original and worth watching. More automation cannot establish audience demand by itself.

## Control-room delivery status

Implemented in v0.2 on `feat/control-room`: the local browser board/library, opportunity/evidence forms, manual idea/script studio, version history, stage validation and JSON export. Records persist in SQLite and stale saves are rejected. The first slice intentionally exposes manual writing instead of pretending a generation provider is connected. Automatic opportunity analysis and script generation remain subsequent slices. The renderer is still CLI-only; there is no dashboard production worker.


## Production desk milestone — November 2026

The historical milestone notes above describe their original delivery, not the current capability set. Discovery formats now connect to local production, script/cover judging, media selection, private preview and reviewed OAuth scheduling. The production desk adds a persistent queue, source-frozen retry attempts, cancellation between stages, dated activity and honest provider readiness. The original manual brief workspace remains available as saved briefs. See [OPERATING.md](OPERATING.md) for current behavior and limits. Next prioritize a licensed local voiceover provider and richer source-grounded scripts before scaling output. Full analytics ingestion and live-channel upload verification remain outstanding.


## Local narration milestone — November 2026

Optional pinned Piper speech now runs inside niche production jobs. The worker measures utterances, adjusts scene/media/caption timing and ducks the music bed. Preference, fallback, model provenance and voice-only review are exposed in the platform. The independent legacy chart renderer stays unchanged. The next production-quality task is deeper source-grounded scripts and better matching of cleared visual material; live OAuth and analytics verification remain outstanding.


## Footage-led explainer milestone

Production studio now accepts a topic independently of discovery. The initial curated water-in-microgravity collection implements an original sourced explanation, explicit passage/shot contracts, multiple footage shots per passage, persistent voice-delivery auditions, measured speech timing, prominent smooth footage, phrase captions, original packaging and private review. Runtime scope is deliberately visible: subject writing and initial visual matches were authored/inspected for this pilot, not generalized autonomous research. Research, source footage, speech and prepared shots are reusable. See [pilot operating and validation notes](../footage-explainer-pilot.md).

## Reviewed topic-to-footage milestone

The creator selected Kokoro `af_heart` after auditions. New topic jobs prepare that local narration and scene-query footage candidates, then expose factual-source and visual review before dispatching to the existing smooth assembler. Native phrase captions replace per-frame image overlays. Missing footage or speech prevents this format from becoming a slideshow. Discovery remains seeded; general source research/fact checking and reliable arbitrary-topic footage coverage are unfinished. No publishing or volume expansion is included. See [current workflow and limits](../kokoro-footage-workflow.md).
