"""
Transaction Database - JSON file storage for statement transactions.

Statement transactions (see SP-025) are a separate concern from receipts -
never itemized, sourced from bank/card statement PDFs rather than photographed
receipts - so they get their own small JSON file, following the same
separate-concern-gets-its-own-file pattern as usage_log_db.py (SP-020), rather
than folding into json_db.py.
"""

import json
import os
import uuid
from typing import List, Dict, Optional
from datetime import datetime


class JSONTransactionDatabase:
    """
    JSON file-based storage for Transaction records.

    Mirrors JSONDatabase's method shapes (app/database/json_db.py) so the
    read/write/ownership conventions stay consistent across both record types.
    """

    def __init__(self, file_path: str):
        """
        Initialize the transaction database.

        Args:
            file_path (str): Path to the JSON file (e.g., './data/transactions.json')
        """
        self.file_path = file_path
        self.initialize()

    def initialize(self) -> None:
        """Create the JSON file (and parent directory) with an empty list if missing."""
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created database directory: {directory}")

        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump([], f)
            print(f"Initialized database file: {self.file_path}")

    def save_transaction(self, transaction_data: Dict) -> str:
        """
        Save a transaction to the JSON file.

        Args:
            transaction_data (Dict): Transaction information to save

        Returns:
            str: The unique ID assigned to this transaction
        """
        transaction_id = str(uuid.uuid4())

        transaction_data['id'] = transaction_id
        transaction_data['saved_at'] = datetime.now().isoformat()

        transactions = self._read_all_transactions()
        transactions.append(transaction_data)
        self._write_all_transactions(transactions)

        print(f"Saved transaction with ID: {transaction_id}")
        return transaction_id

    def get_all_transactions(self, user_email: str) -> List[Dict]:
        """
        Retrieve all transactions owned by user_email from the JSON file.

        Args:
            user_email (str): Email of the transactions' owner

        Returns:
            List[Dict]: List of matching transactions, excluding soft-deleted ones
        """
        transactions = self._read_all_transactions()
        return [
            t for t in transactions
            if not t.get('is_deleted', False) and t.get('user_email') == user_email
        ]

    def get_transaction_by_id(self, transaction_id: str, user_email: str) -> Optional[Dict]:
        """
        Find and return a specific transaction by its ID, if owned by user_email.

        Args:
            transaction_id (str): The transaction ID to search for
            user_email (str): Email of the transaction's expected owner

        Returns:
            Optional[Dict]: Transaction data if found and owned by user_email, None otherwise
        """
        transactions = self._read_all_transactions()

        for transaction in transactions:
            if transaction.get('id') == transaction_id and transaction.get('user_email') == user_email:
                return transaction

        return None

    def update_transaction(self, transaction_id: str, user_email: str, transaction_data: Dict) -> bool:
        """
        Update an existing transaction's fields in place, if owned by user_email.

        Args:
            transaction_id (str): The transaction ID to update
            user_email (str): Email of the transaction's expected owner
            transaction_data (Dict): New field values to apply

        Returns:
            bool: True if the transaction was found, owned by user_email, and updated;
                  False otherwise (not found and not-owned are indistinguishable on purpose)
        """
        transactions = self._read_all_transactions()

        for transaction in transactions:
            if transaction.get('id') == transaction_id and transaction.get('user_email') == user_email:
                # Preserve identity/ownership/lifecycle fields even if transaction_data
                # happened to include them - only the caller's other fields should change.
                preserved_id = transaction.get('id')
                preserved_saved_at = transaction.get('saved_at')
                preserved_user_email = transaction.get('user_email')
                preserved_is_deleted = transaction.get('is_deleted', False)

                transaction.update(transaction_data)

                transaction['id'] = preserved_id
                transaction['saved_at'] = preserved_saved_at
                transaction['user_email'] = preserved_user_email
                transaction['is_deleted'] = preserved_is_deleted

                self._write_all_transactions(transactions)
                print(f"Updated transaction with ID: {transaction_id}")
                return True

        print(f"Transaction not found: {transaction_id}")
        return False

    # Private helper methods (not part of the public interface)

    def _read_all_transactions(self) -> List[Dict]:
        """Internal: read all transactions from the JSON file."""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.initialize()
            return []
        except json.JSONDecodeError as e:
            raise Exception(f"JSON file is corrupted: {e}")

    def _write_all_transactions(self, transactions: List[Dict]) -> None:
        """Internal: write all transactions to the JSON file."""
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(transactions, f, indent=2, ensure_ascii=False)
