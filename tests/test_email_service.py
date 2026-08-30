"""
Tests for SP-039: EmailService (extracted from AuthService.send_otp_email
to support multi-recipient, optional-attachment email for feedback).
"""

from unittest.mock import patch

import pytest

from app.services.email_service import EmailService, EmailDeliveryError

# Spec coverage:
#   TestEmailServicePlainSend        -> SP-039 (no-attachment path matches today's OTP email shape)
#   TestEmailServiceAttachment       -> SP-039 (image attachment support)
#   TestEmailServiceFailure          -> SP-039 (SMTP failures become EmailDeliveryError)


def _make_email_service() -> EmailService:
    return EmailService(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user@example.com",
        smtp_password="password",
        smtp_from="from@example.com",
    )


class _FakeServer:
    def __init__(self, captured):
        self._captured = captured

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def starttls(self):
        pass

    def login(self, u, p):
        pass

    def send_message(self, msg):
        self._captured['msg'] = msg


def _capture_send(service: EmailService, **kwargs) -> dict:
    captured = {}

    def fake_smtp(host, port, timeout=10):
        return _FakeServer(captured)

    with patch('smtplib.SMTP', side_effect=fake_smtp):
        service.send(**kwargs)

    return captured


class TestEmailServicePlainSend:

    def test_no_attachment_produces_plain_mimetext(self):
        service = _make_email_service()
        captured = _capture_send(
            service, to_addresses=["a@example.com"], subject="Subject", body="Body text"
        )
        msg = captured['msg']
        # Plain string payload (not a list) - proves the multipart branch was
        # never taken, matching test_send_otp_email_subject_and_body's shape.
        assert isinstance(msg.get_payload(), str)
        assert "Body text" in msg.get_payload()

    def test_subject_and_from_set(self):
        service = _make_email_service()
        captured = _capture_send(
            service, to_addresses=["a@example.com"], subject="My Subject", body="Body"
        )
        msg = captured['msg']
        assert msg['Subject'] == 'My Subject'
        assert msg['From'] == 'from@example.com'

    def test_multiple_recipients_join_into_to_header(self):
        service = _make_email_service()
        captured = _capture_send(
            service, to_addresses=["a@example.com", "b@example.com"], subject="S", body="B"
        )
        assert captured['msg']['To'] == 'a@example.com, b@example.com'


class TestEmailServiceAttachment:

    def test_attachment_produces_multipart_with_text_and_image_parts(self):
        service = _make_email_service()
        captured = _capture_send(
            service, to_addresses=["a@example.com"], subject="S", body="Body text",
            attachment=(b"fake-image-bytes", "screenshot.jpg")
        )
        msg = captured['msg']
        parts = msg.get_payload()
        assert isinstance(parts, list)
        assert len(parts) == 2
        assert "Body text" in parts[0].get_payload()
        assert parts[1].get_content_subtype() == 'jpeg'

    def test_png_attachment_subtype(self):
        service = _make_email_service()
        captured = _capture_send(
            service, to_addresses=["a@example.com"], subject="S", body="B",
            attachment=(b"fake-png-bytes", "shot.png")
        )
        image_part = captured['msg'].get_payload()[1]
        assert image_part.get_content_subtype() == 'png'


class TestEmailServiceFailure:

    def test_smtp_exception_becomes_email_delivery_error(self):
        service = _make_email_service()
        with patch('smtplib.SMTP', side_effect=Exception("connection refused")):
            with pytest.raises(EmailDeliveryError):
                service.send(to_addresses=["a@example.com"], subject="S", body="B")

    def test_smtp_exception_with_attachment_becomes_email_delivery_error(self):
        service = _make_email_service()
        with patch('smtplib.SMTP', side_effect=Exception("connection refused")):
            with pytest.raises(EmailDeliveryError):
                service.send(
                    to_addresses=["a@example.com"], subject="S", body="B",
                    attachment=(b"bytes", "x.jpg")
                )
