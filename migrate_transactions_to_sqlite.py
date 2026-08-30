"""
One-time migration: moves transaction storage from data/transactions.json
(JSON file, JSONTransactionDatabase) to data/shopping_tracker.db (SQLite,
SqliteTransactionDatabase) - see SP-035. Shares the same .db file SP-034's
receipt migration writes to.

Preserves every transaction's original id, saved_at, and is_deleted flag
exactly (including already-soft-deleted transactions), so it deliberately
does NOT go through SqliteTransactionDatabase.save_transaction() (which
mints a fresh id/timestamp for a new transaction). A stale linked_receipt_id
key may still be sitting in some records (SP-037's own migration
deliberately left it there) - it's simply not read, since the new schema
has no column for it.

Run once from the project root:
    python migrate_transactions_to_sqlite.py
"""

import json
import os
import sqlite3

from app.database.sqlite_transaction_db import SqliteTransactionDatabase

TRANSACTIONS_JSON_PATH = os.path.join(os.path.dirname(__file__), 'data', 'transactions.json')
SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'shopping_tracker.db')


def migrate():
    if not os.path.exists(TRANSACTIONS_JSON_PATH):
        print(f"No transactions file found at {TRANSACTIONS_JSON_PATH} — nothing to migrate.")
        return

    with open(TRANSACTIONS_JSON_PATH, 'r', encoding='utf-8') as f:
        transactions = json.load(f)

    # Reuse SqliteTransactionDatabase.initialize() for schema creation rather
    # than duplicating the CREATE TABLE statement here.
    SqliteTransactionDatabase(SQLITE_DB_PATH)

    conn = sqlite3.connect(SQLITE_DB_PATH)
    try:
        written = 0
        with conn:
            for transaction in transactions:
                conn.execute(
                    '''INSERT INTO transactions
                       (id, date, description, amount, currency, direction, category,
                        source, statement_id, saved_at, user_email, is_deleted)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        transaction['id'],
                        transaction.get('date'),
                        transaction.get('description', ''),
                        transaction.get('amount', 0.0),
                        transaction.get('currency', 'USD'),
                        transaction.get('direction', 'debit'),
                        transaction.get('category', 'Other'),
                        transaction.get('source', 'card'),
                        transaction.get('statement_id'),
                        transaction.get('saved_at'),
                        transaction.get('user_email'),
                        int(bool(transaction.get('is_deleted', False))),
                    )
                )
                written += 1
    finally:
        conn.close()

    print(f"Migration complete: {len(transactions)} transaction(s) read, {written} transaction(s) written to {SQLITE_DB_PATH}.")


if __name__ == '__main__':
    migrate()
