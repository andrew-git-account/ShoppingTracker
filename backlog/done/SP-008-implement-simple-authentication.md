# SP-008: Implement Simple Authentication (Route Protection + OTP Flow)

**Priority**: High
**Status**: Done
**Fulfils**: BS-013, BS-014, BS-015, BS-016, BS-017, BS-018

## Description
Before deploying the application to the Internet there is a need to protect it with simple authentication. Without authentication, anyone who knows the URL can view and upload receipts, which is a privacy risk.

Authentication works as follows:
- A predefined list of allowed email addresses is stored in `data/allowed_users.json`
- When an unauthenticated user visits any page, they are redirected to the login page
- The login page asks for an email address
- If the email is in the allowed list, a 5-digit OTP code is generated and written to `server.log` (mocked delivery — real email sending is SP-009)
- The user is then shown a second screen to enter the code
- If the code matches, the user is granted access and a session is created

## Acceptance Criteria
- [x] Unauthenticated users who visit `/`, `/upload`, or `/history` are redirected to `/login`
- [x] Entering an email NOT in `allowed_users.json` shows an error: "Email address not authorised"
- [x] Entering an allowed email generates a 5-digit code and logs it to `server.log`, then shows the code-entry screen
- [x] Entering the correct code grants access and redirects to the upload page
- [x] Entering a wrong code shows an error: "Invalid code, please try again"
- [x] A logged-in user clicking "Log out" is redirected to `/login` and can no longer access protected pages
- [x] Allowed emails are read from `data/allowed_users.json` (a JSON array of strings, e.g. `["you@example.com"]`); this file is gitignored

## Notes / Context
- `data/allowed_users.json` is a JSON array of email strings: `["alice@example.com", "bob@example.com"]`. Gitignored alongside `data/receipts.json`.
- Flask's built-in `session` object (signed cookie) is used to track login state — no extra library needed
- OTP delivery is mocked in this SP: write the generated code to `server.log` so it can be read during development. Real SMTP sending is handled in SP-009.
- OTP should expire after 10 minutes (store generation timestamp in session)
- Protect all routes: `/`, `/upload`, `/history`, and any future routes — use a `before_request` hook or a `login_required` decorator
- The login page itself (`/login`) and the code-entry page (`/verify`) must be publicly accessible
- Add `SECRET_KEY` to `.env` (Flask needs it to sign sessions); generate with `python -c "import secrets; print(secrets.token_hex(32))"`

## Implementation Notes
**Completed:** 2026-06-26

**New files:**
- `app/services/auth_service.py` — `AuthService` class: loads `allowed_users.json`, generates 5-digit OTP, stores OTP + 10-minute expiry in Flask session, verifies submitted code
- `templates/login.html` — email entry form (step 1 of login flow)
- `templates/verify.html` — OTP code entry form (step 2 of login flow)
- `data/allowed_users.json` — initial allowed users list with `andrew.bihun@gmail.com`
- `tests/conftest.py` — pytest fixtures: app factory with mocked LLM and temp allowed_users.json
- `tests/test_auth.py` — 15 tests covering all acceptance criteria

**Modified files:**
- `app/services/__init__.py` — exported `AuthService`
- `app/main.py` — instantiated `AuthService` with `data/allowed_users.json` path; attached as `app.auth_service`
- `app/routes.py` — added `before_request` guard; added `/login`, `/verify`, `/logout` routes
- `templates/base.html` — nav tabs hidden when not logged in; "Log out" link added
- `static/css/style.css` — added `.auth-card` and `.auth-back` styles for login/verify pages

**Tests:** 15 added, 15 passed
