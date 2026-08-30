import pytest

from app.database.sqlite_allowed_users_db import SqliteAllowedUsersDatabase
from app.services.auth_service import AuthService

# Spec coverage:
#   TestAuthServiceAllowedUsers    -> SP-020 (allowed_users is_admin flag), SP-036 (SQLite storage)
#   TestAuthServiceUserManagement  -> SP-021 (add/toggle-admin/toggle-blocked + last-admin lockout)


def _make_auth_service(allowed_users_path: str) -> AuthService:
    return AuthService(
        allowed_users_path=allowed_users_path,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user@example.com",
        smtp_password="password",
        smtp_from="user@example.com",
    )


def _write_allowed_users(path, entries):
    """
    Seed a SqliteAllowedUsersDatabase at `path` (see SP-036). Accepts a mix
    of bare email strings and {"email", "is_admin", "is_blocked"} dicts as a
    pure test-authoring convenience - normalized to full dicts before
    writing, since every row in the real table always has all three columns.
    """
    normalized = [
        {"email": e, "is_admin": False, "is_blocked": False} if isinstance(e, str) else
        {
            "email": e["email"],
            "is_admin": bool(e.get("is_admin", False)),
            "is_blocked": bool(e.get("is_blocked", False)),
        }
        for e in entries
    ]
    SqliteAllowedUsersDatabase(path).save_all_users(normalized)


class TestAuthServiceAllowedUsers:
    # test_is_email_allowed_true_for_bare_string_entry and
    # test_is_admin_false_for_bare_string_entry were removed here (see
    # SP-036): both asserted AuthService's own runtime tolerance for a
    # hand-edited allowed_users.json mixing bare strings and objects - a
    # JSON-hand-editing accommodation with no SQLite equivalent, since every
    # row in the allowed_users table always has all three columns by
    # construction. _write_allowed_users still accepts bare strings as a
    # test-authoring convenience (see its docstring), just not as a
    # meaningful runtime-tolerance scenario anymore.

    def test_is_email_allowed_true_for_object_entry(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, [{"email": "allowed@example.com", "is_admin": False}])
        auth = _make_auth_service(path)
        assert auth.is_email_allowed("allowed@example.com") is True

    def test_is_email_allowed_false_for_unknown_email(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, ["allowed@example.com"])
        auth = _make_auth_service(path)
        assert auth.is_email_allowed("stranger@example.com") is False

    def test_is_email_allowed_case_insensitive(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, ["Allowed@Example.com"])
        auth = _make_auth_service(path)
        assert auth.is_email_allowed("allowed@example.com") is True

    def test_is_admin_true_for_admin_flagged_entry(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, [{"email": "admin@example.com", "is_admin": True}])
        auth = _make_auth_service(path)
        assert auth.is_admin("admin@example.com") is True

    def test_is_admin_false_for_non_admin_flagged_entry(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, [{"email": "regular@example.com", "is_admin": False}])
        auth = _make_auth_service(path)
        assert auth.is_admin("regular@example.com") is False

    def test_is_admin_false_for_unknown_email(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, [{"email": "admin@example.com", "is_admin": True}])
        auth = _make_auth_service(path)
        assert auth.is_admin("stranger@example.com") is False


class TestAuthServiceUserManagement:

    def test_add_user_success(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, [])
        auth = _make_auth_service(path)

        success, error = auth.add_user("new@example.com")

        assert success is True
        assert error is None
        users = auth.get_all_users()
        assert users == [{"email": "new@example.com", "is_admin": False, "is_blocked": False}]

    def test_add_user_duplicate_rejected(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, ["existing@example.com"])
        auth = _make_auth_service(path)

        success, error = auth.add_user("existing@example.com")

        assert success is False
        assert error is not None
        assert len(auth.get_all_users()) == 1

    def test_add_user_duplicate_case_insensitive(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, ["existing@example.com"])
        auth = _make_auth_service(path)

        success, error = auth.add_user("EXISTING@Example.com")

        assert success is False
        assert len(auth.get_all_users()) == 1

    def test_add_user_invalid_email_rejected(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, [])
        auth = _make_auth_service(path)

        assert auth.add_user("")[0] is False
        assert auth.add_user("not-an-email")[0] is False
        assert auth.get_all_users() == []

    def test_set_admin_false_succeeds_with_multiple_admins(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, [
            {"email": "admin1@example.com", "is_admin": True},
            {"email": "admin2@example.com", "is_admin": True},
        ])
        auth = _make_auth_service(path)

        success, error = auth.set_admin("admin1@example.com", False)

        assert success is True
        assert error is None
        assert auth.is_admin("admin1@example.com") is False
        assert auth.is_admin("admin2@example.com") is True

    def test_set_admin_false_rejected_when_it_would_be_the_last_admin(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, [{"email": "sole-admin@example.com", "is_admin": True}])
        auth = _make_auth_service(path)

        success, error = auth.set_admin("sole-admin@example.com", False)

        assert success is False
        assert error is not None
        # Confirms the mutate-check-revert actually reverts on rejection
        assert auth.is_admin("sole-admin@example.com") is True

    def test_set_blocked_true_rejected_when_it_would_be_the_last_active_admin(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, [{"email": "sole-admin@example.com", "is_admin": True}])
        auth = _make_auth_service(path)

        success, error = auth.set_blocked("sole-admin@example.com", True)

        assert success is False
        assert error is not None
        assert auth.is_email_allowed("sole-admin@example.com") is True

    def test_set_blocked_true_succeeds_with_multiple_active_admins(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, [
            {"email": "admin1@example.com", "is_admin": True},
            {"email": "admin2@example.com", "is_admin": True},
        ])
        auth = _make_auth_service(path)

        success, error = auth.set_blocked("admin1@example.com", True)

        assert success is True
        assert auth.is_email_allowed("admin1@example.com") is False
        assert auth.is_email_allowed("admin2@example.com") is True

    def test_set_blocked_false_always_allowed(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, [{"email": "sole-admin@example.com", "is_admin": True, "is_blocked": True}])
        auth = _make_auth_service(path)

        success, error = auth.set_blocked("sole-admin@example.com", False)

        assert success is True
        assert error is None
        assert auth.is_email_allowed("sole-admin@example.com") is True

    def test_toggle_admin_flips_current_value(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, [
            {"email": "admin1@example.com", "is_admin": True},
            {"email": "regular@example.com", "is_admin": False},
        ])
        auth = _make_auth_service(path)

        success, _ = auth.toggle_admin("regular@example.com")

        assert success is True
        assert auth.is_admin("regular@example.com") is True

    def test_toggle_blocked_flips_current_value(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, [
            {"email": "admin@example.com", "is_admin": True},
            {"email": "regular@example.com", "is_admin": False, "is_blocked": False},
        ])
        auth = _make_auth_service(path)

        success, _ = auth.toggle_blocked("regular@example.com")

        assert success is True
        assert auth.is_email_allowed("regular@example.com") is False

    def test_set_admin_unknown_email_returns_not_found(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, [])
        auth = _make_auth_service(path)

        success, error = auth.set_admin("stranger@example.com", True)

        assert success is False
        assert error is not None

    def test_set_blocked_unknown_email_returns_not_found(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, [])
        auth = _make_auth_service(path)

        success, error = auth.set_blocked("stranger@example.com", True)

        assert success is False
        assert error is not None

    def test_is_email_allowed_false_for_blocked_user(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.db")
        _write_allowed_users(path, [{"email": "blocked@example.com", "is_admin": False, "is_blocked": True}])
        auth = _make_auth_service(path)

        assert auth.is_email_allowed("blocked@example.com") is False
