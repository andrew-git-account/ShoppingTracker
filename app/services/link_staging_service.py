"""
Link Staging Service - holds a pending multi-receipt selection for manually
linking several receipts to one transaction in a single action (see SP-038).

File-backed like ReceiptService's draft mechanism (SP-023, see
ReceiptService._save_draft/_load_draft/_delete_draft), but keyed by
transaction_id rather than a generated id - only one in-progress multi-link
per transaction makes sense at a time, so re-visiting the link page for the
same transaction resumes the same pending selection instead of starting a
new one.
"""

import json
import os
import uuid
from typing import List, Optional


class LinkStagingService:
    """Tracks receipt ids staged for a transaction's manual link, before Add commits them."""

    def __init__(self, upload_folder: str):
        """
        Initialize the link staging service.

        Args:
            upload_folder (str): Folder to store pending-link JSON files in
                (shared with ReceiptService's upload/draft storage)
        """
        self.upload_folder = upload_folder
        os.makedirs(upload_folder, exist_ok=True)

    def _pending_link_path(self, transaction_id: str) -> Optional[str]:
        """
        Path to a transaction's pending-link file.

        Validates transaction_id is a well-formed UUID before building a
        filesystem path from it, so a malformed/malicious id from the URL
        can never escape upload_folder.

        Returns:
            Optional[str]: The file path, or None if transaction_id is malformed
        """
        try:
            uuid.UUID(transaction_id)
        except (ValueError, TypeError, AttributeError):
            return None
        return os.path.join(self.upload_folder, f"pending_link_{transaction_id}.json")

    def get_staged_receipt_ids(self, transaction_id: str) -> List[str]:
        """
        Get the receipt ids currently staged for this transaction, in the
        order they were staged.

        Args:
            transaction_id (str): Transaction ID

        Returns:
            List[str]: Staged receipt ids, or [] if none are staged
        """
        path = self._pending_link_path(transaction_id)
        if path is None:
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f).get('receipt_ids', [])
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def stage_receipt(self, transaction_id: str, receipt_id: str) -> None:
        """Add a receipt to the pending selection, if not already staged."""
        receipt_ids = self.get_staged_receipt_ids(transaction_id)
        if receipt_id not in receipt_ids:
            receipt_ids.append(receipt_id)
            self._save(transaction_id, receipt_ids)

    def unstage_receipt(self, transaction_id: str, receipt_id: str) -> None:
        """Remove a receipt from the pending selection, leaving the rest staged."""
        receipt_ids = [r for r in self.get_staged_receipt_ids(transaction_id) if r != receipt_id]
        self._save(transaction_id, receipt_ids)

    def clear_staged(self, transaction_id: str) -> None:
        """Discard the entire pending selection for this transaction."""
        path = self._pending_link_path(transaction_id)
        if path is None:
            return
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            # Log error but don't raise - file cleanup shouldn't break the app
            print(f"Warning: Failed to delete pending link file for {transaction_id}: {e}")

    def _save(self, transaction_id: str, receipt_ids: List[str]) -> None:
        path = self._pending_link_path(transaction_id)
        if path is None:
            return
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'receipt_ids': receipt_ids}, f, ensure_ascii=False)
