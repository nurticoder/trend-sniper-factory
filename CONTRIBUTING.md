# Development workflow

The project is built in small, independently reviewable slices. The owner does not need to manage Git commands manually when an authorized development agent can do it.

1. Inspect the working tree and current milestone. Preserve unrelated work.
2. Start a named branch for the task before editing. Feature branches normally start from the latest main; planning branches can be used as an explicit base while their PR is still open.
3. Build one useful increment. Use fixture data only when clearly labeled; disconnected services must remain visibly disconnected.
4. Run checks relevant to the changed behavior. Documentation changes need link/diff review, not fresh media. Media code changes need small deterministic integration fixtures; publication tests must use mocks.
5. Commit with a message explaining the change and push the branch. Push further completed checkpoints as work progresses; avoid noisy empty commits.
6. Open a PR with the problem, resulting behavior, checks and limitations. Keep a next-task handoff. The main branch should describe what is actually available.

Common branch names and milestones are in [the product plan](docs/product/PLATFORM.md). Normal code branches use `feat/`, `fix/`, `docs/` and `chore/`.

Before a push, inspect staged paths for secrets, token files, databases, logs containing private information and unintended large media. Local app data belongs outside source control. API keys and OAuth files are never committed, even to private repositories.

A normal feature commit is a useful portfolio record. Push counts alone do not describe engineering progress. Contributions should document actual work and preserve a readable history.
