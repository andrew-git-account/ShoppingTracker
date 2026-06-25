# SP-009: Wire Up SMTP Email Delivery for OTP

**Priority**: High
**Status**: Done
**Fulfils**: BS-015 (real email delivery for OTP)

## Description
SP-008 implemented authentication with OTP codes logged to `server.log` for development. This SP replaces the mock delivery with real email sending via SMTP, so that deployed users receive their login code by email.

## Acceptance Criteria
- [x] When an allowed user submits their email on the login page, they receive an email at that address containing the 5-digit code within 30 seconds
- [x] The email subject is "Your ShoppingTracker login code" and the body contains the code clearly
- [x] If the SMTP send fails (e.g. wrong credentials), the login page shows an error: "Could not send code — please try again" and logs the exception to `server.log`
- [x] SMTP credentials are read from `.env` (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`) — not hardcoded
- [x] The mocked log-only code path is removed

## Notes / Context
- Use Python's built-in `smtplib` + `email.mime` — no extra library needed
- SMTP config in `.env`:
  ```
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=your@gmail.com
  SMTP_PASSWORD=your-app-password
  SMTP_FROM=your@gmail.com
  ```
- For Gmail: generate an App Password at myaccount.google.com → Security → App Passwords (requires 2FA enabled)
- For development/testing without a real account: use [Mailtrap.io](https://mailtrap.io) free tier — it captures emails without sending them
- Use `STARTTLS` (`smtplib.SMTP` on port 587 with `.starttls()`) — not `SMTP_SSL`
- Depends on SP-008 being completed first

## Implementation Notes
**Completed:** 2026-06-26

**Modified files:**
- `app/services/auth_service.py` — replaced `log_otp()` mock with `send_otp_email()` using `smtplib` + `email.mime.text.MIMEText`; added `EmailDeliveryError` exception class; added SMTP config args to `__init__()`
- `app/services/__init__.py` — exported `EmailDeliveryError`
- `app/main.py` — passed five SMTP env vars (`SMTP_HOST/PORT/USER/PASSWORD/FROM`) into `AuthService` constructor
- `app/routes.py` — imported `EmailDeliveryError`; wrapped `send_otp_email()` call in try/except; flashes "Could not send code — please try again" on failure
- `.env.example` — added SMTP configuration section with Gmail and Mailtrap guidance
- `tests/test_auth.py` — patched `send_otp_email` in two tests that POST to `/login` (previously called the removed `log_otp` implicitly)

**New files:**
- `tests/test_smtp_auth.py` — 7 tests: mock removed, env var wiring, send called with correct args, subject/body content, SMTP failure flash message, no redirect on failure, smtplib exception wrapping

**Tested manually:** OTP email confirmed delivered to Mailtrap.io inbox.

**Tests:** 7 added, 90 total passed
