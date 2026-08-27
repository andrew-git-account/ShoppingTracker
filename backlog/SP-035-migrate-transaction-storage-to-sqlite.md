# SP-035: Migrate Transaction Storage to SQLite

**Priority**: High
**Status**: Open

## Description
Replace `JSONTransactionDatabase` with a SQLite-backed equivalent, same approach as SP-034 for receipts: one backend everywhere (test and production both), a `transactions` table added to the same `shopping_tracker.db` file SP-034 created, and a migration script for existing production data. Second of the 3-part storage migration.

## Acceptance Criteria
- [ ] `app/database/sqlite_transaction_db.py` — new `SqliteTransactionDatabase` mirroring `JSONTransactionDatabase`'s exact method shapes (`initialize`, `save_transaction`, `get_all_transactions`, `get_transaction_by_id`, `update_transaction`, `soft_delete_transaction`) — same signatures, same `Dict`/`List[Dict]` return shapes, so `TransactionService` needs zero changes.
- [ ] `initialize()` creates the `transactions` table (`CREATE TABLE IF NOT EXISTS`) in the same `.db` file SP-034's `SqliteDatabase` uses, if missing.
- [ ] `app/main.py` constructs `SqliteTransactionDatabase` instead of `JSONTransactionDatabase` — no env var, no branch.
- [ ] `conftest.py`/`tests/conftest.py` fixtures building `JSONTransactionDatabase` directly are updated to build `SqliteTransactionDatabase` instead — test assertions unchanged.
- [ ] `update_transaction`'s existing preserve-on-update behavior (`id`/`saved_at`/`user_email`/`is_deleted` never overwritten by caller data, per `transaction_db.py`'s current implementation) carries over exactly.
- [ ] A one-off `migrate_transactions_to_sqlite.py` reads production `transactions.json`, inserts every transaction into the new table, and prints a before/after summary — same convention as SP-034's migration script.
- [ ] `linked_receipt_id` values carry over untouched as plain string IDs (no SQL foreign-key JOIN needed — every place that reads/compares this field today does so as a plain equality check in Python, e.g. `TransactionMatcher`, `statement_delete`, `delete_receipt`'s link-cleanup — this SP doesn't need to change any of that).
- [ ] Full existing test suite passes end-to-end with no changes to any test file outside the fixture/database-construction layer.

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
    linked_receipt_id TEXT,
    is_deleted INTEGER NOT NULL DEFAULT 0
);
```
No `REFERENCES receipts(id)` foreign key on `linked_receipt_id` — deliberately, since a soft-deleted receipt is never actually removed as a row (matching today's behavior, where a stale reference is possible until something explicitly clears it, per SP-026/031/033's hand-written cleanup), and enforcing a hard FK here would be new, stricter behavior this SP isn't asking for.

### `statement_id` default for legacy rows
`Transaction.from_dict()` already defaults a missing `statement_id` to the record's own `id` (SP-029's migration-free convention). No special handling needed in the SQLite version - same fallback logic already lives in the model, not the database layer.

### Dependency/file choice
Same as SP-034: stdlib `sqlite3`, hand-written SQL, one shared `.db` file (not a second database file) - `transactions` is just another table alongside `receipts`/`receipt_items`.

### Out of scope (this SP)
- Usage log, categories, or allowed-users storage — SP-036.
- Any change to `TransactionService`, `TransactionMatcher`, routes, or templates.

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
