# Production desk verification

Verified locally on November 4, 2026. This extends the production-worker prototype without a paid provider or public upload.

## Automated checks

All 30 tests pass. Nine new tests cover:

- Paused queue persistence and FIFO continuation after a new application instance.
- Cancellation before execution, immutable source reuse and concurrent retry deduplication.
- Cancellation during execution, including the race just before completion.
- Failed-job isolation so the following job still runs.
- Crash recovery that distinguishes interrupted work from waiting work.
- The twelve-active-job limit and transactional rollback of a blocked retry.
- Preservation of old finished previews, without fabricated timing or spend records.
- API state validation, missing records, cross-origin rejection and hidden cancelled artifacts.
- Unavailable local services and saved-channel reporting without exposing or reading token contents.

The existing suite continues to exercise MP4 encoding/decoding, source-backed script selection, covers, media clearance, fragment/audio timing, daily source deduplication and simulated publishing. New Python modules pass Ruff checks. Installed dependencies pass `pip check`.

## Browser check

An isolated database under ignored `work/worker-qa/` retained its two earlier previews. Through the UI, a physics countdown was selected while the queue was paused, cancelled before rendering, retried from its saved sources and resumed. The second attempt completed in 3.5 worker seconds with 100 cuts, twelve cover candidates and $0 paid-API spend. The first attempt remains in history. It is excluded from unresolved attention counts once superseded.

The finished report exposes script comparisons, the timed selected edit, source links, sound decisions, cover choices and the release proposal. Stage history shows the full journey. Title search and ready-only/attention filters were checked. Existing expanded review panels remained mounted when another job appeared. The same records remained available after restarting the test server.

Desktop and 390-pixel mobile layouts were inspected. Mobile document width equals viewport width (390 pixels). Browser error logs were empty during final inspection. Screenshots: [desktop](images/production-desk.jpg), [mobile](images/production-desk-mobile.jpg). These show actual isolated QA state, not a live channel.

A stale imported-script cache was observed during the browser pass. The update now sends no-store for local HTML/static assets as well as API responses and revises the entry-module URLs so an existing browser picks up this release.

## Practical limits

- This remains a single-process local prototype. SQLite preserves the queue; the machine must be awake and the app running to do work. An active FFmpeg/model operation completes before a requested stop takes effect.
- The QA run disabled online Commons lookup. Earlier coverage checks found no eligible online material. This change does not claim improved footage acquisition.
- Source-constrained rankings compare the sampled uploads' observed metrics. They do not independently explain or verify every subject discussed by those uploads. Draft scores are editorial heuristics.
- Current sound is synthesized music and timed effects. Spoken narration is not connected.
- Installed-model checks do not prove a generation will succeed. Saved OAuth files do not prove the current grant is valid. Live upload and analytics verification still require the channel owner.
- Historical/failed attempt spend is unknown. New successful previews use no paid APIs; device and electricity costs are excluded.

Next task: integrate a license-documented local narration provider with measured speech timing, ducked music and a clear fallback, then improve source-grounded editorial depth and cleared footage coverage.
