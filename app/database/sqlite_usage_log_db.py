"""
SQLite Usage Log Implementation.

Replaces UsageLogDatabase as the LLM usage/cost log backend (see SP-036),
joining the same shopping_tracker.db file SP-034/SP-035 already use. Reuses
_estimate_cost_usd from usage_log_db.py rather than duplicating the pricing
table.
"""

import os
import sqlite3
from datetime import datetime
from typing import Dict, List

from .usage_log_db import _estimate_cost_usd


class SqliteUsageLogDatabase:
    """SQLite-backed log of every LLM (Claude) API call made by the app."""

    def __init__(self, file_path: str):
        """
        Initialize the usage log.

        Args:
            file_path (str): Path to the SQLite database file (shared with
                receipts/transactions in production)
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
        """Create the usage_log table if it doesn't exist."""
        conn = self._connect()
        try:
            with conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS usage_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        user_email TEXT NOT NULL,
                        model TEXT NOT NULL,
                        input_tokens INTEGER NOT NULL,
                        output_tokens INTEGER NOT NULL,
                        cost_usd REAL NOT NULL,
                        success INTEGER NOT NULL,
                        is_retry INTEGER NOT NULL
                    )
                ''')
        finally:
            conn.close()

    def log_call(
        self,
        user_email: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        success: bool,
        is_retry: bool,
    ) -> None:
        """
        Record one LLM API call attempt.

        Args:
            user_email (str): Email of the user whose upload triggered this call
            model (str): Claude model ID used for this call
            input_tokens (int): Input tokens consumed (0 if the call never reached the API)
            output_tokens (int): Output tokens generated (0 if the call never reached the API)
            success (bool): Whether the call succeeded (API responded AND parsed cleanly)
            is_retry (bool): Whether this was the SP-018 reconciliation retry, not the first attempt
        """
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    '''INSERT INTO usage_log
                       (timestamp, user_email, model, input_tokens, output_tokens,
                        cost_usd, success, is_retry)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        datetime.now().isoformat(),
                        user_email,
                        model,
                        input_tokens,
                        output_tokens,
                        _estimate_cost_usd(model, input_tokens, output_tokens),
                        int(bool(success)),
                        int(bool(is_retry)),
                    )
                )
        finally:
            conn.close()

    def get_all_records(self) -> List[Dict]:
        """Return every logged call, oldest first."""
        conn = self._connect()
        try:
            rows = conn.execute('SELECT * FROM usage_log ORDER BY rowid ASC').fetchall()
            return [
                {
                    'timestamp': row['timestamp'],
                    'user_email': row['user_email'],
                    'model': row['model'],
                    'input_tokens': row['input_tokens'],
                    'output_tokens': row['output_tokens'],
                    'cost_usd': row['cost_usd'],
                    'success': bool(row['success']),
                    'is_retry': bool(row['is_retry']),
                }
                for row in rows
            ]
        finally:
            conn.close()
