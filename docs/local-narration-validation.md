# Local narration milestone

Verified November 5, 2026 (Hong Kong).

## What is implemented

New niche productions can generate local English narration using the separately installed Piper 1.8.0 engine and one checksum-pinned LJ Speech model. Production never downloads a model or calls a paid speech API. Control room has automatic, required and off preferences. Each job freezes its preference and retries preserve it.

The worker measures speech duration before selecting material or rendering. It extends scenes, places the first utterance after the opening cover, normalizes the speech peak and ducks music/effects during each utterance. It records voice provenance, utterance timing, spoken text and audio hashes. Review includes a voice-only player/download and a timed storyboard. Caption timing follows scenes, not individual words. Large counts in hooks/payoffs are spoken with explicitly approximate rounded wording; their exact on-screen values remain intact.

Automatic mode reverts the entire edit to caption/music-only output if any utterance fails. Required mode fails the attempt. There is no partially voiced success. Off mode does not call the provider. Voice files with changed hashes are rejected. Failed downloads cannot activate a partial installation.

## Verification

- All 40 automated tests pass. Ten narration tests cover timing extension, untouched original scripts, cancellation, silent/failed speech, required/fallback/off modes, total duration limits, changed/unreadable model files, explicit approximation of spoken metrics, music attenuation, peak bounds, frozen preferences on retry and download-checksum rejection.
- One bounded integration run used the actual installed Piper model and the normal niche-production API against an isolated database under `work/voice-qa/`. Five utterances were synthesized and assembled into a 28.083-second MP4 in 14.99 worker seconds. The run used the source-constrained 100-cut editor and twelve-cover selector. Paid API spend was $0.
- The entire MP4 passed the existing FFmpeg decode check. Decoding its AAC audio and comparing with the prepared mix gave a correlation of 0.99993. Audio duration agrees with the edit, and review-bound artifact hashes validate. This run preceded the final spoken-number shorthand adjustment, which is separately covered by the normalization test.
- Browser QA verified preference persistence after reload, the narration report and WAV player. The player loaded 28.083 seconds with readyState 4 and no media error. The browser error log was empty. [Screenshot](images/local-narration.jpg).
- New Python modules pass Ruff checks. `pip check` reports no broken dependencies. Model and large QA outputs remain outside Git. No OAuth connection or public upload was performed.

## Source and license records

Piper's [official CLI documentation](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/CLI.md) describes its local command-line workflow. [PyPI](https://pypi.org/project/piper-tts/1.8.0/) lists the engine's GPL-3.0-or-later license and macOS wheel. The [LJ Speech voice model card](https://huggingface.co/rhasspy/piper-voices/blob/e7229f7d33a10e145e109b886d661984201ac3c4/en/en_US/ljspeech/medium/MODEL_CARD) names the public-domain training dataset; [the dataset publisher](https://keithito.com/LJ-Speech-Dataset/) specifies US public-domain status. The voice repository declares MIT for the model. Exact source revision, configuration, model and card hashes are pinned in the implementation and retained in outputs. See [third-party notices](../THIRD_PARTY_NOTICES.md).

## Limits and next work

This is one English narrator with a fixed delivery style. It does not provide dialogue acting, voice cloning, word-by-word captions or a measured retention improvement. A single utterance is limited to 20 seconds of audio, synthesis to 40 seconds per utterance, and a narrated edit to 90 seconds. The legacy Steam chart renderer remains caption/music-only.

Next improve script substance and cleared-footage matching. Current ranking cuts compare sampled uploads' metrics; they do not automatically explain every topic behind those uploads. Online footage coverage and real-channel OAuth/analytics validation remain outstanding.
