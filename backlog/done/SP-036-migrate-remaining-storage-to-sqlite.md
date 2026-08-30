# SP-036: Migrate Usage Log, Categories, and Allowed Users to SQLite

**Priority**: Medium
**Status**: Done
**Fulfils**: Specification/DataSchema.md#Categories-SQLite (rewritten), #LLM-Usage-Log-SQLite (new — no prior documentation existed), #Allowed-Users-SQLite (new — no prior documentation existed)

## Description
Final part of the 3-part storage migration: replace `UsageLogDatabase`, `CategoryDatabase`, and `AuthService`'s hand-rolled `allowed_users.json` read/write with SQLite-backed equivalents, all three small enough to bundle into one story. After this SP, no JSON data files remain anywhere in the app — everything lives in the one `shopping_tracker.db` file SP-034/SP-035 already created.

## Acceptance Criteria
- [x] `UsageLogDatabase` → SQLite-backed equivalent: `log_call(...)` and `get_all_records()` behave identically (same fields per record: `timestamp`, `user_email`, `model`, `input_tokens`, `output_tokens`, `cost_usd`, `success`, `is_retry`); `get_all_records()` still returns oldest-first.
- [x] `CategoryDatabase` → SQLite-backed equivalent: `initialize()` still seeds the same default category list on first run if the table is empty; `get_all_categories()` returns dicts with a `name` key matching today's values exactly. The `id` key present in today's JSON-backed dicts is dropped (schema uses `name` as the primary key, no separate integer id) - confirmed safe during verification: every caller (`app/main.py`, `conftest.py`) only ever reads `c['name']`, never `c['id']`. Note this means `TestCategoryDatabaseGetAll::test_entries_have_id_and_name` (which asserts `"id" in cat`) exercises `CategoryDatabase` specifically and keeps passing unchanged since that class is untouched - it is not a scenario the new SQLite class needs to replicate.
- [x] `AuthService`'s allowed-users storage moves to SQLite. Since `AuthService` currently owns `_load_allowed_users`/`_save_allowed_users` directly (no separate `Database`-like class exists for this today, unlike receipts/transactions/usage-log/categories), extract a small storage class first (or add the SQL calls directly in `AuthService`, whichever keeps the diff smaller — decide during implementation) so `is_email_allowed`, `is_admin`, `get_all_users`, `add_user`, `set_admin`, `set_blocked` all keep their exact current behavior, including the last-active-admin safeguard (SP-021) and case-insensitive email matching.
- [x] `app/main.py` constructs all three SQLite-backed classes instead of their JSON equivalents — no env var, no branch.
- [x] `conftest.py`/`tests/conftest.py` fixtures building any of the three JSON classes directly are updated accordingly — test assertions unchanged.
- [x] One-off migration scripts (`migrate_usage_log_to_sqlite.py`, `migrate_categories_to_sqlite.py` — note this is a *different* script from the existing `migrate_categories.py`, which solved a different, already-completed problem — and `migrate_allowed_users_to_sqlite.py`, or one combined script covering all three) move existing production data over, each printing a before/after summary.
- [x] Full existing test suite passes end-to-end with no changes to any test file outside the fixture/database-construction layer.

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
`allowed_users.email TEXT PRIMARY KEY COLLATE NOCASE` — resolved during verification. `AuthService` today stores emails exactly as entered (`add_user` only `.strip()`s, never lowercases) and lowercases only at comparison time (`_find_user`, `is_email_allowed`, `is_admin` all do `user['email'].lower() == target`) - so silently normalizing stored case to lowercase would be an observable regression (an admin's carefully-cased email would flatten to lowercase on the user-management page). `COLLATE NOCASE` gets case-insensitive `WHERE email = ?` lookups for free while preserving whatever case was originally entered, matching current behavior exactly with no `LOWER()` needed on either side.

### Why bundle these three
Each is small (a handful of methods, no complex query needs) and low-risk compared to receipts/transactions - bundling avoids three near-trivial SPs for what's really one afternoon of mechanical, well-precedented work by the time SP-034/SP-035 have established the pattern.

### After this SP
No `DATA_FOLDER`-pointed JSON files remain in production - `receipts.json`, `transactions.json`, `llm_usage.json`, `categories.json`, and `allowed_users.json` are all superseded by tables in `shopping_tracker.db`. Worth a deliberate check (not necessarily automated) that nothing in the app still reads one of the old JSON files directly after this lands.

### Out of scope (this SP)
- Any change to `ReceiptService`, `TransactionService`, `LLMService`, routes, or templates beyond what's needed to swap in the new storage classes.
- Removing the old JSON files from production storage - leaving them in place (unused) is safer than deleting until the SQLite cutover has been running successfully for a while.

## Implementation Notes

Completed 2026-08-30. Final part of the 3-part SQLite migration (SP-034 receipts, SP-035 transactions) — no JSON data files remain in production use after this.

- **`app/database/sqlite_usage_log_db.py`** (new): `SqliteUsageLogDatabase`, reuses `_estimate_cost_usd` imported from `usage_log_db.py` rather than duplicating the pricing table. `get_all_records()` orders `ORDER BY rowid ASC` (oldest first, matching JSON's append order).
- **`app/database/sqlite_category_db.py`** (new): `SqliteCategoryDatabase`, reuses `_SEED_CATEGORIES` imported from `json_db.py`. Seeds only if the table is empty (checked via `COUNT(*)`, since `CREATE TABLE IF NOT EXISTS` alone doesn't tell you whether it pre-existed with data). Drops the `id` column present in the old JSON shape — confirmed via grep that nothing downstream reads it, only `name`.
- **`app/database/sqlite_allowed_users_db.py`** (new): `SqliteAllowedUsersDatabase`, pure storage (no business logic) with two methods mirroring the "load everything, mutate in memory, save everything back" cost model `AuthService` already used: `get_all_users()` and `save_all_users()` (bulk delete-then-reinsert in one transaction). Schema uses `email TEXT PRIMARY KEY COLLATE NOCASE` rather than a lowercase-normalized key — resolved during verification: `AuthService` stores emails exactly as entered and only lowercases at comparison time, so normalizing stored case would have been an observable regression (an admin's carefully-cased email flattening to lowercase on the user-management page). `COLLATE NOCASE` gets case-insensitive lookups with zero behavior change.
- **`app/services/auth_service.py`**: minimal-diff change — constructor signature (`allowed_users_path: str`) is untouched, now builds `self._storage = SqliteAllowedUsersDatabase(allowed_users_path)` internally. `_load_allowed_users()`/`_save_allowed_users()` become thin delegations to `self._storage`; the now-unreachable JSON-tolerant-parsing branch (bare string vs. object entries) and the "file not found" warning print were removed as dead code. Every public method (`is_email_allowed`, `is_admin`, `add_user`, `set_admin`, `set_blocked`, `toggle_admin`, `toggle_blocked`, `_find_user`, `_count_active_admins`) is untouched — the last-active-admin safeguard and case-insensitive matching logic never changed.
- **`app/database/__init__.py`** / **`app/main.py`**: export and wire all three new classes, all three now sharing `database_path` (`shopping_tracker.db`) instead of three separate JSON files. `app/main.py` no longer imports `JSONTransactionDatabase` or `CategoryDatabase` from `json_db`/`transaction_db` at all (only `SqliteDatabase`, `SqliteUsageLogDatabase`, `SqliteTransactionDatabase`, `SqliteCategoryDatabase`).
- **Three raw-JSON-seeding test sites found and fixed** (a Plan-agent review caught two of these before implementation started, beyond the obvious `test_auth_service.py`): `tests/conftest.py`'s `app` fixture (used by nearly all of `test_routes.py`/`test_auth.py` via `client`/`logged_in_client`/`admin_client`) now seeds `allowed_users` via `SqliteAllowedUsersDatabase` instead of writing raw `allowed_users.json`; `tests/test_smtp_auth.py::test_smtp_config_read_from_env` same fix; `tests/test_routes.py::TestLLMUsagePage`'s two month-filter tests (which need explicit control over `timestamp`, unlike `log_call()`'s always-`datetime.now()`) now insert rows directly via a small `_seed_usage_log_records` helper instead of overwriting the usage log file as JSON.
- **`tests/test_auth_service.py`**: `_write_allowed_users` rewritten to seed via `SqliteAllowedUsersDatabase.save_all_users()`, keeping its existing flexible bare-string/dict input shape as a pure test-authoring convenience (21 of 23 existing test bodies unchanged). Removed `test_is_email_allowed_true_for_bare_string_entry` and `test_is_admin_false_for_bare_string_entry` — both asserted `AuthService`'s own runtime tolerance for a hand-edited JSON file mixing bare strings and objects, which has no SQLite equivalent (every row always has all three columns by construction), same category of decision as SP-034's dropped `TestJSONDatabaseLegacyMigration`.
- **`tests/test_database.py`**: added `TestSqliteCategoryDatabase` (7 tests) and `TestSqliteUsageLogDatabase` (4 tests), reading state back through the public interface instead of raw-file-peeking, dropping `id`-related assertions for categories (schema has none).
- **`migrate_usage_log_to_sqlite.py`**, **`migrate_categories_to_sqlite.py`**, **`migrate_allowed_users_to_sqlite.py`** (new, three separate scripts per AC #15's option): same convention as SP-034/035's scripts. **Run against real production data this session**: verified first against scratch copies of all three source files (16/16 usage records, 7/7 categories, 3/3 allowed users — including the real admin account — all field values and flags matched, case-insensitive lookup confirmed working with case preserved), then run for real. `shopping_tracker.db` now holds all five tables (`receipts`, `receipt_items`, `transactions`, `categories`, `usage_log`, `allowed_users`); all five old JSON files left on disk unused, not deleted. Flagged explicitly to the user before running: until the allowed-users migration ran, the live app's `allowed_users` table was empty, meaning nobody (including the account owner) could log in.
- **`Specification/DataSchema.md`**: rewrote the Categories section for SQLite (dropped `id`), added new Usage Log and Allowed Users sections (neither had any prior documentation at all).
- **`Specification/BehaviorSpec.md`**: no new scenario needed (zero user-visible behavior change) — fixed three stale `allowed_users.json` references (BS-014, BS-015, BS-032).
- Deliberate post-migration check (per the SP's own note): grepped `app/` for the five old JSON filenames — all remaining hits are docstring/comment mentions inside the retired JSON classes themselves (`JSONDatabase`, `JSONTransactionDatabase`, `UsageLogDatabase`, `CategoryDatabase`), never a live code path.
- Test summary: 14 new tests, 2 removed (JSON-only tolerance, no SQLite equivalent), 493 passed, 0 failed. Server boot verified before and after running all three migrations — `GET /` → 200 both times.
