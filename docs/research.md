# Implementation research — checked 2026-11-03

Primary sources inform the implementation; these are not guarantees of account eligibility or legal advice.

## Small, free local stack

- [Pillow](https://pillow.readthedocs.io/en/stable/about.html): direct raster drawing avoids stock assets and browser/video editor dependencies. Selected for six original animated puzzle scenes. Its default scalable font is an Aileron subset; see [source](https://github.com/python-pillow/Pillow/blob/main/src/PIL/ImageFont.py).
- [FFmpeg](https://ffmpeg.org/documentation.html): raw RGB stdin → H.264 + AAC MP4. No per-frame PNG files and no cloud processing. [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) distributes platform wheels and supports overriding the executable. Its wrapper license differs from the bundled encoder's; see [legal](https://ffmpeg.org/legal.html).
- [eSpeak NG](https://github.com/espeak-ng/espeak-ng): open-source offline TTS candidate, GPL-3.0-or-later. Not installed or required: voice quality and distribution obligations should be evaluated before adding narration. No proprietary macOS voices are used in the demo.
- [whisper.cpp](https://github.com/ggml-org/whisper.cpp): optional offline transcription candidate. Not needed when we already own the script and scene timings; omitting it avoids model downloads and extra compute.

No image generator or LLM is needed to validate the first complete pipeline. More expensive generation should follow evidence that a distinct format is useful.

## Game reference and trend uncertainty

[Official Roblox DONT SPLASH listing](https://www.roblox.com/games/119958473240233/DONT-SPLASH) establishes the reference URL only. No concurrent-player history or measured acceleration was collected. The demo does not assert any real-game mechanic, ranking, trend velocity or earnings. It is a fictional pool puzzle. Later trend discovery needs timestamped observations from permitted APIs and a comparable baseline.

## Platform constraints

- [YouTube monetization policy](https://support.google.com/youtube/answer/1311392): repetitive/mass-produced work can fail monetization even when the visuals are original. Batch generation therefore does not mean automatically publishing templated variants.
- [Made for kids](https://support.google.com/youtube/answer/9528076): intended audience, including mixed audiences directed at children, matters. No automatic “not made for kids” default. This episode awaits human audience determination.
- [Altered/synthetic content](https://support.google.com/youtube/answer/14328491): realistic and meaningful synthetic alterations have disclosure requirements; clearly unrealistic animation is treated differently. Our local provenance flag is deliberately separate from the final upload decision.
- [videos.insert](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert): requires OAuth authorization. Current retrieved documentation describes a separate upload quota bucket; do not copy historic fixed quota costs or audit restrictions without checking current docs for the project. v0.1 makes no YouTube calls.
- [Video resource](https://developers.google.com/youtube/data/reference/rest/v3/videos): `publishAt` requires a private video that has not been published; past timestamps can cause immediate publication. Local queue rejects past/naive timestamps before any future adapter can use them.
- [API developer policies](https://developers.google.com/youtube/terms/developer-policies): review consent, privacy, stored data, deletion, quota and restrictions before shipping the OAuth adapter. Do not scrape, bypass API limitations or capture account passwords. Use official OAuth and offer token revocation/deletion.

## Low-time development order

Before exams end on December 15, keep the project runnable with one command and work in small optional sessions: assess the demo, create a genuinely distinct second visual treatment, then implement private upload with tests. Connecting a channel is only needed for that upload milestone. Do not consume time producing dozens of near-identical videos before testing whether the first format works.
