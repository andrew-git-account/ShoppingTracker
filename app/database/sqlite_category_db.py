"""
SQLite Category Database Implementation.

Replaces CategoryDatabase as the category vocabulary backend (see SP-036),
joining the same shopping_tracker.db file SP-034/SP-035 already use. Reuses
_SEED_CATEGORIES from json_db.py for the seed list rather than duplicating
the category names.
"""

import os
import sqlite3
from typing import Dict, List

from .json_db import _SEED_CATEGORIES


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
                conn.execute('CREATE TABLE IF NOT EXISTS categories (name TEXT PRIMARY KEY)')
                count = conn.execute('SELECT COUNT(*) AS cnt FROM categories').fetchone()['cnt']
                if count == 0:
                    conn.executemany(
                        'INSERT INTO categories (name) VALUES (?)',
                        [(c['name'],) for c in _SEED_CATEGORIES]
                    )
        finally:
            conn.close()

    def get_all_categories(self) -> List[Dict]:
        """Return all categories."""
        conn = self._connect()
        try:
            rows = conn.execute('SELECT name FROM categories ORDER BY rowid ASC').fetchall()
            return [{'name': row['name']} for row in rows]
        finally:
            conn.close()
