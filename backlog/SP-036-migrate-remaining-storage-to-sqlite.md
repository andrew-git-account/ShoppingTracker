# SP-036: Migrate Usage Log, Categories, and Allowed Users to SQLite

**Priority**: Medium
**Status**: Open

## Description
Final part of the 3-part storage migration: replace `UsageLogDatabase`, `CategoryDatabase`, and `AuthService`'s hand-rolled `allowed_users.json` read/write with SQLite-backed equivalents, all three small enough to bundle into one story. After this SP, no JSON data files remain anywhere in the app — everything lives in the one `shopping_tracker.db` file SP-034/SP-035 already created.

## Acceptance Criteria
- [ ] `UsageLogDatabase` → SQLite-backed equivalent: `log_call(...)` and `get_all_records()` behave identically (same fields per record: `timestamp`, `user_email`, `model`, `input_tokens`, `output_tokens`, `cost_usd`, `success`, `is_retry`); `get_all_records()` still returns oldest-first.
- [ ] `CategoryDatabase` → SQLite-backed equivalent: `initialize()` still seeds the same default category list on first run if the table is empty; `get_all_categories()` returns the same shape.
- [ ] `AuthService`'s allowed-users storage moves to SQLite. Since `AuthService` currently owns `_load_allowed_users`/`_save_allowed_users` directly (no separate `Database`-like class exists for this today, unlike receipts/transactions/usage-log/categories), extract a small storage class first (or add the SQL calls directly in `AuthService`, whichever keeps the diff smaller — decide during implementation) so `is_email_allowed`, `is_admin`, `get_all_users`, `add_user`, `set_admin`, `set_blocked` all keep their exact current behavior, including the last-active-admin safeguard (SP-021) and case-insensitive email matching.
- [ ] `app/main.py` constructs all three SQLite-backed classes instead of their JSON equivalents — no env var, no branch.
- [ ] `conftest.py`/`tests/conftest.py` fixtures building any of the three JSON classes directly are updated accordingly — test assertions unchanged.
- [ ] One-off migration scripts (`migrate_usage_log_to_sqlite.py`, `migrate_categories_to_sqlite.py` — note this is a *different* script from the existing `migrate_categories.py`, which solved a different, already-completed problem — and `migrate_allowed_users_to_sqlite.py`, or one combined script covering all three) move existing production data over, each printing a before/after summary.
- [ ] Full existing test suite passes end-to-end with no changes to any test file outside the fixture/database-construction layer.

## Notes / Context

### Schema
```sql
CREATE TABLE usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    user_email TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    success INTEGER NOT NULL,
    is_retry INTEGER NOT NULL
);
CREATE TABLE categories (
    name TEXT PRIMARY KEY
);
CREATE TABLE allowed_users (
    email TEXT PRIMARY KEY,
    is_admin INTEGER NOT NULL DEFAULT 0,
    is_blocked INTEGER NOT NULL DEFAULT 0
);
```
`allowed_users.email` as primary key assumes case-normalized storage (lowercase) to keep the existing case-insensitive matching working via a simple lookup rather than a `LOWER()` comparison on every query — confirm this against `AuthService`'s current case-handling before finalizing.

### Why bundle these three
Each is small (a handful of methods, no complex query needs) and low-risk compared to receipts/transactions - bundling avoids three near-trivial SPs for what's really one afternoon of mechanical, well-precedented work by the time SP-034/SP-035 have established the pattern.

### After this SP
No `DATA_FOLDER`-pointed JSON files remain in production - `receipts.json`, `transactions.json`, `llm_usage.json`, `categories.json`, and `allowed_users.json` are all superseded by tables in `shopping_tracker.db`. Worth a deliberate check (not necessarily automated) that nothing in the app still reads one of the old JSON files directly after this lands.

### Out of scope (this SP)
- Any change to `ReceiptService`, `TransactionService`, `LLMService`, routes, or templates beyond what's needed to swap in the new storage classes.
- Removing the old JSON files from production storage - leaving them in place (unused) is safer than deleting until the SQLite cutover has been running successfully for a while.

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
