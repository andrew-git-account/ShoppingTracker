import json

import pytest

from app.services.auth_service import AuthService

# Spec coverage:
#   TestAuthServiceAllowedUsers -> SP-020 (allowed_users.json tolerant parsing + is_admin flag)


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
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f)


class TestAuthServiceAllowedUsers:

    def test_is_email_allowed_true_for_bare_string_entry(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.json")
        _write_allowed_users(path, ["allowed@example.com"])
        auth = _make_auth_service(path)
        assert auth.is_email_allowed("allowed@example.com") is True

    def test_is_email_allowed_true_for_object_entry(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.json")
        _write_allowed_users(path, [{"email": "allowed@example.com", "is_admin": False}])
        auth = _make_auth_service(path)
        assert auth.is_email_allowed("allowed@example.com") is True

    def test_is_email_allowed_false_for_unknown_email(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.json")
        _write_allowed_users(path, ["allowed@example.com"])
        auth = _make_auth_service(path)
        assert auth.is_email_allowed("stranger@example.com") is False

    def test_is_email_allowed_case_insensitive(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.json")
        _write_allowed_users(path, ["Allowed@Example.com"])
        auth = _make_auth_service(path)
        assert auth.is_email_allowed("allowed@example.com") is True

    def test_is_admin_true_for_admin_flagged_entry(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.json")
        _write_allowed_users(path, [{"email": "admin@example.com", "is_admin": True}])
        auth = _make_auth_service(path)
        assert auth.is_admin("admin@example.com") is True

    def test_is_admin_false_for_non_admin_flagged_entry(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.json")
        _write_allowed_users(path, [{"email": "regular@example.com", "is_admin": False}])
        auth = _make_auth_service(path)
        assert auth.is_admin("regular@example.com") is False

    def test_is_admin_false_for_bare_string_entry(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.json")
        _write_allowed_users(path, ["regular@example.com"])
        auth = _make_auth_service(path)
        assert auth.is_admin("regular@example.com") is False

    def test_is_admin_false_for_unknown_email(self, tmp_data_dir):
        path = str(tmp_data_dir / "allowed_users.json")
        _write_allowed_users(path, [{"email": "admin@example.com", "is_admin": True}])
        auth = _make_auth_service(path)
        assert auth.is_admin("stranger@example.com") is False
