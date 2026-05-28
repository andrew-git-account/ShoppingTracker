# SP-005: Add Google Authorization to the Shopping Tracker Application

**Priority**: High 
**Status**: Open

## Description
Add Google authorization to the application so that different users can add their own purchases. Each user signs in with their Google account and can only see and manage their own receipts.

## Acceptance Criteria
- [ ] Observable, testable condition 1
- [ ] Observable, testable condition 2

## Notes / Context

### Approach
Use **Flask-Dance** library to handle OAuth 2.0 with Google. It handles the full redirect/token exchange flow.

```bash
pip install flask-dance
```

### Google Cloud Console setup
- Go to https://console.cloud.google.com
- Create a project → Enable "Google+ API" → Create OAuth credentials
- Add authorized redirect URI: `http://localhost:5001/login/google/authorized`
- Add authorized JavaScript origin: `http://localhost:5001`
- Store the credentials in `.env`:
  ```
  GOOGLE_CLIENT_ID=your-client-id
  GOOGLE_CLIENT_SECRET=your-client-secret
  ```
- Note: Google allows `localhost` URIs for development — no deployment needed to test this.
  Set `OAUTHLIB_INSECURE_TRANSPORT=1` in the dev environment to bypass the HTTPS requirement.

### Files to change

| File | Change |
|---|---|
| `requirements.txt` | Add `flask-dance` |
| `.env` / `.env.example` | Add `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` |
| `app/__init__.py` | Register the Google OAuth blueprint |
| `app/routes.py` | Guard protected routes — redirect to Google login if not authorized |
| `templates/base.html` | Add Sign in / Sign out button |
| `app/models.py` | Add `user_email` field to `Receipt` |
| `app/database/json_db.py` | Filter receipts by logged-in user's email when loading |

### Per-user data
Currently all receipts share one `receipts.json`. After auth, each receipt must store the owner's Google email (`user_email` field on the `Receipt` model). The history route must filter to only return receipts belonging to the logged-in user.

### Production note
For deployment, add the production domain alongside localhost in Google Cloud Console. Google requires HTTPS for non-localhost URIs.

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
