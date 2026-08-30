"""
Feedback Service - business logic for user-submitted feedback to admins
(see SP-039).

Coordinates: validating the submission, saving an optional image, saving the
feedback record, and emailing every active admin.
"""

import os
import time
from typing import List, Optional, Tuple

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .email_service import EmailService, EmailDeliveryError
from .auth_service import AuthService
from ..database.sqlite_feedback_db import SqliteFeedbackDatabase

MESSAGE_TYPES = ['Bug Report', 'Enhancement Proposal', 'General Feedback']
FUNCTIONALITIES = ['Upload', 'Upload Statement', 'History', 'Statistics', 'LLM Usage', 'Users', 'All', 'None']

_DEFAULT_MESSAGE_TYPE = 'Bug Report'
_DEFAULT_FUNCTIONALITY = 'None'


class FeedbackService:
    """Handles validation, storage, and admin notification for user feedback."""

    def __init__(
        self,
        database: SqliteFeedbackDatabase,
        email_service: EmailService,
        auth_service: AuthService,
        upload_folder: str,
        allowed_extensions: set,
    ):
        """
        Initialize the feedback service.

        Args:
            database (SqliteFeedbackDatabase): Storage for feedback records
            email_service (EmailService): Sender for the admin notification email
            auth_service (AuthService): Source of the active-admin recipient list
            upload_folder (str): Folder to save feedback images into
            allowed_extensions (set): Allowed image file extensions
        """
        self.database = database
        self.email_service = email_service
        self.auth_service = auth_service
        self.upload_folder = upload_folder
        self.allowed_extensions = allowed_extensions
        # Don't rely on ReceiptService (which shares this same folder)
        # happening to have created it first - matches ReceiptService's own
        # defensive os.makedirs in its constructor.
        os.makedirs(upload_folder, exist_ok=True)

    def submit_feedback(
        self,
        user_email: str,
        message_type: str,
        functionality: str,
        message: str,
        image_file: Optional[FileStorage],
    ) -> Tuple[str, bool]:
        """
        Validate, save, and email a feedback submission.

        Args:
            user_email (str): Email of the submitting user
            message_type (str): One of MESSAGE_TYPES; falls back to the
                default if not a recognized value (e.g. a hand-crafted request)
            functionality (str): One of FUNCTIONALITIES; falls back to the
                default if not a recognized value
            message (str): The feedback text - required
            image_file (FileStorage, optional): An optional image attachment

        Returns:
            Tuple[str, bool]: (feedback_id, email_sent) - email_sent is False
                if the admin notification failed to send, but the feedback
                is saved either way.

        Raises:
            ValueError: If message is empty, or image_file has a disallowed
                extension.
        """
        message = message.strip()
        if not message:
            raise ValueError('Please enter a message.')

        if message_type not in MESSAGE_TYPES:
            message_type = _DEFAULT_MESSAGE_TYPE
        if functionality not in FUNCTIONALITIES:
            functionality = _DEFAULT_FUNCTIONALITY

        image_filename = None
        image_bytes = None
        if image_file and image_file.filename:
            if not self._is_allowed_file(image_file.filename):
                raise ValueError('Invalid file type. Allowed: ' + ', '.join(sorted(self.allowed_extensions)))
            image_filename = self._save_image_file(image_file)
            with open(os.path.join(self.upload_folder, image_filename), 'rb') as f:
                image_bytes = f.read()

        feedback_id = self.database.save_feedback({
            'user_email': user_email,
            'message_type': message_type,
            'functionality': functionality,
            'message': message,
            'image_filename': image_filename,
        })

        email_sent = self._notify_admins(
            user_email, message_type, functionality, message,
            attachment=(image_bytes, image_filename) if image_bytes else None
        )

        return feedback_id, email_sent

    def _notify_admins(
        self, user_email: str, message_type: str, functionality: str, message: str,
        attachment: Optional[Tuple[bytes, str]]
    ) -> bool:
        """Email every active admin the feedback details. Returns False (not raised) on failure."""
        admin_emails = self._active_admin_emails()
        if not admin_emails:
            return False

        subject = f"[ShoppingTracker Feedback] {message_type} — {functionality}"
        body = (
            f"From: {user_email}\n"
            f"Type: {message_type}\n"
            f"Functionality: {functionality}\n\n"
            f"{message}"
        )

        try:
            self.email_service.send(admin_emails, subject, body, attachment=attachment)
            return True
        except EmailDeliveryError:
            return False

    def _active_admin_emails(self) -> List[str]:
        """Emails of users who are admin and not blocked (see AuthService._count_active_admins)."""
        return [u['email'] for u in self.auth_service.get_all_users() if u['is_admin'] and not u['is_blocked']]

    def _is_allowed_file(self, filename: str) -> bool:
        """Check if a filename has an allowed extension (mirrors ReceiptService)."""
        if '.' not in filename:
            return False
        extension = filename.rsplit('.', 1)[1].lower()
        return extension in self.allowed_extensions

    def _save_image_file(self, file: FileStorage) -> str:
        """
        Save an uploaded feedback image permanently into upload_folder.

        Unlike ReceiptService._save_temp_file (a draft awaiting LLM
        processing, sometimes cleaned up), this file is kept indefinitely as
        part of the feedback record.

        Returns:
            str: The unique filename the image was saved under
        """
        filename = secure_filename(file.filename)
        unique_filename = f"{int(time.time())}_{filename}"
        filepath = os.path.join(self.upload_folder, unique_filename)
        file.save(filepath)
        return unique_filename
