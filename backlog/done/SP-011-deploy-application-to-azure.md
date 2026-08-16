# SP-011: Deploy Application to Azure

**Priority**: High
**Status**: Done
**Fulfils**: n/a (infrastructure)

## Description
Deploy ShoppingTracker to Azure App Service so it is accessible on the Internet. Includes adding gunicorn as the production WSGI server, configuring Azure App Settings for all environment variables, and mounting Azure Files for persistent JSON data storage so receipts and allowed_users.json survive restarts and redeployments.

## Acceptance Criteria
- [x] The application is accessible at a public URL (e.g. `https://shopping-tracker-app.azurewebsites.net`)
- [x] Visiting the URL shows the login page (authentication is enforced)
- [x] A receipt can be uploaded and appears in History after the page reloads
- [x] Uploaded receipts and the allowed users list persist after the app is restarted or redeployed
- [x] All secrets (API keys, SMTP credentials, SECRET_KEY) are stored in Azure App Settings — not in any committed file
- [x] The app is served over HTTPS

## Notes / Context
- **Runtime**: Python 3.13 on Azure App Service (Linux)
- **WSGI server**: `gunicorn` — add to `requirements.txt`; create `startup.txt` with:
  `gunicorn --bind=0.0.0.0:8000 --timeout 600 "app.main:create_app()"`
- **Persistent storage**: Azure Files (SMB share) mounted at `/data`; set `DATA_FOLDER=/data` in App Settings. This makes the JSON database survive restarts without any code changes.
- **App Settings to configure**: `ANTHROPIC_API_KEY`, `SECRET_KEY`, `FLASK_ENV=production`, `LLM_MODEL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `DATA_FOLDER=/data`
- **Recommended SKU**: B1 (~$13/month) — needed for custom domain and SSL. F1 (free) works but sleeps after 20 min of inactivity.
- **Deployment method**: ZIP deploy via Azure CLI (`az webapp deploy`) or connect GitHub for auto-deploy on push to main
- See conversation research notes for full CLI command sequence

## Actual resource decisions (as of 2026-08-15)
- **Chosen SKU**: F1 (Free) — confirmed fully working, including the Azure Files
  mount (see Progress Log step 7). No B1 upgrade needed after all.
- **Chosen region**: `switzerlandnorth` for all resources (App Service plan,
  storage account, file share). Rejected in order: `westeurope` (subscription not
  accepted there), `northeurope` and `eastus` (F1 specifically unavailable there —
  see Progress Log for why). Switzerland North is also the closest region to the
  account holder.
- **Resource names**:
  - Resource group: `shopping-tracker-rg` (region tag on the RG itself is
    `westeurope`, but that's just metadata — doesn't need to match where actual
    resources live)
  - Storage account: `shoppingtrackerstch` (Switzerland North) — note: an earlier
    attempt used `shoppingtrackerst` in North Europe; that account was deleted
    once the region moved to Switzerland North, and the name `shoppingtrackerst`
    is now stuck in Azure's post-delete reservation grace period, hence the `ch`
    suffix on the replacement
  - Azure Files share: `shopping-data` (inside `shoppingtrackerstch`), mounted on
    the web app at `/data`
  - App Service plan: `shopping-tracker-plan` (Switzerland North, F1, Linux)
  - Web app: `shopping-tracker-app` — live at
    `https://shopping-tracker-app.azurewebsites.net` (placeholder page, code not
    deployed yet), confirmed `HttpsOnly: True` by default

## Progress Log

### Done
1. **Azure CLI installed and authenticated** — `az login`, confirmed via
   `az account show` (subscription: "Azure subscription 1",
   id `d1b84394-a2c5-4759-8d92-1871f97586f1`).
2. **Resource group created**:
   `az group create --name shopping-tracker-rg --location westeurope` — verified via
   `az group show` and in the portal.
3. **Resource providers registered** — `Microsoft.Storage` and `Microsoft.Web` were
   both `NotRegistered` by default on this subscription, which caused a misleading
   `SubscriptionNotFound` error on the first storage account create attempt. Fixed
   with `az provider register --namespace Microsoft.Storage` and
   `az provider register --namespace Microsoft.Web`, confirmed `Registered` via
   `az provider show --namespace <name> --query registrationState`.
4. **Storage account + file share created in Switzerland North** (final location,
   after two earlier region changes — see below):
   `az storage account create --name shoppingtrackerstch --resource-group shopping-tracker-rg --location switzerlandnorth --sku Standard_LRS`
   and `az storage share create --name shopping-data --account-name shoppingtrackerstch`
   — both `Succeeded`, confirmed via CLI.
5. **App Service plan created**: `shopping-tracker-plan` (F1, Linux, Switzerland
   North) via
   `az appservice plan create --name shopping-tracker-plan --resource-group shopping-tracker-rg --location switzerlandnorth --is-linux --sku F1`
   — `ProvisioningState: Succeeded`, `Status: Ready`.

### Resolved: the "Total VMs: 0" App Service plan quota block
This took a long time to work through — full trail, in case it recurs:

1. First hypothesis: `westeurope` rejected new resources entirely
   (`RequestDisallowedByAzure`) → switched to `northeurope`. Storage account/share
   created fine there.
2. `az appservice plan create` (F1, North Europe) failed:
   `Current Limit (Total VMs): 0`. Retried in `eastus` — same error → concluded
   subscription-wide, not region-specific (this turned out to be wrong — see below).
3. `az vm list-usage` returned **zero entries at all**, and provider check showed
   `Microsoft.Storage`/`Microsoft.Web` were `NotRegistered` (same class of issue
   that caused the earlier storage `SubscriptionNotFound` error). Registered both;
   didn't fix the App Service plan error.
4. Tried filing a quota-increase ticket via `az support in-subscription tickets
   create` → rejected with `InvalidSupportPlan` (the Support Management REST API
   requires a *paid support plan*, separate from the subscription's billing offer,
   even for free quota requests). Portal's dedicated Quotas app "New Quota
   Request" button was also inactive/unclickable.
5. Upgraded the subscription Free Trial → Pay-As-You-Go (confirmed via
   `az account subscription show --query subscriptionPolicies`:
   `quotaId` → `PayAsYouGo_2014-09-01`). Re-ran `az login`. Same error persisted.
6. Checked `Microsoft.Compute` and `Microsoft.Capacity` providers — also
   `NotRegistered`. Registered both. **This fixed the general compute quota** —
   `az vm list-usage` went from zero entries to a full list (`Total Regional
   vCPUs`: limit 10, etc.) — but `az appservice plan create` (F1) **still** hit
   the exact same `Total VMs: 0` error.
7. Root cause found: the error's `Total VMs` bucket doesn't appear anywhere in
   `az vm list-usage` output and has no matching entry in the portal's Quotas UI
   — it's F1's own, separate free-tier allocation, not general compute quota.
   Confirmed via `az appservice list-locations --sku FREE` that F1/Linux was
   listed as "available" in North Europe regardless — so this isn't a hard
   region restriction either, just an **empty free-tier capacity pool for this
   subscription in that specific region**.
8. **Fix**: tried F1 creation in a different region (`switzerlandnorth`) — worked
   immediately (`ProvisioningState: Succeeded`). So `westeurope`/`northeurope`/
   `eastus` simply didn't have free-tier capacity available for this subscription
   at this time; Switzerland North did. Moved the storage account + file share to
   match (deleted the North Europe `shoppingtrackerst`, recreated as
   `shoppingtrackerstch` in Switzerland North — the old name is stuck in Azure's
   post-delete reservation grace period, hence the renamed account).

**Takeaway for future SPs**: when an App Service quota/capacity error mentions a
bucket name that isn't in `az vm list-usage`, suspect a region-specific free/basic
tier capacity limit rather than a subscription-wide quota — trying another region
is a free, fast test before spending time on quota tickets or paid-tier upgrades.

6. **Web app created**: `az webapp create --name shopping-tracker-app --resource-group shopping-tracker-rg --plan shopping-tracker-plan --runtime "PYTHON:3.13"`
   — live at `https://shopping-tracker-app.azurewebsites.net` (verified `200 OK`,
   showing Azure's default placeholder page since no code is deployed yet).
7. **Azure Files share mounted at `/data`**:
   `az webapp config storage-account add --name shopping-tracker-app --resource-group shopping-tracker-rg --custom-id shopping-data --storage-type AzureFiles --account-name shoppingtrackerstch --share-name shopping-data --mount-path /data --access-key <key>`
   — confirmed via `az webapp config storage-account list`, then
   `az webapp restart` to apply it. **This answers the original open question from
   the start of this SP: F1 does support the Azure Files storage mount** — no need
   to upgrade to B1 for persistence after all.

8. **App Settings configured** — all 10 keys (`ANTHROPIC_API_KEY`, `SECRET_KEY`,
   `FLASK_ENV=production`, `LLM_MODEL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
   `SMTP_PASSWORD`, `SMTP_FROM`, `DATA_FOLDER=/data`) set from local `.env` values
   via `az webapp config appsettings set` (values never printed to the transcript —
   verified with `--query "[].name"` only). Also set
   `SCM_DO_BUILD_DURING_DEPLOYMENT=true` (needed for step 11 — see below).
9. **`gunicorn==23.0.0` added to `requirements.txt`** — can't be verified locally
   (Windows dev machine; gunicorn imports `fcntl`, a POSIX-only module, so it can't
   even be imported on Windows), only verifiable once actually running on Azure's
   Linux container — confirmed working in step 11.
10. **`startup.txt` added** to the repo with the gunicorn launch command. Also set
    explicitly via App Service's startup command config for reliability (see the
    quoting bug in step 11 — this ended up mattering a lot).
11. **Code deployed** — multiple failed attempts before success, all logged here
    since the failure modes are non-obvious:
    - Attempt 1: `az webapp deploy --type zip` → site failed to start after 10 min.
      Deployment log showed `"Project type: OneDeploy"` → `"Copying the
      manifest"` → done in ~2s — **no Oryx build ran at all**, despite
      `SCM_DO_BUILD_DURING_DEPLOYMENT=true` being set. Turns out `az webapp
      deploy --type zip` uses the newer OneDeploy path, which doesn't honor that
      setting the way classic Kudu zip-deploy does.
    - Attempt 2: switched to `az webapp deployment source config-zip` (deprecated
      but still functional, classic Kudu path) → this time Oryx build genuinely
      ran (~49s, 0 errors/warnings) but the site **still** failed to start.
    - Root cause: the explicit startup command set in step 10 via `az webapp
      config set --startup-file "..."` had its outer quotes consumed by
      PowerShell, so Azure stored `appCommandLine` as `gunicorn ... 
      app.main:create_app()` **without quotes** around the factory call. When
      Azure's container runs that through a shell, the bare `()` gets parsed as
      shell syntax (looks like a function definition) instead of being passed to
      gunicorn as one argument — a shell syntax error, exit code 2, zero stdout
      captured (confirmed via `az webapp log download` — the container stream log
      was completely empty for every failed attempt).
    - Fix: set `appCommandLine` via `az rest --method patch` on
      `/config/web` with a JSON file body (sidesteps PowerShell/cmd nested-quoting
      entirely — JSON handles the embedded quotes cleanly) so the stored value is
      literally `gunicorn --bind=0.0.0.0:8000 --timeout 600
      "app.main:create_app()"` with real quote characters preserved. Restarted →
      **worked immediately**.
12. **Public URL + login page confirmed**: `https://shopping-tracker-app.azurewebsites.net`
    redirects to `/login`, response contains "Shopping Tracker" branding and the
    email input — confirms BS-013 (unauthenticated access redirected to login) is
    working in production.
13. **HTTPS confirmed** — `HttpsOnly: True` by default on the web app (verified in
    step 6), and the working URL itself is `https://`.

### Done (with one more bug fixed along the way)
14. **End-to-end smoke test (upload → history)** — first login attempt failed with
    "Email address not authorised." Root cause: `allowed_users.json` lives under
    `DATA_FOLDER` (`/data` in production), which is gitignored and never part of
    the deployed code — the mounted Azure Files share started completely empty
    for this file (unlike `receipts.json`/`categories.json`, which
    `JSONDatabase`/`CategoryDatabase` auto-create on first use;
    `AuthService._load_allowed_users()` just returns `[]` if the file is missing,
    per `app/services/auth_service.py`, rather than creating a default). Fixed by
    uploading the local `data/allowed_users.json` directly to the share:
    `az storage file upload --share-name shopping-data --account-name shoppingtrackerstch --source data/allowed_users.json --path allowed_users.json`
    — no restart needed, since `is_email_allowed()` re-reads the file on every
    call rather than caching it at startup. Account holder then logged in
    successfully via the real emailed OTP and confirmed a receipt uploaded and
    appeared on History.
15. **Data persistence across restart confirmed**: `receipts.json` on the share
    was 3258 bytes (up from the initial empty `[]`, 2 bytes) after the upload.
    Ran `az webapp restart`; site came back up (`200` at `/login`) and
    `receipts.json` was still 3258 bytes with the same last-modified timestamp —
    proves the data lives on the persistent Azure Files mount, not the
    container's ephemeral disk.

**All 6 acceptance criteria confirmed.** Ready for `/sdlc-done 11`.

## Implementation Notes
**Completed**: 2026-08-16

This SP was carried out interactively via Azure CLI over several sessions rather
than as a single code change — the full step-by-step trail (every command run,
every failure, and its root cause) is preserved above in the **Progress Log**
section rather than duplicated here. Summary:

**Infrastructure created** (all in Switzerland North, after West
Europe/North Europe/East US each rejected something along the way):
`shopping-tracker-rg` (resource group), `shoppingtrackerstch` (storage account),
`shopping-data` (Azure Files share, mounted at `/data`), `shopping-tracker-plan`
(App Service plan, F1/Free/Linux), `shopping-tracker-app` (the web app itself,
live at `https://shopping-tracker-app.azurewebsites.net`).

**Code changes**: `requirements.txt` (+`gunicorn==23.0.0`), `startup.txt` (new).

**Five distinct real bugs found and fixed along the way** (not just
configuration steps — each cost real debugging time, so recorded here for
future SPs touching this deployment):
1. `Microsoft.Storage`/`Microsoft.Web` resource providers were unregistered by
   default, producing a misleading `SubscriptionNotFound` error.
2. F1 App Service plans draw from a region-specific free-tier capacity pool
   that's separate from general compute quota and isn't visible in
   `az vm list-usage` or the portal's Quotas UI — West Europe/North Europe/East
   US all had none available for this subscription; Switzerland North did.
3. `az webapp deploy --type zip` (OneDeploy) silently skips the Oryx build step
   regardless of `SCM_DO_BUILD_DURING_DEPLOYMENT` — needed the classic
   `az webapp deployment source config-zip` path instead.
4. PowerShell stripped the quotes around gunicorn's factory-call syntax
   (`"app.main:create_app()"`) when passed via `az webapp config set
   --startup-file`, causing a shell parse error on every container start (exit
   code 2, no stdout) — fixed by patching `appCommandLine` directly via
   `az rest` with a JSON file body.
5. `allowed_users.json` is gitignored (lives under `DATA_FOLDER`) and was never
   deployed with the code; unlike `receipts.json`/`categories.json` (which the
   database classes auto-create), `AuthService` doesn't create a default —
   uploaded the local file directly to the Azure Files share to fix.

**Verification**: all 6 acceptance criteria confirmed directly — public HTTPS
URL, login enforced, a real receipt uploaded via the emailed OTP and shown on
History, and data confirmed surviving a full `az webapp restart` (receipts.json
unchanged at 3258 bytes/same timestamp on the Azure Files share afterward). All
secrets live only in Azure App Settings, never committed.

No test suite changes — this SP is infrastructure/deployment, not application
code, so `tests/` is unaffected (`pytest` was not re-run as part of this SP).
