# Niche production routing fix and voice comparison

## Verified active path

Started from `feat/footage-explainer` at `1ab2bcf`. Work is on `fix/niche-content-routing`.

The actual discovery UI is `web/static/discover.js`: selection calls `/api/niche-selection`; the action calls `/api/niche-production`. `web/niches.py` freezes the selected card into a durable job. `web/factory.py` dispatches it to `production/run.py`. Previously `web/formats.py` mapped most subjects to Countdown, and `production/editor.py` wrote permutations of upload titles/metrics. Gaming used a generic fictional block puzzle. The separate curated explainer studio was not the general niche-production entry point.

## Scoped correction

- Original topic content is the default. The writer receives niche name/category, never creator names, reference titles, view counts or channel metrics.
- One generic local-model contract produces a concrete topic, promise, payoff, narration passages and subject/action/purpose visual briefs. There are no niche-specific production scripts in the new writer. Test responses are fixtures, not application templates.
- Discovery keeps its observations for topic selection. Analytics/reporting requires an explicit format selection, and the statistics editor also checks that explicit flag.
- During this milestone, the normal content action stops at a persisted `planned` state. Fact and footage review are visibly required. Plans cannot serve an MP4 or enter the existing finished-video release path. No full-length videos were rendered.
- Invalid/offline generation fails visibly. No competitor report or generic story is silently substituted. Unsupported claims of fictional research/discoveries are rejected. Existing analytics components remain accessible explicitly; previously finished videos remain intact.
- Versioned job keys keep earlier results from masking the fix. Daily jobs use the same content-first behavior.

## Specific files

All paths below are relative to the repository root `/Users/nur/Documents/ChatGPT/mvp`.

| File | Change |
| --- | --- |
| `src/trend_sniper/production/content.py` | New shared topic/story/visual contract and generic local writer; no discovery statistics in context |
| `src/trend_sniper/web/formats.py` | Default subject-content routing; retain legacy generation explicitly |
| `src/trend_sniper/production/editor.py` | Require explicit analytics flag |
| `src/trend_sniper/production/run.py` | Plan-only default; explicit reporting path preserved |
| `src/trend_sniper/web/niches.py` | Validated content/analytics selection, distinct deduplication keys, and refreshed legacy saved-selection labels |
| `src/trend_sniper/web/factory.py` | Preserve per-request format options; serve plan artifacts without pretending there is an MP4 |
| `src/trend_sniper/production/jobs.py` | Persist a separate planned status |
| `src/trend_sniper/production/daily.py` | Apply content-first keys to automatic niche jobs |
| `src/trend_sniper/web/static/discover.js` | Minimal format choice and readable plan result |
| `src/trend_sniper/web/static/discover.html` | Accurate default format labels/copy |
| `src/trend_sniper/web/static/desk.js` | Display plans separately from finished previews |
| `tests/test_formats.py` | Normal-path two-niche regression, explicit reporting, offline/invalid-output and invented-research rejection; no renders |
| `tests/test_workers.py` | Exercise legacy workers explicitly instead of relying on obsolete defaults |
| `tools/voice_auditions.py` | Audition-only CLI; no permanent provider integration |
| `docs/niche-content-fix.md` | This delivery record |

## Verification and limits

Twenty-six relevant tests pass across formats, existing workers, queue operations, discovery and web boundaries. The regressions select Physics and Minecraft through the normal application API, execute the worker with controlled provider responses, assert different subject-specific narration/visual plans, reject analytics contamination and assert the renderer is never called. Existing legacy reporting tests still run explicitly. Full-render test modules were intentionally not run for this scope.

Two niches also exercised the normal selection/production API with the real local model, including a final check after tightening the prompt. Physics produced a quantum-entanglement plan; Minecraft produced a redstone-repeater plan. Both stayed on subject rather than reporting channel metrics. They do not establish factual reliability: an earlier Minecraft draft invented a compass-measurement visual and promotional research claims. The final prompt and narrow rejection guard discourage those claims, but cannot fact-check arbitrary narration. The final plans still have vague visual instructions and unverified explanations; they are unsuitable for production without review. A `planned` result is not a sourced or production-ready video.

## Voice comparison

Playable local files are under ignored `local-data/voice-comparison/`: `piper.wav`, `kokoro.wav`, `script.txt` and `comparison.json`. Both use the same approximately fifteen-second script, mono 24 kHz WAV, loudnorm target -16 LUFS, no background music and no time stretching.

- Piper: existing pinned LJ English voice, length scale 0.92; 15.238 seconds.
- Kokoro: Kokoro-82M v1.0 int8 ONNX, `af_heart`, speed 0.95; 15.787 seconds. Audition runtime is isolated in ignored `work/voice-comparison-env`; application dependencies and voice selection are unchanged.
- Google cloud comparison was skipped: no configured application credentials/API key or default cloud credential file, and no verified free allowance. No cloud calls, billing activation or charges.

The official [Kokoro model card](https://huggingface.co/hexgrad/Kokoro-82M) declares Apache-2.0 model weights. The [ONNX runner](https://github.com/thewh1teagle/kokoro-onnx) is MIT. Official release URLs and downloaded model/voice hashes are recorded in the local comparison manifest. No model binaries or private audio are committed. The assistant cannot receive audio input in this session; these are listening samples for the creator, not a claimed by-ear quality verdict. No replacement was permanently integrated or automatically selected.
