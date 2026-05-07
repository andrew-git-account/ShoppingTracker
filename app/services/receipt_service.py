"""
Receipt Service - Business Logic Layer.

This service coordinates the entire receipt processing workflow.
It acts as the "orchestrator" that brings together:
- File handling (uploads)
- LLM service (data extraction)
- Database (storage)
- Models (data validation)

Think of this as the "brain" of the application that knows the steps
to process a receipt from start to finish.

Why separate this from routes:
- Routes should be thin (just handle HTTP stuff)
- Business logic should be independent of web framework
- Can test this without running Flask
- Can reuse this logic in different contexts (CLI, API, etc.)
"""

import os
from typing import List, Dict, Optional
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

from ..models import Receipt, ReceiptItem
from ..database.base import Database
from .llm_service import LLMService


class ReceiptService:
    """
    Service for processing receipts.

    This class orchestrates the entire receipt processing workflow:
    1. Validate uploaded file
    2. Save temporarily
    3. Extract data using LLM
    4. Validate extracted data
    5. Save to database
    6. Clean up temporary files
    """

    def __init__(
        self,
        database: Database,
        llm_service: LLMService,
        upload_folder: str,
        allowed_extensions: set
    ):
        """
        Initialize the receipt service.

        Args:
            database (Database): Database instance for storing receipts
            llm_service (LLMService): LLM service for data extraction
            upload_folder (str): Path to temporary upload folder
            allowed_extensions (set): Set of allowed file extensions (e.g., {'jpg', 'png'})

        Note: We use dependency injection here - the service receives
              its dependencies (database, llm_service) from outside.
              This makes testing easier and code more flexible.
        """
        self.database = database
        self.llm_service = llm_service
        self.upload_folder = upload_folder
        self.allowed_extensions = allowed_extensions

        # Ensure upload folder exists
        os.makedirs(upload_folder, exist_ok=True)

    def process_receipt(self, file: FileStorage) -> Receipt:
        """
        Process an uploaded receipt image end-to-end.

        This is the main method that coordinates everything:
        1. Validate file
        2. Save temporarily
        3. Extract data with LLM
        4. Create Receipt object
        5. Validate data
        6. Save to database
        7. Clean up temp file

        Args:
            file (FileStorage): Uploaded file from Flask request

        Returns:
            Receipt: The processed receipt with extracted data

        Raises:
            ValueError: If file is invalid or data extraction fails
            Exception: If any step in the process fails
        """
        print(f"Starting receipt processing for file: {file.filename}")

        # Step 1: Validate the file
        if not self._is_allowed_file(file.filename):
            raise ValueError(
                f"Invalid file type. Allowed types: {', '.join(self.allowed_extensions)}"
            )

        # Step 2: Save file temporarily
        temp_path = self._save_temp_file(file)
        print(f"Saved temporary file: {temp_path}")

        try:
            # Step 3: Extract data using LLM
            llm_data = self.llm_service.extract_receipt_data(temp_path)

            # Step 4: Convert LLM data to Receipt object
            receipt = Receipt.from_llm_response(llm_data)

            # Step 5: Validate the receipt data
            is_valid, error_message = receipt.validate()
            if not is_valid:
                raise ValueError(f"Invalid receipt data: {error_message}")

            # Step 6: Save to database
            receipt_dict = receipt.to_dict()
            receipt_id = self.database.save_receipt(receipt_dict)

            # Update the receipt object with the assigned ID
            receipt.receipt_id = receipt_id

            print(f"Successfully processed receipt: {receipt_id}")
            return receipt

        finally:
            # Step 7: Always clean up temp file (even if error occurs)
            # The 'finally' block ensures this runs no matter what
            self._delete_temp_file(temp_path)
            print(f"Deleted temporary file: {temp_path}")

    def get_all_receipts(self) -> List[Receipt]:
        """
        Retrieve all receipts from database.

        Returns:
            List[Receipt]: List of all receipts

        Note: Converts database dictionaries to Receipt objects
        """
        receipt_dicts = self.database.get_all_receipts()
        return [Receipt.from_dict(data) for data in receipt_dicts]

    def get_receipt_by_id(self, receipt_id: str) -> Optional[Receipt]:
        """
        Retrieve a specific receipt by ID.

        Args:
            receipt_id (str): Receipt ID

        Returns:
            Optional[Receipt]: Receipt if found, None otherwise
        """
        receipt_dict = self.database.get_receipt_by_id(receipt_id)
        if receipt_dict:
            return Receipt.from_dict(receipt_dict)
        return None

    def delete_receipt(self, receipt_id: str) -> bool:
        """
        Delete a receipt from database.

        Args:
            receipt_id (str): Receipt ID

        Returns:
            bool: True if deleted, False if not found
        """
        return self.database.delete_receipt(receipt_id)

    def get_receipts_count(self) -> int:
        """
        Get total number of receipts.

        Returns:
            int: Number of receipts in database
        """
        return self.database.get_receipts_count()

    # Private helper methods

    def _is_allowed_file(self, filename: str) -> bool:
        """
        Check if a filename has an allowed extension.

        Args:
            filename (str): Name of the file

        Returns:
            bool: True if extension is allowed, False otherwise

        Example:
            'receipt.jpg' -> True (if 'jpg' in allowed_extensions)
            'receipt.pdf' -> False (if 'pdf' not in allowed_extensions)
        """
        # Check if filename has an extension
        if '.' not in filename:
            return False

        # Get the extension (part after the last dot)
        extension = filename.rsplit('.', 1)[1].lower()

        return extension in self.allowed_extensions

    def _save_temp_file(self, file: FileStorage) -> str:
        """
        Save uploaded file to temporary location.

        Args:
            file (FileStorage): Uploaded file

        Returns:
            str: Path to saved file

        Note: Uses secure_filename to prevent directory traversal attacks
              (e.g., someone uploading "../../etc/passwd" as filename)
        """
        # secure_filename removes dangerous characters from filename
        filename = secure_filename(file.filename)

        # Create unique filename to avoid conflicts
        # Format: timestamp_originalname.ext
        import time
        timestamp = int(time.time())
        unique_filename = f"{timestamp}_{filename}"

        # Build full path
        filepath = os.path.join(self.upload_folder, unique_filename)

        # Save the file
        file.save(filepath)

        return filepath

    def _delete_temp_file(self, filepath: str) -> None:
        """
        Delete a temporary file.

        Args:
            filepath (str): Path to file to delete

        Note: Silently ignores if file doesn't exist (maybe already deleted)
        """
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            # Log error but don't raise - file cleanup shouldn't break the app
            print(f"Warning: Failed to delete temp file {filepath}: {e}")