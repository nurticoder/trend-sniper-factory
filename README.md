# Trend Sniper Factory

A local-first creator platform: **discover niches → analyze opportunities → develop original ideas and scripts → assemble video and sound → review → publish → learn from results**.

The goal is a browser dashboard that runs the workflow without asking a development chat to make each video. Designed for one creator, minimal recurring costs and limited time. Gaming Shorts are the first use case; DONT SPLASH and Poppy Playtime are example subjects, not fixed niches or verified growth opportunities.

![Production desk with a completed local QA preview](docs/images/production-desk.jpg)

## Production workers

[Research and automation plan](docs/product/AUTOMATION.md) · [Worker operations, media licenses and release scheduling](docs/product/OPERATING.md)

Choose a niche and produce a private preview. New discovery runs retain competing scripts, scene material decisions, twelve covers and a release-time proposal. The control room exposes the worker report. Daily previews and reviewed owner-channel scheduling are optional.

## Start the dashboard

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[web,test]"
trend-sniper serve
```

Open **http://127.0.0.1:8765**. After installation, macOS users can double-click `start.command` to start the server and open a browser. Keep its terminal running while using the app; Ctrl+C stops it. Windows users activate `.venv\Scripts\activate` instead.

## What works today

The homepage is a scrolling niche explorer built from dated public YouTube channel observations. Picks span gaming, education, news, stories and other subjects. Each shows its production format, reference images, original video links, source date and measured lifetime pace or change between observations. Discovery covers a seeded channel set. An observed audience for reference material is not proof of demand for the adapted format. Scans refresh daily while the app runs.

Choose a niche, then **Produce a Short**. Rankings and news compare up to 100 source-constrained cuts. Fiction uses an optional local model with an honest built-in fallback. The factory matches cleared media, generates and selects among twelve covers, compiles original graphics with captions and timed sound, verifies the MP4, and proposes a release time. A fresh install needs no paid provider. Optional local Piper narration measures speech first, extends scene timing and lowers music during speech. It is installed and verified on the development machine; fresh installations can add it with the setup below.

**The control room** is the production desk: pause or resume the queue, stop jobs, retry from saved inputs, inspect activity/runtime/spend, filter episodes and review completed previews. The worker report contains script comparisons, a timed storyboard, material decisions, covers and release details. Waiting jobs survive a restart. Interrupted jobs keep their inputs for an explicit retry. Run one local server per database.

Daily private previews are opt-in and skip reused source sets. Scheduling requires owner OAuth and review of the exact finished artifacts, audience and disclosure. The transport is implemented but has only been tested with simulated uploads. Live analytics ingestion is not connected. A saved credential is shown separately from verified access.

The Steam chart renderer remains available within the same homepage at `/#steam`. It produces original chart graphics from dated Steam observations. Previous manual briefs are preserved inside the control room.

## Optional offline voice

```sh
pip install -e ".[voice]"
trend-sniper install-voice
```

This explicit setup downloads a checksum-pinned English voice (about 64 MB) from the upstream model repository. No model downloads occur during production. In Control room, choose **Local voice when available**, **Require local voice**, or **Captions and music only** for new niche previews. Retry attempts preserve their original preference. An unavailable/failed provider is recorded as a fallback, or fails the job when voice is required. [Voice operation and verification](docs/local-narration-validation.md).

## The essential platform

| Area | Purpose |
| --- | --- |
| Discover & analyze | Find accessible niches and breakout topics; show sources, velocity, competition and confidence |
| Ideas & scripts | Develop an original hook and payoff; produce an editable timed script, storyboard and audio cues |
| Media & sound | Select permitted visuals, voices, effects, meme-style stings and music for specific moments |
| Production | Run durable jobs, assemble shots, mix audio, add captions, preview, retry and track cost |
| Review & publishing | Check the exact output, audience and rights; privately upload and schedule approved work |
| Results | Compare actual same-age performance and cost; feed evidence into the next idea |

Read the [product direction and ordered build plan](docs/product/PLATFORM.md). The implemented production slice is described in the [automation plan](docs/product/AUTOMATION.md).

## Current stack

Buildless HTML/CSS/JavaScript interface, Python FastAPI service and SQLite. This first slice avoids a Node installation or frontend build; all static assets ship inside the Python package. The earlier React interface proposal is deferred until component complexity justifies it. No web font, CDN, paid provider or cloud database is used.

The server binds only to `127.0.0.1`, restricts Host headers and cross-origin writes, and serves same-origin assets with a content security policy. It is a **single-user local tool without authentication**, not a public hosting configuration. Do not expose it through a tunnel or bind it to a public interface.

App data is stored in ignored `local-data/control-room.sqlite3` relative to the launch directory. Choose another database with `trend-sniper serve --db PATH` or the exported `TSF_DB_PATH` environment variable. `.env` files are not automatically loaded. Stop the server before copying the SQLite database for backup; keep backups private and outside Git. QA runs use a separate database under ignored `work/`. A fresh checkout starts without production jobs or a channel connection.

## Check the project

```sh
python -m unittest discover -s tests -v
```

The suite covers media roundtrip, validated briefs, source-grounded cuts, cover generation, licensed fragment/audio selection, queue capacity, restart recovery, concurrent retries, cancellation and review-bound publishing with simulated transport. Browser QA covers the choose → pause → cancel → retry → resume → private-preview journey and readable edit review. See [production-desk verification](docs/factory-operations-validation.md).

## Existing renderer

For installation, commands, output format, batch generation and local review/queue usage, see the [render engine guide](docs/render-engine.md). These are developer commands, not the finished platform interface. No new video is generated just by opening this project or reading the docs.

## Development workflow

Every feature starts on a named branch. Commit and push meaningful working increments, run relevant checks, then open a pull request. See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md). No artificial commits, backdating or empty pushes.

Current milestone is local narration on `feat/local-narration`: pinned voice setup, speech-aware scene timing, background ducking and reviewable speech provenance, on top of the durable production desk. Live channel authorization and audience measurement remain account-dependent.

The control room now supports pause/resume, cancellation, retries from saved sources, activity history and searchable previews. The worker report shows leading script candidates and a timed storyboard with source/audio decisions. [Operating guide](docs/product/OPERATING.md) · [Verification](docs/factory-operations-validation.md).

## Rights, cost and honest scope

All production assets must carry permission evidence; popular meme sounds are not automatically free to reuse. Default to owned, licensed or original synthesized audio. An asset licensed only for YouTube's native Shorts creation flow cannot be assumed usable in an exported MP4.

Originality, audience designation and publication decisions require real review. No trend, monetization or income guarantees. Paid provider calls must be optional, budgeted and visible. Source code is MIT; dependencies retain their own licenses. See [third-party notices](THIRD_PARTY_NOTICES.md), [research](docs/research.md) and [baseline validation](docs/validation.md).

### Format studio

The current homepage filters daily observations to five automatic production recipes. Family drama, later-life letters and block-world quests use the local Ollama model `llama3.2:3b` when available. A built-in authored episode covers an offline model. News desk attributes dated headline cards to the reporting channel. Countdown ranks the observed reference uploads by recorded views. Source thumbnails stay in the research interface. Each output uses original motion graphics, on-screen text and synthesized sound. Select a card and press **Produce a Short** to queue the MP4. Publishing and audience review remain separate.

Daily scans compare the same videos across snapshots when available. Initial picks use lifetime views per day. Source-channel attention is a proxy for the proposed format, particularly when adapting family fiction for older viewers.
