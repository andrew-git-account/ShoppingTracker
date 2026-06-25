"""
Tests for SP-009: SMTP Email Delivery for OTP

Covers all acceptance criteria:
- Allowed email triggers send_otp_email (real SMTP call mocked)
- Email subject and body contain the expected content
- SMTP failure flashes "Could not send code — please try again"
- SMTP credentials come from env vars (not hardcoded)
- The old log_otp mock method no longer exists on AuthService
"""

import time
from unittest.mock import patch, MagicMock
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _inject_valid_otp(client):
    with client.session_transaction() as sess:
        sess['otp_code'] = '55555'
        sess['otp_email'] = 'allowed@example.com'
        sess['otp_expires'] = time.time() + 600


# ---------------------------------------------------------------------------
# AC: log_otp mock removed
# ---------------------------------------------------------------------------

def test_log_otp_method_removed(app):
    """The old mocked delivery method must not exist on AuthService."""
    assert not hasattr(app.auth_service, 'log_otp'), (
        "log_otp() should have been removed in SP-009"
    )


# ---------------------------------------------------------------------------
# AC: SMTP credentials come from env vars
# ---------------------------------------------------------------------------

def test_smtp_config_read_from_env(monkeypatch, tmp_path):
    """AuthService receives SMTP config from os.getenv() calls in main.py."""
    import json, os
    (tmp_path / 'allowed_users.json').write_text(
        json.dumps(['allowed@example.com']), encoding='utf-8'
    )
    monkeypatch.setenv('DATA_FOLDER', str(tmp_path))
    monkeypatch.setenv('SMTP_HOST', 'smtp.testhost.com')
    monkeypatch.setenv('SMTP_PORT', '587')
    monkeypatch.setenv('SMTP_USER', 'user@testhost.com')
    monkeypatch.setenv('SMTP_PASSWORD', 'secret')
    monkeypatch.setenv('SMTP_FROM', 'from@testhost.com')
    monkeypatch.setattr(
        'app.services.llm_service.LLMService.__init__',
        lambda self, **kwargs: None
    )

    from app.main import create_app as flask_create_app
    flask_app = flask_create_app()

    assert flask_app.auth_service._smtp_host == 'smtp.testhost.com'
    assert flask_app.auth_service._smtp_user == 'user@testhost.com'
    assert flask_app.auth_service._smtp_from == 'from@testhost.com'


# ---------------------------------------------------------------------------
# AC: Allowed email calls send_otp_email
# ---------------------------------------------------------------------------

def test_allowed_email_calls_send_otp_email(client, app):
    """Submitting an allowed email triggers send_otp_email (not a log call)."""
    with patch.object(app.auth_service, 'send_otp_email') as mock_send:
        client.post('/login', data={'email': 'allowed@example.com'})
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[0][0] == 'allowed@example.com'  # first positional arg is the email
        otp_sent = call_args[0][1]
        assert len(otp_sent) == 5 and otp_sent.isdigit()


# ---------------------------------------------------------------------------
# AC: Email subject and body content
# ---------------------------------------------------------------------------

def test_send_otp_email_subject_and_body(app):
    """send_otp_email builds a message with the correct subject and body text."""
    captured = {}

    def fake_smtp(host, port, timeout=10):
        class FakeServer:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def starttls(self): pass
            def login(self, u, p): pass
            def send_message(self, msg):
                captured['subject'] = msg['Subject']
                captured['body'] = msg.get_payload()
        return FakeServer()

    with patch('smtplib.SMTP', side_effect=fake_smtp):
        app.auth_service.send_otp_email('allowed@example.com', '42000')

    assert captured['subject'] == 'Your ShoppingTracker login code'
    assert '42000' in captured['body']


# ---------------------------------------------------------------------------
# AC: SMTP failure flashes correct error message
# ---------------------------------------------------------------------------

def test_smtp_failure_flashes_error(client, app):
    """If send_otp_email raises EmailDeliveryError, the login page shows the right message."""
    from app.services import EmailDeliveryError
    with patch.object(app.auth_service, 'send_otp_email', side_effect=EmailDeliveryError('timeout')):
        response = client.post(
            '/login',
            data={'email': 'allowed@example.com'},
            follow_redirects=True
        )
    assert response.status_code == 200
    assert 'Could not send code' in response.data.decode()
    assert 'please try again' in response.data.decode()


def test_smtp_failure_does_not_redirect_to_verify(client, app):
    """On SMTP failure the user stays on the login page, not redirected to /verify."""
    from app.services import EmailDeliveryError
    with patch.object(app.auth_service, 'send_otp_email', side_effect=EmailDeliveryError('timeout')):
        response = client.post('/login', data={'email': 'allowed@example.com'})
    # 200 means we rendered login.html directly (no redirect)
    assert response.status_code == 200


def test_smtp_failure_smtplib_exception_raises_delivery_error(app):
    """Any smtplib exception is caught and re-raised as EmailDeliveryError."""
    import smtplib
    from app.services import EmailDeliveryError
    with patch('smtplib.SMTP', side_effect=smtplib.SMTPAuthenticationError(535, b'bad auth')):
        with pytest.raises(EmailDeliveryError):
            app.auth_service.send_otp_email('allowed@example.com', '12345')
