"""
Tests for SP-039: FeedbackService (validation, storage, and admin
notification for user feedback submissions).
"""

import io

import pytest
from unittest.mock import MagicMock
from werkzeug.datastructures import FileStorage

from app.database.sqlite_feedback_db import SqliteFeedbackDatabase
from app.services.email_service import EmailDeliveryError
from app.services.feedback_service import FeedbackService

# Spec coverage:
#   TestFeedbackServiceValidation    -> SP-039 (required message, allowed image types)
#   TestFeedbackServiceFallbacks     -> SP-039 (invalid select values fall back silently)
#   TestFeedbackServiceRecipients    -> SP-039 (active-admin recipient filtering)
#   TestFeedbackServiceEmailFailure  -> SP-039 (email failure doesn't lose the feedback)


def _make_image_file(filename="screenshot.jpg") -> FileStorage:
    return FileStorage(stream=io.BytesIO(b"fake-image-bytes"), filename=filename, content_type="image/jpeg")


@pytest.fixture
def feedback_service(tmp_path):
    database = SqliteFeedbackDatabase(str(tmp_path / "feedback.db"))
    email_service = MagicMock()
    auth_service = MagicMock()
    auth_service.get_all_users.return_value = [
        {"email": "admin@example.com", "is_admin": True, "is_blocked": False},
    ]
    upload_folder = str(tmp_path / "uploads")

    service = FeedbackService(
        database=database,
        email_service=email_service,
        auth_service=auth_service,
        upload_folder=upload_folder,
        allowed_extensions={"jpg", "jpeg", "png"},
    )
    # expose the mocks for assertions
    service.email_service_mock = email_service
    service.auth_service_mock = auth_service
    return service


class TestFeedbackServiceValidation:

    def test_empty_message_raises_value_error(self, feedback_service):
        with pytest.raises(ValueError):
            feedback_service.submit_feedback("user@example.com", "Bug Report", "History", "", None)
        assert feedback_service.database.get_all_feedback() == []

    def test_whitespace_only_message_raises_value_error(self, feedback_service):
        with pytest.raises(ValueError):
            feedback_service.submit_feedback("user@example.com", "Bug Report", "History", "   ", None)
        assert feedback_service.database.get_all_feedback() == []

    def test_disallowed_image_extension_raises_value_error(self, feedback_service):
        bad_file = FileStorage(stream=io.BytesIO(b"data"), filename="notes.pdf", content_type="application/pdf")
        with pytest.raises(ValueError):
            feedback_service.submit_feedback("user@example.com", "Bug Report", "History", "A bug", bad_file)
        assert feedback_service.database.get_all_feedback() == []

    def test_valid_submission_no_image(self, feedback_service):
        feedback_id, _ = feedback_service.submit_feedback(
            "user@example.com", "Bug Report", "History", "Something broke", None
        )
        records = feedback_service.database.get_all_feedback()
        assert len(records) == 1
        assert records[0]["id"] == feedback_id
        assert records[0]["user_email"] == "user@example.com"
        assert records[0]["message_type"] == "Bug Report"
        assert records[0]["functionality"] == "History"
        assert records[0]["message"] == "Something broke"
        assert records[0]["image_filename"] is None

    def test_valid_submission_with_image_saves_file_and_attaches(self, feedback_service):
        import os
        feedback_service.submit_feedback(
            "user@example.com", "Bug Report", "History", "See screenshot", _make_image_file()
        )
        records = feedback_service.database.get_all_feedback()
        assert records[0]["image_filename"] is not None
        saved_path = os.path.join(feedback_service.upload_folder, records[0]["image_filename"])
        assert os.path.exists(saved_path)

        call_kwargs = feedback_service.email_service_mock.send.call_args.kwargs
        attachment = call_kwargs.get("attachment") or feedback_service.email_service_mock.send.call_args.args[-1]
        assert attachment[0] == b"fake-image-bytes"


class TestFeedbackServiceFallbacks:

    def test_invalid_message_type_falls_back_to_bug_report(self, feedback_service):
        feedback_service.submit_feedback(
            "user@example.com", "Not A Real Type", "History", "Hello", None
        )
        assert feedback_service.database.get_all_feedback()[0]["message_type"] == "Bug Report"

    def test_invalid_functionality_falls_back_to_none(self, feedback_service):
        feedback_service.submit_feedback(
            "user@example.com", "Bug Report", "Not A Real Page", "Hello", None
        )
        assert feedback_service.database.get_all_feedback()[0]["functionality"] == "None"


class TestFeedbackServiceRecipients:

    def test_only_active_admins_notified(self, feedback_service):
        feedback_service.auth_service_mock.get_all_users.return_value = [
            {"email": "admin1@example.com", "is_admin": True, "is_blocked": False},
            {"email": "admin2-blocked@example.com", "is_admin": True, "is_blocked": True},
            {"email": "regular@example.com", "is_admin": False, "is_blocked": False},
        ]
        feedback_service.submit_feedback("user@example.com", "Bug Report", "History", "Hello", None)

        to_addresses = feedback_service.email_service_mock.send.call_args.args[0]
        assert to_addresses == ["admin1@example.com"]

    def test_no_active_admins_saves_but_does_not_email(self, feedback_service):
        feedback_service.auth_service_mock.get_all_users.return_value = [
            {"email": "regular@example.com", "is_admin": False, "is_blocked": False},
        ]
        feedback_id, email_sent = feedback_service.submit_feedback(
            "user@example.com", "Bug Report", "History", "Hello", None
        )
        assert email_sent is False
        feedback_service.email_service_mock.send.assert_not_called()
        assert len(feedback_service.database.get_all_feedback()) == 1


class TestFeedbackServiceEmailFailure:

    def test_email_delivery_error_does_not_lose_feedback(self, feedback_service):
        feedback_service.email_service_mock.send.side_effect = EmailDeliveryError("smtp down")
        feedback_id, email_sent = feedback_service.submit_feedback(
            "user@example.com", "Bug Report", "History", "Hello", None
        )
        assert email_sent is False
        records = feedback_service.database.get_all_feedback()
        assert len(records) == 1
        assert records[0]["id"] == feedback_id
