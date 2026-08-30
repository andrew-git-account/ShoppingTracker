"""
SQLite Database Implementation.

This module implements the Database interface using SQLite for storage (see
SP-034). Replaces JSONDatabase as the receipt storage backend in every
environment - test and production both build this same class, just pointed
at different files, so the SQLite code path is exercised by the automated
test suite rather than only running, untested, in production.

Hand-written SQL via the stdlib sqlite3 module, no ORM - matches this
codebase's existing style of hand-writing storage code rather than using an
abstraction layer over it. One connection is opened and closed per public
method call (never held on the instance), mirroring JSONDatabase's own
"read/write the whole file per call" cost model.
"""

import os
import sqlite3
import uuid
from datetime import datetime
from typing import List, Dict, Optional

from .base import Database

# Columns update_receipt() is allowed to change. id/saved_at/user_email/
# is_deleted are deliberately excluded - they can never appear in the SET
# clause, so a caller's dict can't touch them regardless of what it contains
# (mirrors JSONDatabase.update_receipt()'s explicit preserve-and-restore).
_UPDATABLE_RECEIPT_COLUMNS = (
    'store_name', 'purchase_date', 'tax_amount', 'discount_amount',
    'total_amount', 'currency', 'linked_transaction_id'
)


def _item_values(item: Dict) -> tuple:
    """
    Pull (name, price, quantity, category, amount, unit) out of an item
    dict, defaulting every field exactly like ReceiptItem.from_dict() does.

    Never rely on the receipt_items table's own SQL DEFAULT clauses for
    this - a SQL DEFAULT only applies when a column is omitted from the
    INSERT entirely, not when it's explicitly given NULL. item.get('amount')
    with no Python-side default would return None for a legacy item dict
    that never had an 'amount' key, and binding NULL into a NOT NULL column
    raises sqlite3.IntegrityError instead of falling back to the default.
    """
    return (
        item.get('name', ''),
        item.get('price', 0.0),
        item.get('quantity', 1),
        item.get('category', 'Other'),
        item.get('amount', 1.0),
        item.get('unit', 'piece'),
    )


class SqliteDatabase(Database):
    """SQLite-backed database implementation for receipts."""

    def __init__(self, file_path: str):
        """
        Initialize the SQLite database.

        Args:
            file_path (str): Path to the SQLite database file
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
        """Create the receipts/receipt_items tables if they don't exist."""
        conn = self._connect()
        try:
            with conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS receipts (
                        id TEXT PRIMARY KEY,
                        store_name TEXT,
                        purchase_date TEXT,
                        tax_amount REAL NOT NULL DEFAULT 0,
                        discount_amount REAL NOT NULL DEFAULT 0,
                        total_amount REAL,
                        saved_at TEXT NOT NULL,
                        currency TEXT NOT NULL DEFAULT 'USD',
                        user_email TEXT NOT NULL,
                        is_deleted INTEGER NOT NULL DEFAULT 0,
                        linked_transaction_id TEXT
                    )
                ''')
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS receipt_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        receipt_id TEXT NOT NULL REFERENCES receipts(id),
                        name TEXT NOT NULL,
                        price REAL NOT NULL,
                        quantity INTEGER NOT NULL DEFAULT 1,
                        category TEXT NOT NULL DEFAULT 'Other',
                        amount REAL NOT NULL DEFAULT 1.0,
                        unit TEXT NOT NULL DEFAULT 'piece',
                        position INTEGER NOT NULL
                    )
                ''')
        finally:
            conn.close()

    def save_receipt(self, receipt_data: Dict) -> str:
        """
        Save a receipt to SQLite.

        Args:
            receipt_data (Dict): Receipt information to save

        Returns:
            str: The unique ID assigned to this receipt
        """
        receipt_id = str(uuid.uuid4())
        saved_at = datetime.now().isoformat()
        receipt_data['id'] = receipt_id
        receipt_data['saved_at'] = saved_at

        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    '''INSERT INTO receipts
                       (id, store_name, purchase_date, tax_amount, discount_amount,
                        total_amount, saved_at, currency, user_email, is_deleted,
                        linked_transaction_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        receipt_id,
                        receipt_data.get('store_name'),
                        receipt_data.get('purchase_date'),
                        receipt_data.get('tax_amount', 0.0),
                        receipt_data.get('discount_amount', 0.0),
                        receipt_data.get('total_amount'),
                        saved_at,
                        receipt_data.get('currency', 'USD'),
                        receipt_data.get('user_email'),
                        int(bool(receipt_data.get('is_deleted', False))),
                        receipt_data.get('linked_transaction_id'),
                    )
                )
                for position, item in enumerate(receipt_data.get('items', [])):
                    name, price, quantity, category, amount, unit = _item_values(item)
                    conn.execute(
                        '''INSERT INTO receipt_items
                           (receipt_id, name, price, quantity, category, amount, unit, position)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (receipt_id, name, price, quantity, category, amount, unit, position)
                    )
        finally:
            conn.close()

        print(f"Saved receipt with ID: {receipt_id}")
        return receipt_id

    def get_all_receipts(self, user_email: str) -> List[Dict]:
        """
        Retrieve all receipts owned by user_email, newest first.

        Args:
            user_email (str): Email of the receipts' owner

        Returns:
            List[Dict]: List of matching receipts
        """
        conn = self._connect()
        try:
            # rowid tracks insertion order exactly, unlike saved_at which can
            # collide within the same second - needed to match JSONDatabase's
            # list(reversed(...)) behavior precisely.
            rows = conn.execute(
                'SELECT * FROM receipts WHERE user_email = ? AND is_deleted = 0 ORDER BY rowid DESC',
                (user_email,)
            ).fetchall()
            return [self._row_to_dict(conn, row) for row in rows]
        finally:
            conn.close()

    def get_receipt_by_id(self, receipt_id: str, user_email: str) -> Optional[Dict]:
        """
        Find and return a specific receipt by its ID, if owned by user_email.

        Deliberately does not filter on is_deleted - a soft-deleted receipt
        is still fetchable by id, matching JSONDatabase.

        Args:
            receipt_id (str): The receipt ID to search for
            user_email (str): Email of the receipt's expected owner

        Returns:
            Optional[Dict]: Receipt data if found and owned by user_email, None otherwise
        """
        conn = self._connect()
        try:
            row = conn.execute(
                'SELECT * FROM receipts WHERE id = ? AND user_email = ?',
                (receipt_id, user_email)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_dict(conn, row)
        finally:
            conn.close()

    def update_receipt(self, receipt_id: str, user_email: str, receipt_data: Dict) -> bool:
        """
        Update an existing receipt's fields in place, if owned by user_email.

        Only the keys present in receipt_data are changed - id/saved_at/
        user_email/is_deleted are never eligible (see
        _UPDATABLE_RECEIPT_COLUMNS), and items are only touched if 'items'
        is literally a key in receipt_data (a partial update with no
        'items' key leaves existing items untouched).

        Args:
            receipt_id (str): The receipt ID to update
            user_email (str): Email of the receipt's expected owner
            receipt_data (Dict): New field values to apply

        Returns:
            bool: True if the receipt was found, owned by user_email, and updated;
                  False otherwise
        """
        conn = self._connect()
        try:
            existing = conn.execute(
                'SELECT id FROM receipts WHERE id = ? AND user_email = ?',
                (receipt_id, user_email)
            ).fetchone()
            if existing is None:
                print(f"Receipt not found: {receipt_id}")
                return False

            set_clauses = [f"{col} = ?" for col in _UPDATABLE_RECEIPT_COLUMNS if col in receipt_data]
            params = [receipt_data[col] for col in _UPDATABLE_RECEIPT_COLUMNS if col in receipt_data]

            with conn:
                if set_clauses:
                    conn.execute(
                        f"UPDATE receipts SET {', '.join(set_clauses)} WHERE id = ? AND user_email = ?",
                        params + [receipt_id, user_email]
                    )
                if 'items' in receipt_data:
                    conn.execute('DELETE FROM receipt_items WHERE receipt_id = ?', (receipt_id,))
                    for position, item in enumerate(receipt_data['items']):
                        name, price, quantity, category, amount, unit = _item_values(item)
                        conn.execute(
                            '''INSERT INTO receipt_items
                               (receipt_id, name, price, quantity, category, amount, unit, position)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                            (receipt_id, name, price, quantity, category, amount, unit, position)
                        )

            print(f"Updated receipt with ID: {receipt_id}")
            return True
        finally:
            conn.close()

    def soft_delete_receipt(self, receipt_id: str, user_email: str) -> bool:
        """
        Soft-delete a receipt by marking it as deleted, if owned by user_email.

        Args:
            receipt_id (str): The receipt ID to soft-delete
            user_email (str): Email of the receipt's expected owner

        Returns:
            bool: True if receipt was found, owned by user_email, and marked;
                  False otherwise
        """
        conn = self._connect()
        try:
            with conn:
                cursor = conn.execute(
                    'UPDATE receipts SET is_deleted = 1 WHERE id = ? AND user_email = ?',
                    (receipt_id, user_email)
                )
            if cursor.rowcount > 0:
                print(f"Soft-deleted receipt with ID: {receipt_id}")
                return True
            print(f"Receipt not found: {receipt_id}")
            return False
        finally:
            conn.close()

    def delete_receipt(self, receipt_id: str, user_email: str) -> bool:
        """
        Delete a receipt (and its items) from SQLite, if owned by user_email.

        Args:
            receipt_id (str): The receipt ID to delete
            user_email (str): Email of the receipt's expected owner

        Returns:
            bool: True if receipt was owned by user_email and deleted, False otherwise
        """
        conn = self._connect()
        try:
            existing = conn.execute(
                'SELECT id FROM receipts WHERE id = ? AND user_email = ?',
                (receipt_id, user_email)
            ).fetchone()
            if existing is None:
                print(f"Receipt not found: {receipt_id}")
                return False

            with conn:
                # No ON DELETE CASCADE in the schema - clear the child table
                # manually before removing the parent row.
                conn.execute('DELETE FROM receipt_items WHERE receipt_id = ?', (receipt_id,))
                conn.execute(
                    'DELETE FROM receipts WHERE id = ? AND user_email = ?',
                    (receipt_id, user_email)
                )

            print(f"Deleted receipt with ID: {receipt_id}")
            return True
        finally:
            conn.close()

    def get_receipts_count(self, user_email: str) -> int:
        """
        Get the total number of receipts owned by user_email.

        Args:
            user_email (str): Email of the receipts' owner

        Returns:
            int: Number of matching receipts
        """
        conn = self._connect()
        try:
            row = conn.execute(
                'SELECT COUNT(*) AS cnt FROM receipts WHERE user_email = ? AND is_deleted = 0',
                (user_email,)
            ).fetchone()
            return row['cnt']
        finally:
            conn.close()

    def _row_to_dict(self, conn: sqlite3.Connection, row: sqlite3.Row) -> Dict:
        """Assemble a receipt row plus its ordered items into the shared dict shape."""
        items = conn.execute(
            'SELECT name, price, quantity, category, amount, unit FROM receipt_items '
            'WHERE receipt_id = ? ORDER BY position ASC',
            (row['id'],)
        ).fetchall()
        return {
            'id': row['id'],
            'store_name': row['store_name'],
            'purchase_date': row['purchase_date'],
            'items': [dict(item) for item in items],
            'tax_amount': row['tax_amount'],
            'discount_amount': row['discount_amount'],
            'total_amount': row['total_amount'],
            'saved_at': row['saved_at'],
            'currency': row['currency'],
            'user_email': row['user_email'],
            'is_deleted': bool(row['is_deleted']),
            'linked_transaction_id': row['linked_transaction_id'],
        }
