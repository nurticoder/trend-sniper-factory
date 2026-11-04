# Operating the production workers

Select a niche on Discover and choose **Produce a Short**. Open **Workers, covers & release plan** under the finished preview or in Control room. The panel links to the complete draft pool, cover contact sheet, selected cover, dated observations, edit decisions and proposed release window. Old previews and the standalone Steam chart renderer still work. Worker reports belong to new discovery runs.

## What executes

- Rankings and news build up to 100 distinct full cuts from the frozen channel sample. The editor measures source coverage, opening length, payoff, scene reading density and total runtime. These are deterministic editing variants of the observed story. A fact in a feed is evidence of a published upload and its observed metrics. Headline summaries do not independently verify events in the world.
- Fiction requests batches of five distinct four-beat scripts from local Ollama, to a maximum of 100 and a six-minute batch budget. A separate local model call can judge the five strongest rubric finalists. The report records the actual count and fallback. Without Ollama, one built-in story is available. A 100-script pool produces one episode.
- The collector searches Commons for cleared images or footage using up to two public source titles. It accepts CC0 metadata, records the file page and credit, verifies the bytes and requires a specific term match. Online video additionally needs two frames in a candidate window to pass a local subject-visibility check using an installed moondream model. Missing matches, offline services or absent vision models leave original visualizations available. There is no download of reference YouTube footage or audio. Set `TSF_COMMONS=0` to disable online media lookup. [Commons reuse guidance](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia)
- A local cleared library can contribute strictly bounded video fragments, photos, music and effects. The compiler uses the chosen material, includes credits in upload copy and records input hashes. An original musical pulse and timed accents are available on a fresh installation.
- Twelve covers are generated from the actual edit, then compared by text fit, contrast, visual detail and hook agreement. The winner appears in the first half-second and as a standalone JPEG. A contact sheet and each candidate's selection data are available for review. YouTube cover selection/upload is platform-dependent and separate from video scheduling.
- Every preview is encoded and decoded locally. Existing runs are preserved. Waiting jobs survive a restart. An interrupted running job keeps its source packet and can be retried from Control room.

## Daily private previews

After selecting a niche, enable daily previews to check it automatically while the local server runs. The scheduler can produce at most one new private preview per Hong Kong calendar day. It skips stale observations and previously used source sets. Stopping daily previews leaves existing artifacts intact. Daily preview generation and YouTube scheduling have separate controls.

## Local media catalog

Place media and a `catalog.json` array under `local-data/media-library/`, beside the dashboard database. Each entry describes one eligible moment or still. Multiple entries may describe different fragments of one file. Use exact subject/action descriptions for visuals and functional descriptions such as “reveal impact” for audio. Assets require one of `owned`, `CC0-1.0`, `CC-BY-4.0` or `public-domain`, a credit, permission evidence, source and the actual SHA-256 digest. The operator's clearance record is authoritative for local files. The application does not grant rights to imported media.

Example entry shape (placeholders must be replaced with real records):

```json
[{"file":"observatory.mp4","kind":"video","start":12.4,"end":21.0,
  "description":"observatory telescope mirror aligning",
  "license":"owned","evidence":"Original shoot release dated YYYY-MM-DD",
  "source":"Owned footage archive, reel 2","credit":"Creator name",
  "sha256":"hex digest of the actual file"}]
```

Use `photo`, `video`, `music` or `effect`. Audio and video require start/end seconds. A clip too short for the shot is ineligible. An invalid record, disallowed license or changed hash is skipped with a reason. Keep private libraries and permissions outside Git.

## Scheduling and upload

The planner proposes tomorrow's time in Asia/Hong_Kong. With no comparable evidence it rotates noon, 17:00 and 20:00 local time. To use observations, add `channel-history.json` beside the database, containing records with `video_id`, `format`, an aware ISO `published_at`, and nonnegative integer `views_at_24h`. Import only owner-authorized, genuinely measured same-age observations. Duplicate IDs are ignored. At least two local-hour groups with three comparable uploads each are needed to use medians. This is an observational comparison with possible content and audience confounding. Automatic channel analytics ingestion is future work.

The optional uploader uses the official Google libraries. Enable the YouTube Data API in your project and create a Desktop OAuth client. Once, with the channel owner present:

```sh
pip install -e ".[web,publish]"
trend-sniper connect-youtube --client /path/to/client_secret.json
```

For an alternate database directory, pass `--auth-dir <database-parent>/youtube`. The OAuth browser flow connects one creator channel and stores a mode-0600 token outside Git. Revoke access in your Google account and remove the local token/channel files to disconnect.

To release, watch the preview, inspect the metadata, select audience/disclosure settings and choose a future time. The button **Schedule on YouTube** authorizes one exact video for the displayed channel and time. The app rechecks channel identity, validates a frozen copy against the reviewed hashes, reserves that channel/day, and sends a private resumable upload with a future publication time. The release record distinguishes confirmed schedule from an unconfirmed remote schedule. A remote ID is retained whenever received. A proposed slot or daily private preview creates no remote upload. [Upload guide](https://developers.google.com/youtube/v3/guides/uploading_a_video) · [Video status fields](https://developers.google.com/youtube/v3/docs/videos)

If the connection fails before any submission, resolve the cause and review again. If a submission may have succeeded, the app blocks automatic resubmission. Check YouTube Studio for that upload and its scheduled time. Reconciliation of ambiguous submissions is manual in this release. Use one server process per local database.

## Production desk

Open **The control room** from the home navigation. The desk shows waiting, running, ready and attention counts, a title/format search, filters and stage history. Ready previews stay mounted while other jobs update, so polling does not reset an open review form or playing video.

**Pause queue** persists across application restarts. It lets the current preview finish and prevents the next waiting preview from starting. Daily mode can still add a new waiting preview when enabled. **Remove from queue** cancels an unstarted attempt. **Stop after current step** requests cancellation at the next stage boundary, or before the finished preview becomes available. A model request or FFmpeg operation already in progress is allowed to finish. Neither action touches YouTube releases.

**Retry saved sources** creates a new attempt from the original, frozen input packet. It does not reuse an unfinished MP4. The old attempt and its activity remain visible. Repeated retry requests return the same child attempt. A source set already submitted, even if failed or cancelled, is not silently rerun by daily mode or repeated Produce clicks. Retry it explicitly in Control room. The queue holds at most twelve waiting/running previews.

On startup, waiting jobs resume automatically unless paused. Running jobs left by a crash become failed with an interruption message, requiring a retry. Old completed previews remain available. There is one local worker and one app process per database. The queue is durable in SQLite, but computation stops when the computer sleeps or the application closes. Graceful shutdown completes the active preview and leaves waiting jobs for the next launch.

**Factory services** performs bounded local checks. An installed model is distinguished from a successful generation. A saved channel connection is distinguished from a freshly verified OAuth grant. Media catalog counts are entries, not clearance approvals. Permissions and file hashes are checked during production. Spoken narration and live analytics remain disconnected. Runtime and zero paid-API spend are recorded for new successful runs. Older or incomplete attempts have unknown spend instead of invented totals. Device/electricity costs are excluded.

In a finished worker report, expand **Compare leading script candidates** and **Selected edit** to read the candidate cuts, scoring criteria, exact scene times, source links and audio cues. Scores are editorial heuristics, not predictions of views. All source/download records remain available alongside the readable view.
