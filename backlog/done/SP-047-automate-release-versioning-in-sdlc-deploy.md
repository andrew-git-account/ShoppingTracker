# SP-047: Automate Release Versioning in sdlc-deploy

**Priority**: Medium
**Status**: Done
**Fulfils**: n/a (infrastructure)

## Description
Change the `sdlc-deploy` skill so every deployment is a numbered release. Before the deployment package is built, the skill works out which stories are shipping, drafts a new `releases.json` entry with the next version number and plain-language text for each story, asks for approval, commits it as a release commit, and only then packages and deploys `HEAD`. The version and release notes the user sees in the app (SP-046) are therefore always part of the package they belong to.

**Depends on SP-046** (`releases.json`, the footer and the What's New page must exist first).

## Acceptance Criteria
- [x] The skill file `.claude/skills/sdlc-deploy/SKILL.md` has a new step between the migration check and the package build that: finds the SPs shipping in this deploy using the existing marker diff (`git log <marker-commit>..HEAD --grep="^SP-[0-9]"`), drafts a new top entry for `releases.json` with version = previous top version + 1, today's date, and one change per shipped SP (`sp` number plus user-friendly `text`).
- [x] The draft text is shown to the user and the skill waits for explicit approval (or edits) before writing anything.
- [x] On approval, the skill writes the entry to `releases.json`, commits it as `Release N` (N = new version), pushes it, and then builds the package with `git archive` of `HEAD`, so the new entry is inside the deployment package.
- [x] No commit SHA is stored in `releases.json`.
- [x] Idempotent after a failed deploy: if the top version in `releases.json` at `HEAD` is already greater than the top version in `releases.json` at the last-deployed marker commit (`git show <marker-commit>:releases.json`), the skill reuses that existing entry (showing it to the user) instead of bumping again, so no version number is skipped.
- [x] If `releases.json` does not exist at the marker commit (e.g. the marker predates SP-046), the previous version is treated as 0 and the skill drafts the entry normally instead of failing. If an existing top entry in `releases.json` does not cover every SP in the shipping range, the skill shows both and asks the user whether to extend that entry or replace it.
- [x] If the shipped range contains no `SP-NNN` commits (a non-SP change), the skill tells the user and asks whether to create a release anyway or deploy without a version bump.
- [x] Step 8 (marker), Step 9 (`**Deployed**` lines) and the existing verification steps keep working unchanged; the Step 10 report additionally states the released version number.
- [x] A dry check by reading the updated skill end to end: the step order (marker diff, release entry, release commit, package, deploy, verify, marker, deployed lines) is consistent and no step refers to a removed step number.

## Notes / Context
- Ordering matters: `git archive HEAD` packages only committed content, so the release commit must exist before Step 5/6. This makes a deploy two commits (`Release N`, then the existing "Mark SP-... as deployed" commit).
- A release commit cannot contain its own SHA, hence no SHAs in `releases.json`; the SHA stays in the marker and in the `**Deployed**` lines.
- Comparing against `releases.json` at the marker commit, rather than a `version` field in the marker, works even for the first run after SP-046, when the marker (written by the old skill) has no version. It needs no change to the marker format. A marker commit that predates `releases.json` entirely is the edge case covered by the "does not exist at the marker commit" criterion.
- User-friendly text: SP titles are sometimes technical (e.g. "Normalize Categories to a Category ID"). The skill should draft a short end-user sentence per SP (from the SP's description and title) and let the user edit it; internal-only stories may be omitted from `changes` if the user says so.
- The skill must still follow its existing rule of never using `az webapp deploy --type zip`.

### Out of scope
- Changing the app or the What's New page (SP-046).
- Changing the format of `deployment_state.json`.
- Rewriting or re-versioning past releases.

## Implementation Notes
Completed 2026-10-07.

- `.claude/skills/sdlc-deploy/SKILL.md` - added Step 5, "Prepare the release entry (version + What's New)", between the migration check and the package build, and renumbered the later steps (package 6, deploy 7, verify 8, marker 9, mark deployed 10, report 11) with every cross-reference updated. Step 5: (5a) finds the shipping SPs from the marker range (`git log <marker>..HEAD --grep="^SP-[0-9]"`), asking the user when there is no marker, and asking whether to release anyway or skip the bump when no SP commits are in the range; (5b) compares the top version of `releases.json` at the marker commit (`git show <marker>:releases.json`, absent = 0) with the one at `HEAD` - if `HEAD` is higher an entry is already pending, so the version is not bumped again, and if that entry misses any shipping SP the user is asked to extend or replace it (same version); otherwise the new version is `head + 1`; (5c) drafts one plain-language sentence per SP and waits for explicit approval (approval includes the commit and push); (5d) writes the entry at the top of `releases.json` with no commit SHAs, commits `Release N` and pushes, so `git archive HEAD` packages it. The `az webapp deploy --type zip` ban, the marker step and the `**Deployed**` lines step are unchanged; the report step now includes the released version and its changes.
- `tests/test_deploy_skill.py` (new) - 12 plain-text checks on the skill file: steps numbered 1-11 consecutively, every "Step N" reference points at an existing step, step order, the renumbered cross-references, the key Step 5 rules (commit before packaging, approval before writing, no SHAs, pending-entry reuse, extend/replace, no-SP-commits question), and that the `--type zip` ban, `config-zip`, marker, `Deployed` lines and report wording survive.
- Dry logic check (read-only git commands): at marker `6e7a2e7`, `releases.json` does not exist (prev = 0), `HEAD` top version is 10 with only SP-046 in its changes while SP-046/048/049 ship, so the next deploy goes down the extend/replace path.
- No app code, migrations, data changes or new dependencies; `deployment_state.json` format unchanged. The skill's runtime behavior is exercised only by a real `/sdlc-deploy`; the tests guard its structure.
- Tests: 12 added; full suite 667 passed.
