import io

import pytest
from PIL import Image as _PIL_Image
from werkzeug.datastructures import FileStorage

from app.services.transaction_matcher import TransactionMatcher

# Spec coverage:
#   TestTransactionMatcher -> backlog/SP-026-automatically-match-transactions-to-receipts.md

TEST_USER_EMAIL = "owner@example.com"

# Tiny 1x1 white JPEG - small enough to skip compression, valid enough for Pillow
_buf = io.BytesIO()
_PIL_Image.new("RGB", (1, 1), (255, 255, 255)).save(_buf, "JPEG")
TINY_JPEG = _buf.getvalue()


def make_image_file(filename: str = "receipt.jpg") -> FileStorage:
    return FileStorage(stream=io.BytesIO(TINY_JPEG), filename=filename, content_type="image/jpeg")


def make_pdf_file(filename: str = "statement.pdf") -> FileStorage:
    return FileStorage(stream=io.BytesIO(b"%PDF-1.4 fake"), filename=filename, content_type="application/pdf")


def receipt_llm_data(store_name: str, purchase_date: str, total_amount: float, currency: str = "USD") -> dict:
    """Minimal LLM response shape that passes Receipt.validate() unchanged."""
    return {
        "store_name": store_name,
        "purchase_date": purchase_date,
        "items": [{"name": "Item", "price": total_amount, "quantity": 1, "category": "Other"}],
        "tax_amount": 0.0,
        "discount_amount": 0.0,
        "total_amount": total_amount,
        "currency": currency,
    }


@pytest.fixture
def matcher(receipt_service, statement_service):
    """
    Wires a TransactionMatcher onto the (independently-built) receipt_service/
    statement_service fixtures, the same way app/main.py does post-construction.
    """
    m = TransactionMatcher(
        receipt_service=receipt_service,
        transaction_service=statement_service.transaction_service,
    )
    receipt_service.matcher = m
    statement_service.matcher = m
    return m


class TestTransactionMatcher:

    def test_statement_upload_links_to_existing_receipt(
        self, receipt_service, statement_service, matcher, mock_llm_service
    ):
        mock_llm_service.extract_receipt_data.return_value = (
            receipt_llm_data("Corner Store", "2026-06-15", 12.50), True
        )
        receipt, draft_id, review_reason = receipt_service.process_receipt(make_image_file(), TEST_USER_EMAIL)
        assert review_reason is None

        mock_llm_service.extract_statement_transactions.return_value = [
            {"date": "2026-06-15", "description": "CORNER STORE #123", "amount": 12.50, "currency": "USD"},
        ]
        transactions = statement_service.process_statement(make_pdf_file(), TEST_USER_EMAIL, "card")

        assert transactions[0].linked_receipt_id == receipt.receipt_id

    def test_receipt_upload_links_to_existing_transaction(
        self, receipt_service, statement_service, matcher, mock_llm_service
    ):
        mock_llm_service.extract_statement_transactions.return_value = [
            {"date": "2026-06-15", "description": "Corner Store", "amount": 12.50, "currency": "USD"},
        ]
        transactions = statement_service.process_statement(make_pdf_file(), TEST_USER_EMAIL, "card")
        assert transactions[0].linked_receipt_id is None

        mock_llm_service.extract_receipt_data.return_value = (
            receipt_llm_data("Corner Store", "2026-06-15", 12.50), True
        )
        receipt, _, _ = receipt_service.process_receipt(make_image_file(), TEST_USER_EMAIL)

        updated = statement_service.transaction_service.get_all_transactions(TEST_USER_EMAIL)
        assert updated[0].linked_receipt_id == receipt.receipt_id

    def test_receipt_edit_creates_new_match(
        self, receipt_service, statement_service, matcher, mock_llm_service
    ):
        mock_llm_service.extract_receipt_data.return_value = (
            receipt_llm_data("Store A", "2026-06-15", 10.00), True
        )
        receipt, _, _ = receipt_service.process_receipt(make_image_file(), TEST_USER_EMAIL)

        mock_llm_service.extract_statement_transactions.return_value = [
            {"date": "2026-06-15", "description": "Store A", "amount": 25.00, "currency": "USD"},
        ]
        transactions = statement_service.process_statement(make_pdf_file(), TEST_USER_EMAIL, "card")
        assert transactions[0].linked_receipt_id is None

        fetched = receipt_service.get_receipt_by_id(receipt.receipt_id, TEST_USER_EMAIL)
        fetched.total_amount = 25.00
        receipt_service.update_receipt(receipt.receipt_id, TEST_USER_EMAIL, fetched)

        updated = statement_service.transaction_service.get_all_transactions(TEST_USER_EMAIL)
        assert updated[0].linked_receipt_id == receipt.receipt_id

    def test_ambiguous_amount_narrowed_by_store_name_substring(
        self, receipt_service, statement_service, matcher, mock_llm_service
    ):
        mock_llm_service.extract_receipt_data.return_value = (
            receipt_llm_data("Corner Store", "2026-06-15", 20.00), True
        )
        receipt1, _, _ = receipt_service.process_receipt(make_image_file(), TEST_USER_EMAIL)

        mock_llm_service.extract_receipt_data.return_value = (
            receipt_llm_data("Gas Station", "2026-06-15", 20.00), True
        )
        receipt2, _, _ = receipt_service.process_receipt(make_image_file(), TEST_USER_EMAIL)

        mock_llm_service.extract_statement_transactions.return_value = [
            {"date": "2026-06-15", "description": "GAS STATION #55", "amount": 20.00, "currency": "USD"},
        ]
        transactions = statement_service.process_statement(make_pdf_file(), TEST_USER_EMAIL, "card")

        assert transactions[0].linked_receipt_id == receipt2.receipt_id
        assert transactions[0].linked_receipt_id != receipt1.receipt_id

    def test_ambiguous_amount_not_narrowed_stays_unlinked(
        self, receipt_service, statement_service, matcher, mock_llm_service
    ):
        mock_llm_service.extract_receipt_data.return_value = (
            receipt_llm_data("Corner Store", "2026-06-15", 20.00), True
        )
        receipt_service.process_receipt(make_image_file(), TEST_USER_EMAIL)

        mock_llm_service.extract_receipt_data.return_value = (
            receipt_llm_data("Gas Station", "2026-06-15", 20.00), True
        )
        receipt_service.process_receipt(make_image_file(), TEST_USER_EMAIL)

        mock_llm_service.extract_statement_transactions.return_value = [
            {"date": "2026-06-15", "description": "Unrelated Merchant", "amount": 20.00, "currency": "USD"},
        ]
        transactions = statement_service.process_statement(make_pdf_file(), TEST_USER_EMAIL, "card")

        assert transactions[0].linked_receipt_id is None

    def test_one_to_one_no_relink(
        self, receipt_service, statement_service, matcher, mock_llm_service
    ):
        mock_llm_service.extract_receipt_data.return_value = (
            receipt_llm_data("Corner Store", "2026-06-15", 12.50), True
        )
        receipt, _, _ = receipt_service.process_receipt(make_image_file(), TEST_USER_EMAIL)

        mock_llm_service.extract_statement_transactions.return_value = [
            {"date": "2026-06-15", "description": "Corner Store", "amount": 12.50, "currency": "USD"},
        ]
        first_batch = statement_service.process_statement(make_pdf_file(), TEST_USER_EMAIL, "card")
        assert first_batch[0].linked_receipt_id == receipt.receipt_id

        second_batch = statement_service.process_statement(make_pdf_file(), TEST_USER_EMAIL, "card")
        assert second_batch[0].linked_receipt_id is None

        all_transactions = statement_service.transaction_service.get_all_transactions(TEST_USER_EMAIL)
        still_linked_to_receipt = [t for t in all_transactions if t.linked_receipt_id == receipt.receipt_id]
        assert len(still_linked_to_receipt) == 1

    def test_no_candidates_no_error(
        self, receipt_service, statement_service, matcher, mock_llm_service
    ):
        mock_llm_service.extract_statement_transactions.return_value = [
            {"date": "2026-06-15", "description": "Corner Store", "amount": 12.50, "currency": "USD"},
        ]
        transactions = statement_service.process_statement(make_pdf_file(), TEST_USER_EMAIL, "card")
        assert transactions[0].linked_receipt_id is None

        mock_llm_service.extract_receipt_data.return_value = (
            receipt_llm_data("Unrelated Store", "2026-01-01", 99.99), True
        )
        receipt, draft_id, review_reason = receipt_service.process_receipt(make_image_file(), TEST_USER_EMAIL)
        assert review_reason is None
        assert receipt.receipt_id is not None

    def test_credit_direction_still_matches(
        self, receipt_service, statement_service, matcher, mock_llm_service
    ):
        mock_llm_service.extract_receipt_data.return_value = (
            receipt_llm_data("Refund Store", "2026-06-15", 15.00), True
        )
        receipt, _, _ = receipt_service.process_receipt(make_image_file(), TEST_USER_EMAIL)

        mock_llm_service.extract_statement_transactions.return_value = [
            {
                "date": "2026-06-15", "description": "Refund Store", "amount": 15.00,
                "currency": "USD", "direction": "credit",
            },
        ]
        transactions = statement_service.process_statement(make_pdf_file(), TEST_USER_EMAIL, "card")

        assert transactions[0].direction == "credit"
        assert transactions[0].linked_receipt_id == receipt.receipt_id
