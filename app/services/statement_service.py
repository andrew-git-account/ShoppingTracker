"""
Statement Service - Business Logic Layer for bank/card statement uploads.

Mirrors ReceiptService's upload-orchestration shape (see SP-025), but for a
PDF statement that extracts to a *list* of Transaction records instead of one
itemized Receipt. Owns its own small file-upload helpers rather than sharing
ReceiptService's, matching this project's existing style of each upload-
handling service being self-contained.
"""

import os
import time
import uuid
from typing import List
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

from ..models import Transaction
from .llm_service import LLMService
from .transaction_service import TransactionService

_VALID_DIRECTIONS = {'debit', 'credit'}


class StatementService:
    """
    Service for processing bank/card statement uploads.

    Orchestrates: validate uploaded PDF, save temporarily, extract transactions
    via LLM, save each as its own Transaction, clean up the temp file.
    """

    def __init__(
        self,
        transaction_service: TransactionService,
        llm_service: LLMService,
        upload_folder: str,
        allowed_extensions: set,
        valid_categories: List[str] = None
    ):
        """
        Initialize the statement service.

        Args:
            transaction_service (TransactionService): Service for storing transactions
            llm_service (LLMService): LLM service for statement extraction
            upload_folder (str): Path to temporary upload folder
            allowed_extensions (set): Set of allowed file extensions (e.g., {'pdf'})
            valid_categories (List[str]): Categories to classify transactions
                into - same vocabulary receipt items use (see SP-025)
        """
        self.transaction_service = transaction_service
        self.llm_service = llm_service
        self.upload_folder = upload_folder
        self.allowed_extensions = allowed_extensions
        self.valid_categories = valid_categories or []

        os.makedirs(upload_folder, exist_ok=True)

    def process_statement(self, file: FileStorage, user_email: str, source: str) -> List[Transaction]:
        """
        Process an uploaded statement PDF end-to-end.

        Args:
            file (FileStorage): Uploaded file from Flask request
            user_email (str): Email of the logged-in user uploading this statement
            source (str): Statement type - 'bank' or 'card'

        Returns:
            List[Transaction]: The extracted and saved transactions

        Raises:
            ValueError: If the file isn't a PDF, or no text could be extracted from it
            Exception: If any step in the process fails
        """
        print(f"Starting statement processing for file: {file.filename}")

        if not self._is_allowed_file(file.filename):
            raise ValueError(
                f"Invalid file type. Allowed types: {', '.join(self.allowed_extensions)}"
            )

        temp_path = self._save_temp_file(file)
        print(f"Saved temporary file: {temp_path}")

        try:
            extracted = self.llm_service.extract_statement_transactions(temp_path, user_email)

            # Every transaction from this one upload shares a statement_id,
            # so History (SP-029) can group them into a single expandable
            # card - the same relationship a receipt has to its items.
            statement_id = str(uuid.uuid4())

            transactions = []
            for item in extracted:
                raw_direction = item.get('direction')
                raw_category = item.get('category', 'Other')
                transaction = Transaction(
                    date=item.get('date'),
                    description=item.get('description', ''),
                    amount=float(item.get('amount') or 0.0),
                    currency=item.get('currency', 'USD'),
                    direction=raw_direction if raw_direction in _VALID_DIRECTIONS else 'debit',
                    category=raw_category if raw_category in self.valid_categories else 'Other',
                    source=source,
                    statement_id=statement_id,
                    user_email=user_email
                )
                transaction_id = self.transaction_service.save_transaction(transaction)
                transaction.transaction_id = transaction_id
                transactions.append(transaction)

            print(f"Successfully processed statement: {len(transactions)} transactions")
            return transactions

        finally:
            self._delete_temp_file(temp_path)
            print(f"Deleted temporary file: {temp_path}")

    # Private helper methods

    def _is_allowed_file(self, filename: str) -> bool:
        """
        Check if a filename has an allowed extension.

        Args:
            filename (str): Name of the file

        Returns:
            bool: True if extension is allowed, False otherwise
        """
        if '.' not in filename:
            return False
        extension = filename.rsplit('.', 1)[1].lower()
        return extension in self.allowed_extensions

    def _save_temp_file(self, file: FileStorage) -> str:
        """
        Save uploaded file to temporary location.

        Args:
            file (FileStorage): Uploaded file

        Returns:
            str: Path to saved file
        """
        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        unique_filename = f"{timestamp}_{filename}"
        filepath = os.path.join(self.upload_folder, unique_filename)
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
            print(f"Warning: Failed to delete temp file {filepath}: {e}")
