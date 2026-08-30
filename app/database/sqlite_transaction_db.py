"""
SQLite Transaction Database Implementation.

This module implements statement transaction storage using SQLite (see
SP-035), joining the same shopping_tracker.db file SP-034's SqliteDatabase
uses for receipts. Replaces JSONTransactionDatabase as the transaction
storage backend in every environment, mirroring its exact method shapes so
TransactionService needs zero changes.

Hand-written SQL via the stdlib sqlite3 module, no ORM - same style as
SqliteDatabase. One connection is opened and closed per public method call.
"""

import os
import sqlite3
import uuid
from datetime import datetime
from typing import List, Dict, Optional

# Columns update_transaction() is allowed to change. id/saved_at/user_email/
# is_deleted are deliberately excluded - mirrors SqliteDatabase.update_receipt's
# allowlist-as-preservation-mechanism approach.
_UPDATABLE_TRANSACTION_COLUMNS = (
    'date', 'description', 'amount', 'currency', 'direction', 'category',
    'source', 'statement_id'
)


class SqliteTransactionDatabase:
    """SQLite-backed storage for statement Transaction records."""

    def __init__(self, file_path: str):
        """
        Initialize the SQLite transaction database.

        Args:
            file_path (str): Path to the SQLite database file (shared with
                SqliteDatabase's receipts/receipt_items tables in production)
        """
        self.file_path = file_path
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        """Open a fresh connection, creating the parent directory if needed."""
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        conn = sqlite3.connect(self.file_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        """Create the transactions table if it doesn't exist."""
        conn = self._connect()
        try:
            with conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS transactions (
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
                    )
                ''')
        finally:
            conn.close()

    def save_transaction(self, transaction_data: Dict) -> str:
        """
        Save a transaction to SQLite.

        Args:
            transaction_data (Dict): Transaction information to save

        Returns:
            str: The unique ID assigned to this transaction
        """
        transaction_id = str(uuid.uuid4())
        saved_at = datetime.now().isoformat()
        transaction_data['id'] = transaction_id
        transaction_data['saved_at'] = saved_at

        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    '''INSERT INTO transactions
                       (id, date, description, amount, currency, direction, category,
                        source, statement_id, saved_at, user_email, is_deleted)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        transaction_id,
                        transaction_data.get('date'),
                        transaction_data.get('description', ''),
                        transaction_data.get('amount', 0.0),
                        transaction_data.get('currency', 'USD'),
                        transaction_data.get('direction', 'debit'),
                        transaction_data.get('category', 'Other'),
                        transaction_data.get('source', 'card'),
                        transaction_data.get('statement_id'),
                        saved_at,
                        transaction_data.get('user_email'),
                        int(bool(transaction_data.get('is_deleted', False))),
                    )
                )
        finally:
            conn.close()

        print(f"Saved transaction with ID: {transaction_id}")
        return transaction_id

    def get_all_transactions(self, user_email: str) -> List[Dict]:
        """
        Retrieve all transactions owned by user_email.

        Args:
            user_email (str): Email of the transactions' owner

        Returns:
            List[Dict]: List of matching transactions, excluding soft-deleted ones
        """
        conn = self._connect()
        try:
            # Plain insertion order (ascending) - JSONTransactionDatabase does
            # NOT reverse this, unlike receipts, so this must not either.
            rows = conn.execute(
                'SELECT * FROM transactions WHERE user_email = ? AND is_deleted = 0 ORDER BY rowid ASC',
                (user_email,)
            ).fetchall()
            return [self._row_to_dict(row) for row in rows]
        finally:
            conn.close()

    def get_transaction_by_id(self, transaction_id: str, user_email: str) -> Optional[Dict]:
        """
        Find and return a specific transaction by its ID, if owned by user_email.

        Args:
            transaction_id (str): The transaction ID to search for
            user_email (str): Email of the transaction's expected owner

        Returns:
            Optional[Dict]: Transaction data if found and owned by user_email, None otherwise
        """
        conn = self._connect()
        try:
            row = conn.execute(
                'SELECT * FROM transactions WHERE id = ? AND user_email = ?',
                (transaction_id, user_email)
            ).fetchone()
            return self._row_to_dict(row) if row is not None else None
        finally:
            conn.close()

    def update_transaction(self, transaction_id: str, user_email: str, transaction_data: Dict) -> bool:
        """
        Update an existing transaction's fields in place, if owned by user_email.

        Only the keys present in transaction_data that appear in
        _UPDATABLE_TRANSACTION_COLUMNS are changed - id/saved_at/user_email/
        is_deleted are never eligible, so a caller's dict can't touch them
        regardless of what it contains.

        Args:
            transaction_id (str): The transaction ID to update
            user_email (str): Email of the transaction's expected owner
            transaction_data (Dict): New field values to apply

        Returns:
            bool: True if the transaction was found, owned by user_email, and updated;
                  False otherwise
        """
        conn = self._connect()
        try:
            existing = conn.execute(
                'SELECT id FROM transactions WHERE id = ? AND user_email = ?',
                (transaction_id, user_email)
            ).fetchone()
            if existing is None:
                print(f"Transaction not found: {transaction_id}")
                return False

            set_clauses = [f"{col} = ?" for col in _UPDATABLE_TRANSACTION_COLUMNS if col in transaction_data]
            params = [transaction_data[col] for col in _UPDATABLE_TRANSACTION_COLUMNS if col in transaction_data]

            if set_clauses:
                with conn:
                    conn.execute(
                        f"UPDATE transactions SET {', '.join(set_clauses)} WHERE id = ? AND user_email = ?",
                        params + [transaction_id, user_email]
                    )

            print(f"Updated transaction with ID: {transaction_id}")
            return True
        finally:
            conn.close()

    def soft_delete_transaction(self, transaction_id: str, user_email: str) -> bool:
        """
        Soft-delete a transaction by marking it as deleted, if owned by user_email.

        Args:
            transaction_id (str): The transaction ID to soft-delete
            user_email (str): Email of the transaction's expected owner

        Returns:
            bool: True if the transaction was found, owned by user_email, and
                  marked; False otherwise
        """
        conn = self._connect()
        try:
            with conn:
                cursor = conn.execute(
                    'UPDATE transactions SET is_deleted = 1 WHERE id = ? AND user_email = ?',
                    (transaction_id, user_email)
                )
            if cursor.rowcount > 0:
                print(f"Soft-deleted transaction with ID: {transaction_id}")
                return True
            print(f"Transaction not found: {transaction_id}")
            return False
        finally:
            conn.close()

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """Assemble a transaction row into the shared dict shape."""
        return {
            'id': row['id'],
            'date': row['date'],
            'description': row['description'],
            'amount': row['amount'],
            'currency': row['currency'],
            'direction': row['direction'],
            'category': row['category'],
            'source': row['source'],
            'statement_id': row['statement_id'],
            'saved_at': row['saved_at'],
            'user_email': row['user_email'],
            'is_deleted': bool(row['is_deleted']),
        }
