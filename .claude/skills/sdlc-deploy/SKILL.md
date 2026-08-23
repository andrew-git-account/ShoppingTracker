---
name: sdlc-deploy
description: Redeploy the current code to the already-provisioned Azure App Service (shopping-tracker-app) for the ShoppingTracker project. Use when the user asks to deploy, redeploy, push to Azure, or update the live app. Assumes SP-011's infrastructure already exists - this only pushes new code, it does not provision infrastructure or change App Settings.
---

## Redeploying to Azure

When invoked (`/sdlc-deploy`), follow these steps in order.

Known-good values from SP-011 (`backlog/done/SP-011-deploy-application-to-azure.md`):
resource group `shopping-tracker-rg`, app `shopping-tracker-app`, storage account
`shoppingtrackerstch`, file share `shopping-data`, live URL
`https://shopping-tracker-app.azurewebsites.net`.

### Step 1 — Check for uncommitted changes

`git status --short`. Deployment packages only committed content (see Step 5), so
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
  files). Keep the changed-files list for Step 4.
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
with no migration — `config-zip` in Step 6 already recycles the container itself
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

to bring the app back — Step 6's code deploy will recycle it again regardless,
but there's no reason to leave it stopped any longer than necessary.

### Step 5 — Build the deployment package

```
git archive --format=zip --output=<scratchpad>/deploy.zip HEAD
```

Same technique proven in SP-011 — only git-tracked files get included, so
`.env`, `venv/`, and local `data/` never end up in the package.

### Step 6 — Deploy using the proven-working command

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

### Step 7 — Verify

Request `https://shopping-tracker-app.azurewebsites.net` and confirm a `200`
that redirects to `/login`. This proves the real app started (not a crashed
container serving a stale response) — the same check used at the end of SP-011.

### Step 8 — Record the new deployment marker

Only after Step 7's verification passes: write a local
`deployment_state.json` with the current commit (`git rev-parse HEAD` and
`git rev-parse --short HEAD`) and the current UTC timestamp, then upload it to
the share via `az storage file upload`, overwriting the previous marker:

```json
{"commit": "<full sha>", "short": "<short sha>", "deployed_at": "<ISO8601 UTC>"}
```

### Step 9 — Mark deployed stories

Only after Step 8 succeeds. Every `/sdlc-done` commit's message starts with
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

### Step 10 — Report

Summarize for the user:
- The deployed commit (short SHA)
- The commits shipped since the previous deploy (or "no prior marker found" on
  a first run)
- Whether a data migration ran, and its outcome
- Which stories got marked `**Deployed**` (or none)
- The verification result
- The live URL
