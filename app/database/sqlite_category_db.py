"""
SQLite Category Database Implementation.

Replaces CategoryDatabase as the category vocabulary backend (see SP-036),
joining the same shopping_tracker.db file SP-034/SP-035 already use. Reuses
_SEED_CATEGORIES from json_db.py for the seed list rather than duplicating
the category names.

See SP-044: categories now has a stable integer id (rather than name as the
primary key), so receipt_items/transactions can reference it by
category_id instead of duplicating the name as free text - a rename or a
hide/unhide (SP-041) then applies to every row that used it, with no
text-matching cascade needed.

See SP-041: categories also has a `hidden` flag - a hidden category is
excluded from future assignment (LLM prompts, edit-form dropdowns) but a
row already referencing it is completely unaffected, since nothing about
the category row's identity changed.
"""

import os
import sqlite3
from typing import Dict, List, Optional

from .json_db import _SEED_CATEGORIES

_CREATE_CATEGORIES_TABLE_SQL = (
    'CREATE TABLE IF NOT EXISTS categories ('
    'id INTEGER PRIMARY KEY AUTOINCREMENT, '
    'name TEXT NOT NULL UNIQUE'
    ')'
)


def _ensure_hidden_column(conn: sqlite3.Connection) -> None:
    """
    Add the `hidden` column if an existing categories table predates it
    (SP-041). A plain ADD COLUMN with a DEFAULT is safe on a table that
    already has rows - unlike SP-044's `id` change, this needs no table
    rebuild, so every existing database (including production) self-heals
    the next time any of the three DB classes' initialize() runs.
    """
    columns = {row['name'] for row in conn.execute('PRAGMA table_info(categories)')}
    if 'hidden' not in columns:
        conn.execute('ALTER TABLE categories ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0')


def ensure_categories_table(conn: sqlite3.Connection) -> None:
    """
    Create the categories table if it doesn't exist yet (no seeding), and
    make sure it has the `hidden` column.

    receipt_items.category_id and transactions.category_id reference this
    table, so SqliteDatabase and SqliteTransactionDatabase each call this
    from their own initialize() too - guaranteeing the table exists even if
    one of them is constructed on its own, without SqliteCategoryDatabase
    (as several tests do), and before any row is saved. resolve_category_id()
    below then creates missing category rows on demand, so an empty (not yet
    seeded) table is fine. New rows default to hidden=0 (visible).
    """
    conn.execute(_CREATE_CATEGORIES_TABLE_SQL)
    _ensure_hidden_column(conn)


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
        """Return all categories (visible and hidden), in insertion order."""
        conn = self._connect()
        try:
            rows = conn.execute('SELECT id, name, hidden FROM categories ORDER BY rowid ASC').fetchall()
            return [{'id': row['id'], 'name': row['name'], 'hidden': bool(row['hidden'])} for row in rows]
        finally:
            conn.close()

    def get_category_by_id(self, category_id: int) -> Optional[Dict]:
        """Return a single category by id, or None if it doesn't exist."""
        conn = self._connect()
        try:
            row = conn.execute(
                'SELECT id, name, hidden FROM categories WHERE id = ?', (category_id,)
            ).fetchone()
            if row is None:
                return None
            return {'id': row['id'], 'name': row['name'], 'hidden': bool(row['hidden'])}
        finally:
            conn.close()

    def get_category_by_name(self, name: str) -> Optional[Dict]:
        """Return a single category by exact name match, or None if it doesn't exist."""
        conn = self._connect()
        try:
            row = conn.execute(
                'SELECT id, name, hidden FROM categories WHERE name = ?', (name,)
            ).fetchone()
            if row is None:
                return None
            return {'id': row['id'], 'name': row['name'], 'hidden': bool(row['hidden'])}
        finally:
            conn.close()

    def add_category(self, name: str) -> int:
        """Insert a new category and return its id. Caller is responsible for
        checking for an existing duplicate first (see CategoryService)."""
        conn = self._connect()
        try:
            with conn:
                cursor = conn.execute('INSERT INTO categories (name) VALUES (?)', (name,))
                return cursor.lastrowid
        finally:
            conn.close()

    def rename_category(self, category_id: int, new_name: str) -> bool:
        """Rename a category by id. Returns whether a row was actually updated."""
        conn = self._connect()
        try:
            with conn:
                cursor = conn.execute(
                    'UPDATE categories SET name = ? WHERE id = ?', (new_name, category_id)
                )
                return cursor.rowcount > 0
        finally:
            conn.close()

    def set_hidden(self, category_id: int, hidden: bool) -> bool:
        """Set a category's hidden flag by id. Returns whether a row was actually updated."""
        conn = self._connect()
        try:
            with conn:
                cursor = conn.execute(
                    'UPDATE categories SET hidden = ? WHERE id = ?', (int(hidden), category_id)
                )
                return cursor.rowcount > 0
        finally:
            conn.close()
