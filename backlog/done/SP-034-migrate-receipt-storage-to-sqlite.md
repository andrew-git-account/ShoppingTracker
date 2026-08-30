# SP-034: Migrate Receipt Storage to SQLite

**Priority**: High
**Status**: Done
**Fulfils**: Specification/DataSchema.md#Receipt-Storage-SQLite (rewritten for the new backend; also backfilled `saved_at`/`user_email`/item `amount`/`unit`/`position` rows that were missing from the old JSON-era doc)
**Deployed**: 3164e4e (2026-08-31)

## Description
Replace `JSONDatabase` with a `SqliteDatabase` implementing the same `Database` abstract interface, used in *every* environment — test and production both build the same class, just pointed at different files (a `tmp_path` `.db` in tests, the real data file in production). No dev/test-vs-prod backend split: that was considered and rejected, since it would leave the SQLite code path completely untested by the automated suite. First of a 3-part migration (receipts here; transactions in SP-035; usage log/categories/allowed-users in SP-036) — each part is a complete, independently-deployable cutover for its own data, not a phase behind a feature flag.

## Acceptance Criteria
- [x] `app/database/sqlite_db.py` — new `SqliteDatabase(Database)` implementing all 8 abstract methods (`save_receipt`, `get_all_receipts`, `get_receipt_by_id`, `delete_receipt`, `update_receipt`, `soft_delete_receipt`, `get_receipts_count`, `initialize`), same signatures, same return shapes (`Dict`/`List[Dict]`) as `JSONDatabase` today — `ReceiptService` and everything above it needs zero changes.
- [x] `initialize()` creates the `receipts` and `receipt_items` tables (`CREATE TABLE IF NOT EXISTS`) if missing, mirroring `JSONDatabase.initialize()`'s self-creating behavior — no separate setup step required.
- [x] `app/main.py` constructs `SqliteDatabase` instead of `JSONDatabase` — no env var, no branch; this is the only backend from this point on.
- [x] `conftest.py` (root) and `tests/conftest.py`'s fixtures that build `JSONDatabase` directly are updated to build `SqliteDatabase` against a `tmp_path` `.db` file instead — existing test *assertions* are unchanged, since both backends return the same dict shape.
- [x] `tests/test_database.py`'s existing `JSONDatabase` test class(es) are either parameterized to run against both backends, or duplicated as an equivalent `SqliteDatabase` test class asserting the identical behavior — full interface parity with `JSONDatabase`'s current test coverage, not a subset.
- [x] A one-off `migrate_receipts_to_sqlite.py` (repo root, matching the existing `migrate_categories.py` convention) reads the current production `receipts.json`, creates the SQLite schema if needed, inserts every receipt (including `linked_transaction_id`, if set) and its items (preserving item order), and prints a before/after summary (record count in, record count written).
- [x] Item order is preserved on read-back — a `position` column (or equivalent) on `receipt_items`, since SQL rows have no inherent order the way a JSON list does.
- [x] Full existing test suite passes end-to-end against the new backend with no changes to any test file outside the fixture/database-construction layer described above.

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
    is_deleted INTEGER NOT NULL DEFAULT 0,
    linked_transaction_id TEXT
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

`linked_transaction_id` (nullable, no FK constraint since the `transactions` table doesn't exist until SP-035) was added to this schema during verification - the original draft predated SP-037, which added this field to `Receipt`. Since `JSONDatabase` is schema-agnostic (persists whatever dict it's given), it already carries this field with zero code changes; `SqliteDatabase` needs it as an explicit column or every receipt's transaction link would be silently dropped on save.

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

Completed 2026-08-30.

- **`app/database/sqlite_db.py`** (new): `SqliteDatabase(Database)`, stdlib `sqlite3` only, one connection opened and closed per public method call. Implements all 8 `Database` methods with exact `JSONDatabase` parity: `get_all_receipts` orders `ORDER BY rowid DESC` to match JSON's insertion-order reversal precisely (a timestamp sort alone can collide within the same second); `get_receipt_by_id` doesn't filter `is_deleted`, matching JSON; `update_receipt` only touches columns present in the caller's dict via an explicit allowlist (the allowlist itself is what makes `id`/`saved_at`/`user_email`/`is_deleted` un-overwritable) and only replaces `receipt_items` rows when `'items'` is literally a key in the update dict; `delete_receipt` manually cascades to `receipt_items` first (no `ON DELETE CASCADE` in the schema). Every item field is defaulted in Python (mirroring `ReceiptItem.from_dict()`) before binding into an `INSERT` — a Plan-agent review caught that SQL `DEFAULT` doesn't apply when a column is explicitly passed `NULL`, and an existing test seeds legacy items with no `amount`/`unit` keys at all.
- **`app/database/__init__.py`**: exports `SqliteDatabase` alongside the existing re-exports.
- **`app/main.py`**: builds `SqliteDatabase` against `data/shopping_tracker.db` instead of `JSONDatabase` against `data/receipts.json` — the only change needed above the `Database` abstraction boundary.
- **`conftest.py`** (root): `receipt_service` fixture and the confirmed-dead `app`/`client` fixture pair switched from `JSONDatabase` to `SqliteDatabase`; added a new `receipts_db_path` fixture (doesn't pre-touch the file, unlike the existing `receipts_file` fixture which pre-writes JSON bytes that would break SQLite's `initialize()`). `tests/conftest.py` needed no changes — it builds the app via the real `create_app()`, which picked up the new backend automatically.
- **`tests/test_database.py`**: added `TestSqliteDatabaseSoftDelete`, `TestSqliteDatabaseUpdateReceipt`, `TestSqliteDatabaseUserScoping` (same scenarios as the existing `TestJSONDatabase*` classes, reading state back through the public interface instead of peeking at a raw file), plus new coverage with no JSON-side equivalent: item-order round-trips (save and update), legacy items missing `amount`/`unit`/`category` (the regression test for the bug above), and hard-delete's cross-table cascade. `JSONDatabase` and its own tests are untouched — it stays a valid, tested `Database` implementation (`CategoryDatabase`, same file, still needs JSON support until SP-036); `app/main.py` simply stops choosing it for receipts. No `TestSqliteDatabaseLegacyMigration` equivalent — that class tests a JSON-file-specific backfill with no SQLite analog.
- **`migrate_receipts_to_sqlite.py`** (new): one-off migration following `migrate_categories.py`'s convention. Reuses `SqliteDatabase.initialize()` for schema creation, then uses a raw `sqlite3` connection to insert every receipt (including already-soft-deleted ones) preserving its original `id`/`saved_at`/`is_deleted` exactly — deliberately bypasses `SqliteDatabase.save_receipt()`, which mints fresh values. **Run against real production data this session**: verified first against a scratch copy (40/40 receipts, 210/210 items, soft-delete flags, and item order all matched exactly against the source JSON), then run for real — `data/shopping_tracker.db` now holds all 40 receipts/210 items; `data/receipts.json` is left on disk unused, not deleted.
- **`Specification/DataSchema.md`**: rewrote the Receipt section for the new SQLite schema (was JSON-array-shaped); backfilled `saved_at`/`user_email`/item `amount`/`unit`/`position` rows that existed in the model but were never in the old field-reference table.
- **`Specification/BehaviorSpec.md`**: no new scenario needed (zero user-visible behavior change, confirmed by the full suite passing unchanged) — fixed one stale implementation-detail phrase in BS-035 ("nothing is saved to `receipts.json` yet" → "nothing is saved to permanent storage yet").
- Test summary: 28 new tests added, 470 passed, 0 failed. Server boot verified twice (before and after running the production migration) — `GET /` → 200 both times.
