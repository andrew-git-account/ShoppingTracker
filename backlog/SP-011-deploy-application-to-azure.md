# SP-011: Deploy Application to Azure

**Priority**: High
**Status**: In Progress

## Description
Deploy ShoppingTracker to Azure App Service so it is accessible on the Internet. Includes adding gunicorn as the production WSGI server, configuring Azure App Settings for all environment variables, and mounting Azure Files for persistent JSON data storage so receipts and allowed_users.json survive restarts and redeployments.

## Acceptance Criteria
- [ ] The application is accessible at a public URL (e.g. `https://shopping-tracker-app.azurewebsites.net`)
- [ ] Visiting the URL shows the login page (authentication is enforced)
- [ ] A receipt can be uploaded and appears in History after the page reloads
- [ ] Uploaded receipts and the allowed users list persist after the app is restarted or redeployed
- [ ] All secrets (API keys, SMTP credentials, SECRET_KEY) are stored in Azure App Settings — not in any committed file
- [ ] The app is served over HTTPS

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
- **Chosen SKU**: F1 (Free) — confirmed working (see Progress Log). Will still
  upgrade to B1 later only if the Azure Files mount (step 7) turns out to need it.
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
  - Azure Files share: `shopping-data` (inside `shoppingtrackerstch`)
  - App Service plan: `shopping-tracker-plan` (Switzerland North, F1, Linux)
  - Web app (planned, not yet created): `shopping-tracker-app`

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

### Not started yet
6. Create the web app (`shopping-tracker-app`) on the plan
7. Mount the Azure Files share (`shopping-data`) to the web app at `/data`
8. Configure App Settings (secrets + `DATA_FOLDER=/data`)
9. Add `gunicorn` to `requirements.txt`
10. Add `startup.txt`
11. Deploy the code
12. Confirm public URL + login page
13. Confirm HTTPS enforced
14. End-to-end smoke test (upload → history)
15. Confirm data persists across `az webapp restart`

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
