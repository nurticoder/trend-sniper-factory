# Trend Sniper Factory

A local-first creator platform: **discover niches → analyze opportunities → develop original ideas and scripts → assemble video and sound → review → publish → learn from results**.

The goal is a browser dashboard that runs the workflow without asking a development chat to make each video. Designed for one creator, minimal recurring costs and limited time. Gaming Shorts are the first use case; DONT SPLASH and Poppy Playtime are example subjects, not fixed niches or verified growth opportunities.

![Control room with an explicitly labeled local example](docs/images/control-room.png)

## Start the dashboard

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[web,test]"
trend-sniper serve
```

Open **http://127.0.0.1:8765**. After installation, macOS users can double-click `start.command` to start the server and open a browser. Keep its terminal running while using the app; Ctrl+C stops it. Windows users activate `.venv\Scripts\activate` instead.

## What works today

- Responsive control-room board and searchable opportunity library.
- Create/edit/archive topics with a niche, hypothesis, reference link and dated manual evidence.
- Multiple original ideas per opportunity; editable hooks, payoffs, scripts, storyboards and audio cue sheets.
- Editorial stages: Idea → Writing → Script ready. Readiness requires a complete brief and never approves publication.
- Saved script history, stale-edit conflict detection, unsaved-change protection and JSON brief export.
- Local SQLite persistence across browser reloads and app restarts.
- Honest disconnected states for discovery, AI scripts, YouTube and analytics.
- The existing original Python/FFmpeg renderer remains available through its CLI, separate from this dashboard.

**Automatic discovery/analysis, model-generated scripts, media/sound selection, dashboard render jobs, OAuth publishing and analytics are not implemented yet.** Manual briefs are labeled manual. The included pool-puzzle video is a preserved technical fixture, not proof of audience demand.

## The essential platform

| Area | Purpose |
| --- | --- |
| Discover & analyze | Find accessible niches and breakout topics; show sources, velocity, competition and confidence |
| Ideas & scripts | Develop an original hook and payoff; produce an editable timed script, storyboard and audio cues |
| Media & sound | Select permitted visuals, voices, effects, meme-style stings and music for specific moments |
| Production | Run durable jobs, assemble shots, mix audio, add captions, preview, retry and track cost |
| Review & publishing | Check the exact output, audience and rights; privately upload and schedule approved work |
| Results | Compare actual same-age performance and cost; feed evidence into the next idea |

Read the [product direction and ordered build plan](docs/product/PLATFORM.md). First implementation slice: **a persistent control room and opportunity-to-script workflow**, before further video generation.

## Current stack

Buildless HTML/CSS/JavaScript interface, Python FastAPI service and SQLite. This first slice avoids a Node installation or frontend build; all static assets ship inside the Python package. The earlier React interface proposal is deferred until component complexity justifies it. No web font, CDN, paid provider or cloud database is used.

The server binds only to `127.0.0.1`, restricts Host headers and cross-origin writes, and serves same-origin assets with a content security policy. It is a **single-user local tool without authentication**, not a public hosting configuration. Do not expose it through a tunnel or bind it to a public interface.

App data is stored in ignored `local-data/control-room.sqlite3` relative to the launch directory. Choose another database with `trend-sniper serve --db PATH` or the exported `TSF_DB_PATH` environment variable. `.env` files are not automatically loaded. Stop the server before copying the SQLite database for backup; keep backups private and outside Git. The browser QA example on the development machine is explicitly labeled “Example”; a fresh checkout/database starts empty.

## Check the project

```sh
python -m unittest discover -s tests -v
```

Nine tests cover real media roundtrip, persistence after a new app instance, evidence validation, archival behavior, script readiness, version history, stale edits, export, local-request boundaries and static files. Browser QA covers create/edit/save/reload, search, library navigation, version history and the actual downloaded JSON on mobile/desktop breakpoints. See [control-room verification](docs/control-room-validation.md).

## Existing renderer

For installation, commands, output format, batch generation and local review/queue usage, see the [render engine guide](docs/render-engine.md). These are developer commands, not the finished platform interface. No new video is generated just by opening this project or reading the docs.

## Development workflow

Every feature starts on a named branch. Commit and push meaningful working increments, run relevant checks, then open a pull request. See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md). No artificial commits, backdating or empty pushes.

Current milestone: the control room is implemented on `feat/control-room`. Next slice: evidence-backed opportunity analysis and provider adapters; no credentials are needed for manual work.

## Rights, cost and honest scope

All production assets must carry permission evidence; popular meme sounds are not automatically free to reuse. Default to owned, licensed or original synthesized audio. An asset licensed only for YouTube's native Shorts creation flow cannot be assumed usable in an exported MP4.

Originality, audience designation and publication decisions require real review. No trend, monetization or income guarantees. Paid provider calls must be optional, budgeted and visible. Source code is MIT; dependencies retain their own licenses. See [third-party notices](THIRD_PARTY_NOTICES.md), [research](docs/research.md) and [baseline validation](docs/validation.md).
