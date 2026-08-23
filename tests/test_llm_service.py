import io
import json
from unittest.mock import MagicMock

import pytest
from PIL import Image as _PIL_Image
from pypdf import PdfWriter

from app.services.llm_service import LLMService

# Spec coverage:
#   TestReconciliationSingleCall -> SP-018 (no retry when the extraction already reconciles)
#   TestReconciliationRetry      -> SP-018 (retry once, with the discrepancy, on mismatch)
#   TestUsageLogging             -> SP-020 (every API call attempt is logged with cost/outcome)
#   TestStatementExtraction      -> SP-025 (statement PDF -> transaction list extraction)

# Tiny 1x1 white JPEG — small enough to skip compression, valid enough for _encode_image
_buf = io.BytesIO()
_PIL_Image.new("RGB", (1, 1), (255, 255, 255)).save(_buf, "JPEG")
TINY_JPEG = _buf.getvalue()

TEST_USER_EMAIL = "test@example.com"


def _mock_response(payload: dict, input_tokens: int = 1000, output_tokens: int = 200) -> MagicMock:
    """Build a fake Anthropic response whose text matches what _parse_response expects."""
    resp = MagicMock()
    text = "Step 1 transcription...\n\n```json\n" + json.dumps(payload) + "\n```"
    resp.content = [MagicMock(text=text)]
    resp.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
    return resp


def make_service(tmp_path, usage_logger=None) -> tuple:
    """Create an LLMService with a mocked Anthropic client and a real tiny image on disk."""
    service = LLMService(
        api_key="test-key",
        model="test-model",
        valid_categories=["Food & Groceries", "Other"],
        usage_logger=usage_logger,
    )
    service.client = MagicMock()

    image_path = tmp_path / "receipt.jpg"
    image_path.write_bytes(TINY_JPEG)

    return service, str(image_path)


class TestReconciliationSingleCall:

    def test_reconciled_first_attempt_makes_single_call(self, tmp_path):
        service, image_path = make_service(tmp_path)
        payload = {
            "store_name": "Test Mart",
            "purchase_date": "2026-06-16",
            "items": [{"name": "Milk", "price": 2.99, "quantity": 1, "category": "Food & Groceries"}],
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 2.99,
            "currency": "USD",
        }
        service.client.messages.create.side_effect = [_mock_response(payload)]

        result, reconciled = service.extract_receipt_data(image_path, TEST_USER_EMAIL)

        assert service.client.messages.create.call_count == 1
        assert result == payload
        assert reconciled is True

    def test_reconciled_via_net_formula_makes_single_call(self, tmp_path):
        service, image_path = make_service(tmp_path)
        # sum(items) = 10.00, total = 10.50, tax = 0.50 -> reconciles via VAT-exclusive formula
        payload = {
            "store_name": "US Store",
            "purchase_date": "2026-06-16",
            "items": [{"name": "Widget", "price": 10.00, "quantity": 1, "category": "Other"}],
            "tax_amount": 0.50,
            "discount_amount": 0.0,
            "total_amount": 10.50,
            "currency": "USD",
        }
        service.client.messages.create.side_effect = [_mock_response(payload)]

        result, reconciled = service.extract_receipt_data(image_path, TEST_USER_EMAIL)

        assert service.client.messages.create.call_count == 1
        assert result == payload
        assert reconciled is True

    def test_tolerance_absorbs_rounding_noise(self, tmp_path):
        service, image_path = make_service(tmp_path)
        # sum(items) = 5.00, total = 5.01 -> 0.01 gap, under the 0.02 tolerance
        payload = {
            "store_name": "Rounding Store",
            "purchase_date": "2026-06-16",
            "items": [{"name": "Item", "price": 5.00, "quantity": 1, "category": "Other"}],
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 5.01,
            "currency": "USD",
        }
        service.client.messages.create.side_effect = [_mock_response(payload)]

        result, reconciled = service.extract_receipt_data(image_path, TEST_USER_EMAIL)

        assert service.client.messages.create.call_count == 1
        assert result == payload
        assert reconciled is True


class TestReconciliationRetry:

    def _mismatched_payload(self):
        # Mirrors the real SP-018 bug: one item's price is understated,
        # so sum(items) = 4.20 vs a printed total of 6.90 (2.70 gap).
        return {
            "store_name": "Shell Rautistrasse",
            "purchase_date": "2026-08-18",
            "items": [
                {"name": "MMSCThonsMex", "price": 3.20, "quantity": 1, "category": "Food & Groceries"},
                {"name": "TGFMLaugbrGruy190g", "price": 1.00, "quantity": 1, "category": "Food & Groceries"},
            ],
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 6.90,
            "currency": "CHF",
        }

    def _corrected_payload(self):
        return {
            "store_name": "Shell Rautistrasse",
            "purchase_date": "2026-08-18",
            "items": [
                {"name": "MMSCThonsMex", "price": 3.20, "quantity": 1, "category": "Food & Groceries"},
                {"name": "TGFMLaugbrGruy190g", "price": 3.70, "quantity": 1, "category": "Food & Groceries"},
            ],
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 6.90,
            "currency": "CHF",
        }

    def test_unreconciled_triggers_one_retry(self, tmp_path):
        service, image_path = make_service(tmp_path)
        first = self._mismatched_payload()
        second = self._corrected_payload()
        service.client.messages.create.side_effect = [_mock_response(first), _mock_response(second)]

        result, reconciled = service.extract_receipt_data(image_path, TEST_USER_EMAIL)

        assert service.client.messages.create.call_count == 2
        assert result == second
        assert reconciled is True

    def test_retry_prompt_contains_discrepancy(self, tmp_path):
        service, image_path = make_service(tmp_path)
        first = self._mismatched_payload()
        second = self._corrected_payload()
        service.client.messages.create.side_effect = [_mock_response(first), _mock_response(second)]

        service.extract_receipt_data(image_path, TEST_USER_EMAIL)

        retry_call = service.client.messages.create.call_args_list[1]
        retry_prompt = retry_call.kwargs["messages"][0]["content"][1]["text"]

        # computed sum = 4.20, expected total = 6.90, gap = 2.70
        assert "4.20" in retry_prompt
        assert "6.90" in retry_prompt
        assert "2.70" in retry_prompt

    def test_retry_capped_at_one_call(self, tmp_path):
        service, image_path = make_service(tmp_path)
        first = self._mismatched_payload()
        still_mismatched = self._mismatched_payload()  # second attempt still doesn't reconcile
        service.client.messages.create.side_effect = [
            _mock_response(first),
            _mock_response(still_mismatched),
        ]

        result, reconciled = service.extract_receipt_data(image_path, TEST_USER_EMAIL)

        assert service.client.messages.create.call_count == 2
        assert result == still_mismatched
        assert reconciled is False

    def test_retry_api_failure_keeps_first_result(self, tmp_path):
        service, image_path = make_service(tmp_path)
        first = self._mismatched_payload()
        service.client.messages.create.side_effect = [
            _mock_response(first),
            Exception("simulated transient API failure"),
        ]

        result, reconciled = service.extract_receipt_data(image_path, TEST_USER_EMAIL)

        assert service.client.messages.create.call_count == 2
        assert result == first
        assert reconciled is False


class TestUsageLogging:

    def _payload(self, total_amount=2.99):
        return {
            "store_name": "Test Mart",
            "purchase_date": "2026-06-16",
            "items": [{"name": "Milk", "price": 2.99, "quantity": 1, "category": "Food & Groceries"}],
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": total_amount,
            "currency": "USD",
        }

    def test_successful_call_logs_usage(self, tmp_path):
        logger = MagicMock()
        service, image_path = make_service(tmp_path, usage_logger=logger)
        payload = self._payload()
        service.client.messages.create.side_effect = [
            _mock_response(payload, input_tokens=1234, output_tokens=321)
        ]

        service.extract_receipt_data(image_path, TEST_USER_EMAIL)

        logger.log_call.assert_called_once_with(
            user_email=TEST_USER_EMAIL,
            model="test-model",
            input_tokens=1234,
            output_tokens=321,
            success=True,
            is_retry=False,
        )

    def test_retry_logs_two_calls_with_correct_is_retry_flags(self, tmp_path):
        logger = MagicMock()
        service, image_path = make_service(tmp_path, usage_logger=logger)
        mismatched = self._payload(total_amount=5.00)  # sum(items)=2.99, gap=2.01 -> retries
        corrected = self._payload(total_amount=2.99)  # sum(items)=2.99 -> reconciles
        service.client.messages.create.side_effect = [
            _mock_response(mismatched, input_tokens=100, output_tokens=20),
            _mock_response(corrected, input_tokens=150, output_tokens=25),
        ]

        service.extract_receipt_data(image_path, TEST_USER_EMAIL)

        assert logger.log_call.call_count == 2
        first_kwargs = logger.log_call.call_args_list[0].kwargs
        second_kwargs = logger.log_call.call_args_list[1].kwargs
        assert first_kwargs['is_retry'] is False
        assert first_kwargs['input_tokens'] == 100
        assert second_kwargs['is_retry'] is True
        assert second_kwargs['input_tokens'] == 150

    def test_api_call_failure_logs_zero_tokens(self, tmp_path):
        logger = MagicMock()
        service, image_path = make_service(tmp_path, usage_logger=logger)
        service.client.messages.create.side_effect = [Exception("network error")]

        with pytest.raises(Exception):
            service.extract_receipt_data(image_path, TEST_USER_EMAIL)

        logger.log_call.assert_called_once_with(
            user_email=TEST_USER_EMAIL,
            model="test-model",
            input_tokens=0,
            output_tokens=0,
            success=False,
            is_retry=False,
        )

    def test_parse_failure_after_response_logs_real_tokens(self, tmp_path):
        logger = MagicMock()
        service, image_path = make_service(tmp_path, usage_logger=logger)
        bad_response = MagicMock()
        bad_response.content = [MagicMock(text="This is not JSON at all")]
        bad_response.usage = MagicMock(input_tokens=500, output_tokens=10)
        service.client.messages.create.side_effect = [bad_response]

        with pytest.raises(Exception):
            service.extract_receipt_data(image_path, TEST_USER_EMAIL)

        logger.log_call.assert_called_once_with(
            user_email=TEST_USER_EMAIL,
            model="test-model",
            input_tokens=500,
            output_tokens=10,
            success=False,
            is_retry=False,
        )

    def test_no_usage_logger_does_not_error(self, tmp_path):
        service, image_path = make_service(tmp_path)  # usage_logger defaults to None
        payload = self._payload()
        service.client.messages.create.side_effect = [_mock_response(payload)]

        result, reconciled = service.extract_receipt_data(image_path, TEST_USER_EMAIL)
        assert result == payload
        assert reconciled is True


class TestStatementExtraction:

    def _transactions_payload(self):
        return {
            "transactions": [
                {"date": "2026-06-15", "description": "CORNER STORE #123", "amount": 12.50, "currency": "USD"},
                {"date": "2026-06-16", "description": "GAS STATION", "amount": 40.00, "currency": "USD"},
            ]
        }

    def test_extract_statement_transactions_returns_list_of_dicts(self, tmp_path, mocker):
        service, pdf_path = make_service(tmp_path)
        mocker.patch.object(service, "_extract_pdf_text", return_value="some statement text")
        payload = self._transactions_payload()
        service.client.messages.create.side_effect = [_mock_response(payload)]

        result = service.extract_statement_transactions(pdf_path, TEST_USER_EMAIL)

        assert result == payload["transactions"]

    def test_extract_statement_transactions_uses_text_only_content_block(self, tmp_path, mocker):
        service, pdf_path = make_service(tmp_path)
        mocker.patch.object(service, "_extract_pdf_text", return_value="some statement text")
        service.client.messages.create.side_effect = [_mock_response(self._transactions_payload())]

        service.extract_statement_transactions(pdf_path, TEST_USER_EMAIL)

        call = service.client.messages.create.call_args
        content_blocks = call.kwargs["messages"][0]["content"]
        assert all(block["type"] != "image" for block in content_blocks)
        assert any(block["type"] == "text" for block in content_blocks)

    def test_extract_statement_transactions_prompt_includes_valid_categories(self, tmp_path, mocker):
        # make_service(tmp_path) builds the service with valid_categories=["Food & Groceries", "Other"]
        service, pdf_path = make_service(tmp_path)
        mocker.patch.object(service, "_extract_pdf_text", return_value="some statement text")
        service.client.messages.create.side_effect = [_mock_response(self._transactions_payload())]

        service.extract_statement_transactions(pdf_path, TEST_USER_EMAIL)

        call = service.client.messages.create.call_args
        prompt_text = call.kwargs["messages"][0]["content"][0]["text"]
        assert "Food & Groceries" in prompt_text

    def test_extract_statement_transactions_preserves_direction_and_category(self, tmp_path, mocker):
        service, pdf_path = make_service(tmp_path)
        mocker.patch.object(service, "_extract_pdf_text", return_value="some statement text")
        payload = {
            "transactions": [
                {
                    "date": "2026-06-15", "description": "CORNER STORE #123", "amount": 12.50,
                    "currency": "USD", "direction": "credit", "category": "Food & Groceries",
                },
            ]
        }
        service.client.messages.create.side_effect = [_mock_response(payload)]

        result = service.extract_statement_transactions(pdf_path, TEST_USER_EMAIL)

        assert result[0]["direction"] == "credit"
        assert result[0]["category"] == "Food & Groceries"

    def test_extract_statement_transactions_logs_usage(self, tmp_path, mocker):
        logger = MagicMock()
        service, pdf_path = make_service(tmp_path, usage_logger=logger)
        mocker.patch.object(service, "_extract_pdf_text", return_value="some statement text")
        service.client.messages.create.side_effect = [
            _mock_response(self._transactions_payload(), input_tokens=300, output_tokens=80)
        ]

        service.extract_statement_transactions(pdf_path, TEST_USER_EMAIL)

        logger.log_call.assert_called_once_with(
            user_email=TEST_USER_EMAIL,
            model="test-model",
            input_tokens=300,
            output_tokens=80,
            success=True,
            is_retry=False,
        )

    def test_extract_statement_transactions_empty_pdf_raises_without_calling_api(self, tmp_path):
        service, _ = make_service(tmp_path)

        blank_pdf_path = tmp_path / "blank.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        with open(blank_pdf_path, "wb") as f:
            writer.write(f)

        with pytest.raises(ValueError):
            service.extract_statement_transactions(str(blank_pdf_path), TEST_USER_EMAIL)

        service.client.messages.create.assert_not_called()

    def test_extract_statement_transactions_missing_transactions_field_raises(self, tmp_path, mocker):
        service, pdf_path = make_service(tmp_path)
        mocker.patch.object(service, "_extract_pdf_text", return_value="some statement text")
        service.client.messages.create.side_effect = [_mock_response({"not_transactions": []})]

        with pytest.raises(Exception):
            service.extract_statement_transactions(pdf_path, TEST_USER_EMAIL)
