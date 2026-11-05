# Footage-led explainer pilot

The Production studio is a new route within the existing platform. It uses the same durable preview queue, local storage, Piper installation, FFmpeg toolchain and artifact-serving boundary. Existing discovery, countdown, fiction, Steam and reviewed publishing paths remain available. Publishing is explicitly disabled for the explainer pilot.

## Normal application workflow

1. Open **Production studio**. Enter a water/microgravity topic and develop the brief.
2. Generate two local audio auditions if desired. They are steady/brisk deliveries of the same licensed LJ English narrator, not different speakers. The selected delivery persists in SQLite and is frozen with each job.
3. Inspect the promise, original angle and payoff. Edit individual narration passages, pause lengths, pronunciation replacements, shot purposes, source intervals, or framing. Save a revision.
4. Produce a private preview. The worker checks primary-source pages and NASA ownership metadata, acquires the bounded footage, measures speech, assembles multiple shots per passage, applies phrase captions and ducked music, and decodes the finished MP4.
5. Inspect the preview, title/thumbnail, technical findings, subject sources, source intervals and rights records. Record private editorial approval only after watching. No upload is performed or enabled for this pilot.

Unsupported topics produce an actionable scope error rather than a generic countdown or slide presentation. Missing speech, changed source files, insufficient clip length or uncertain third-party ownership fail visibly. The editor offers a narrower script, another inspected clip interval and an explicit diagram treatment. Real footage remains a validated requirement for this format.

## Pilot content and provenance

**Why water becomes a ball in space** is a human-authored, original four-passage explanation. It distinguishes the effect responsible for floating from the force shaping the drop. It also acknowledges that the source demonstrations show water touching a straw, rather than claiming every image depicts an isolated free drop.

The subject packet uses these primary sources:

- [NASA: What is the Fluidic Telescope?](https://www.nasa.gov/science-research/astrophysics/what-is-the-fluidic-telescope/)
- [NASA Glenn: What is Microgravity?](https://www.nasa.gov/centers-and-facilities/glenn/what-is-microgravity/)

Footage is restricted to the inspected NASA JSC demonstrations [Moving Water in Space](https://images.nasa.gov/details/Moving_Water_in_Space-8K) and [Fluids on the Space Station](https://images.nasa.gov/details/Fluids_on_the_Space_Station). Metadata, source and policy snapshots, retrieval dates, hashes, original identifiers, selected intervals and restrictions accompany the preview. Source audio is removed. Attribution is included in the upload copy and picture. The thumbnail is an original diagram, avoiding use of astronaut likenesses as promotional packaging.

[NASA's media guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/) allow factual informational use subject to their conditions and identify separate restrictions concerning third-party materials, logos, endorsement and identifiable people. This private informational pilot is not blanket clearance for advertisements or commercial packaging. The review screen makes that limitation explicit.

## Reuse and review

Research downloads, source footage, normalized speech and prepared shots are cached by content and verified with hashes. Speech keys include text, delivery profile and model checksums. Shot keys include source digest, interval, framing and duration, so moving a shot on the timeline does not itself regenerate it. Each render keeps an immutable input snapshot and separate output directory. A saved revision preserves earlier previews.

The pilot was developed through the browser intake, audition and produce actions. A first edit exposed insufficient visual prominence. The second revision used prominent vertical crops and reused all four narration clips. Further source and focus revisions avoided cropped source captions and kept the moving water visible. A remaining tool-contact view is flagged because a hand partially obscures the drop; the review screen offers a saved alternative without automatically starting another render. These are revisions of one bounded pilot, not a batch of unrelated videos. Existing research, source files and speech were reused.

## Checks and limits

Screenshot evidence is retained in [the review screenshot](images/footage-pilot-review.jpg).

The completed edit is approximately 37.54 seconds, 720×1280, 24fps, with seven shots across four passages. One explicitly labelled, original orbital schematic explains shared free fall; real footage occupies the rest. Full MP4 decoding, dimensions, frame rate and duration agreement are checked. All 50 automated tests pass. The test suite covers the preserved workflows plus source/cache integrity, scene contracts, required narration, source/shot validation, stale revisions, frozen voice selection and encoded timing checks.

This milestone is a **curated production collection**, not autonomous research/writing for arbitrary topics. The angle, prose and initial shot matches were authored and visually inspected during development. Runtime source terminology checks do not establish semantic fact verification. Those decisions remain visible for human review. Future collections need their own reviewed subject packets and footage candidates.

Captions are phrase-sized and timed within measured utterances using word-count proportions. They are not forced-aligned to individual words. The local narrator has fixed expression. Reframed source footage can lose contextual detail; the source quality and available delivery styles constrain the result. The review screen retains these issues rather than equating a successful encode with editorial approval.

Next: expand reusable researched collections and candidate acquisition, add visual crop previews and stronger factual/scene assessment, then improve speech/caption alignment. No paid services were enabled.
