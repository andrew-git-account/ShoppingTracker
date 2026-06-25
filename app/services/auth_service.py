"""
Authentication service - handles OTP-based login logic.

Flow:
1. User submits email -> check against allowed_users.json
2. If allowed, generate a 5-digit OTP, store it in session with expiry
3. Send the OTP to the user's email address via SMTP
4. User submits code -> compare with session value and check expiry
"""

import json
import os
import random
import smtplib
import time
from email.mime.text import MIMEText


# OTP is valid for 10 minutes (600 seconds)
_OTP_TTL_SECONDS = 600


class EmailDeliveryError(Exception):
    """Raised when the SMTP send fails so the route can show a user-friendly error."""
    pass


class AuthService:
    """
    Manages the OTP authentication flow.

    Args:
        allowed_users_path (str): Path to the JSON file containing allowed email addresses.
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
        self._allowed_users_path = allowed_users_path
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_user = smtp_user
        self._smtp_password = smtp_password
        self._smtp_from = smtp_from

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

    def send_otp_email(self, email: str, otp: str) -> None:
        """
        Send the OTP code to the user's email address via SMTP (STARTTLS on port 587).

        Args:
            email (str): Recipient email address.
            otp   (str): The 5-digit code to send.

        Raises:
            EmailDeliveryError: If the SMTP connection or send fails for any reason.
        """
        msg = MIMEText(
            f"Your ShoppingTracker login code is: {otp}\n\n"
            f"This code expires in 10 minutes.\n"
            f"If you did not request this code, you can ignore this email."
        )
        msg["Subject"] = "Your ShoppingTracker login code"
        msg["From"] = self._smtp_from
        msg["To"] = email

        try:
            # smtplib.SMTP opens a plain connection; starttls() upgrades it to TLS
            with smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self._smtp_user, self._smtp_password)
                server.send_message(msg)
            print(f"[AUTH] OTP email sent to {email}")
        except Exception as exc:
            # Log the technical detail to server.log, raise a clean error for the route
            print(f"[AUTH] SMTP send failed for {email}: {exc}")
            raise EmailDeliveryError(str(exc)) from exc

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
