# SP-035: Migrate Transaction Storage to SQLite

**Priority**: High
**Status**: Done
**Fulfils**: Specification/DataSchema.md#Transaction-Storage-SQLite (new section — DataSchema.md previously had no Transaction documentation at all, a pre-existing gap predating this SP, closed while touching this area)

## Description
Replace `JSONTransactionDatabase` with a SQLite-backed equivalent, same approach as SP-034 for receipts: one backend everywhere (test and production both), a `transactions` table added to the same `shopping_tracker.db` file SP-034 created, and a migration script for existing production data. Second of the 3-part storage migration.

## Acceptance Criteria
- [x] `app/database/sqlite_transaction_db.py` — new `SqliteTransactionDatabase` mirroring `JSONTransactionDatabase`'s exact method shapes (`initialize`, `save_transaction`, `get_all_transactions`, `get_transaction_by_id`, `update_transaction`, `soft_delete_transaction`) — same signatures, same `Dict`/`List[Dict]` return shapes, so `TransactionService` needs zero changes.
- [x] `initialize()` creates the `transactions` table (`CREATE TABLE IF NOT EXISTS`) in the same `.db` file SP-034's `SqliteDatabase` uses, if missing.
- [x] `app/main.py` constructs `SqliteTransactionDatabase` instead of `JSONTransactionDatabase` — no env var, no branch.
- [x] `conftest.py`/`tests/conftest.py` fixtures building `JSONTransactionDatabase` directly are updated to build `SqliteTransactionDatabase` instead — test assertions unchanged.
- [x] `update_transaction`'s existing preserve-on-update behavior (`id`/`saved_at`/`user_email`/`is_deleted` never overwritten by caller data, per `transaction_db.py`'s current implementation) carries over exactly.
- [x] A one-off `migrate_transactions_to_sqlite.py` reads production `transactions.json`, inserts every transaction into the new table, and prints a before/after summary — same convention as SP-034's migration script. A stale `linked_receipt_id` key may still be sitting in some records (SP-037's own migration deliberately left it there rather than cleaning it up) - the script simply ignores it, since the new schema has no column for it.
- [x] Full existing test suite passes end-to-end with no changes to any test file outside the fixture/database-construction layer.

## Notes / Context

### Schema
```sql
CREATE TABLE transactions (
    id TEXT PRIMARY KEY,
    date TEXT,
    description TEXT NOT NULL DEFAULT '',
    amount REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'USD',
    direction TEXT NOT NULL DEFAULT 'debit',
    category TEXT NOT NULL DEFAULT 'Other',
    source TEXT NOT NULL DEFAULT 'card',
    statement_id TEXT,
    saved_at TEXT,
    user_email TEXT NOT NULL,
    is_deleted INTEGER NOT NULL DEFAULT 0
);
```
No `linked_receipt_id` column - removed during verification. This SP's original draft predated SP-037, which removed `Transaction.linked_receipt_id` from the model entirely and moved the link the other direction (`Receipt.linked_transaction_id`). `Transaction.to_dict()` no longer emits this field at all, so a column for it here would sit permanently empty/unused. The receipt-to-transaction link itself is already covered by SP-034's `receipts.linked_transaction_id` column - nothing left for this SP to carry over.

### `statement_id` default for legacy rows
`Transaction.from_dict()` already defaults a missing `statement_id` to the record's own `id` (SP-029's migration-free convention). No special handling needed in the SQLite version - same fallback logic already lives in the model, not the database layer.

### Dependency/file choice
Same as SP-034: stdlib `sqlite3`, hand-written SQL, one shared `.db` file (not a second database file) - `transactions` is just another table alongside `receipts`/`receipt_items`.

### Out of scope (this SP)
- Usage log, categories, or allowed-users storage — SP-036.
- Any change to `TransactionService`, `TransactionMatcher`, routes, or templates.

## Implementation Notes

Completed 2026-08-30.

- **`app/database/sqlite_transaction_db.py`** (new): `SqliteTransactionDatabase`, same shape as SP-034's `SqliteDatabase` (one connection per method call, no ORM). All 6 methods mirror `JSONTransactionDatabase` exactly, including `get_all_transactions`'s plain ascending insertion order (`ORDER BY rowid ASC`) — unlike receipts, `JSONTransactionDatabase` does NOT reverse, so this had to match that rather than SP-034's `ORDER BY rowid DESC`. `update_transaction` uses the same allowlist-of-updatable-columns pattern as `update_receipt` (`id`/`saved_at`/`user_email`/`is_deleted` never eligible). No `linked_receipt_id` column — removed during verification (see below).
- **`app/database/__init__.py`** / **`app/main.py`**: export and wire `SqliteTransactionDatabase`, sharing the same `database_path` (`shopping_tracker.db`) SP-034 already set up rather than a second file. Dropped the now-unused `transactions_path`/`transactions.json` reference.
- **`conftest.py`** (root): `statement_service` fixture switched from `JSONTransactionDatabase` to `SqliteTransactionDatabase`; added a `transactions_db_path` fixture (doesn't pre-touch the file, same reasoning as SP-034's `receipts_db_path`). `tests/conftest.py` needed no changes.
- **`tests/test_database.py`**: added `TestSqliteTransactionDatabase`, mirroring all 9 existing `TestJSONTransactionDatabase` scenarios exactly (closer 1:1 mirror than SP-034's receipts tests, since the JSON class already reads state back through the public interface, no raw-file-peeking to adapt away from). Added 5 new tests beyond the mirror: `soft_delete_transaction` had zero existing coverage on the JSON side at all (only exercised indirectly via a test that seeds an already-deleted record directly), so added 3 tests for it directly; added an explicit insertion-order test and an "update returns False when not owned" test, both real behaviors with no existing test on either backend.
- **`migrate_transactions_to_sqlite.py`** (new): same convention as `migrate_receipts_to_sqlite.py` — preserves original `id`/`saved_at`/`is_deleted` exactly, bypassing `save_transaction()`. Ignores any leftover `linked_receipt_id` key still sitting in old records (SP-037's own migration left it there deliberately). **Run against real production data this session**: verified first against a scratch copy (70/70 transactions, all field values and soft-delete flags matched, stale `linked_receipt_id` keys correctly ignored), then run for real — `shopping_tracker.db` now holds all 40 receipts and 70 transactions; `transactions.json` left on disk unused, not deleted.
- **Verification-time correction**: the SP's original schema and AC #16 (removed) were built around `Transaction.linked_receipt_id`, a field SP-037 (done earlier this session) removed from the model entirely — the receipt-to-transaction link moved to `Receipt.linked_transaction_id` instead. Building the schema as originally drafted would have added a permanently-empty, dead column.
- **`Specification/DataSchema.md`**: added a full "Transaction Storage" section — DataSchema.md previously had zero documentation of transactions at all (a pre-existing gap predating this SP, closed while touching this area, same as SP-034 did for the Receipt section's missing fields).
- Test summary: 14 new tests added, 484 passed, 0 failed. Server boot verified twice (before and after running the production migration) — `GET /` → 200 both times.
