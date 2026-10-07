# SP-048: Backfill Release History into releases.json

**Priority**: Low
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-051 (populates the release history that scenario lists; the script itself is tooling)
**Deployed**: 0273459 (2026-10-07)

## Description
Add the nine deployments made before release versioning existed (versions 1-9) to `releases.json`, so the What's New page shows the full history. The history is derived from git and the backlog by a small, re-runnable script rather than typed by hand, so the result can be reviewed and reproduced.

**Depends on SP-046** (defines `releases.json` and its entry format).

## Acceptance Criteria
- [x] A script `backfill_releases.py` at the repo root derives past releases and merges them into `releases.json`. It is not named `migrate_*.py` (the `sdlc-deploy` skill treats any new or changed `migrate_*.py` as a production data migration).
- [x] Deployments are found from the "Mark ... as deployed (<sha>)" commits in git history (`git log --grep="as deployed"`), oldest first; the oldest is version 1, the next version 2, and so on.
- [x] Each release's `date` is taken from the `**Deployed**: <sha> (<date>)` lines of its SPs in `backlog/done/` (not from the date of the marking commit), and each release's `changes` list has one `{"sp": "NNN", "text": "<SP title>"}` per SP deployed in it, in ascending SP order.
- [x] No commit SHAs are written to `releases.json`.
- [x] Without arguments the script only prints the entries it would add (a dry run); it writes the file only when run with an explicit `--write` flag.
- [x] The script only adds releases whose derived version number is lower than the lowest `version` already in `releases.json`. Any derived release at or above that number is skipped, with a message listing what was skipped (git history may by then hold deployments newer than the existing entries, e.g. the SP-046 deploy that produced version 10). Existing entries are never modified, and the new entries are placed after them so the file stays newest first. Running the script twice adds nothing the second time.
- [x] After running with `--write` on a file whose lowest existing version is N (version 10 when SP-046 has just shipped), `releases.json` contains versions 1 to N-1 followed by the pre-existing entries, in descending order. Versions 1 to N-1 together cover every SP deployed before release N exactly once (SP-001 to SP-045 when N is 10), and the What's New page (SP-046) shows them all.
- [x] Tests cover the derivation using a small fixture (a temporary git repo or mocked git output plus sample SP files): version numbering order, date taken from the SP `Deployed` line, SP ordering within a release, dry run writes nothing, second run is a no-op, existing entries preserved, and a derived release at or above the lowest existing version is skipped with a message.

## Notes / Context
- Expected result, from the existing history (for the reviewer to compare against the dry run):

  | Version | Date | Deployed commit | SPs |
  |---|---|---|---|
  | 1 | 2026-08-16 | cb773f5 | 001-004, 006-013 (initial tracked release; includes SP-011, the Azure deployment) |
  | 2 | 2026-08-19 | b6f3230 | 005, 014-019 |
  | 3 | 2026-08-21 | 18b0666 | 020, 021 |
  | 4 | 2026-08-22 | 6f2a14b | 022-024 |
  | 5 | 2026-08-26 | 41e8c91 | 025-033 |
  | 6 | 2026-08-31 | 3164e4e | 034-038 |
  | 7 | 2026-08-31 | 3ca5911 | 039, 040 |
  | 8 | 2026-09-12 | 4b94918 | 041-044 |
  | 9 | 2026-10-07 | 6e7a2e7 | 045 |

- Known wrinkles: the version 3 marking commit is dated 2026-08-22 but the deploy happened on 2026-08-21 (hence taking dates from the SP files); version 1 was the first deploy tracked under the marker system and likely was not the very first real deploy, so it is described as the "initial tracked release".
- Each SP's `**Deployed**` line gives its short SHA; the SHA groups SPs into releases, and the ascending order of those releases' dates (ties broken by marking-commit order) fixes the version numbers. Both the "as deployed" commit subjects and the `Deployed` lines are consistent with each other today; if they ever disagree, the script should stop with a clear message rather than guess.
- Change text reuses the SP titles, which are developer-oriented; rewriting them as end-user sentences is optional follow-up work, not part of this SP.
- This is a one-off tool, kept in the repo to document where the history came from. Comment it heavily (learning project).

### Out of scope
- Rewriting release text in end-user language.
- Changing the app, the footer or the What's New page (SP-046).
- Automatic versioning of future deploys (SP-047).

## Implementation Notes
Completed 2026-10-07.

- `backfill_releases.py` (new, repo root) - derives past releases from git and the backlog and merges them into `releases.json`. Releases are the "Mark ... as deployed (<sha>)" commits, oldest first (1, 2, 3 ...); each release's date and change texts come from its stories' `**Deployed**: <sha> (<date>)` lines and `# SP-NNN: Title` headings, SPs in ascending order, no SHAs stored. Dry run by default, `--write` to apply. Only releases older than the lowest existing version are added (others are reported as skipped); existing entries are never modified; a second run adds nothing. Inconsistent history (missing SP file, no Deployed line, SHA mismatch, disagreeing dates) or a malformed `releases.json` stops with a `[FAIL]` message and writes nothing. Deliberately not named `migrate_*.py`, so `sdlc-deploy` does not treat it as a production data migration.
- `releases.json` - ran the script with `--write`: versions 1-9 added below version 10 (46 changes in total, SP-001 to SP-046). Verified a second run is a no-op.
- `tests/test_backfill_releases.py` (new) - 22 tests: subject parsing, version numbering, dates from SP files, SP ordering, no SHAs, the four inconsistency errors, merge rules (lowest-existing-version, untouched existing entries), dry run / `--write` / idempotent second run / skipped message / malformed file untouched, and a check against this repo's real history (versions 1-9 cover SP-001 to SP-045 exactly once).
- No app code, migrations or new dependencies. No BehaviorSpec change: BS-051 already describes the What's New page listing every release newest first, which now shows the full history.
- Tests: 22 added; full suite 653 passed.
