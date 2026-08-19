"""
Database abstraction layer - Base interface.

This module defines the abstract base class (interface) that all database
implementations must follow. This allows us to easily switch between different
database types (JSON files, SQLite, PostgreSQL, etc.) without changing
any other code.

Why we use abstraction:
- Easy to switch from JSON to SQL later (just change one line in config)
- Makes testing easier (can use mock database)
- Follows good software design principles (separation of concerns)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class Database(ABC):
    """
    Abstract base class for database operations.

    All database implementations (JSON, SQL, etc.) must inherit from this class
    and implement all the abstract methods below.

    ABC = Abstract Base Class (from Python's abc module)
    """

    @abstractmethod
    def save_receipt(self, receipt_data: Dict) -> str:
        """
        Save a receipt to the database.

        Args:
            receipt_data (Dict): Dictionary containing receipt information
                                 (items, prices, store name, date, etc.)

        Returns:
            str: The ID of the saved receipt

        Raises:
            Exception: If save operation fails
        """
        pass

    @abstractmethod
    def get_all_receipts(self, user_email: str) -> List[Dict]:
        """
        Retrieve all receipts owned by the given user.

        Args:
            user_email (str): Email of the receipts' owner

        Returns:
            List[Dict]: List of matching receipt dictionaries

        Raises:
            Exception: If retrieval fails
        """
        pass

    @abstractmethod
    def get_receipt_by_id(self, receipt_id: str, user_email: str) -> Optional[Dict]:
        """
        Retrieve a specific receipt by its ID, if owned by the given user.

        Args:
            receipt_id (str): The unique identifier of the receipt
            user_email (str): Email of the receipt's expected owner

        Returns:
            Optional[Dict]: Receipt data if found and owned by user_email, None otherwise

        Raises:
            Exception: If retrieval fails (not including "not found")
        """
        pass

    @abstractmethod
    def delete_receipt(self, receipt_id: str, user_email: str) -> bool:
        """
        Delete a receipt from the database, if owned by the given user.

        Args:
            receipt_id (str): The unique identifier of the receipt to delete
            user_email (str): Email of the receipt's expected owner

        Returns:
            bool: True if deleted, False if not found or not owned by user_email

        Raises:
            Exception: If delete operation fails
        """
        pass

    @abstractmethod
    def soft_delete_receipt(self, receipt_id: str, user_email: str) -> bool:
        """
        Soft-delete a receipt (mark as deleted, keep in storage), if owned by the given user.

        Args:
            receipt_id (str): The unique identifier of the receipt to soft-delete
            user_email (str): Email of the receipt's expected owner

        Returns:
            bool: True if soft-deleted, False if not found or not owned by user_email

        Raises:
            Exception: If the operation fails
        """
        pass

    @abstractmethod
    def get_receipts_count(self, user_email: str) -> int:
        """
        Get the total number of receipts owned by the given user.

        Args:
            user_email (str): Email of the receipts' owner

        Returns:
            int: Number of matching receipts

        Raises:
            Exception: If count operation fails
        """
        pass

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the database (create files, tables, etc. if needed).

        This method is called when the database is first set up.
        For JSON: create empty file if it doesn't exist
        For SQL: create tables if they don't exist

        Raises:
            Exception: If initialization fails
        """
        pass
