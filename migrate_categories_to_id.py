"""
One-time migration: normalizes categories to an id-based reference (see
SP-044). Before this, `categories` was a name-only table (name TEXT PRIMARY
KEY) with no FK relationship at all to receipt_items.category /
transactions.category, which were independent free-text columns that just
happened to contain a matching string.

After this migration:
- categories gains a stable integer id (name becomes UNIQUE instead of the
  primary key)
- receipt_items and transactions each gain a category_id column, backfilled
  from their existing category text (any category value with no matching
  vocabulary row is added to categories first, so nothing is left
  unresolvable)
- the old category TEXT column is dropped from both tables

Every step below is individually guarded, so running this script twice is
safe and the second run is a no-op - same convention as this project's other
migrate_*_to_sqlite.py scripts.

Run once from the project root:
    python migrate_categories_to_id.py
"""

import os
import sqlite3

SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'shopping_tracker.db')


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row['name'] == column for row in conn.execute(f'PRAGMA table_info({table})'))


def _rebuild_categories_with_id(conn: sqlite3.Connection) -> None:
    if _has_column(conn, 'categories', 'id'):
        print("categories already has an id column - skipping rebuild.")
        return
    with conn:
        conn.execute(
            'CREATE TABLE categories_new ('
            'id INTEGER PRIMARY KEY AUTOINCREMENT, '
            'name TEXT NOT NULL UNIQUE'
            ')'
        )
        conn.execute('INSERT INTO categories_new (name) SELECT name FROM categories ORDER BY rowid')
        conn.execute('DROP TABLE categories')
        conn.execute('ALTER TABLE categories_new RENAME TO categories')
    count = conn.execute('SELECT COUNT(*) AS cnt FROM categories').fetchone()['cnt']
    print(f"categories rebuilt with an id column ({count} categories).")


def _backfill_category_id(conn: sqlite3.Connection, table: str) -> None:
    if _has_column(conn, table, 'category_id'):
        print(f"{table} already has category_id - skipping backfill.")
        return

    with conn:
        # Any category text with no matching vocabulary row (a legacy or
        # since-removed category) gets added first, so every row below can
        # resolve to a real id.
        added = conn.execute(
            f'INSERT OR IGNORE INTO categories (name) '
            f'SELECT DISTINCT category FROM {table} WHERE category IS NOT NULL'
        ).rowcount

        conn.execute(f'ALTER TABLE {table} ADD COLUMN category_id INTEGER REFERENCES categories(id)')
        conn.execute(
            f'UPDATE {table} SET category_id = ('
            f'SELECT id FROM categories WHERE categories.name = {table}.category'
            f')'
        )

        remaining_null = conn.execute(
            f'SELECT COUNT(*) AS cnt FROM {table} WHERE category_id IS NULL'
        ).fetchone()['cnt']
        backfilled = conn.execute(f'SELECT COUNT(*) AS cnt FROM {table}').fetchone()['cnt'] - remaining_null

    print(f"{table}: {added} new categor(y/ies) added, {backfilled} row(s) backfilled with category_id.")
    if remaining_null:
        print(f"WARNING: {table} has {remaining_null} row(s) still missing category_id.")


def _drop_old_category_column(conn: sqlite3.Connection, table: str) -> None:
    if not _has_column(conn, table, 'category'):
        print(f"{table} has no category column left - skipping drop.")
        return
    with conn:
        conn.execute(f'ALTER TABLE {table} DROP COLUMN category')
    print(f"{table}.category (old text column) dropped.")


def migrate(db_path: str = None) -> None:
    """
    Run the migration against db_path (defaults to the real
    data/shopping_tracker.db). The optional parameter exists so tests can
    point this at a temporary file - production usage is always the
    parameterless `python migrate_categories_to_id.py`.
    """
    db_path = db_path or SQLITE_DB_PATH
    if not os.path.exists(db_path):
        print(f"No database found at {db_path} — nothing to migrate.")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        _rebuild_categories_with_id(conn)
        for table in ('receipt_items', 'transactions'):
            _backfill_category_id(conn, table)
        for table in ('receipt_items', 'transactions'):
            _drop_old_category_column(conn, table)
    finally:
        conn.close()

    print("Migration complete.")


if __name__ == '__main__':
    migrate()
