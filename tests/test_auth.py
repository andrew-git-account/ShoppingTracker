"""
Tests for SP-008: Simple Authentication (Route Protection + OTP Flow)

Covers all acceptance criteria:
- Unauthenticated users are redirected to /login
- Unknown email shows "Email address not authorised"
- Allowed email generates OTP and redirects to /verify
- Correct code logs in and redirects to upload page
- Wrong code shows "Invalid code, please try again"
- Logout clears session and redirects to /login
"""


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _inject_valid_otp(client, app):
    """
    Shortcut: set a valid OTP directly in the session so tests can skip
    the email-entry step and focus on the code-verification step.
    """
    import time
    with client.session_transaction() as sess:
        sess['otp_code'] = '11111'
        sess['otp_email'] = 'allowed@example.com'
        sess['otp_expires'] = time.time() + 600  # 10 minutes from now


def _login(client, app):
    """Fully authenticate the test client."""
    _inject_valid_otp(client, app)
    client.post('/verify', data={'code': '11111'}, follow_redirects=False)


# ---------------------------------------------------------------------------
# AC1: Unauthenticated redirect
# ---------------------------------------------------------------------------

def test_unauthenticated_root_redirects_to_login(client):
    response = client.get('/')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_unauthenticated_upload_redirects_to_login(client):
    response = client.get('/upload')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_unauthenticated_history_redirects_to_login(client):
    response = client.get('/history')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_login_page_is_publicly_accessible(client):
    response = client.get('/login')
    assert response.status_code == 200


def test_verify_page_is_publicly_accessible_after_otp_stored(client, app):
    _inject_valid_otp(client, app)
    response = client.get('/verify')
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# AC2: Unknown email shows correct error
# ---------------------------------------------------------------------------

def test_unknown_email_shows_not_authorised(client):
    response = client.post('/login', data={'email': 'stranger@example.com'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'Email address not authorised' in response.data


# ---------------------------------------------------------------------------
# AC3: Allowed email redirects to verify
# ---------------------------------------------------------------------------

def test_allowed_email_redirects_to_verify(client):
    response = client.post('/login', data={'email': 'allowed@example.com'})
    assert response.status_code == 302
    assert '/verify' in response.headers['Location']


def test_allowed_email_stores_otp_in_session(client, app):
    client.post('/login', data={'email': 'allowed@example.com'})
    with client.session_transaction() as sess:
        assert sess.get('otp_code') is not None
        assert len(sess['otp_code']) == 5
        assert sess['otp_code'].isdigit()


# ---------------------------------------------------------------------------
# AC4: Correct code grants access
# ---------------------------------------------------------------------------

def test_correct_code_redirects_to_index(client, app):
    _inject_valid_otp(client, app)
    response = client.post('/verify', data={'code': '11111'})
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/')


def test_correct_code_sets_logged_in_session(client, app):
    _inject_valid_otp(client, app)
    client.post('/verify', data={'code': '11111'})
    with client.session_transaction() as sess:
        assert sess.get('logged_in') is True


def test_authenticated_user_can_reach_index(client, app):
    _login(client, app)
    response = client.get('/')
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# AC5: Wrong code shows correct error
# ---------------------------------------------------------------------------

def test_wrong_code_shows_error(client, app):
    _inject_valid_otp(client, app)
    response = client.post('/verify', data={'code': '99999'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'Invalid code, please try again' in response.data


def test_wrong_code_does_not_set_logged_in(client, app):
    _inject_valid_otp(client, app)
    client.post('/verify', data={'code': '99999'})
    with client.session_transaction() as sess:
        assert not sess.get('logged_in')


# ---------------------------------------------------------------------------
# AC6: Logout clears session
# ---------------------------------------------------------------------------

def test_logout_redirects_to_login(client, app):
    _login(client, app)
    response = client.get('/logout')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_after_logout_protected_pages_redirect_to_login(client, app):
    _login(client, app)
    client.get('/logout')
    response = client.get('/')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']
