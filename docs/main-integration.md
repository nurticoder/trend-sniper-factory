# Main integration and demonstration

The twelve open feature PRs were a cumulative development chain. The integration branch includes every head commit, including the existing footage branch merge, while preserving the latest application's file contents. A single integration PR targets `main`; earlier PRs can be closed as superseded only after their commits are confirmed to be ancestors of the updated `main`. Feature branches remain available. No force push or history rewriting is needed.

The complete 72-test suite passed locally, including the real app-to-playable-artifact test and the bounded media roundtrip. Live discovery refresh is mocked during the check; tests exercise source adapters with controlled fixtures. These tests do not establish autonomous cloud-video quality.

The demonstration uses the canonical dashboard on port 8765:

1. Browse dated niche cards and open reference evidence.
2. Inspect the saved Minecraft selection and draft. Automatic production reports the paused cloud-host failure; it does not request manual clip collection or start desktop media production.
3. Open Control room to inspect job status, history and available services.
4. Play the previously produced water-in-space pilot, its captions and packaging, and inspect scene/source/rights records. This is an archived demonstration with the earlier voice, not a new autonomous cloud render. New production retains the selected Kokoro voice. No approval or publication is performed during the demo.

One archived pilot may be linked into the local main library without copying source downloads or rendering another video. Its media bytes and manifest remain unchanged; previous approval records are not imported. The local database is backed up first, and all private state remains ignored by Git.

The current limitation remains compatible cloud hosting. The failed Hugging Face experiment is paused; no paid plan is enabled. The next production task is to connect a compatible eligible worker, then verify the saved Minecraft request through the normal workflow and inspect its complete playback/audio.
