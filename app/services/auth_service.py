"""
Authentication service - handles OTP-based login logic.

Flow:
1. User submits email -> check against allowed_users.json
2. If allowed, generate a 5-digit OTP, store it in session with expiry
3. Log the OTP to server.log (mocked delivery; real email is SP-009)
4. User submits code -> compare with session value and check expiry
"""

import json
import os
import random
import time


# OTP is valid for 10 minutes (600 seconds)
_OTP_TTL_SECONDS = 600


class AuthService:
    """
    Manages the OTP authentication flow.

    Args:
        allowed_users_path (str): Path to the JSON file containing allowed email addresses.
    """

    def __init__(self, allowed_users_path: str):
        self._allowed_users_path = allowed_users_path

    def is_email_allowed(self, email: str) -> bool:
        """
        Check whether the given email address is in the allowed users list.

        Args:
            email (str): Email address entered by the user.

        Returns:
            bool: True if allowed, False otherwise.
        """
        allowed = self._load_allowed_users()
        # Case-insensitive comparison so capitalisation differences don't matter
        return email.strip().lower() in [e.lower() for e in allowed]

    def generate_otp(self) -> str:
        """
        Generate a random 5-digit OTP code.

        Returns:
            str: Zero-padded 5-digit string, e.g. "04821"
        """
        # random.randint(0, 99999) gives 0-99999; zfill pads with leading zeros
        return str(random.randint(0, 99999)).zfill(5)

    def log_otp(self, email: str, otp: str) -> None:
        """
        Write the OTP to server.log so it can be read during development.
        Real email delivery will replace this in SP-009.

        Args:
            email (str): The recipient email address.
            otp   (str): The generated OTP code.
        """
        # Print goes to server.log when the app is started via run_server.py
        print(f"[AUTH] OTP for {email}: {otp}")

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
        Read the allowed users list from the JSON file.

        Returns an empty list if the file does not exist yet, so the app
        still starts cleanly even if the file is missing.
        """
        if not os.path.exists(self._allowed_users_path):
            print(f"[WARN] allowed_users.json not found at {self._allowed_users_path}")
            return []
        with open(self._allowed_users_path, 'r', encoding='utf-8') as f:
            return json.load(f)
