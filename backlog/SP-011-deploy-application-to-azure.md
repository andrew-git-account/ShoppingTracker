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

## Actual resource decisions (as of 2026-08-11)
- **Chosen SKU**: F1 (Free) — trying this first; will upgrade the App Service plan to
  B1 only if the Azure Files mount (step 7 below) turns out to require a paid tier.
  Could not confirm from Microsoft docs either way, so this is being determined
  empirically.
- **Chosen region**: `northeurope`, not the originally planned `westeurope` —
  West Europe rejected new resources on this subscription ("not accepting new
  customers" for this account). Storage account and file share are already created
  in North Europe; App Service plan/app should stay in the same region to avoid
  latency.
- **Resource names**:
  - Resource group: `shopping-tracker-rg` (region tag: westeurope, but this is just
    metadata — doesn't need to match where actual resources live)
  - Storage account: `shoppingtrackerst` (North Europe)
  - Azure Files share: `shopping-data` (inside `shoppingtrackerst`)
  - App Service plan (planned, not yet created): `shopping-tracker-plan`
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
4. **Storage account created** (after a failed West Europe attempt —
   `RequestDisallowedByAzure: region not accepting new customers`):
   `az storage account create --name shoppingtrackerst --resource-group shopping-tracker-rg --location northeurope --sku Standard_LRS`
   — `ProvisioningState: Succeeded`, confirmed in portal.
5. **Azure Files share created**:
   `az storage share create --name shopping-data --account-name shoppingtrackerst`
   — confirmed via `az storage share list` and in the portal.

### Blocked
6. **App Service plan creation is blocked on a subscription quota issue.**
   Attempted:
   `az appservice plan create --name shopping-tracker-plan --resource-group shopping-tracker-rg --location northeurope --is-linux --sku F1`
   → `ERROR: Operation cannot be completed without additional quota. Current Limit
   (Total VMs): 0`. Retried in `eastus` — same error, so it's subscription-wide, not
   region-specific. `az vm list-usage --location eastus` returns **zero quota
   entries at all** — this subscription has no baseline compute quota provisioned
   yet (common gap for brand-new Azure Free Trial accounts), and the portal's "My
   Quotas" page confirms the same (no entries to request an increase against).

   **Decision**: waiting it out (quota sometimes self-provisions within 24-48h of
   account creation) rather than opening a support ticket or upgrading to
   Pay-As-You-Go. Retry `az appservice plan create` (command above) periodically —
   once quota exists, resume at step 7 below.

### Not started yet
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
