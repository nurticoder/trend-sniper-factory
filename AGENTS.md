# Working agreement

## Product intent

Build the Trend Sniper Factory platform. The chat develops software; users operate the factory through its interface. Do not create a fresh video on every development turn. Keep the original renderer as a component and its bundled demo as a technical fixture. Follow docs/product/PLATFORM.md and report implemented vs planned behavior accurately.

The active source of truth is this Git checkout. Earlier ZIPs and copies in the original chat outputs are archived snapshots, not parallel editable projects.

## Branches and delivery

- Before each new feature or meaningful task, inspect status and create a named branch from the appropriate clean base. Use feat/, fix/, docs/ or chore/. Do not overwrite existing user changes.
- Commit coherent working increments with clear messages. Run checks appropriate to the change; pure documentation does not need a video render.
- Push verified increments to the configured GitHub remote when authorized access is available. The user has requested normal ongoing pushes for this project. Report failed pushes honestly; do not claim local commits are remote.
- Before ending a development session, run the relevant checks and push passing work to GitHub. End with a 1–3 word push description. If checks fail or push is blocked, report that explicitly rather than claiming success.
- Open a reviewable PR for completed work. Avoid unrelated changes, empty commits, artificial push counts, backdating and force pushes.
- Record the current milestone and a concrete next task in the PR so work can continue without replaying chat history.

## Implementation

- Start with one creator and local persistence. Do not introduce paid services or a multi-user architecture without a concrete need.
- Use validated shared contracts for evidence, scripts, timelines, assets, jobs and reviews. Missing data and disconnected providers must be visible; do not fabricate success, analytics or trend evidence.
- Media creation belongs to an explicitly requested production job or a bounded test fixture. Keep routine development checks relevant and inexpensive.
- Expensive operations run in durable worker jobs, not long HTTP requests. Persist attempts, outputs and recovery state.
- Keep secrets, OAuth tokens, local databases, private analytics and new large render outputs out of Git. The existing small public demo is an intentional exception for portfolio documentation.
- Preserve per-asset provenance and rights restrictions. Match audio to events and verify license eligibility before selecting it.
- Publishing must use official owner OAuth and review-bound exact artifacts, with explicit audience designation and duplicate-upload recovery. Do not publish during development tests.
- Do not assume ChatGPT subscriptions provide application API access. Providers are optional and budgeted.

## Communication

Use plain English unless the user requests another language. Lead with what works, what changed, what was checked and what remains. Do not ask the user to perform routine coding, Git or setup work that tools can safely handle.
