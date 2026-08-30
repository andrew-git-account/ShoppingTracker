# SP-039: Send Feedback to Admins

**Priority**: Medium
**Status**: Done
**Fulfils**: Specification/BehaviorSpec.md#BS-046 (new)

## Description
As a user, I want to send feedback to admins so that I can report issues with the application. A "Contact" button (mail icon or similar), visible on every page, opens a feedback form: message type (Bug Report / Enhancement Proposal / General Feedback, defaulting to Bug Report), related functionality (defaulting to the page the user was on when they clicked Contact, with "All" and "None" also selectable), a required text message, and an optional image attachment. Submitting stores the feedback record and emails every admin with the user's email, message type, related functionality, message text, and the attached image if one was provided.

## Acceptance Criteria
- [x] A "Contact" action (icon + label) is visible on every authenticated page, for every logged-in user (not admin-only).
- [x] Clicking it opens a feedback form pre-filled with the functionality the user was on, with fields: message type (radio or select, default "Bug Report"), functionality (select, default = current page's functionality, plus "All" and "None" options), message text (required, non-empty), image (optional, same upload constraints/allowed types as receipt image upload).
- [x] Submitting with a required field missing re-shows the form with the user's other input preserved and an error message, the same pattern used elsewhere in the app (e.g. receipt/statement editing).
- [x] On valid submission: the feedback record is saved to storage (user's email, message type, functionality, message text, image if any, timestamp) and an email is sent to every current admin (`AuthService.get_all_users()` filtered by `is_admin` and not `is_blocked`) containing the user's email, message type, functionality, message text, and the image as an attachment if one was provided.
- [x] After successful submission, the user sees a confirmation (flash message) and is redirected to History.
- [x] If the email send fails, the feedback is still saved (not lost) and the user sees an appropriate message — mirrors the existing `EmailDeliveryError` pattern already used for OTP emails, rather than losing the report if SMTP has a transient failure.
- [x] A shared `EmailService` (`app/services/email_service.py`) supports sending an email with an optional image attachment to one or more recipients; `AuthService.send_otp_email` is refactored to use it internally with no behavior change (still plain text, no attachment) — proven by the existing `AuthService`/OTP test suite passing unchanged.
- [x] Restricted to logged-in users, same auth guard as every other route in the app.

## Notes / Context

### No JS modals
This app is deliberately JS-free (see CLAUDE.md). "Opens a window" is a dedicated `GET/POST /feedback` page (full navigation), the same pattern already used for Link/Edit/Review flows — not a JS popup/modal. The nav's "Contact" link carries the page the user came from as a query param (`url_for('feedback', from=request.endpoint)`), read server-side to compute the default functionality.

### Functionality list — resolved
Centralize as one Python constant (e.g. `FEEDBACK_FUNCTIONALITIES` in `app/routes.py` or a small shared module) mapped from `request.endpoint`, mirroring the nav's actual sections (`templates/base.html`) so the two can't drift apart:
- `index`/`upload` → "Upload"
- `upload_statement` → "Upload Statement"
- `history` → "History"
- `statistics` → "Statistics"
- `llm_usage` → "LLM Usage"
- `users`/`add_user`/`toggle_user_admin`/`toggle_user_blocked` → "Users"
- Anything else (including the feedback page itself) → default to "None"

Dropdown always offers all six functionalities plus "All" and "None", regardless of the reporting user's own admin status (a non-admin can still meaningfully report "the Users link doesn't show up for me").

### Storage — resolved
New `feedback` table in the shared `data/shopping_tracker.db` (SP-034/035/036's file), via a new `SqliteFeedbackDatabase` (`app/database/sqlite_feedback_db.py`), following the existing one-connection-per-call pattern:
```sql
CREATE TABLE feedback (
    id TEXT PRIMARY KEY,
    user_email TEXT NOT NULL,
    message_type TEXT NOT NULL,
    functionality TEXT NOT NULL,
    message TEXT NOT NULL,
    image_filename TEXT,
    created_at TEXT NOT NULL
);
```
A new `FeedbackService` (mirrors `ReceiptService`'s role) owns validation, image handling, and orchestrating storage + email.

### Image storage — resolved
Reuse `ReceiptService`'s existing upload pattern (`secure_filename` + timestamp-prefixed unique filename, saved into the same `UPLOAD_FOLDER`) rather than inventing a new one. Same allowed-extensions set already used for receipt images (jpg/jpeg/png).

### Email delivery — resolved
`AuthService.send_otp_email` currently builds a plain-text-only `MIMEText` message — it has no attachment support today, so sending the optional image requires a real capability addition, not just a reuse. Extract a small `EmailService` (`app/services/email_service.py`) with `send(to_addresses: List[str], subject: str, body: str, attachment: Optional[...] = None) -> None`, using `MIMEMultipart` + an image MIME part when an attachment is given, raising the existing `EmailDeliveryError`. Refactor `AuthService.send_otp_email` to delegate to it (no behavior change - just removes the duplicated `smtplib` boilerplate), and have the new feedback-sending path use the same service for its (multi-recipient) admin email.

### Admin recipient list — resolved
`AuthService.get_all_users()` already returns every allowed user with `is_admin`/`is_blocked` flags. Recipients = active admins only (`is_admin` and not `is_blocked`), matching the "active admin" definition `_count_active_admins` already uses elsewhere.

### Route/redirect
`POST /feedback` always redirects to History on success (matches other multi-step flows like `transaction_link_confirm`) rather than trying to reconstruct the exact originating page's query string.

### Out of scope (this SP)
- Any admin-facing UI to view/manage past feedback submissions (this SP is "user submits, admin gets an email" — a dedicated feedback-inbox page could be a follow-up).
- Replying to feedback from within the app (admin replies via their own email client for now).

## Implementation Notes

Completed 2026-08-31.

- **`app/services/email_service.py`** (new): `EmailService` + `EmailDeliveryError` (moved here from `auth_service.py`). `send(to_addresses, subject, body, attachment=None)` builds a plain `MIMEText` when there's no attachment (matches the old OTP email exactly) or a `MIMEMultipart` with a `MIMEImage` part when there is one. The image's MIME subtype is derived explicitly from the filename extension rather than relying on `MIMEImage`'s default `imghdr`-based sniffing, since `imghdr` is removed in Python 3.13.
- **`app/services/auth_service.py`**: `__init__` keeps its four raw `_smtp_*` attributes unchanged (an existing test reads them directly) and additionally builds an internal `EmailService`; `send_otp_email` is now a thin delegator. Full existing `AuthService`/OTP test suite passes unchanged, confirming the extraction is behavior-preserving.
- **`app/database/sqlite_feedback_db.py`** (new): `SqliteFeedbackDatabase`, same one-connection-per-call style as the other five `Sqlite*Database` classes, sharing `shopping_tracker.db`. `save_feedback`/`get_all_feedback` (the latter unused by any route — a test seam only, matching this SP's explicit no-admin-inbox scope).
- **`app/services/feedback_service.py`** (new): `FeedbackService.submit_feedback(...)` validates (required message, allowed image extension), falls back invalid `message_type`/`functionality` select values silently (same tolerance as the receipt category `<select>`), saves the image and record, and emails active admins (`is_admin` and not `is_blocked`) without losing the saved record if the email itself fails. Found and fixed a real bug during testing: the service wasn't creating its own upload folder, silently depending on `ReceiptService` (which shares the same folder) having already created it — now creates it independently in `__init__`.
- **`app/routes.py`**: new `/feedback` GET/POST route, protected automatically by the existing `require_login` guard (not in `_PUBLIC_ENDPOINTS`, no special-casing needed). Functionality options and the endpoint-to-functionality mapping are centralized as module-level constants, kept in sync by hand with `templates/base.html`'s nav.
- **`templates/feedback_form.html`** (new) + **`templates/base.html`**: new "Contact" nav link (visible to every logged-in user, not admin-gated) and the feedback form itself. Several follow-up UI polish passes after initial implementation: widened the page and made the message textarea span full width and resize vertically; aligned Type/Functionality as label-left/selector-same-line rows (Message keeps label-above-textarea); fixed both selectors to a consistent 200px width with smaller font; equalized label column width (110px) so both selectors line up in a column; fixed the Message label's alignment (it was inheriting `.upload-form`'s `text-align: center`) and font size to match the other two labels.
- **Wiring** (`app/database/__init__.py`, `app/services/__init__.py`, `app/main.py`): all new classes exported and constructed. `FeedbackService` gets its own standalone `EmailService` instance (built from the same `SMTP_*` env vars `AuthService` already uses) rather than sharing `AuthService`'s internal one, since `AuthService`'s constructor couldn't change shape without breaking the test that reads its raw `_smtp_*` attributes.
- **Tests**: `tests/test_email_service.py` (7 tests), `tests/test_feedback_service.py` (10 tests), `tests/test_database.py::TestSqliteFeedbackDatabase` (5 tests), `tests/test_routes.py::TestFeedbackRoute` (9 tests) — 31 new tests total.
- **`Specification/BehaviorSpec.md`**: added BS-046 for the new feedback feature (a real gap — no scenario existed for it before).
- No data migration needed (new table only, no existing data to move).
- Test summary: 31 new tests added, 524 passed, 0 failed. Server boot verified repeatedly across the UI polish iterations.
