"""
SQLite Category Database Implementation.

Replaces CategoryDatabase as the category vocabulary backend (see SP-036),
joining the same shopping_tracker.db file SP-034/SP-035 already use. Reuses
_SEED_CATEGORIES from json_db.py for the seed list rather than duplicating
the category names.

See SP-044: categories now has a stable integer id (rather than name as the
primary key), so receipt_items/transactions can reference it by
category_id instead of duplicating the name as free text - a rename or a
future hide/unhide (SP-041) then applies to every row that used it, with no
text-matching cascade needed.
"""

import os
import sqlite3
from typing import Dict, List

from .json_db import _SEED_CATEGORIES

_CREATE_CATEGORIES_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS categories ('
    'id INTEGER PRIMARY KEY AUTOINCREMENT, '
    'name TEXT NOT NULL UNIQUE'
    ')'
)


def ensure_categories_table(conn: sqlite3.Connection) -> None:
    """
    Create the categories table if it doesn't exist yet (no seeding).

    receipt_items.category_id and transactions.category_id reference this
    table, so SqliteDatabase and SqliteTransactionDatabase each call this
    from their own initialize() too - guaranteeing the table exists even if
    one of them is constructed on its own, without SqliteCategoryDatabase
    (as several tests do), and before any row is saved. resolve_category_id()
    below then creates missing category rows on demand, so an empty (not yet
    seeded) table is fine.
    """
    conn.execute(_CREATE_CATEGORIES_TABLE_SQL)


def resolve_category_id(conn: sqlite3.Connection, name: str) -> int:
    """
    Look up categories.id for a category name, creating the row if it's not
    there yet (e.g. a legacy/typo'd category no longer in the seed list).

    Shared by sqlite_db.py and sqlite_transaction_db.py so receipt items and
    transactions can resolve the name they're handed (from LLM extraction or
    an edit form) to the id they now store, without either file duplicating
    this lookup. Takes the caller's own connection/transaction rather than
    opening a new one, since all three tables live in the same database file.
    """
    row = conn.execute('SELECT id FROM categories WHERE name = ?', (name,)).fetchone()
    if row is not None:
        return row['id']
    cursor = conn.execute('INSERT INTO categories (name) VALUES (?)', (name,))
    return cursor.lastrowid


class SqliteCategoryDatabase:
    """SQLite-backed storage for the category vocabulary."""

    def __init__(self, file_path: str):
        """
        Initialize the category database.

        Args:
            file_path (str): Path to the SQLite database file (shared with
                receipts/transactions/usage log in production)
        """
        self.file_path = file_path
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        conn = sqlite3.connect(self.file_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        """Create the categories table and seed it if empty."""
        conn = self._connect()
        try:
            with conn:
                ensure_categories_table(conn)
                count = conn.execute('SELECT COUNT(*) AS cnt FROM categories').fetchone()['cnt']
                if count == 0:
                    conn.executemany(
                        'INSERT INTO categories (name) VALUES (?)',
                        [(c['name'],) for c in _SEED_CATEGORIES]
                    )
        finally:
            conn.close()

    def get_all_categories(self) -> List[Dict]:
        """Return all categories, in insertion order."""
        conn = self._connect()
        try:
            rows = conn.execute('SELECT id, name FROM categories ORDER BY rowid ASC').fetchall()
            return [{'id': row['id'], 'name': row['name']} for row in rows]
        finally:
            conn.close()
