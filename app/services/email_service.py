"""
Email Service - shared SMTP sending, with optional attachment support (see
SP-039).

Extracted from AuthService.send_otp_email, which only ever needed a
plain-text, single-recipient message - feedback emails (SP-039) need an
optional image attachment and multiple recipients, so this is a real,
reusable sender rather than a second copy of the same smtplib boilerplate.
"""

import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional, Tuple

# Maps a file extension to the MIME image subtype. Derived explicitly rather
# than relying on MIMEImage's default subtype-sniffing (which calls
# imghdr.what() internally) - imghdr was removed in Python 3.13, so leaving
# _subtype unset is a version-compatibility risk, not just a style choice.
_IMAGE_SUBTYPES = {'jpg': 'jpeg', 'jpeg': 'jpeg', 'png': 'png'}


class EmailDeliveryError(Exception):
    """Raised when the SMTP send fails so the route can show a user-friendly error."""
    pass


class EmailService:
    """
    Sends email via SMTP (STARTTLS), to one or more recipients, with an
    optional single image attachment.

    Args:
        smtp_host     (str): SMTP server hostname (e.g. "smtp.gmail.com").
        smtp_port     (int): SMTP port — use 587 for STARTTLS.
        smtp_user     (str): SMTP login username (usually the sending email address).
        smtp_password (str): SMTP login password or app-password.
        smtp_from     (str): The "From" address shown in sent emails.
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        smtp_from: str,
    ):
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_user = smtp_user
        self._smtp_password = smtp_password
        self._smtp_from = smtp_from

    def send(
        self,
        to_addresses: List[str],
        subject: str,
        body: str,
        attachment: Optional[Tuple[bytes, str]] = None,
    ) -> None:
        """
        Send a plain-text email, optionally with one image attachment.

        Args:
            to_addresses (List[str]): Recipient email addresses
            subject (str): Email subject
            body (str): Plain-text body
            attachment (Tuple[bytes, str], optional): (image_bytes, filename)

        Raises:
            EmailDeliveryError: If the SMTP connection or send fails for any reason.
        """
        if attachment is None:
            msg = MIMEText(body)
        else:
            image_bytes, filename = attachment
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            image_part = MIMEImage(image_bytes, _subtype=_IMAGE_SUBTYPES.get(ext, 'jpeg'))
            image_part.add_header('Content-Disposition', 'attachment', filename=filename)

            msg = MIMEMultipart()
            msg.attach(MIMEText(body))
            msg.attach(image_part)

        msg["Subject"] = subject
        msg["From"] = self._smtp_from
        msg["To"] = ", ".join(to_addresses)

        try:
            # smtplib.SMTP opens a plain connection; starttls() upgrades it to TLS
            with smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self._smtp_user, self._smtp_password)
                server.send_message(msg)
            print(f"[EMAIL] sent to {', '.join(to_addresses)}: {subject}")
        except Exception as exc:
            # Log the technical detail to server.log, raise a clean error for the caller
            print(f"[EMAIL] SMTP send failed for {', '.join(to_addresses)}: {exc}")
            raise EmailDeliveryError(str(exc)) from exc
