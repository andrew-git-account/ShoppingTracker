# SP-009: Wire Up SMTP Email Delivery for OTP

**Priority**: High
**Status**: Open

## Description
SP-008 implemented authentication with OTP codes logged to `server.log` for development. This SP replaces the mock delivery with real email sending via SMTP, so that deployed users receive their login code by email.

## Acceptance Criteria
- [ ] When an allowed user submits their email on the login page, they receive an email at that address containing the 5-digit code within 30 seconds
- [ ] The email subject is "Your ShoppingTracker login code" and the body contains the code clearly
- [ ] If the SMTP send fails (e.g. wrong credentials), the login page shows an error: "Could not send code — please try again" and logs the exception to `server.log`
- [ ] SMTP credentials are read from `.env` (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`) — not hardcoded
- [ ] The mocked log-only code path is removed

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
_Filled in when the work is done, before moving to backlog/done/._
