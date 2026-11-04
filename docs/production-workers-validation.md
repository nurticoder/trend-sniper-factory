# Production workers verification

Verified locally on November 4, 2026 in Hong Kong.

- Twenty-one automated tests pass. The suite exercises the complete production request, full MP4 decode, 100 distinct source-grounded cuts, winner use, 12 cover treatments, media clearance rejection, a real FFmpeg time-coded fragment, delayed sound placement, persisted daily deduplication, schedule proposals and release guards.
- A separate live-source QA run completed in 9.35 seconds. Both Commons queries returned zero eligible media and the run recorded original visual fallbacks. This validates the search/fallback route. It does not establish broad stock-footage coverage.
- The final browser run used the normal selected-niche Produce button, displayed stage progress, returned a playable preview, and exposed the selected script, covers and release proposal in the dashboard.
- The source-constrained cut pool selected script 46 in the observed QA sample. The final cover round selected option 7. These are reproducible editorial scores, not measured CTR or retention.
- The optional Google libraries were installed and imported. Upload success, stale approval, missing channel, duplicate release, frozen media bytes and uncertain submission were tested using a simulated transport. No live OAuth grant or YouTube upload occurred.
- Independent local tests confirm catalog hash/license filtering, fragment boundaries, soundtrack timing and lower-confidence exploratory scheduling when there is insufficient history.
- Python checks on the new modules, dependency consistency and project links pass. Screenshot evidence is in `docs/images/worker-report.png`.
- Full-length 100-story model batches and real channel analytics ingestion remain unverified. Narrative tests cover deduplication, budget/failure handling and truthful draft counts. Discovery currently observes a seeded channel set. Extend source coverage and assess actual viewer response before scaling daily output.

The local server must remain running for scheduled private previews. A reviewed release is submitted immediately as a private upload with a future YouTube publication time. Ambiguous submissions require reconciliation in YouTube Studio before another attempt.
