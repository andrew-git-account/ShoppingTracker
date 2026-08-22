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

# One-time backfill target for receipts saved before SP-005 introduced
# per-user ownership. Not a general-purpose default - see JSONDatabase.initialize().
_LEGACY_OWNER_EMAIL = "andrew.bihun@gmail.com"

_SEED_CATEGORIES = [
    {"id": 1, "name": "Other"},
    {"id": 2, "name": "Food & Groceries"},
    {"id": 3, "name": "Household & Cleaning"},
    {"id": 4, "name": "Personal Care & Health"},
    {"id": 5, "name": "Electronics & Tech"},
    {"id": 6, "name": "Clothing & Apparel"},
    {"id": 7, "name": "Dining & Takeout"},
]


class CategoryDatabase:
    """Manages the categories vocabulary stored in categories.json."""

    DEFAULT_CATEGORY = "Other"

    def __init__(self, file_path: str):
        self.file_path = file_path

    def initialize(self) -> None:
        """Create categories.json with seed data if it doesn't exist."""
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(_SEED_CATEGORIES, f, indent=2, ensure_ascii=False)
            print(f"Initialized categories file: {self.file_path}")

    def get_all_categories(self) -> List[Dict]:
        """Return all categories from the JSON file."""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            return json.load(f)


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
            return

        # One-time migration (SP-005): backfill receipts saved before per-user
        # ownership existed. Idempotent - only writes if something is missing.
        receipts = self._read_all_receipts()
        migrated = False
        for receipt in receipts:
            if not receipt.get('user_email'):
                receipt['user_email'] = _LEGACY_OWNER_EMAIL
                migrated = True
        if migrated:
            self._write_all_receipts(receipts)
            print(f"Backfilled user_email on legacy receipts in: {self.file_path}")

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

    def get_all_receipts(self, user_email: str) -> List[Dict]:
        """
        Retrieve all receipts owned by user_email from the JSON file.

        Returns receipts in reverse chronological order (newest first).

        Args:
            user_email (str): Email of the receipts' owner

        Returns:
            List[Dict]: List of matching receipts

        Raises:
            Exception: If file read fails
        """
        receipts = self._read_all_receipts()
        # Return newest first, excluding soft-deleted and other users' entries
        return list(reversed([
            r for r in receipts
            if not r.get('is_deleted', False) and r.get('user_email') == user_email
        ]))

    def get_receipt_by_id(self, receipt_id: str, user_email: str) -> Optional[Dict]:
        """
        Find and return a specific receipt by its ID, if owned by user_email.

        Args:
            receipt_id (str): The receipt ID to search for
            user_email (str): Email of the receipt's expected owner

        Returns:
            Optional[Dict]: Receipt data if found and owned by user_email, None otherwise
        """
        receipts = self._read_all_receipts()

        for receipt in receipts:
            if receipt.get('id') == receipt_id and receipt.get('user_email') == user_email:
                return receipt

        # Not found (or not owned by this user)
        return None

    def update_receipt(self, receipt_id: str, user_email: str, receipt_data: Dict) -> bool:
        """
        Update an existing receipt's fields in place, if owned by user_email.

        Args:
            receipt_id (str): The receipt ID to update
            user_email (str): Email of the receipt's expected owner
            receipt_data (Dict): New field values to apply

        Returns:
            bool: True if the receipt was found, owned by user_email, and updated;
                  False otherwise (not found and not-owned are indistinguishable
                  on purpose, same as soft_delete_receipt)
        """
        receipts = self._read_all_receipts()

        for receipt in receipts:
            if receipt.get('id') == receipt_id and receipt.get('user_email') == user_email:
                # Preserve identity/ownership/lifecycle fields even if receipt_data
                # happened to include them - only the caller's other fields should change.
                preserved_id = receipt.get('id')
                preserved_saved_at = receipt.get('saved_at')
                preserved_user_email = receipt.get('user_email')
                preserved_is_deleted = receipt.get('is_deleted', False)

                receipt.update(receipt_data)

                receipt['id'] = preserved_id
                receipt['saved_at'] = preserved_saved_at
                receipt['user_email'] = preserved_user_email
                receipt['is_deleted'] = preserved_is_deleted

                self._write_all_receipts(receipts)
                print(f"Updated receipt with ID: {receipt_id}")
                return True

        print(f"Receipt not found: {receipt_id}")
        return False

    def soft_delete_receipt(self, receipt_id: str, user_email: str) -> bool:
        """
        Soft-delete a receipt by marking it as deleted, if owned by user_email.

        The receipt remains in the JSON file but is excluded from
        get_all_receipts() results.

        Args:
            receipt_id (str): The receipt ID to soft-delete
            user_email (str): Email of the receipt's expected owner

        Returns:
            bool: True if receipt was found, owned by user_email, and marked;
                  False otherwise (not found and not-owned are indistinguishable
                  on purpose, so a user can't probe which IDs exist)
        """
        receipts = self._read_all_receipts()

        for receipt in receipts:
            if receipt.get('id') == receipt_id and receipt.get('user_email') == user_email:
                receipt['is_deleted'] = True
                self._write_all_receipts(receipts)
                print(f"Soft-deleted receipt with ID: {receipt_id}")
                return True

        print(f"Receipt not found: {receipt_id}")
        return False

    def delete_receipt(self, receipt_id: str, user_email: str) -> bool:
        """
        Delete a receipt from the JSON file, if owned by user_email.

        Args:
            receipt_id (str): The receipt ID to delete
            user_email (str): Email of the receipt's expected owner

        Returns:
            bool: True if receipt was owned by user_email and deleted, False otherwise
        """
        receipts = self._read_all_receipts()

        # Find and remove the receipt
        # We use enumerate to get both index and receipt
        for index, receipt in enumerate(receipts):
            if receipt.get('id') == receipt_id and receipt.get('user_email') == user_email:
                # Found it! Remove from list
                receipts.pop(index)
                # Write updated list back to file
                self._write_all_receipts(receipts)
                print(f"Deleted receipt with ID: {receipt_id}")
                return True

        # Not found
        print(f"Receipt not found: {receipt_id}")
        return False

    def get_receipts_count(self, user_email: str) -> int:
        """
        Get the total number of receipts owned by user_email.

        Excludes soft-deleted receipts, matching get_all_receipts().

        Args:
            user_email (str): Email of the receipts' owner

        Returns:
            int: Number of matching receipts in database
        """
        receipts = self._read_all_receipts()
        return len([
            r for r in receipts
            if not r.get('is_deleted', False) and r.get('user_email') == user_email
        ])

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
