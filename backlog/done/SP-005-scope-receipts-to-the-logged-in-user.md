# SP-005: Scope Receipts to the Logged-In User

**Priority**: High
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-031
**Deployed**: b6f3230 (2026-08-19)

## Description
Show each logged-in user only their own receipts, not everyone's. The current OTP-based login (SP-008) is unchanged and stays as the authentication mechanism — this SP adds per-user data ownership: each receipt is tagged with the uploader's email, and every receipt-listing view (History, Statistics, Search) is filtered to the logged-in user's own receipts. Deleting a receipt is also restricted to its owner.

## Acceptance Criteria
- [x] After verifying an OTP code, the logged-in user's email is retained in the session (currently discarded by `clear_otp_from_session`) so the app knows who is logged in for the rest of the session.
- [x] A newly uploaded receipt is stored with a `user_email` field set to the email of the currently logged-in user.
- [x] The History page (`/history`) only shows receipts belonging to the logged-in user — receipts uploaded by a different user never appear, and the "Total receipts" count reflects only the logged-in user's own receipts.
- [x] The Statistics page (`/statistics`) and item search (`/history?q=...`) are also scoped to the logged-in user's own receipts.
- [x] Deleting a receipt (`/delete-receipt/<id>`) only succeeds if the receipt belongs to the logged-in user; attempting to delete another user's receipt fails the same way as deleting a nonexistent one (existing "Receipt not found" flash), without revealing that the receipt exists.
- [x] All receipts that existed before this change are backfilled with `user_email: andrew.bihun@gmail.com` (the only currently allowed user) as a one-time migration, so no historical data is lost or hidden.

## Notes / Context
- This SP does **not** touch authentication — the existing OTP/email allowlist login (SP-008, SP-009, SP-014) stays exactly as it is. This is purely about scoping *data*, not changing *how* users sign in. (An earlier draft of this SP proposed Google OAuth instead — rejected; the current auth is fine as-is.)
- **Session change**: `app/routes.py`'s `/verify` route currently does `session['logged_in'] = True` then `app.auth_service.clear_otp_from_session(session)`, which pops `otp_email` out of the session entirely (`app/services/auth_service.py`). The logged-in user's email needs to be preserved — e.g. capture it into `session['user_email']` before the OTP data is cleared.
- **Data model**: `app/models.py`'s `Receipt` class has no `user_email` field today — needs adding to `__init__`, `to_dict()`, `from_dict()`. `from_llm_response()` has no way to receive the uploader's identity currently; `ReceiptService.process_receipt()` (`app/services/receipt_service.py`) will need to accept and thread through the current user's email from the route.
- **Filtering**: `app/database/json_db.py`'s `get_all_receipts()` currently returns every non-deleted receipt with no owner filter. History, Statistics, and Search (`app/routes.py`) all currently call `app.receipt_service.get_all_receipts()` unfiltered — needs a `user_email` filter parameter (or a new filtered method) used consistently by all three.
- **Delete ownership check**: `soft_delete_receipt()` / `delete_receipt()` currently take only a `receipt_id`, with no ownership check. Needs to verify the receipt's `user_email` matches the logged-in user's before deleting.
- **Legacy data migration**: confirmed via the codebase and the live production Azure Files share that no receipt anywhere currently has a `user_email` field — it doesn't exist in the schema yet. Per decision: backfill every existing receipt to `andrew.bihun@gmail.com`, the only email currently in `allowed_users.json`. Whether this is a one-time migration script or a "missing `user_email` defaults to that address" fallback is the implementer's call — either way it must be applied to both local test data and the production Azure Files share (`/data/receipts.json`, mounted from the `shoppingtrackerstch` storage account).
- **Out of scope**: adding more users to `allowed_users.json` is a separate, already-possible manual step (just editing the JSON file) — not part of this SP.

## Implementation Notes
_Completed 2026-08-19._

- `app/models.py` — `Receipt` gained a `user_email` field (`__init__`, `to_dict()`, `from_dict()`).
- `app/database/base.py` — abstract `get_all_receipts`, `get_receipt_by_id`, `delete_receipt`, `get_receipts_count` now require `user_email`; also declared `soft_delete_receipt` on the interface for the first time (it existed on `JSONDatabase` but was never part of the ABC).
- `app/database/json_db.py` — every receipt read/write method now filters/matches on `user_email`; a non-owned receipt is treated identically to a nonexistent one (no existence leak) on delete/lookup. `initialize()` gained a one-time, idempotent migration: any receipt missing `user_email` is backfilled to `_LEGACY_OWNER_EMAIL = "andrew.bihun@gmail.com"` and persisted back to the file.
- `app/services/receipt_service.py` — `process_receipt`, `get_all_receipts`, `get_receipt_by_id`, `get_receipts_count`, `soft_delete_receipt`, `delete_receipt` all thread `user_email` through to the database layer.
- `app/routes.py`:
  - `/verify` now captures `session['user_email']` from `session['otp_email']` before it's cleared.
  - `before_request` guard requires both `logged_in` and `user_email`.
  - `/login`'s "already logged in" shortcut also requires `user_email` — without this fix, a session predating this feature (`logged_in=True`, no `user_email`) caused an infinite redirect loop between `/` and `/login` (found and fixed during manual verification; the server log showed hundreds of alternating 302s in the same second).
  - `/upload`, `/history`, `/statistics`, `/receipt/<id>`, `/delete-receipt/<id>` all pass `session['user_email']` into the corresponding service call. `/receipt/<id>` (single-receipt detail view) was brought into scope too even though not explicitly named in the original ACs, since it was an unfiltered cross-user data leak of the same kind.
- `test_setup.py` — updated its direct `JSONDatabase.get_all_receipts()` call for the new required parameter (manual smoke-test script, excluded from pytest collection).
- **Data migration**: local `data/receipts.json` — manually corrected 3 receipts that had stray `user_email: "test@example.com"` from historical test pollution (a recurrence of the issue SP-004 previously cleaned up once), then the automatic migration backfilled the remaining receipts on next server start; all 34 local receipts now correctly owned by `andrew.bihun@gmail.com`. Production's `receipts.json` (Azure Files share `shoppingtrackerstch`) was checked and has no such pollution — it will be cleanly backfilled by the same migration on next deploy.
- **Follow-up spun off, not fixed here**: while verifying the migration, found a real test-isolation gap — `app/main.py`'s `load_dotenv(override=True)` can, depending on import order within a process, override a test's `DATA_FOLDER` monkeypatch and cause it to touch the real local `data/receipts.json`. This is the root cause behind the recurring test pollution. Flagged as a separate background task rather than fixed as part of this SP.
- Tests: 24 added (across `test_database.py`, `test_receipt_service.py`, `test_routes.py`), including a regression test for the login redirect-loop bug found during manual verification. 191 passed (full suite).
