---
name: sdlc-deploy
description: Redeploy the current code to the already-provisioned Azure App Service (shopping-tracker-app) for the ShoppingTracker project. Use when the user asks to deploy, redeploy, push to Azure, or update the live app. Assumes SP-011's infrastructure already exists - this only pushes new code, it does not provision infrastructure or change App Settings.
---

## Redeploying to Azure

When invoked (`/sdlc-deploy`), follow these steps in order.

Every deployment is a numbered release: the version number and the What's New text
live in `releases.json` (SP-046), and Step 5 prepares the new entry and commits it
before the package is built.

Known-good values from SP-011 (`backlog/done/SP-011-deploy-application-to-azure.md`):
resource group `shopping-tracker-rg`, app `shopping-tracker-app`, storage account
`shoppingtrackerstch`, file share `shopping-data`, live URL
`https://shopping-tracker-app.azurewebsites.net`.

### Step 1 — Check for uncommitted changes

`git status --short`. Deployment packages only committed content (see Step 6), so
uncommitted changes to tracked files won't ship. If any exist, tell the user and
ask whether to proceed anyway (deploy the last commit as-is), commit first, or
cancel. Ignore untracked `data/` — that's local receipt data, never part of a
deploy.

### Step 2 — Confirm target resources still exist

```
az webapp show --name shopping-tracker-app --resource-group shopping-tracker-rg --query state --output tsv
```

If this errors, stop and report that the infrastructure from SP-011 looks
missing or changed. This skill only redeploys code — it does not re-provision
infrastructure. Point the user back to SP-011 for that.

### Step 3 — Fetch the last-deployed marker and diff against it

Download the deployment marker from the share:

```
az storage file download --share-name shopping-data --account-name shoppingtrackerstch --path deployment_state.json --dest <scratchpad>/deployment_state.json
```

- **If found**: read its `commit` field. Run `git log <commit>..HEAD --oneline`
  (commits about to ship) and `git diff <commit>..HEAD --name-only` (changed
  files). Keep the changed-files list for Step 4, and the marker commit for Step 5.
- **If not found** (no prior deploy tracked under this system): skip the diff,
  note "no prior deployment marker found" for the final report, and treat Step 4
  as having no changed-files list to check (skip straight to Step 5).

### Step 4 — Check whether a data migration is needed

From the changed-files list, look for any `migrate_*.py` file added or changed
since the last deployed commit (matching the existing `migrate_categories.py`
convention at the repo root — a one-off script that transforms a JSON data file
in place and prints a summary of what it changed).

**If none is found, skip straight to Step 5.** The established convention in
this codebase is that model `from_dict()` methods supply defaults for missing
fields, so most schema changes need no active migration — see how SP-001
(currency) and SP-013 (amount/unit) both did this.

**If one is found**, it needs real production data changed, so run 4a-4e before
doing anything else:

#### 4a. Stop the app

```
az webapp stop --name shopping-tracker-app --resource-group shopping-tracker-rg
```

The running app reads/writes files like `receipts.json` on every request with no
file locking. Migrating the shared data file while the live app could
concurrently write to it risks a lost write or a corrupted read. Stopping first
eliminates that race entirely. (This is *not* needed for a plain code deploy
with no migration — `config-zip` in Step 7 already recycles the container itself
as part of that step.)

#### 4b. Download and back up

Pull the production data file(s) the migration script touches from the share
(`az storage file download`). Before changing anything, save two backups:
- a local copy in the scratchpad
- a re-upload of the *untouched original* under a `backups/` path on the same
  share (e.g. `backups/receipts-<timestamp>.json`)

so there's a recovery point independent of the local machine.

#### 4c. Preview locally

Run the migration script against the *downloaded local copy* — not the live
share — and show its before/after summary (the existing script pattern already
prints a count of what changed). Nothing production-facing has been touched yet.

#### 4d. Confirm

Pause and show the user the preview summary. Get explicit confirmation before
the next step. This is a real, hard-to-reverse write to production user data,
unlike everything done in local/test contexts — proceed only on a clear yes.

#### 4e. Apply

Upload the now-migrated local copy back to the share via `az storage file
upload`, overwriting the live file. This is the step that actually changes
production. Then:

```
az webapp start --name shopping-tracker-app --resource-group shopping-tracker-rg
```

to bring the app back — Step 7's code deploy will recycle it again regardless,
but there's no reason to leave it stopped any longer than necessary.

### Step 5 — Prepare the release entry (version + What's New)

The app shows its version in the footer and lists every release on the What's New
page, both read from `releases.json` (newest release first, SP-046). Step 6 packages
`git archive HEAD`, which only contains *committed* files, so the new entry must be
committed **before** packaging. Because a commit can't contain its own SHA, never
store commit SHAs in `releases.json` — the SHA lives in the deployment marker
(Step 9) and the `**Deployed**` lines (Step 10).

#### 5a. Find the stories shipping in this release

If Step 3 found a marker, list the SP commits in the range:

```
git log <marker-commit>..HEAD --format=%s --grep="^SP-[0-9]"
```

Extract the SP numbers from the subjects. (The "Mark ... as deployed" and
"Release N" commits don't start with `SP-`, so they never match.)

- **No marker found**: there is no range to diff. Ask the user which SPs this
  release covers, or whether to skip the release step and go to Step 6.
- **Range found but no commit matches** (a non-SP change, e.g. a config tweak):
  tell the user and ask whether to create a release anyway (with hand-written
  change text) or deploy without a version bump (skip to Step 6).

#### 5b. Check whether a release entry is already pending

This keeps the step safe to re-run: a previous deploy may have committed its
`Release N` entry and then failed, and bumping again would skip a version number.

Read the top version of `releases.json` at the marker commit (`prev`) and at
`HEAD` (`head`), using the project's venv Python (Bash path shown; use
`.\venv\Scripts\python.exe` in PowerShell):

```
git show <marker-commit>:releases.json | ./venv/Scripts/python.exe -c "import json,sys; d=json.load(sys.stdin); print(d[0]['version'] if d else 0)"
./venv/Scripts/python.exe -c "import json; d=json.load(open('releases.json',encoding='utf-8')); print(d[0]['version'] if d else 0)"
```

If `git show` fails or the file is missing or unreadable (for example, the marker
predates `releases.json`), treat that version as `0`. In that case the first command
prints a Python `JSONDecodeError` traceback because it received no input - that is
expected, not a problem. With no marker, `prev` is `0`.

- **`head` > `prev`**: an entry for the not-yet-deployed release already exists
  (a failed earlier deploy, or a version committed together with a feature).
  **Do not bump the version.** Show that entry to the user and compare its
  `changes` with the SP numbers from 5a:
  - It covers every shipping SP: reuse it as is, and go straight to Step 6.
  - It is missing some: show the entry and the missing SPs, and ask whether to
    **extend** it (add the missing SPs' changes) or **replace** its text. Either
    way the version number stays `head`. Continue with 5c.
- **`head` == `prev`**: this is a new release. The version is `head + 1`
  (so `1` if there is no `releases.json` yet). Continue with 5c.

#### 5c. Draft the entry and get approval

For each shipping SP read `backlog/done/SP-NNN-*.md` (title and description) and
draft one short, plain-language sentence for an end user of the app, as
`{"sp": "NNN", "text": "..."}`. SP titles are often technical, so rewrite them
(for example "Normalize Categories to a Category ID" is not a useful release note).
An internal-only story (infrastructure or tooling, no visible change) may be left
out of `changes` **only if the user agrees**.

Show the complete draft entry — version, today's date (`YYYY-MM-DD`), and the
list of changes — and ask the user to approve it or edit the text. Say clearly
that approval also means: commit it as `Release N` and push it to `origin/main`.
Wait for an explicit yes. Write nothing before that.

#### 5d. Write the entry, commit and push

Only after approval, update `releases.json` (a missing file starts as an empty
list). Insert a new entry at the top, or, when 5b chose extend/replace, overwrite
the existing top entry with the same `version`:

```
./venv/Scripts/python.exe - <<'EOF'
import json
path = 'releases.json'
try:
    data = json.load(open(path, encoding='utf-8'))
except OSError:
    data = []
entry = {"version": N, "date": "YYYY-MM-DD", "changes": [{"sp": "NNN", "text": "..."}]}
if data and data[0]['version'] == entry['version']:
    data[0] = entry          # extend / replace the pending entry
else:
    data.insert(0, entry)    # new release goes first (newest first)
with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')
EOF
```

Then check the file still loads, and commit and push:

```
git add releases.json
git commit -m "Release N"
git push origin main
```

`HEAD` is now the Release commit, so Step 6 packages it and Step 9 records its SHA
as the deployed commit; the next deploy compares against this release.

### Step 6 — Build the deployment package

```
git archive --format=zip --output=<scratchpad>/deploy.zip HEAD
```

Same technique proven in SP-011 — only git-tracked files get included, so
`.env`, `venv/`, and local `data/` never end up in the package.

### Step 7 — Deploy using the proven-working command

**Do not use `az webapp deploy --type zip`** — SP-011 documented that it uses
the newer OneDeploy path, which silently skips the Oryx build step regardless of
`SCM_DO_BUILD_DURING_DEPLOYMENT`, producing a site that reports "deployed" but
never actually starts (missing dependencies). Use the classic path instead:

```
az webapp deployment source config-zip --resource-group shopping-tracker-rg --name shopping-tracker-app --src <scratchpad>/deploy.zip
```

Expect 1-3 minutes on the F1 plan (Oryx build + container restart). Watch the
output for "Site failed to start." If that happens, don't guess — pull real logs
the way SP-011 did (`az webapp log deployment show`, `az webapp log download`)
rather than retrying blindly. Known past root causes: the OneDeploy build-skip
above, and a shell-quoting bug in the startup command (see SP-011's Progress Log
for the exact fix via `az rest --method patch` if the startup command itself
ever needs to change).

### Step 8 — Verify

Request `https://shopping-tracker-app.azurewebsites.net` and confirm a `200`
that redirects to `/login`. This proves the real app started (not a crashed
container serving a stale response) — the same check used at the end of SP-011.

### Step 9 — Record the new deployment marker

Only after Step 8's verification passes: write a local
`deployment_state.json` with the current commit (`git rev-parse HEAD` and
`git rev-parse --short HEAD`) and the current UTC timestamp, then upload it to
the share via `az storage file upload`, overwriting the previous marker:

```json
{"commit": "<full sha>", "short": "<short sha>", "deployed_at": "<ISO8601 UTC>"}
```

### Step 10 — Mark deployed stories

Only after Step 9 succeeds. Every `/sdlc-done` commit's message starts with
`SP-NNN: Title` (established convention — check `git log --oneline` against
`backlog/done/`), which makes the shipped stories in this deploy mechanically
identifiable, no separate tracking needed:

- **If Step 3 found a prior marker**: run
  `git log <previous-marker-commit>..HEAD --oneline --grep="^SP-[0-9]"` over the
  just-shipped range and extract the SP number from each matching commit subject.
- **If Step 3 found no prior marker** (first tracked deploy): treat every file
  currently in `backlog/done/` as shipped by this deploy — that's factually true,
  since this deploy is the first one this system has tracked and it shipped
  everything currently on `main`.

For each matched `backlog/done/SP-{NNN}-*.md`, add or update a line
`**Deployed**: <short-sha> (<date>)` immediately after the `**Fulfils**:` line
(or after `**Status**:` if the file has no `Fulfils` line). This is separate
from — and doesn't change — the existing `**Status**: Done`; it answers a
different question ("is this story's code actually live?"), so it must not
collide with the `Status` values `sdlc-list` sorts on.

If any files were updated, stage them together and ask the user once: "Commit
and push 'Mark SP-{NNN}[, SP-{NNN}...] as deployed (<short-sha>)'? (yes / no)".
If confirmed, commit with that message and push in the same step:
`git commit -m "Mark SP-{NNN}[, SP-{NNN}...] as deployed (<short-sha>)"` then
`git push origin main`.

If no commits in the shipped range matched `^SP-[0-9]` (e.g. a deploy of some
non-SP change), skip this step entirely — nothing to mark.

### Step 11 — Report

Summarize for the user:
- The deployed commit (short SHA)
- The released version number and its What's New changes (or "no version bump"
  if Step 5 was skipped)
- The commits shipped since the previous deploy (or "no prior marker found" on
  a first run)
- Whether a data migration ran, and its outcome
- Which stories got marked `**Deployed**` (or none)
- The verification result
- The live URL
