import io

import pytest
from PIL import Image as _PIL_Image
from werkzeug.datastructures import FileStorage

from app.services.transaction_matcher import TransactionMatcher

# Spec coverage:
#   TestTransactionMatcher -> backlog/SP-026-automatically-match-transactions-to-receipts.md
#   TestDateWindow         -> backlog/SP-045-allow-date-window-in-transaction-matching.md

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

        updated_receipt = receipt_service.get_receipt_by_id(receipt.receipt_id, TEST_USER_EMAIL)
        assert updated_receipt.linked_transaction_id == transactions[0].transaction_id

    def test_receipt_upload_links_to_existing_transaction(
        self, receipt_service, statement_service, matcher, mock_llm_service
    ):
        mock_llm_service.extract_statement_transactions.return_value = [
            {"date": "2026-06-15", "description": "Corner Store", "amount": 12.50, "currency": "USD"},
        ]
        transactions = statement_service.process_statement(make_pdf_file(), TEST_USER_EMAIL, "card")

        mock_llm_service.extract_receipt_data.return_value = (
            receipt_llm_data("Corner Store", "2026-06-15", 12.50), True
        )
        receipt, _, _ = receipt_service.process_receipt(make_image_file(), TEST_USER_EMAIL)

        updated_receipt = receipt_service.get_receipt_by_id(receipt.receipt_id, TEST_USER_EMAIL)
        assert updated_receipt.linked_transaction_id == transactions[0].transaction_id

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

        fetched = receipt_service.get_receipt_by_id(receipt.receipt_id, TEST_USER_EMAIL)
        assert fetched.linked_transaction_id is None
        fetched.total_amount = 25.00
        receipt_service.update_receipt(receipt.receipt_id, TEST_USER_EMAIL, fetched)

        updated_receipt = receipt_service.get_receipt_by_id(receipt.receipt_id, TEST_USER_EMAIL)
        assert updated_receipt.linked_transaction_id == transactions[0].transaction_id

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

        updated_receipt2 = receipt_service.get_receipt_by_id(receipt2.receipt_id, TEST_USER_EMAIL)
        updated_receipt1 = receipt_service.get_receipt_by_id(receipt1.receipt_id, TEST_USER_EMAIL)
        assert updated_receipt2.linked_transaction_id == transactions[0].transaction_id
        assert updated_receipt1.linked_transaction_id is None

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

        receipts = receipt_service.get_all_receipts(TEST_USER_EMAIL)
        assert all(r.linked_transaction_id is None for r in receipts)

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
        updated_receipt = receipt_service.get_receipt_by_id(receipt.receipt_id, TEST_USER_EMAIL)
        assert updated_receipt.linked_transaction_id == first_batch[0].transaction_id

        second_batch = statement_service.process_statement(make_pdf_file(), TEST_USER_EMAIL, "card")
        still_linked = receipt_service.get_receipt_by_id(receipt.receipt_id, TEST_USER_EMAIL)
        assert still_linked.linked_transaction_id == first_batch[0].transaction_id
        assert still_linked.linked_transaction_id != second_batch[0].transaction_id

    def test_no_candidates_no_error(
        self, receipt_service, statement_service, matcher, mock_llm_service
    ):
        mock_llm_service.extract_statement_transactions.return_value = [
            {"date": "2026-06-15", "description": "Corner Store", "amount": 12.50, "currency": "USD"},
        ]
        statement_service.process_statement(make_pdf_file(), TEST_USER_EMAIL, "card")

        mock_llm_service.extract_receipt_data.return_value = (
            receipt_llm_data("Unrelated Store", "2026-01-01", 99.99), True
        )
        receipt, draft_id, review_reason = receipt_service.process_receipt(make_image_file(), TEST_USER_EMAIL)
        assert review_reason is None
        assert receipt.receipt_id is not None

    def test_credit_direction_never_matches_statement_to_receipt(
        self, receipt_service, statement_service, matcher, mock_llm_service
    ):
        mock_llm_service.extract_receipt_data.return_value = (
            receipt_llm_data("Refund Store", "2026-06-15", 15.00), True
        )
        receipt_service.process_receipt(make_image_file(), TEST_USER_EMAIL)

        mock_llm_service.extract_statement_transactions.return_value = [
            {
                "date": "2026-06-15", "description": "Refund Store", "amount": 15.00,
                "currency": "USD", "direction": "credit",
            },
        ]
        transactions = statement_service.process_statement(make_pdf_file(), TEST_USER_EMAIL, "card")

        assert transactions[0].direction == "credit"
        receipts = receipt_service.get_all_receipts(TEST_USER_EMAIL)
        assert all(r.linked_transaction_id is None for r in receipts)

    def test_credit_direction_never_matches_receipt_to_statement(
        self, receipt_service, statement_service, matcher, mock_llm_service
    ):
        mock_llm_service.extract_statement_transactions.return_value = [
            {
                "date": "2026-06-15", "description": "Refund Store", "amount": 15.00,
                "currency": "USD", "direction": "credit",
            },
        ]
        statement_service.process_statement(make_pdf_file(), TEST_USER_EMAIL, "card")

        mock_llm_service.extract_receipt_data.return_value = (
            receipt_llm_data("Refund Store", "2026-06-15", 15.00), True
        )
        receipt_service.process_receipt(make_image_file(), TEST_USER_EMAIL)

        receipts = receipt_service.get_all_receipts(TEST_USER_EMAIL)
        assert all(r.linked_transaction_id is None for r in receipts)


RECEIPT_DATE = "2026-06-15"


class TestDateWindow:
    """
    A transaction matches a receipt when its date is between the receipt date
    and receipt date + 5 days (inclusive). Receipt date is 2026-06-15 and the
    amount is 12.50 throughout, so only the transaction date varies.
    """

    def _save_receipt(self, receipt_service, mock_llm_service, store="Corner Store", purchase_date=RECEIPT_DATE):
        mock_llm_service.extract_receipt_data.return_value = (
            receipt_llm_data(store, purchase_date, 12.50), True
        )
        receipt, _, _ = receipt_service.process_receipt(make_image_file(), TEST_USER_EMAIL)
        return receipt

    def _upload_statement(self, statement_service, mock_llm_service, tx_date, description="Corner Store"):
        mock_llm_service.extract_statement_transactions.return_value = [
            {"date": tx_date, "description": description, "amount": 12.50, "currency": "USD"},
        ]
        return statement_service.process_statement(make_pdf_file(), TEST_USER_EMAIL, "card")

    # --- Statement upload matching against an existing receipt ---------------

    @pytest.mark.parametrize("tx_date", [
        "2026-06-15",  # same day
        "2026-06-18",  # inside the window
        "2026-06-20",  # +5 days: last day of the window (inclusive)
    ])
    def test_statement_upload_matches_receipt_inside_window(
        self, receipt_service, statement_service, matcher, mock_llm_service, tx_date
    ):
        receipt = self._save_receipt(receipt_service, mock_llm_service)
        transactions = self._upload_statement(statement_service, mock_llm_service, tx_date)

        updated = receipt_service.get_receipt_by_id(receipt.receipt_id, TEST_USER_EMAIL)
        assert updated.linked_transaction_id == transactions[0].transaction_id

    @pytest.mark.parametrize("tx_date", [
        "2026-06-21",  # +6 days: one day past the window
        "2026-06-14",  # -1 day: before the receipt, never matches
    ])
    def test_statement_upload_ignores_receipt_outside_window(
        self, receipt_service, statement_service, matcher, mock_llm_service, tx_date
    ):
        receipt = self._save_receipt(receipt_service, mock_llm_service)
        self._upload_statement(statement_service, mock_llm_service, tx_date)

        updated = receipt_service.get_receipt_by_id(receipt.receipt_id, TEST_USER_EMAIL)
        assert updated.linked_transaction_id is None

    # --- Receipt save matching against an existing transaction ---------------

    @pytest.mark.parametrize("tx_date", ["2026-06-15", "2026-06-20"])
    def test_receipt_save_matches_transaction_inside_window(
        self, receipt_service, statement_service, matcher, mock_llm_service, tx_date
    ):
        transactions = self._upload_statement(statement_service, mock_llm_service, tx_date)
        receipt = self._save_receipt(receipt_service, mock_llm_service)

        updated = receipt_service.get_receipt_by_id(receipt.receipt_id, TEST_USER_EMAIL)
        assert updated.linked_transaction_id == transactions[0].transaction_id

    @pytest.mark.parametrize("tx_date", ["2026-06-21", "2026-06-14"])
    def test_receipt_save_ignores_transaction_outside_window(
        self, receipt_service, statement_service, matcher, mock_llm_service, tx_date
    ):
        self._upload_statement(statement_service, mock_llm_service, tx_date)
        receipt = self._save_receipt(receipt_service, mock_llm_service)

        updated = receipt_service.get_receipt_by_id(receipt.receipt_id, TEST_USER_EMAIL)
        assert updated.linked_transaction_id is None

    # --- Ambiguity inside the window -----------------------------------------

    def test_two_receipts_in_window_not_narrowed_stays_unlinked(
        self, receipt_service, statement_service, matcher, mock_llm_service
    ):
        # Same amount, different purchase dates, both within 5 days before the
        # transaction. Description matches neither store, so we must not guess.
        self._save_receipt(receipt_service, mock_llm_service, store="Corner Store", purchase_date="2026-06-15")
        self._save_receipt(receipt_service, mock_llm_service, store="Gas Station", purchase_date="2026-06-17")
        self._upload_statement(statement_service, mock_llm_service, "2026-06-19", description="Unrelated Merchant")

        receipts = receipt_service.get_all_receipts(TEST_USER_EMAIL)
        assert all(r.linked_transaction_id is None for r in receipts)

    def test_two_receipts_in_window_narrowed_by_store_name(
        self, receipt_service, statement_service, matcher, mock_llm_service
    ):
        receipt1 = self._save_receipt(receipt_service, mock_llm_service, store="Corner Store", purchase_date="2026-06-15")
        receipt2 = self._save_receipt(receipt_service, mock_llm_service, store="Gas Station", purchase_date="2026-06-17")
        transactions = self._upload_statement(
            statement_service, mock_llm_service, "2026-06-19", description="GAS STATION #55"
        )

        updated1 = receipt_service.get_receipt_by_id(receipt1.receipt_id, TEST_USER_EMAIL)
        updated2 = receipt_service.get_receipt_by_id(receipt2.receipt_id, TEST_USER_EMAIL)
        assert updated2.linked_transaction_id == transactions[0].transaction_id
        assert updated1.linked_transaction_id is None

    def test_receipt_outside_window_is_not_a_candidate_for_ambiguity(
        self, receipt_service, statement_service, matcher, mock_llm_service
    ):
        # Two same-amount receipts, but only one is inside the window of the
        # transaction, so there is no ambiguity and it links without a name match.
        in_window = self._save_receipt(receipt_service, mock_llm_service, store="Corner Store", purchase_date="2026-06-17")
        out_of_window = self._save_receipt(receipt_service, mock_llm_service, store="Gas Station", purchase_date="2026-06-10")
        transactions = self._upload_statement(
            statement_service, mock_llm_service, "2026-06-19", description="Unrelated Merchant"
        )

        updated_in = receipt_service.get_receipt_by_id(in_window.receipt_id, TEST_USER_EMAIL)
        updated_out = receipt_service.get_receipt_by_id(out_of_window.receipt_id, TEST_USER_EMAIL)
        assert updated_in.linked_transaction_id == transactions[0].transaction_id
        assert updated_out.linked_transaction_id is None
