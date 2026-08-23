"""
Transaction Service - Business Logic Layer for statement transactions.

Thin wrapper around JSONTransactionDatabase, converting between Transaction
objects and the dicts the database layer works with - mirrors ReceiptService's
data-access methods (see SP-025). Settled here (rather than routes talking to
the database directly) so every route continues to go through a *_service
object, matching the rest of this app's "routes are thin, services do the
work" convention.
"""

from typing import List, Optional

from ..models import Transaction
from ..database.transaction_db import JSONTransactionDatabase


class TransactionService:
    """Service for reading and writing statement transactions."""

    def __init__(self, database: JSONTransactionDatabase):
        """
        Initialize the transaction service.

        Args:
            database (JSONTransactionDatabase): Database instance for storing transactions
        """
        self.database = database

    def get_all_transactions(self, user_email: str) -> List[Transaction]:
        """
        Retrieve all transactions owned by user_email from database.

        Args:
            user_email (str): Email of the transactions' owner

        Returns:
            List[Transaction]: List of matching transactions
        """
        transaction_dicts = self.database.get_all_transactions(user_email)
        return [Transaction.from_dict(data) for data in transaction_dicts]

    def get_transaction_by_id(self, transaction_id: str, user_email: str) -> Optional[Transaction]:
        """
        Retrieve a specific transaction by ID, if owned by user_email.

        Args:
            transaction_id (str): Transaction ID
            user_email (str): Email of the transaction's expected owner

        Returns:
            Optional[Transaction]: Transaction if found and owned by user_email, None otherwise
        """
        transaction_dict = self.database.get_transaction_by_id(transaction_id, user_email)
        if transaction_dict:
            return Transaction.from_dict(transaction_dict)
        return None

    def save_transaction(self, transaction: Transaction) -> str:
        """
        Save a new transaction to the database.

        Args:
            transaction (Transaction): The transaction to save

        Returns:
            str: The unique ID assigned to this transaction
        """
        return self.database.save_transaction(transaction.to_dict())

    def update_transaction(self, transaction_id: str, user_email: str, transaction: Transaction) -> bool:
        """
        Update an existing transaction in place, if owned by user_email.

        Args:
            transaction_id (str): Transaction ID
            user_email (str): Email of the transaction's expected owner
            transaction (Transaction): The transaction with updated field values

        Returns:
            bool: True if updated, False if not found or not owned by user_email
        """
        return self.database.update_transaction(transaction_id, user_email, transaction.to_dict())
