# SP-047: Automate Release Versioning in sdlc-deploy

**Priority**: Medium
**Status**: Ready

## Description
Change the `sdlc-deploy` skill so every deployment is a numbered release. Before the deployment package is built, the skill works out which stories are shipping, drafts a new `releases.json` entry with the next version number and plain-language text for each story, asks for approval, commits it as a release commit, and only then packages and deploys `HEAD`. The version and release notes the user sees in the app (SP-046) are therefore always part of the package they belong to.

**Depends on SP-046** (`releases.json`, the footer and the What's New page must exist first).

## Acceptance Criteria
- [ ] The skill file `.claude/skills/sdlc-deploy/SKILL.md` has a new step between the migration check and the package build that: finds the SPs shipping in this deploy using the existing marker diff (`git log <marker-commit>..HEAD --grep="^SP-[0-9]"`), drafts a new top entry for `releases.json` with version = previous top version + 1, today's date, and one change per shipped SP (`sp` number plus user-friendly `text`).
- [ ] The draft text is shown to the user and the skill waits for explicit approval (or edits) before writing anything.
- [ ] On approval, the skill writes the entry to `releases.json`, commits it as `Release N` (N = new version), pushes it, and then builds the package with `git archive` of `HEAD`, so the new entry is inside the deployment package.
- [ ] No commit SHA is stored in `releases.json`.
- [ ] Idempotent after a failed deploy: if the top version in `releases.json` at `HEAD` is already greater than the top version in `releases.json` at the last-deployed marker commit (`git show <marker-commit>:releases.json`), the skill reuses that existing entry (showing it to the user) instead of bumping again, so no version number is skipped.
- [ ] If `releases.json` does not exist at the marker commit (e.g. the marker predates SP-046), the previous version is treated as 0 and the skill drafts the entry normally instead of failing. If an existing top entry in `releases.json` does not cover every SP in the shipping range, the skill shows both and asks the user whether to extend that entry or replace it.
- [ ] If the shipped range contains no `SP-NNN` commits (a non-SP change), the skill tells the user and asks whether to create a release anyway or deploy without a version bump.
- [ ] Step 8 (marker), Step 9 (`**Deployed**` lines) and the existing verification steps keep working unchanged; the Step 10 report additionally states the released version number.
- [ ] A dry check by reading the updated skill end to end: the step order (marker diff, release entry, release commit, package, deploy, verify, marker, deployed lines) is consistent and no step refers to a removed step number.

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
_Filled in when the work is done, before moving to backlog/done/._
