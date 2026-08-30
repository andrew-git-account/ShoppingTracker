"""
One-time migration: moves receipt storage from data/receipts.json (JSON
file, JSONDatabase) to data/shopping_tracker.db (SQLite, SqliteDatabase) -
see SP-034.

Preserves every receipt's original id, saved_at, and is_deleted flag
exactly (including already-soft-deleted receipts - this is a full storage
migration, not a live-only export), so it deliberately does NOT go through
SqliteDatabase.save_receipt() (which mints a fresh id/timestamp for a new
receipt). Item fields are defaulted the same way SqliteDatabase itself
defaults them, since historic JSON records can be missing amount/unit/
category from before SP-013.

Run once from the project root:
    python migrate_receipts_to_sqlite.py
"""

import json
import os
import sqlite3

from app.database.sqlite_db import SqliteDatabase

RECEIPTS_JSON_PATH = os.path.join(os.path.dirname(__file__), 'data', 'receipts.json')
SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'shopping_tracker.db')


def _item_values(item: dict) -> tuple:
    return (
        item.get('name', ''),
        item.get('price', 0.0),
        item.get('quantity', 1),
        item.get('category', 'Other'),
        item.get('amount', 1.0),
        item.get('unit', 'piece'),
    )


def migrate():
    if not os.path.exists(RECEIPTS_JSON_PATH):
        print(f"No receipts file found at {RECEIPTS_JSON_PATH} — nothing to migrate.")
        return

    with open(RECEIPTS_JSON_PATH, 'r', encoding='utf-8') as f:
        receipts = json.load(f)

    # Reuse SqliteDatabase.initialize() for schema creation rather than
    # duplicating the CREATE TABLE statements here.
    SqliteDatabase(SQLITE_DB_PATH)

    conn = sqlite3.connect(SQLITE_DB_PATH)
    try:
        written = 0
        with conn:
            for receipt in receipts:
                conn.execute(
                    '''INSERT INTO receipts
                       (id, store_name, purchase_date, tax_amount, discount_amount,
                        total_amount, saved_at, currency, user_email, is_deleted,
                        linked_transaction_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        receipt['id'],
                        receipt.get('store_name'),
                        receipt.get('purchase_date'),
                        receipt.get('tax_amount', 0.0),
                        receipt.get('discount_amount', 0.0),
                        receipt.get('total_amount'),
                        receipt.get('saved_at'),
                        receipt.get('currency', 'USD'),
                        receipt.get('user_email'),
                        int(bool(receipt.get('is_deleted', False))),
                        receipt.get('linked_transaction_id'),
                    )
                )
                for position, item in enumerate(receipt.get('items', [])):
                    name, price, quantity, category, amount, unit = _item_values(item)
                    conn.execute(
                        '''INSERT INTO receipt_items
                           (receipt_id, name, price, quantity, category, amount, unit, position)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (receipt['id'], name, price, quantity, category, amount, unit, position)
                    )
                written += 1
    finally:
        conn.close()

    print(f"Migration complete: {len(receipts)} receipt(s) read, {written} receipt(s) written to {SQLITE_DB_PATH}.")


if __name__ == '__main__':
    migrate()
