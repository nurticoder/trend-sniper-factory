# Kokoro and the reviewed footage workflow

Branch: `feat/kokoro-footage-workflow`, based on the verified `fix/niche-content-routing` checkout. This slice connects the existing production paths; it does not expand discovery or enable publishing.

## Operate it

1. Discover → choose a niche → **Develop topic plan**. The local writer produces an original subject plan, not an upload-statistics report. The durable worker prepares each passage's Kokoro narration and searches the cleared local library, then Commons, using the visual brief's concrete search query.
2. Open the scene review. Listen to the measured speech and play candidate footage. Inspect credit, source and license. Each candidate is explicitly unverified for visual correspondence. Selected steady/brisk delivery is frozen with preparation and retained at rendering. Missing narration, unsuccessful searches and invalid library entries remain recorded.
3. Edit narration, visual subject/action/purpose or search terms. **Save edits and find footage** creates a new durable preparation attempt. Identical speech and prepared shots reuse verified caches. Earlier attempts remain intact. A re-preparation can retry a previously empty query after a service/library repair.
4. Supply a factual source URL and supporting passage/notes for each scene. Select one to four clips within a spoken passage, trim their intervals and choose whole-subject framing or a vertical crop. Review facts and actual footage before **Build reviewed private preview**. Changed narration/visual decisions require preparation again. Missing/changed footage, missing speech, short clip intervals or edits outside the 20–75 second format block the preview with an actionable error.
5. The same smooth assembler used by the curated explainer measures speech, allocates shot durations, reuses shot caches, ducks background audio and writes 720×1280/24fps video, native phrase captions, truthful title packaging, source/rights records and an editorial review. Open the full review in Production studio. A completed render is still awaiting editorial approval. Publishing remains disabled for this format.

The curated water-in-microgravity intake remains available independently in Production studio. It now uses the selected Kokoro voice and shared assembler. Old previews and the explicit analytics renderer remain accessible. Daily niche jobs now prepare plans; they do not skip scene review or publish.

## Voice setup

```sh
pip install -e ".[web,voice]"
trend-sniper install-voice
```

Use `--data-dir <database-parent>` for another workspace. The explicit installer stages pinned upstream Kokoro-82M v1.0 int8 weights and voice bank (~120 MB). Production never downloads a model. The selected voice is `af_heart`; steady delivery is 0.95 speed, brisk is 1.05. Each utterance runs in a bounded local child; no external TTS account or paid API is used. Text arrives through stdin. Files remain under ignored local data with provenance and hashes. Earlier Piper delivery auditions are invalidated on migration; existing finished files are preserved. Piper remains an explicit legacy utility, never a silent fallback.

The earlier control-room auto/off/required setting applies to the legacy analytics path. This narrated-footage format always requires speech. Phrase caption timing is estimated within measured utterances, not forced alignment or verified word boundaries. FFmpeg must provide libass; the tested bundled encoder does.

## Footage and reusable records

The library schema remains in [OPERATING.md](product/OPERATING.md). The online candidate adapter accepts source-declared CC0 and CC BY 4.0 videos, preserves creator, file page, license URL, metadata receipt and hash, and caps candidates/download sizes. It does not require the old vision model to make a candidate available for review. Attribution-bearing assets are credited in generated metadata, with trimming/reframing disclosed. Share-alike, noncommercial, unknown/restricted media and unlicensed YouTube gameplay are not silently accepted. `TSF_COMMONS=0` disables online lookup.

Preparation saves internal `prepared.json`, public `content-plan.json` and a reusable script. Candidate bytes and speech are served through job-scoped routes, with paths/hashes checked. Reviewed render jobs freeze source support, clip choices and assets in the existing queue input. They recheck bytes before assembly. Source/rights review and private editorial approval remain separate from publication.

## Verification and remaining limitations

- 55 targeted tests pass, including existing fragment mixing and review/scheduling boundaries. Full-episode render tests are deliberately excluded.
- Regression checks exercise Physics and Minecraft from selection through preparation and reviewed dispatch into the shared assembler. The routing tests use controlled writer/media/voice fixtures; they do not prove automatic editorial quality. Legacy workers, persistence, cancellation, retries and review boundaries remain covered.
- A two-second synthetic encoder fixture tests actual 24fps shot preparation, cache reuse, native subtitle rendering, audio-stream presence and decoding. No full episode is rendered during this change.
- The selected Kokoro production speech cache generated the existing 15-second audition script (15.787 seconds), then reused it without synthesis on a second request.
- Browser QA played real Kokoro scene audio and a clearly labeled two-second technical video candidate in the scene-review interface. The restarted main app reports Kokoro ready; its steady/brisk delivery auditions are ready, with existing previews preserved. This verifies playback and integration, not a by-ear editorial quality verdict.
- One bounded live Commons query (`water surface tension`) returned no eligible video candidates. The adapter is not demonstrated to supply footage reliably for arbitrary topics. Gaming footage remains especially dependent on suitable cleared material. No stock API account/key was created.
- General subject research and fact checking are not automated by this slice. Source support is supplied/reviewed by the creator. The small local writer can still produce weak or inaccurate explanations. Candidate ranking is lexical; visual correspondence requires inspection. No virality, monetization or naturalness guarantee is inferred from passing tests.
- No cloud TTS, new paid service, full-length episode, upload, branch merge or discovery expansion is included. Next: review representative topic drafts and available footage; improve factual grounding before scaling production.

## Changed areas

| Files | Purpose |
| --- | --- |
| `production/kokoro.py`, `narration.py`, `legacy_piper.py`, `voice_install.py`, `pyproject.toml`, `tools/voice_auditions.py` | Selected voice, explicit setup, cache/provenance compatibility, retained legacy audition utility |
| `production/content.py`, `commons.py`, `topic_workflow.py` | Scene queries, licensed candidates, reusable preparation, reviewed subject-plan conversion |
| `production/explainer.py`, `captions.py` | Shared smooth assembly, topic-specific packaging, native captions, audio-stream check |
| `production/run.py`, `daily.py`, `web/factory.py`, `niches.py` | Existing worker dispatch, versioned keys, public artifact state |
| `web/content.py`, `app.py`, `explainers.py`, `readiness.py`, `voice.py` | Thin review/playback routes, voice migration, accurate services/scope |
| `web/static/content.js`, `discover.js`, `desk.js`, `desk.css`, `discover.html`, `explainer.js` | Existing-interface scene editing, media playback and private review handoff |
| `tests/test_formats.py`, `test_narration.py`, `test_explainers.py`, `test_topic_workflow.py` | Topic routing, voice, persistence, review and short real-encoder regressions |
| `README.md`, `THIRD_PARTY_NOTICES.md`, `docs/product/OPERATING.md`, `PLATFORM.md`, this document | Current capabilities, licenses and limitations |
