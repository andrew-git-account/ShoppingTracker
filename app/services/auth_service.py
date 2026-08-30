"""
Authentication service - handles OTP-based login logic.

Flow:
1. User submits email -> check against the allowed_users table (SQLite, see SP-036)
2. If allowed, generate a 5-digit OTP, store it in session with expiry
3. Send the OTP to the user's email address via SMTP
4. User submits code -> compare with session value and check expiry
"""

import random
import time
from typing import Dict, List, Optional, Tuple

from ..database.sqlite_allowed_users_db import SqliteAllowedUsersDatabase
from .email_service import EmailService, EmailDeliveryError


# OTP is valid for 10 minutes (600 seconds)
_OTP_TTL_SECONDS = 600


class AuthService:
    """
    Manages the OTP authentication flow.

    Args:
        allowed_users_path (str): Path to the SQLite database file holding the
            allowed_users table (see SP-036; shared with receipts/transactions).
        smtp_host     (str): SMTP server hostname (e.g. "smtp.gmail.com").
        smtp_port     (int): SMTP port — use 587 for STARTTLS.
        smtp_user     (str): SMTP login username (usually the sending email address).
        smtp_password (str): SMTP login password or app-password.
        smtp_from     (str): The "From" address shown in sent emails.
    """

    def __init__(
        self,
        allowed_users_path: str,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        smtp_from: str,
    ):
        self._storage = SqliteAllowedUsersDatabase(allowed_users_path)
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_user = smtp_user
        self._smtp_password = smtp_password
        self._smtp_from = smtp_from
        # A second EmailService is built for FeedbackService (see SP-039) from
        # the same SMTP_* env vars, rather than injecting this one - keeping
        # AuthService's constructor signature (a set of raw smtp_* args, not
        # a service object) unchanged, since existing tests read the raw
        # _smtp_host/_smtp_user/_smtp_from attributes directly.
        self._email_service = EmailService(smtp_host, smtp_port, smtp_user, smtp_password, smtp_from)

    def is_email_allowed(self, email: str) -> bool:
        """
        Check whether the given email address is in the allowed users list.

        Args:
            email (str): Email address entered by the user.

        Returns:
            bool: True if allowed, False otherwise.
        """
        allowed = self._load_allowed_users()
        target = email.strip().lower()
        # Case-insensitive comparison so capitalisation differences don't matter.
        # A blocked user is excluded even though their record still exists (see SP-021).
        return any(u['email'].lower() == target and not u['is_blocked'] for u in allowed)

    def is_admin(self, email: str) -> bool:
        """
        Check whether the given email address is flagged as an admin (see SP-020).

        Args:
            email (str): Email address to check.

        Returns:
            bool: True if the user is allowed AND flagged as admin, False otherwise
                  (including if the email isn't in the allowed list at all).
        """
        allowed = self._load_allowed_users()
        target = email.strip().lower()
        for user in allowed:
            if user['email'].lower() == target:
                return user['is_admin']
        return False

    def get_all_users(self) -> List[Dict]:
        """
        List every allowed user (see SP-021), for the admin user-management page.

        Returns:
            List[Dict]: Normalized {"email", "is_admin", "is_blocked"} dicts.
        """
        return self._load_allowed_users()

    def add_user(self, email: str) -> Tuple[bool, Optional[str]]:
        """
        Add a new allowed user (see SP-021). Starts as non-admin, not blocked.

        Args:
            email (str): Email address to add.

        Returns:
            Tuple[bool, Optional[str]]: (True, None) on success, or
                (False, error_message) if the email is invalid or already exists.
        """
        email = email.strip()
        if not email or '@' not in email:
            return False, 'Please enter a valid email address.'

        users = self._load_allowed_users()
        if self._find_user(users, email) is not None:
            return False, 'That email is already in the list.'

        users.append({'email': email, 'is_admin': False, 'is_blocked': False})
        self._save_allowed_users(users)
        return True, None

    def set_admin(self, email: str, is_admin: bool) -> Tuple[bool, Optional[str]]:
        """
        Set a user's admin flag (see SP-021).

        Rejected if it would leave zero active admins (admin flag set AND not
        blocked) - applies whether the target is the acting admin or someone else.

        Args:
            email (str): Email address to update.
            is_admin (bool): New admin flag value.

        Returns:
            Tuple[bool, Optional[str]]: (True, None) on success, or
                (False, error_message) if the user isn't found or the change
                would violate the last-active-admin rule.
        """
        users = self._load_allowed_users()
        target = self._find_user(users, email)
        if target is None:
            return False, 'User not found.'

        original = target['is_admin']
        target['is_admin'] = is_admin
        if self._count_active_admins(users) == 0:
            target['is_admin'] = original
            return False, 'This would leave no active admins - at least one must remain.'

        self._save_allowed_users(users)
        return True, None

    def set_blocked(self, email: str, is_blocked: bool) -> Tuple[bool, Optional[str]]:
        """
        Set a user's blocked flag (see SP-021). Blocking deactivates login
        access without deleting the user's record; unblocking restores it.

        Rejected if it would leave zero active admins (admin flag set AND not
        blocked) - applies whether the target is the acting admin or someone else.

        Args:
            email (str): Email address to update.
            is_blocked (bool): New blocked flag value.

        Returns:
            Tuple[bool, Optional[str]]: (True, None) on success, or
                (False, error_message) if the user isn't found or the change
                would violate the last-active-admin rule.
        """
        users = self._load_allowed_users()
        target = self._find_user(users, email)
        if target is None:
            return False, 'User not found.'

        original = target['is_blocked']
        target['is_blocked'] = is_blocked
        if self._count_active_admins(users) == 0:
            target['is_blocked'] = original
            return False, 'This would leave no active admins - at least one must remain.'

        self._save_allowed_users(users)
        return True, None

    def toggle_admin(self, email: str) -> Tuple[bool, Optional[str]]:
        """Flip a user's admin flag to its opposite value (see SP-021)."""
        users = self._load_allowed_users()
        target = self._find_user(users, email)
        if target is None:
            return False, 'User not found.'
        return self.set_admin(email, not target['is_admin'])

    def toggle_blocked(self, email: str) -> Tuple[bool, Optional[str]]:
        """Flip a user's blocked flag to its opposite value (see SP-021)."""
        users = self._load_allowed_users()
        target = self._find_user(users, email)
        if target is None:
            return False, 'User not found.'
        return self.set_blocked(email, not target['is_blocked'])

    def generate_otp(self) -> str:
        """
        Generate a random 5-digit OTP code.

        Returns:
            str: Zero-padded 5-digit string, e.g. "04821"
        """
        # random.randint(0, 99999) gives 0-99999; zfill pads with leading zeros
        return str(random.randint(0, 99999)).zfill(5)

    def send_otp_email(self, email: str, otp: str) -> None:
        """
        Send the OTP code to the user's email address via SMTP (STARTTLS on port 587).

        Args:
            email (str): Recipient email address.
            otp   (str): The 5-digit code to send.

        Raises:
            EmailDeliveryError: If the SMTP connection or send fails for any reason.
        """
        body = (
            f"Your ShoppingTracker login code is: {otp}\n\n"
            f"This code expires in 10 minutes.\n"
            f"If you did not request this code, you can ignore this email."
        )
        self._email_service.send([email], "Your ShoppingTracker login code", body)

    def verify_otp(self, session: dict, submitted_code: str) -> bool:
        """
        Verify the submitted OTP code against the value stored in the session.

        Args:
            session        (dict): Flask session object.
            submitted_code (str): Code entered by the user.

        Returns:
            bool: True if code matches and has not expired.
        """
        stored_code = session.get('otp_code')
        expires_at = session.get('otp_expires')

        if not stored_code or not expires_at:
            return False

        # Check expiry first
        if time.time() > expires_at:
            return False

        return submitted_code.strip() == stored_code

    def store_otp_in_session(self, session: dict, email: str, otp: str) -> None:
        """
        Save the OTP and its expiry timestamp into the Flask session.

        Args:
            session (dict): Flask session object.
            email   (str):  The email address being authenticated.
            otp     (str):  The generated OTP code.
        """
        session['otp_code'] = otp
        session['otp_email'] = email.strip().lower()
        session['otp_expires'] = time.time() + _OTP_TTL_SECONDS

    def clear_otp_from_session(self, session: dict) -> None:
        """Remove OTP data from session after successful login or logout."""
        session.pop('otp_code', None)
        session.pop('otp_email', None)
        session.pop('otp_expires', None)

    def _load_allowed_users(self) -> list:
        """
        Read the allowed users list, normalized to a list of
        {"email": ..., "is_admin": ..., "is_blocked": ...} dicts.

        Every row in the allowed_users table already has all three columns
        (see SP-036), so no tolerant parsing is needed here anymore - that
        was a JSON-hand-editing accommodation (SP-020/SP-021) with no SQLite
        equivalent.
        """
        return self._storage.get_all_users()

    def _save_allowed_users(self, users: List[Dict]) -> None:
        """Write the (normalized) allowed users list back to storage."""
        self._storage.save_all_users(users)

    @staticmethod
    def _find_user(users: List[Dict], email: str) -> Optional[Dict]:
        """Case-insensitive lookup of a user dict by email within an already-loaded list."""
        target = email.strip().lower()
        for user in users:
            if user['email'].lower() == target:
                return user
        return None

    @staticmethod
    def _count_active_admins(users: List[Dict]) -> int:
        """Count users who are both flagged admin and not blocked (see SP-021)."""
        return sum(1 for u in users if u['is_admin'] and not u['is_blocked'])
