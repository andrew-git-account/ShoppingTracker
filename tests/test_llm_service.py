import io
import json
from unittest.mock import MagicMock

import pytest
from PIL import Image as _PIL_Image

from app.services.llm_service import LLMService

# Spec coverage:
#   TestReconciliationSingleCall -> SP-018 (no retry when the extraction already reconciles)
#   TestReconciliationRetry      -> SP-018 (retry once, with the discrepancy, on mismatch)

# Tiny 1x1 white JPEG — small enough to skip compression, valid enough for _encode_image
_buf = io.BytesIO()
_PIL_Image.new("RGB", (1, 1), (255, 255, 255)).save(_buf, "JPEG")
TINY_JPEG = _buf.getvalue()


def _mock_response(payload: dict) -> MagicMock:
    """Build a fake Anthropic response whose text matches what _parse_response expects."""
    resp = MagicMock()
    text = "Step 1 transcription...\n\n```json\n" + json.dumps(payload) + "\n```"
    resp.content = [MagicMock(text=text)]
    return resp


def make_service(tmp_path) -> tuple:
    """Create an LLMService with a mocked Anthropic client and a real tiny image on disk."""
    service = LLMService(api_key="test-key", model="test-model", valid_categories=["Food & Groceries", "Other"])
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

        result = service.extract_receipt_data(image_path)

        assert service.client.messages.create.call_count == 1
        assert result == payload

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

        result = service.extract_receipt_data(image_path)

        assert service.client.messages.create.call_count == 1
        assert result == payload

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

        result = service.extract_receipt_data(image_path)

        assert service.client.messages.create.call_count == 1
        assert result == payload


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

        result = service.extract_receipt_data(image_path)

        assert service.client.messages.create.call_count == 2
        assert result == second

    def test_retry_prompt_contains_discrepancy(self, tmp_path):
        service, image_path = make_service(tmp_path)
        first = self._mismatched_payload()
        second = self._corrected_payload()
        service.client.messages.create.side_effect = [_mock_response(first), _mock_response(second)]

        service.extract_receipt_data(image_path)

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

        result = service.extract_receipt_data(image_path)

        assert service.client.messages.create.call_count == 2
        assert result == still_mismatched

    def test_retry_api_failure_keeps_first_result(self, tmp_path):
        service, image_path = make_service(tmp_path)
        first = self._mismatched_payload()
        service.client.messages.create.side_effect = [
            _mock_response(first),
            Exception("simulated transient API failure"),
        ]

        result = service.extract_receipt_data(image_path)

        assert service.client.messages.create.call_count == 2
        assert result == first
