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
    def get_all_receipts(self) -> List[Dict]:
        """
        Retrieve all receipts from the database.

        Returns:
            List[Dict]: List of all receipt dictionaries

        Raises:
            Exception: If retrieval fails
        """
        pass

    @abstractmethod
    def get_receipt_by_id(self, receipt_id: str) -> Optional[Dict]:
        """
        Retrieve a specific receipt by its ID.

        Args:
            receipt_id (str): The unique identifier of the receipt

        Returns:
            Optional[Dict]: Receipt data if found, None if not found

        Raises:
            Exception: If retrieval fails (not including "not found")
        """
        pass

    @abstractmethod
    def delete_receipt(self, receipt_id: str) -> bool:
        """
        Delete a receipt from the database.

        Args:
            receipt_id (str): The unique identifier of the receipt to delete

        Returns:
            bool: True if deleted, False if receipt not found

        Raises:
            Exception: If delete operation fails
        """
        pass

    @abstractmethod
    def get_receipts_count(self) -> int:
        """
        Get the total number of receipts in the database.

        Returns:
            int: Number of receipts

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
