# SP-020: LLM Usage & Cost Tracking Page

**Priority**: Medium
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-032

## Description
Add a new page that tracks and displays LLM (Claude API) usage statistics — separate from the existing shopping "Statistics" page, which is about spending on purchases, not API usage. For v1, track: total number of requests sent to the LLM, total estimated cost, retry rate (how often the SP-018 reconciliation retry fires), and success/failure rate. The page supports filtering by user (selection) and by date (year/month selection). This page is admin-only — visible and accessible only to users flagged as admin.

## Acceptance Criteria
- [x] Every call to the Anthropic API — including the SP-018 reconciliation retry, so up to 2 per upload — is logged with at least: timestamp, uploading user's email, model used, input tokens, output tokens, computed cost, success/failure, and whether it was a retry attempt.
- [x] A call that fails before a response comes back (network/API error, no usage data available) is still logged as a failed request — never silently dropped.
- [x] A new page (e.g. `/llm-usage`), linked from the nav alongside Upload/History/Statistics, displays aggregated totals for the current filter scope: total requests, total cost, retry rate, and success rate.
- [x] A "User" filter (dropdown) narrows the display to one specific user or all users combined (default: all users).
- [x] A "Date" filter (year + month selection) narrows the display to one calendar month or all time (default: all time) — same UX pattern as the existing Statistics page's month picker.
- [x] The two filters combine (e.g. one user + one month) and the displayed numbers update accordingly.
- [x] Cost is computed using the pricing for the model actually recorded on each call, not the currently configured `LLM_MODEL` — so historical totals stay correct even after a future model change (this project has already migrated models once, per `CLAUDE.md`).
- [x] The LLM Usage page is admin-only: a non-admin logged-in user is denied server-side if they hit `/llm-usage` directly (not just a hidden link), and doesn't see the nav link at all. An admin is determined by a new `is_admin` flag on their `allowed_users.json` entry.
- [x] `andrew.bihun@gmail.com` is admin; `andrzej.bihun@gmail.com` is not — locally confirmed live. **Production's `allowed_users.json` is intentionally not yet migrated** (see Implementation Notes) — required as a manual step at deploy time, not automatic.

## Notes / Context

### Where this hooks in
- `app/services/llm_service.py` — `LLMService._attempt_extraction()` (added in SP-018) is the single choke point where every actual API call happens, including the retry. This is where each call's outcome (success + `response.usage.input_tokens`/`output_tokens`, or failure) should be logged. `extract_receipt_data()` calls it 1-2 times per upload; both attempts should each get their own log entry, with `is_retry: false` / `true` respectively.
- `LLMService` doesn't currently have a logger/database dependency — it'll need one injected via `__init__` (same pattern `ReceiptService`/`AuthService` already use), wired in `app/main.py`'s `create_app()`. `tests/test_llm_service.py`'s `make_service()` helper constructs `LLMService` directly and will need updating for the new constructor param, same kind of mechanical update as past SPs.
- The uploading user's email is available in the route (`session['user_email']`, per SP-005) but `LLMService.extract_receipt_data()` doesn't currently receive it — `ReceiptService.process_receipt()` already receives `user_email` (per SP-005) and calls `llm_service.extract_receipt_data()`, so it's the natural place to thread it through.

### Storage
- New JSON file (e.g. `data/llm_usage.json`), a flat list of records, following the same read-all/write-all pattern already used in `app/database/json_db.py`. Unlike `receipts.json`, this is an append-only log — no update/delete needed, so it can be simpler than the full `Database` interface (no need to force it into the existing ABC).
- Suggested record shape:
  ```json
  {
    "timestamp": "2026-08-19T12:00:00",
    "user_email": "andrew.bihun@gmail.com",
    "model": "claude-sonnet-4-6",
    "input_tokens": 1234,
    "output_tokens": 567,
    "cost_usd": 0.0123,
    "success": true,
    "is_retry": false
  }
  ```
- Not addressed in this SP: log file growth/rotation over time. Fine to leave unbounded for now given current usage volume; revisit later if it becomes a real file size.

### Cost calculation
Current pricing for the model this project uses (`LLM_MODEL=claude-sonnet-4-6` per `.env`), per Anthropic's published rates as of 2026-08:
| Model | Input $/1M tokens | Output $/1M tokens |
|---|---|---|
| `claude-sonnet-4-6` | $3.00 | $15.00 |

Since pricing varies by model and can change over time, store a small pricing table (keyed by model ID) in code rather than hardcoding a single rate, and look up the rate using each record's own `model` field when computing cost at write time (not at display time) — this is what makes historical totals stay correct across a future model change (the AC above).

### Filters and page design
- Follow the existing `/statistics?month=YYYY-MM` pattern (`app/routes.py`'s `statistics()`, `_month_key()` helper) for the date filter's UX and query-param shape, for consistency with the rest of the app.
- The "User" filter should list the emails present in `allowed_users.json` (or distinct `user_email` values actually seen in the log), plus an "All users" option.
- Unlike receipt data (SP-005), the "User" filter here lets an admin see *other* users' totals too (that's the point of a cost-monitoring page) — the restriction is on who can reach the page at all (admins only), not on which users' data an admin can see once there.

### Admin access
- **Data model change**: `data/allowed_users.json` is currently a flat JSON array of email strings (`["andrew.bihun@gmail.com", "andrzej.bihun@gmail.com"]`), read by `AuthService._load_allowed_users()` / `is_email_allowed()` (`app/services/auth_service.py`). This needs an `is_admin` flag per user, so the format becomes a list of objects:
  ```json
  [
    {"email": "andrew.bihun@gmail.com", "is_admin": true},
    {"email": "andrzej.bihun@gmail.com", "is_admin": false}
  ]
  ```
  Update `_load_allowed_users()` / `is_email_allowed()` for the new shape, and add a new `AuthService.is_admin(email: str) -> bool` method. Consider tolerant parsing (accept a bare string entry as `is_admin: false`, alongside object entries) so a partially-migrated or manually-hand-edited file doesn't break login — similar in spirit to how `Receipt.from_dict()` supplies defaults for missing fields.
- **Migration target** (per decision): `andrew.bihun@gmail.com` → `is_admin: true`, `andrzej.bihun@gmail.com` → `is_admin: false`. Must be applied to **both** local `data/allowed_users.json` and production's copy (Azure Files share `shoppingtrackerstch`/`shopping-data`, mounted at `/data` — same file this session already edited directly via `az storage file download`/`upload` when adding the second test user).
- **Route + nav enforcement**: the `/llm-usage` route must check `app.auth_service.is_admin(session['user_email'])` itself and deny non-admins server-side (redirect + flash, matching the existing pattern for other authorization failures in this app) — a hidden nav link alone is not enough, consistent with how SP-005 enforced receipt ownership at the service/database layer rather than just hiding UI buttons. `templates/base.html`'s nav should only render the "LLM Usage" link when the logged-in user is an admin.
- This SP does not introduce a general-purpose roles/permissions system — just the one `is_admin` boolean gating this one page. No other route changes behavior based on it.

### Out of scope for v1
Latency per call, image size sent, and daily/monthly trend charts were discussed as good follow-ons but are not required for this story — the four v1 metrics (request count, cost, retry rate, success rate) plus the two filters are the full scope here.

## Implementation Notes
_Completed 2026-08-21._

- `app/database/usage_log_db.py` (new) — `UsageLogDatabase`: append-only JSON log (not the `Database` ABC), with a `_PRICING_PER_MILLION_TOKENS` table (keyed by model ID, `claude-sonnet-4-6`: $3/$15, plus a couple of other current models and a fallback default) and `log_call()`/`get_all_records()`.
- `app/database/__init__.py` — exports `UsageLogDatabase` alongside `JSONDatabase`.
- `app/services/llm_service.py` — `extract_receipt_data()` and `_attempt_extraction()` now require `user_email`; every attempt (first and the SP-018 retry) logs its outcome via a new `_record_usage()` helper — real token counts and `success=True` on a clean response, zero tokens on an API-level failure (no response ever came back), and real token counts with `success=False` if a response came back but `_parse_response` failed (still burned real tokens, still logged — AC2). `usage_logger` is an optional constructor param (`None` by default) so it never breaks a caller that doesn't supply one.
- `app/services/receipt_service.py` — one-line change threading `user_email` into the `extract_receipt_data()` call (it already had `user_email` from SP-005).
- `app/services/auth_service.py` — `_load_allowed_users()` now tolerantly normalizes both a bare email string and an `{"email", "is_admin"}` object into the same shape; `is_email_allowed()` updated for the new shape; new `is_admin(email)` method.
- `app/main.py` — constructs `UsageLogDatabase`, passes it into `LLMService` as `usage_logger`, attaches `app.usage_log_db`.
- `app/routes.py` — `/verify` now also sets `session['is_admin']` (cached at login, same trust model as `user_email`/`logged_in`). New `/llm-usage` route: checks `session.get('is_admin')` first (redirect + flash if not), then filters `usage_log_db.get_all_records()` by optional `?user=`/`?month=` query params and computes totals.
- `templates/base.html` — "LLM Usage" nav link, only rendered when `session.get('is_admin')` is truthy.
- `templates/llm_usage.html` (new) — reuses existing CSS classes throughout (`.search-form`/`.search-input` for the filter form, `.stats-panel`/`.summary-row` for the totals, `.empty-state` for no data) — no new CSS needed.
- **Data migration**: local `data/allowed_users.json` rewritten to the new `{email, is_admin}` shape (`andrew.bihun@gmail.com`: admin, `andrzej.bihun@gmail.com`: not). **Production's copy was deliberately left untouched** — it's still running the pre-SP-020 code, which would crash on the new object shape (`AttributeError: 'dict' object has no attribute 'lower'` in the old flat-string-only parsing) if the file were migrated ahead of the code. This is a required manual step (`az storage file download`/`upload` against the `shoppingtrackerstch`/`shopping-data` share, same procedure used twice already this session for this file) to perform as part of or immediately after deploying this SP — **do not forget it at deploy time**.
- Verified live in the browser (not just automated tests): logged in as `andrew.bihun@gmail.com` through the real OTP flow, confirmed the "LLM Usage" nav link appears and the page renders with the correct empty state and filter dropdowns.
- Tests: 56 added (`test_llm_service.py`'s `TestUsageLogging`, `test_database.py`'s `TestUsageLogDatabase`, new `test_auth_service.py`, `test_auth.py`'s admin-login tests, `test_routes.py`'s `TestLLMUsagePage`), plus the 7 pre-existing `test_llm_service.py` tests mechanically updated for the new required `user_email` param. 220 passed (full suite).
