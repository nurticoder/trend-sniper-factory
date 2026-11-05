---
title: Trend Sniper private media worker
emoji: 🎬
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
tags:
  - trend-sniper-factory-worker
---

Authenticated single-creator worker. Source downloads, scene inspection, short clip extraction,
Kokoro narration and FFmpeg rendering run here. No GPU or paid storage is requested.
CPU Basic is the only supported deployment hardware. A new compute Space may require
an existing paid account plan under current Hugging Face eligibility rules; this application
never purchases or upgrades a plan. Previews expire and ephemeral storage can be lost on restart.

Job and media routes require the private TSF_WORKER_KEY secret. No job data is committed to this repository.
