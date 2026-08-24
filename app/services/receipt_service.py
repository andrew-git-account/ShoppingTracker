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

import io
import json
import os
import uuid
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from PIL import Image

from ..models import Receipt, ReceiptItem
from ..database.base import Database
from .llm_service import LLMService

if TYPE_CHECKING:
    from .transaction_matcher import TransactionMatcher

# Claude API enforces a 5 MB limit on the base64-encoded image string.
# Base64 inflates raw bytes by 4/3, so the raw file must stay under 5MB * 3/4 = 3.75MB.
# Use 3.5 MB to leave a safe margin.
_MAX_IMAGE_BYTES = 3_500_000


def _compress_to_limit(filepath: str) -> None:
    """Rewrite filepath in-place as a JPEG small enough for the Claude API."""
    size = os.path.getsize(filepath)
    if size <= _MAX_IMAGE_BYTES:
        return

    img = Image.open(filepath).convert('RGB')
    for quality in (85, 70, 55, 40):
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=quality, optimize=True)
        data = buf.getvalue()
        if len(data) <= _MAX_IMAGE_BYTES:
            with open(filepath, 'wb') as f:
                f.write(data)
            return

    # Last resort: halve the resolution
    w, h = img.size
    img = img.resize((w // 2, h // 2), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=40, optimize=True)
    with open(filepath, 'wb') as f:
        f.write(buf.getvalue())


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
        allowed_extensions: set,
        valid_categories: List[str] = None,
        matcher: Optional['TransactionMatcher'] = None
    ):
        """
        Initialize the receipt service.

        Args:
            database (Database): Database instance for storing receipts
            llm_service (LLMService): LLM service for data extraction
            upload_folder (str): Path to temporary upload folder
            allowed_extensions (set): Set of allowed file extensions (e.g., {'jpg', 'png'})
            matcher (TransactionMatcher, optional): Auto-links a newly saved or
                edited receipt to a matching statement transaction (see SP-026).
                Assigned after construction in main.py, since it in turn depends
                on this service - defaults to None (skipped) so tests that build
                a ReceiptService directly don't need one.

        Note: We use dependency injection here - the service receives
              its dependencies (database, llm_service) from outside.
              This makes testing easier and code more flexible.
        """
        self.database = database
        self.llm_service = llm_service
        self.upload_folder = upload_folder
        self.allowed_extensions = allowed_extensions
        self.valid_categories = valid_categories or []
        self.matcher = matcher

        # Ensure upload folder exists
        os.makedirs(upload_folder, exist_ok=True)

    def process_receipt(
        self,
        file: FileStorage,
        user_email: str,
        edit_before_save: bool = False
    ) -> Tuple[Optional[Receipt], Optional[str], Optional[str]]:
        """
        Process an uploaded receipt image end-to-end.

        This is the main method that coordinates everything:
        1. Validate file
        2. Save temporarily
        3. Extract data with LLM
        4. Create Receipt object
        5. Decide whether it needs review before saving, and either write a
           draft (see SP-023/SP-024) or save it immediately
        6. Clean up temp file

        Args:
            file (FileStorage): Uploaded file from Flask request
            user_email (str): Email of the logged-in user uploading this receipt (see SP-005)
            edit_before_save (bool): If True, always route to review instead of
                saving immediately, even if the data is otherwise fine (see SP-023)

        Returns:
            Tuple[Optional[Receipt], Optional[str], Optional[str]]:
                (receipt, draft_id, review_reason). Exactly one of
                receipt/draft_id is populated:
                - (receipt, None, None) - saved immediately, as today.
                - (None, draft_id, review_reason) - written as a draft for
                  review instead. review_reason is one of:
                  'invalid' (failed Receipt.validate()), 'unreconciled' (SP-018's
                  retry still didn't reconcile), or 'checkbox' (the user asked
                  to review it, per SP-023) - see SP-024. Checked in that
                  priority order when more than one applies, since an actual
                  data problem is more important to surface than the neutral
                  "review before saving" preference.

        Raises:
            ValueError: If the file itself is invalid (bad extension, etc.)
            Exception: If any step in the process fails
        """
        print(f"Starting receipt processing for file: {file.filename}")

        # Step 1: Validate the file
        if not self._is_allowed_file(file.filename):
            raise ValueError(
                f"Invalid file type. Allowed types: {', '.join(self.allowed_extensions)}"
            )

        # Step 2: Save file temporarily, then compress if over the API size limit
        temp_path = self._save_temp_file(file)
        print(f"Saved temporary file: {temp_path}")
        _compress_to_limit(temp_path)

        try:
            # Step 3: Extract data using LLM
            llm_data, reconciled = self.llm_service.extract_receipt_data(temp_path, user_email)

            # Step 4: Convert LLM data to Receipt object
            receipt = Receipt.from_llm_response(llm_data, valid_categories=self.valid_categories)
            receipt.user_email = user_email

            # Step 5: Decide whether this needs review before saving (see SP-024)
            is_valid, error_message = receipt.validate()

            if not is_valid:
                review_reason = 'invalid'
            elif not reconciled:
                review_reason = 'unreconciled'
            elif edit_before_save:
                review_reason = 'checkbox'
            else:
                review_reason = None

            if review_reason:
                draft_id = self._save_draft(receipt)
                print(f"Saved receipt as draft (reason={review_reason}): {draft_id}")
                return None, draft_id, review_reason

            # Save to database
            receipt_dict = receipt.to_dict()
            receipt_id = self.database.save_receipt(receipt_dict)

            # Update the receipt object with the assigned ID
            receipt.receipt_id = receipt_id

            if self.matcher:
                self.matcher.match_receipt(receipt)

            print(f"Successfully processed receipt: {receipt_id}")
            return receipt, None, None

        finally:
            # Step 6: Always clean up temp file (even if error occurs)
            # The 'finally' block ensures this runs no matter what
            self._delete_temp_file(temp_path)
            print(f"Deleted temporary file: {temp_path}")

    def get_all_receipts(self, user_email: str) -> List[Receipt]:
        """
        Retrieve all receipts owned by user_email from database.

        Args:
            user_email (str): Email of the receipts' owner

        Returns:
            List[Receipt]: List of matching receipts

        Note: Converts database dictionaries to Receipt objects
        """
        receipt_dicts = self.database.get_all_receipts(user_email)
        return [Receipt.from_dict(data) for data in receipt_dicts]

    def get_receipt_by_id(self, receipt_id: str, user_email: str) -> Optional[Receipt]:
        """
        Retrieve a specific receipt by ID, if owned by user_email.

        Args:
            receipt_id (str): Receipt ID
            user_email (str): Email of the receipt's expected owner

        Returns:
            Optional[Receipt]: Receipt if found and owned by user_email, None otherwise
        """
        receipt_dict = self.database.get_receipt_by_id(receipt_id, user_email)
        if receipt_dict:
            return Receipt.from_dict(receipt_dict)
        return None

    def update_receipt(self, receipt_id: str, user_email: str, receipt: Receipt) -> bool:
        """
        Update an existing receipt in place, if owned by user_email.

        Args:
            receipt_id (str): Receipt ID
            user_email (str): Email of the receipt's expected owner
            receipt (Receipt): The receipt with updated field values

        Returns:
            bool: True if updated, False if not found or not owned by user_email
        """
        updated = self.database.update_receipt(receipt_id, user_email, receipt.to_dict())
        if updated and self.matcher:
            self.matcher.match_receipt(receipt)
        return updated

    def get_draft(self, draft_id: str, user_email: str) -> Optional[Receipt]:
        """
        Retrieve a not-yet-saved draft receipt, if owned by user_email. See SP-023.

        Args:
            draft_id (str): Draft ID
            user_email (str): Email of the draft's expected owner

        Returns:
            Optional[Receipt]: Draft as a Receipt (receipt_id/saved_at are None)
                if found and owned by user_email, None otherwise
        """
        draft_data = self._load_draft(draft_id)
        if not draft_data or draft_data.get('user_email') != user_email:
            return None
        return Receipt.from_dict(draft_data)

    def save_draft(self, draft_id: str, user_email: str, receipt: Receipt) -> Optional[Receipt]:
        """
        Save a draft as a new receipt for the first time, if owned by user_email,
        then delete the draft file. See SP-023.

        Args:
            draft_id (str): Draft ID
            user_email (str): Email of the draft's expected owner
            receipt (Receipt): The (possibly edited) receipt to save

        Returns:
            Optional[Receipt]: The saved receipt (with its new ID assigned) if
                the draft was found and owned by user_email, None otherwise
        """
        draft_data = self._load_draft(draft_id)
        if not draft_data or draft_data.get('user_email') != user_email:
            return None

        receipt.user_email = user_email
        receipt_id = self.database.save_receipt(receipt.to_dict())
        receipt.receipt_id = receipt_id

        if self.matcher:
            self.matcher.match_receipt(receipt)

        self._delete_draft(draft_id)
        print(f"Saved draft {draft_id} as receipt: {receipt_id}")
        return receipt

    def discard_draft(self, draft_id: str, user_email: str) -> bool:
        """
        Discard a draft without ever saving it, if owned by user_email. See SP-023.

        Args:
            draft_id (str): Draft ID
            user_email (str): Email of the draft's expected owner

        Returns:
            bool: True if the draft was found, owned by user_email, and discarded;
                  False otherwise
        """
        draft_data = self._load_draft(draft_id)
        if not draft_data or draft_data.get('user_email') != user_email:
            return False

        self._delete_draft(draft_id)
        print(f"Discarded draft: {draft_id}")
        return True

    def soft_delete_receipt(self, receipt_id: str, user_email: str) -> bool:
        """
        Soft-delete a receipt (marks as deleted, keeps in DB), if owned by user_email.

        Args:
            receipt_id (str): Receipt ID
            user_email (str): Email of the receipt's expected owner

        Returns:
            bool: True if deleted, False if not found or not owned by user_email
        """
        return self.database.soft_delete_receipt(receipt_id, user_email)

    def delete_receipt(self, receipt_id: str, user_email: str) -> bool:
        """
        Delete a receipt from database, if owned by user_email.

        Args:
            receipt_id (str): Receipt ID
            user_email (str): Email of the receipt's expected owner

        Returns:
            bool: True if deleted, False if not found or not owned by user_email
        """
        return self.database.delete_receipt(receipt_id, user_email)

    def get_receipts_count(self, user_email: str) -> int:
        """
        Get total number of receipts owned by user_email.

        Args:
            user_email (str): Email of the receipts' owner

        Returns:
            int: Number of matching receipts in database
        """
        return self.database.get_receipts_count(user_email)

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

    def _draft_path(self, draft_id: str) -> str:
        """Path to a draft's JSON file. draft_id must already be a validated UUID."""
        return os.path.join(self.upload_folder, f"draft_{draft_id}.json")

    def _save_draft(self, receipt: Receipt) -> str:
        """
        Write a receipt's data to a new draft file. See SP-023.

        Args:
            receipt (Receipt): The not-yet-saved receipt (user_email must already be set)

        Returns:
            str: The generated draft ID
        """
        draft_id = str(uuid.uuid4())
        with open(self._draft_path(draft_id), 'w', encoding='utf-8') as f:
            json.dump(receipt.to_dict(), f, ensure_ascii=False)
        return draft_id

    def _load_draft(self, draft_id: str) -> Optional[Dict]:
        """
        Read a draft's data from its file.

        Validates draft_id is a well-formed UUID before building a filesystem
        path from it, so a malformed/malicious ID from the URL can never escape
        upload_folder.

        Args:
            draft_id (str): Draft ID

        Returns:
            Optional[Dict]: The draft's data, or None if draft_id is invalid,
                the file doesn't exist, or it can't be read
        """
        try:
            uuid.UUID(draft_id)
        except (ValueError, TypeError, AttributeError):
            return None

        draft_path = self._draft_path(draft_id)
        try:
            with open(draft_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _delete_draft(self, draft_id: str) -> None:
        """
        Delete a draft file.

        Args:
            draft_id (str): Draft ID

        Note: Silently ignores if the file doesn't exist (maybe already deleted)
        """
        try:
            draft_path = self._draft_path(draft_id)
            if os.path.exists(draft_path):
                os.remove(draft_path)
        except Exception as e:
            # Log error but don't raise - file cleanup shouldn't break the app
            print(f"Warning: Failed to delete draft file for {draft_id}: {e}")