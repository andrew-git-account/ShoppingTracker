# SP-011: Deploy Application to Azure

**Priority**: High
**Status**: Ready

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

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
