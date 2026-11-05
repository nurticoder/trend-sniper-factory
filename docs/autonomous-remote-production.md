# Autonomous production on a remote worker

Branch: `feat/autonomous-remote-production`, based on `feat/kokoro-footage-workflow`.

## Corrected responsibility

The previous default stopped at a manually reviewed topic/footage plan. That was not the intended factory experience. Original topic production now dispatches to an authenticated remote worker. The creator chooses a niche/topic and reviews a finished video; they are not asked to hunt for clips, add library files, trim every shot or supply source excerpts to make the default workflow proceed.

The failed Minecraft draft inspected during this change also invented pulleys and a conveyor-belt mechanic. The new worker researches before writing instead of searching for material to rationalize that unsupported draft. Upload statistics are not subject evidence.

## What the worker does

1. Choose a specific explanatory question within the selected subject; retrieve reference text. Current sources include Wikipedia and a subject-specific Minecraft Wiki adapter. Source URLs, titles and excerpts remain attached to the script.
2. Write an original 90–140-word explanation with paired visual briefs and exact supporting source quotes. Reject fabricated quotations; a separate editorial call checks whether spoken claims follow their evidence and answer the opening promise. Revise unsupported writing.
3. Generate and adapt scene queries after failed searches. Try Commons, Internet Archive, NASA and source-declared Creative Commons YouTube material. Unknown/standard YouTube licenses, protected media and DRM are not accepted. Source availability/permission metadata can still be incomplete or wrong; final review remains necessary.
4. Inspect sampled frames against the requested subject, action, purpose and narration. Search different candidate windows instead of selecting a random first clip. YouTube retrieval requests a bounded section, prioritizing a matching chapter where available; the downloaded section is inspected before use.
5. Cut accepted windows on the remote machine, remove original audio, preserve source/derivative hashes and original timestamps, and retain attribution/license records. Failed searches trigger script/visual-concept revision, not a demand that the creator collect footage.
6. Use Kokoro, actual narration duration, multiple shots per passage, the existing smooth 720×1280/24fps assembler, native captions, deliberate audio mixing, topic-specific packaging and technical checks. Return the complete private preview for editorial approval. No publishing occurs.

Qwen2.5 7B provides the remote writer/editor, Moondream performs sampled visual checks, and Kokoro remains the selected narrator. This is automatic review, not proof of truth, rights ownership, naturalness or virality. It can still fail. Three editorial/retrieval rounds, 36 provider searches, 24 candidate inspections, a 45-minute production budget and a source-byte budget prevent unlimited work. Cold model startup is separate and can be slow on two CPU cores.

## Storage and recovery

- Source downloads, selected clips, models, speech and MP4 encoding stay on the remote machine. The desktop stores only small control/review JSON. Media playback uses an authenticated, range-aware streaming proxy with `Cache-Control: no-store`; it never creates a local source/MP4 cache. Explicit user downloads still save files to the destination the user chooses.
- Full sources are deleted after the attempt. Up to three completed jobs are retained for at most twelve hours; a background cleaner also runs. Shared immutable speech/shot caches are reused across jobs, capped at approximately 1 GB and evicted when idle. Active work is not evicted. The worker filesystem is ephemeral and can disappear on a hosting restart.
- The existing durable queue runs on both sides. The desktop retains the remote job ID, reconnects interrupted remote work, and retries transient control failures without resubmitting the production request. Explicit retries can reuse a still-running/finished remote job or start another worker attempt. Cancellation is forwarded. Expired previews need rebuilding and another exact-artifact approval.
- Worker authentication is mandatory, job/artifact routes are bounded, manifests are verified remotely, and credentials stay in ignored mode-0600 files. Credentials are never frozen into queue payloads or included in the source upload. An earlier working connection survives a failed new setup.

## Connection and cost

Use **Control room → Factory services → Remote production worker**. Enter the Hugging Face write token in the local password field, never in chat. The deployment runs as a durable job, uploads application source only and sets a private worker key. It will not overwrite a Space belonging to another project. It requests only `cpu-basic`, refuses existing/requested paid hardware and never purchases an account plan, GPU or persistent storage.

**Current Hugging Face policy matters:** CPU Basic has no hourly charge, but creating a new Docker/Gradio Space requires an eligible paid account plan under the current documentation. Existing entitlements can differ; the API checks eligibility. An ineligible account is reported without purchasing anything. A new free account is not a guaranteed zero-cost deployment route. See the official [Spaces overview](https://huggingface.co/docs/hub/spaces-overview) and [hardware/billing documentation](https://huggingface.co/docs/hub/spaces-gpus). The initial recommendation of an unconditionally free new compute Space was corrected during this task.

`deploy/worker.Dockerfile` and `deploy/space-README.md` define the remote container. No container/model images are built or pulled onto the creator's Mac by this workflow. `TSF_WORKER_PROCESS=1` belongs only in that container. `TSF_LOCAL_FIXTURE_MODE=1` exists only for explicitly bounded local technical tests; normal production never silently enables it.

## Evidence and current limits

The targeted test set passes 69 checks: the existing 55 plus remote routing for Physics/Minecraft, absence of desktop media creation, streaming ranges, private token handling, remote authentication, exact artifacts, expiry, restart recovery, reconnect without duplicate submission, deployment-source isolation, paid-eligibility refusal, invented quote rejection, failed-query feedback, exclusion of standard-license YouTube downloads, source license version preservation and automatic scene revision/cache reuse before compilation. Provider/model/compiler behavior is controlled in these protocol/automation tests; they do not establish finished-video quality.

A live **text-only** lookup returned Minecraft Wiki's Redstone Repeater reference. No source footage or new large model was downloaded to the Mac during this work. No cloud account/worker was connected at implementation time, so the full hosted container/model/retrieval/render path and the complained-about Minecraft episode have **not** been demonstrated live. A hosting connection and eligible compute access are required before that verification; passing fixture tests is not a finished video.

Browser verification on port 8765 opened the existing failed Minecraft draft, selected **Finish video automatically**, and confirmed the disconnected state routes to the private cloud connection form without starting a local media job. Existing preview records remained present. Account setup reached Hugging Face's required password identity checkpoint; no token was created and no Space was deployed.

Discovery remains seeded and is not expanded here. The older local graphics fixtures, existing previews and explicit legacy analytics components remain available; legacy online footage lookup is disabled on the desktop. Publishing is unchanged and disabled for these footage previews.

## Changed areas

| Area | Files |
| --- | --- |
| Remote control/streaming/deployment | `remote/client.py`, `remote/deploy.py`, `remote/worker.py`, `web/remote.py`, deployment files |
| Autonomous research and footage | `remote/editorial.py`, `remote/footage.py`, `remote/producer.py`, `production/fragments.py` |
| Existing workflow integration | `production/run.py`, `jobs.py`, `daily.py`, `explainer.py`, `web/factory.py`, `niches.py`, `app.py`, `explainers.py` |
| Default UI and secure connection | `web/static/remote.js`, `discover.js`, `discover.html`, `desk.js`, `desk.css`, `explainer.js` |
| Regression checks | `tests/test_remote.py`; explicitly isolated local fixtures in `test_formats.py`, `test_topic_workflow.py` |
| Setup and scope | `pyproject.toml`, `.gitignore`, `.env.example`, README, third-party notices and product docs |
