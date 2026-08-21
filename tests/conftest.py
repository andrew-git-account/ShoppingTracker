"""
Pytest configuration and shared fixtures.

Fixtures defined here are automatically available to all test files.
"""

import json
import os
import pytest

# We need to set a dummy API key before importing the app,
# because main.py validates it at startup.
os.environ.setdefault('ANTHROPIC_API_KEY', 'test-key-not-used')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')


@pytest.fixture()
def app(monkeypatch, tmp_path):
    """
    Create a Flask app instance configured for testing.

    - Writes a temporary allowed_users.json with a known test email
    - Mocks LLMService so no real Anthropic API calls are made
    - Uses a temporary receipts database
    """
    # Write the allowed users file directly into tmp_path. Mixed shapes on
    # purpose (see SP-020): a bare string entry exercises AuthService's
    # tolerant parsing, and the object entry provides a real admin-capable
    # email for tests that log in via the actual OTP flow.
    allowed_users = tmp_path / 'allowed_users.json'
    allowed_users.write_text(
        json.dumps(['allowed@example.com', {'email': 'admin@example.com', 'is_admin': True}]),
        encoding='utf-8'
    )

    # Point DATA_FOLDER at tmp_path so the app reads from the right place
    monkeypatch.setenv('DATA_FOLDER', str(tmp_path))

    # Mock LLMService.__init__ to prevent real API calls at startup
    monkeypatch.setattr(
        'app.services.llm_service.LLMService.__init__',
        lambda self, **kwargs: None
    )

    from app.main import create_app as flask_create_app
    flask_app = flask_create_app()
    flask_app.config['TESTING'] = True

    return flask_app


@pytest.fixture()
def client(app):
    """Flask test client — use this to make HTTP requests in tests."""
    return app.test_client()


@pytest.fixture()
def logged_in_client(app):
    """
    Flask test client with an active authenticated session.

    Use this in tests that hit protected routes (/, /upload, /history, etc.)
    so the before_request auth guard doesn't redirect to /login.

    user_email matches seed_receipt()/seed_receipt_with_items()'s default
    owner (see test_routes.py), so seeded receipts are visible to this client.
    """
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['logged_in'] = True
        sess['user_email'] = 'test@example.com'
        sess['is_admin'] = False
    return c


@pytest.fixture()
def admin_client(app):
    """
    Flask test client with an active authenticated ADMIN session (see SP-020).

    Use this for tests exercising the admin-only LLM Usage page. Matches the
    admin entry seeded into allowed_users.json by the app fixture above.
    """
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['logged_in'] = True
        sess['user_email'] = 'admin@example.com'
        sess['is_admin'] = True
    return c
