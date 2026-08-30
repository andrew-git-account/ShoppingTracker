"""
SQLite Allowed Users Database Implementation.

Backs AuthService's allowed-users storage (see SP-036), joining the same
shopping_tracker.db file SP-034/SP-035 already use. AuthService keeps
owning all business logic (case-insensitive matching, last-active-admin
safeguard) - this class is pure storage, mirroring the "load everything,
mutate in memory, save everything back" cost model AuthService already used
against the JSON file.
"""

import os
import sqlite3
from typing import Dict, List


class SqliteAllowedUsersDatabase:
    """SQLite-backed storage for the allowed-users list."""

    def __init__(self, file_path: str):
        """
        Initialize the allowed users database.

        Args:
            file_path (str): Path to the SQLite database file (shared with
                receipts/transactions/usage log/categories in production)
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
        """
        Create the allowed_users table if it doesn't exist.

        email uses COLLATE NOCASE rather than a lowercase-normalized primary
        key, so stored case is preserved exactly as entered (matching
        AuthService's current behavior) while WHERE email = ? lookups still
        match case-insensitively with no LOWER() needed on either side.
        """
        conn = self._connect()
        try:
            with conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS allowed_users (
                        email TEXT PRIMARY KEY COLLATE NOCASE,
                        is_admin INTEGER NOT NULL DEFAULT 0,
                        is_blocked INTEGER NOT NULL DEFAULT 0
                    )
                ''')
        finally:
            conn.close()

    def get_all_users(self) -> List[Dict]:
        """Return every allowed user as a normalized {email, is_admin, is_blocked} dict."""
        conn = self._connect()
        try:
            rows = conn.execute('SELECT * FROM allowed_users').fetchall()
            return [
                {
                    'email': row['email'],
                    'is_admin': bool(row['is_admin']),
                    'is_blocked': bool(row['is_blocked']),
                }
                for row in rows
            ]
        finally:
            conn.close()

    def save_all_users(self, users: List[Dict]) -> None:
        """
        Replace the entire allowed-users list in one transaction.

        Bulk delete-then-reinsert, mirroring the "write the whole list back"
        cost model AuthService already used against the JSON file - fine for
        a handful of admin users, and wrapped in one transaction so a crash
        mid-write leaves the table exactly as it was before the call, never
        empty.
        """
        conn = self._connect()
        try:
            with conn:
                conn.execute('DELETE FROM allowed_users')
                conn.executemany(
                    'INSERT INTO allowed_users (email, is_admin, is_blocked) VALUES (?, ?, ?)',
                    [
                        (u['email'], int(bool(u['is_admin'])), int(bool(u['is_blocked'])))
                        for u in users
                    ]
                )
        finally:
            conn.close()
