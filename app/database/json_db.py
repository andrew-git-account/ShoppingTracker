"""
JSON Database Implementation.

This module implements the Database interface using JSON files for storage.
This is perfect for V1 as it's simple, requires no setup, and is easy to debug.

How it works:
- All receipts are stored in a single JSON file (receipts.json)
- The file contains a list of receipt dictionaries
- Each receipt has a unique ID (generated using UUID)
- File is read/written for each operation (simple but works for small datasets)

For V2, we'll create a similar class (sql_db.py) that implements the same
interface but uses PostgreSQL instead. We won't need to change any other code!
"""

import json
import os
import uuid
from typing import List, Dict, Optional
from datetime import datetime

from .base import Database


class JSONDatabase(Database):
    """
    JSON file-based database implementation.

    This class stores all receipt data in a JSON file on the local filesystem.
    It implements all methods from the Database abstract class.
    """

    def __init__(self, file_path: str):
        """
        Initialize the JSON database.

        Args:
            file_path (str): Path to the JSON file (e.g., './data/receipts.json')
        """
        self.file_path = file_path
        # Initialize the database file if it doesn't exist
        self.initialize()

    def initialize(self) -> None:
        """
        Create the JSON file if it doesn't exist.

        Creates an empty list [] in the file to store receipts.
        Also creates the parent directory if needed.
        """
        # Create the directory if it doesn't exist
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created database directory: {directory}")

        # Create the file with an empty list if it doesn't exist
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump([], f)
            print(f"Initialized database file: {self.file_path}")

    def save_receipt(self, receipt_data: Dict) -> str:
        """
        Save a receipt to the JSON file.

        This method:
        1. Generates a unique ID for the receipt
        2. Adds a timestamp for when it was saved
        3. Reads existing receipts from file
        4. Appends the new receipt
        5. Writes everything back to file

        Args:
            receipt_data (Dict): Receipt information to save

        Returns:
            str: The unique ID assigned to this receipt

        Raises:
            Exception: If file operations fail
        """
        # Generate a unique ID for this receipt
        # UUID4 creates a random unique identifier like: "a1b2c3d4-e5f6-..."
        receipt_id = str(uuid.uuid4())

        # Add metadata to the receipt
        receipt_data['id'] = receipt_id
        receipt_data['saved_at'] = datetime.now().isoformat()  # ISO format: "2026-05-07T15:30:00"

        # Read existing receipts
        receipts = self._read_all_receipts()

        # Append new receipt
        receipts.append(receipt_data)

        # Write back to file
        self._write_all_receipts(receipts)

        print(f"Saved receipt with ID: {receipt_id}")
        return receipt_id

    def get_all_receipts(self) -> List[Dict]:
        """
        Retrieve all receipts from the JSON file.

        Returns receipts in reverse chronological order (newest first).

        Returns:
            List[Dict]: List of all receipts

        Raises:
            Exception: If file read fails
        """
        receipts = self._read_all_receipts()
        # Return newest first (reverse the list)
        return list(reversed(receipts))

    def get_receipt_by_id(self, receipt_id: str) -> Optional[Dict]:
        """
        Find and return a specific receipt by its ID.

        Args:
            receipt_id (str): The receipt ID to search for

        Returns:
            Optional[Dict]: Receipt data if found, None otherwise
        """
        receipts = self._read_all_receipts()

        # Search through all receipts for matching ID
        for receipt in receipts:
            if receipt.get('id') == receipt_id:
                return receipt

        # Not found
        return None

    def delete_receipt(self, receipt_id: str) -> bool:
        """
        Delete a receipt from the JSON file.

        Args:
            receipt_id (str): The receipt ID to delete

        Returns:
            bool: True if receipt was deleted, False if not found
        """
        receipts = self._read_all_receipts()

        # Find and remove the receipt
        # We use enumerate to get both index and receipt
        for index, receipt in enumerate(receipts):
            if receipt.get('id') == receipt_id:
                # Found it! Remove from list
                receipts.pop(index)
                # Write updated list back to file
                self._write_all_receipts(receipts)
                print(f"Deleted receipt with ID: {receipt_id}")
                return True

        # Not found
        print(f"Receipt not found: {receipt_id}")
        return False

    def get_receipts_count(self) -> int:
        """
        Get the total number of receipts.

        Returns:
            int: Number of receipts in database
        """
        receipts = self._read_all_receipts()
        return len(receipts)

    # Private helper methods (not part of the public interface)
    # These methods are only used internally by this class

    def _read_all_receipts(self) -> List[Dict]:
        """
        Internal method: Read all receipts from the JSON file.

        Returns:
            List[Dict]: List of receipts

        Note: The underscore prefix indicates this is a private method
              (should only be used within this class)
        """
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            # If file doesn't exist, initialize it and return empty list
            self.initialize()
            return []
        except json.JSONDecodeError as e:
            # If file is corrupted, raise an error
            raise Exception(f"JSON file is corrupted: {e}")

    def _write_all_receipts(self, receipts: List[Dict]) -> None:
        """
        Internal method: Write all receipts to the JSON file.

        Args:
            receipts (List[Dict]): List of receipts to write

        The indent=2 makes the JSON file human-readable (pretty-printed)
        """
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(receipts, f, indent=2, ensure_ascii=False)
