# Control-room verification — 2026-11-03

Implemented on `feat/control-room`, based on `docs/platform-foundation` (the foundation PR remains separate). The browser interface and Python service are real; discovery, AI, rendering integration, publishing and analytics remain disconnected.

## Automated checks

- Nine unittest cases pass on Python 3.14/macOS ARM.
- SQLite survives creation of a new app instance. Evidence dates require timezones, URLs are validated and unknown input fields are rejected.
- Script-ready requires hook/payoff/script/storyboard. Every script save preserves a version; stale idea and opportunity revisions return 409.
- Archive blocks new ideas until the opportunity is unarchived. Missing records return 404.
- JSON export contains the linked opportunity and current scripts. Host/origin restrictions, CSP, no-store responses and packaged static routes are checked.
- Existing renderer/queue regression tests still pass. Only the bounded two-second temporary media test runs; no new production video was created.
- Shell launcher syntax, dependency consistency, package assets and local Markdown links are checked before the push.

## Browser checks

- Fresh database showed an honest empty workspace and zero saved records.
- Created an explicitly labeled `Example: DONT SPLASH` opportunity with a fictional/manual hypothesis, no trend metrics or invented evidence.
- Created a complete manual script, storyboard and audio cue sheet. Moved it to Script ready and saved a second version.
- Reloaded the browser: the opportunity, script stage and revision remained saved.
- Switched between board/library, searched for a missing topic and verified the empty result; clearing search restored the record.
- Exported `production-brief.json` through the browser and parsed the actual downloaded file; it contains the linked example and version 2 of the script.
- Verified Connections lists the manual-only and not-connected states accurately.
- Inspected the mobile layout and the 1440×1000 desktop breakpoint; restored the browser's default viewport after testing. Screenshot is in `docs/images/control-room.png` and uses clearly labeled example content.

The QA example is local ignored app data, not a remotely fetched recommendation. Fresh installations start empty. There is no OAuth token, API key, paid service, remote upload, automatic script generation or trend-analysis score in this milestone.
