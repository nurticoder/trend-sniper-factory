---
title: Trend Sniper Factory Worker
sdk: gradio
sdk_version: 6.31.0
python_version: '3.12'
app_file: app.py
tags:
  - trend-sniper-factory-worker
---

Private experimental ML production worker for the owner's local Trend Sniper Factory app.
The Gradio page is informational; authenticated job APIs use the existing durable queue.
The real Moondream vision checker uses ZeroGPU's limited free GPU allocation; the rest of production uses CPU. No paid inference providers or owner billing token are used.
Free account eligibility, sleep and resource limits apply. No finished video quality is guaranteed.
