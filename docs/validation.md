# Local verification — 2026-11-03

- macOS ARM, Python 3.14.7; Pillow 13.0.0, imageio-ffmpeg 0.8.0, FFmpeg 9.0.
- Editable package installation succeeded; installed `trend-sniper` command rendered the final demo.
- Four unittest cases passed (including actual MP4 roundtrip), including multiple invalid script inputs and queue rejection paths.
- Complete MP4 decoded with FFmpeg `-xerror`; separate frame-count pass returned **600 frames / 25.0 seconds**.
- Stream inspection: H.264 High / yuv420p, 720×1280, 24 fps; AAC LC mono, 24 kHz.
- Six-scene contact sheet inspected for text overflow and layout. Replaced an unsupported bullet glyph and regenerated the final artifact.
- Paid API spend: $0. Final render elapsed time: 5.97 seconds. Hardware/electricity not measured.
- Final MP4 SHA-256: `be1f57f0f1667ad14794d701adef205c5a6956096a606bd9fa94f7cdedf67627`.
- Content approval is still pending: no audience attestation, remote upload or public publication was performed.
- GitHub Actions is configured but has not run on GitHub. OAuth, analytics and trend measurement are not implemented.

The example folder contains the exact verified output, not a fabricated preview. Automated decode validates media integrity, not factual accuracy, creative quality, audience suitability or likely performance.
