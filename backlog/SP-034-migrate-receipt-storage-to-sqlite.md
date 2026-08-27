# SP-034: Migrate Receipt Storage to SQLite

**Priority**: High
**Status**: Open

## Description
Replace `JSONDatabase` with a `SqliteDatabase` implementing the same `Database` abstract interface, used in *every* environment — test and production both build the same class, just pointed at different files (a `tmp_path` `.db` in tests, the real data file in production). No dev/test-vs-prod backend split: that was considered and rejected, since it would leave the SQLite code path completely untested by the automated suite. First of a 3-part migration (receipts here; transactions in SP-035; usage log/categories/allowed-users in SP-036) — each part is a complete, independently-deployable cutover for its own data, not a phase behind a feature flag.

## Acceptance Criteria
- [ ] `app/database/sqlite_db.py` — new `SqliteDatabase(Database)` implementing all 8 abstract methods (`save_receipt`, `get_all_receipts`, `get_receipt_by_id`, `delete_receipt`, `update_receipt`, `soft_delete_receipt`, `get_receipts_count`, `initialize`), same signatures, same return shapes (`Dict`/`List[Dict]`) as `JSONDatabase` today — `ReceiptService` and everything above it needs zero changes.
- [ ] `initialize()` creates the `receipts` and `receipt_items` tables (`CREATE TABLE IF NOT EXISTS`) if missing, mirroring `JSONDatabase.initialize()`'s self-creating behavior — no separate setup step required.
- [ ] `app/main.py` constructs `SqliteDatabase` instead of `JSONDatabase` — no env var, no branch; this is the only backend from this point on.
- [ ] `conftest.py` (root) and `tests/conftest.py`'s fixtures that build `JSONDatabase` directly are updated to build `SqliteDatabase` against a `tmp_path` `.db` file instead — existing test *assertions* are unchanged, since both backends return the same dict shape.
- [ ] `tests/test_database.py`'s existing `JSONDatabase` test class(es) are either parameterized to run against both backends, or duplicated as an equivalent `SqliteDatabase` test class asserting the identical behavior — full interface parity with `JSONDatabase`'s current test coverage, not a subset.
- [ ] A one-off `migrate_receipts_to_sqlite.py` (repo root, matching the existing `migrate_categories.py` convention) reads the current production `receipts.json`, creates the SQLite schema if needed, inserts every receipt and its items (preserving item order), and prints a before/after summary (record count in, record count written).
- [ ] Item order is preserved on read-back — a `position` column (or equivalent) on `receipt_items`, since SQL rows have no inherent order the way a JSON list does.
- [ ] Full existing test suite passes end-to-end against the new backend with no changes to any test file outside the fixture/database-construction layer described above.

## Notes / Context

### Why no dev/test-vs-prod split
Discussed and explicitly rejected in favor of one backend everywhere: a JSON/SQLite split would mean the SQLite code path — the one actually running in production — is never exercised by the automated suite, since tests would always take the JSON path. Since `Database` already returns plain dicts regardless of backend, switching test fixtures to `SqliteDatabase` costs almost nothing (fixture construction only, not test logic).

### Schema
```sql
CREATE TABLE receipts (
    id TEXT PRIMARY KEY,
    store_name TEXT,
    purchase_date TEXT,
    tax_amount REAL NOT NULL DEFAULT 0,
    discount_amount REAL NOT NULL DEFAULT 0,
    total_amount REAL,
    saved_at TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    user_email TEXT NOT NULL,
    is_deleted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE receipt_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id TEXT NOT NULL REFERENCES receipts(id),
    name TEXT NOT NULL,
    price REAL NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    category TEXT NOT NULL DEFAULT 'Other',
    amount REAL NOT NULL DEFAULT 1.0,
    unit TEXT NOT NULL DEFAULT 'piece',
    position INTEGER NOT NULL
);
```
`subtotal` is not stored — `Receipt.to_dict()` already computes it on the fly from items, same as today.

### Dependency choice
Stdlib `sqlite3`, hand-written SQL — no SQLAlchemy or other ORM. Matches this codebase's existing style (`JSONDatabase` hand-writes file I/O rather than using an abstraction layer over it) and avoids a new dependency for a small schema.

### One database file, multiple tables
`shopping_tracker.db` will eventually hold every table (`receipts`, `receipt_items`, `transactions`, `usage_log`, `categories`, `allowed_users` — the latter four added in SP-035/SP-036), replacing today's five separate JSON files with one file. This SP only creates the `receipts`/`receipt_items` tables in it; later SPs add their own tables to the same file, each independently.

### `update_receipt`/`soft_delete_receipt` semantics carry over exactly
Today's `JSONDatabase.update_receipt`/`soft_delete_receipt` preserve `id`/`saved_at`/`user_email`/`is_deleted` even if a caller's dict happens to include them (see `json_db.py`). `SqliteDatabase`'s equivalents must preserve this same behavior (e.g. an `UPDATE` statement that only ever touches the editable columns, never `id`/`saved_at`/`user_email`) rather than relying on the caller not to send those fields.

### Migration script (`migrate_receipts_to_sqlite.py`)
Follows the `sdlc-deploy` skill's existing migration-detection convention (Step 4: it already looks for a changed/added `migrate_*.py` file and, if found, walks through stop-app → backup → preview-locally → confirm → apply-to-production before the code deploy proceeds) — no new deploy-process work needed, the tooling to run this safely against production already exists.

### Out of scope (this SP)
- Transactions, usage log, categories, or allowed-users storage — SP-035/SP-036.
- Any change to `ReceiptService`, routes, or templates — the abstraction boundary means none of them should need to change at all.

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
