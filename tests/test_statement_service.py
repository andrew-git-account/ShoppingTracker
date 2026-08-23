import io

import pytest
from werkzeug.datastructures import FileStorage

# Spec coverage:
#   TestStatementServiceProcessStatement -> SP-025 (statement upload -> transaction extraction/storage)

TEST_USER_EMAIL = "owner@example.com"


def make_pdf_file_storage(content: bytes = b"%PDF-1.4 fake", filename: str = "statement.pdf") -> FileStorage:
    return FileStorage(
        stream=io.BytesIO(content),
        filename=filename,
        content_type="application/pdf",
    )


class TestStatementServiceProcessStatement:

    def test_process_statement_saves_one_transaction_per_extracted_line(self, statement_service, mock_llm_service):
        mock_llm_service.extract_statement_transactions.return_value = [
            {"date": "2026-06-15", "description": "Corner Store", "amount": 12.50, "currency": "USD"},
            {"date": "2026-06-16", "description": "Gas Station", "amount": 40.00, "currency": "USD"},
        ]

        transactions = statement_service.process_statement(make_pdf_file_storage(), TEST_USER_EMAIL, "card")

        assert len(transactions) == 2
        assert all(t.transaction_id is not None for t in transactions)
        saved = statement_service.transaction_service.get_all_transactions(TEST_USER_EMAIL)
        assert len(saved) == 2
        assert {t.description for t in saved} == {"Corner Store", "Gas Station"}

    def test_process_statement_tags_source_and_user(self, statement_service, mock_llm_service):
        mock_llm_service.extract_statement_transactions.return_value = [
            {"date": "2026-06-15", "description": "Corner Store", "amount": 12.50, "currency": "USD"},
        ]

        statement_service.process_statement(make_pdf_file_storage(), TEST_USER_EMAIL, "bank")

        saved = statement_service.transaction_service.get_all_transactions(TEST_USER_EMAIL)
        assert saved[0].source == "bank"
        assert saved[0].user_email == TEST_USER_EMAIL

    def test_process_statement_invalid_extension_rejected(self, statement_service):
        with pytest.raises(ValueError, match="Invalid file type"):
            statement_service.process_statement(
                make_pdf_file_storage(filename="statement.txt", content=b"not a pdf"),
                TEST_USER_EMAIL,
                "card",
            )

    def test_process_statement_amount_defaults_to_zero_when_missing(self, statement_service, mock_llm_service):
        mock_llm_service.extract_statement_transactions.return_value = [
            {"date": "2026-06-15", "description": "Corner Store", "currency": "USD"},
        ]

        transactions = statement_service.process_statement(make_pdf_file_storage(), TEST_USER_EMAIL, "card")

        assert transactions[0].amount == 0.0

    def test_process_statement_currency_defaults_to_usd_when_missing(self, statement_service, mock_llm_service):
        mock_llm_service.extract_statement_transactions.return_value = [
            {"date": "2026-06-15", "description": "Corner Store", "amount": 5.00},
        ]

        transactions = statement_service.process_statement(make_pdf_file_storage(), TEST_USER_EMAIL, "card")

        assert transactions[0].currency == "USD"

    def test_process_statement_returns_empty_list_when_no_transactions_extracted(
        self, statement_service, mock_llm_service
    ):
        mock_llm_service.extract_statement_transactions.return_value = []

        transactions = statement_service.process_statement(make_pdf_file_storage(), TEST_USER_EMAIL, "card")

        assert transactions == []
        assert statement_service.transaction_service.get_all_transactions(TEST_USER_EMAIL) == []

    def test_process_statement_valid_direction_and_category_preserved(self, statement_service, mock_llm_service):
        mock_llm_service.extract_statement_transactions.return_value = [
            {
                "date": "2026-06-15", "description": "Corner Store", "amount": 12.50, "currency": "USD",
                "direction": "credit", "category": "Food & Groceries",
            },
        ]

        transactions = statement_service.process_statement(make_pdf_file_storage(), TEST_USER_EMAIL, "card")

        assert transactions[0].direction == "credit"
        assert transactions[0].category == "Food & Groceries"

    def test_process_statement_direction_defaults_to_debit_when_missing(self, statement_service, mock_llm_service):
        mock_llm_service.extract_statement_transactions.return_value = [
            {"date": "2026-06-15", "description": "Corner Store", "amount": 12.50, "currency": "USD"},
        ]

        transactions = statement_service.process_statement(make_pdf_file_storage(), TEST_USER_EMAIL, "card")

        assert transactions[0].direction == "debit"

    def test_process_statement_invalid_direction_defaults_to_debit(self, statement_service, mock_llm_service):
        mock_llm_service.extract_statement_transactions.return_value = [
            {
                "date": "2026-06-15", "description": "Corner Store", "amount": 12.50, "currency": "USD",
                "direction": "sideways",
            },
        ]

        transactions = statement_service.process_statement(make_pdf_file_storage(), TEST_USER_EMAIL, "card")

        assert transactions[0].direction == "debit"

    def test_process_statement_category_defaults_to_other_when_missing(self, statement_service, mock_llm_service):
        mock_llm_service.extract_statement_transactions.return_value = [
            {"date": "2026-06-15", "description": "Corner Store", "amount": 12.50, "currency": "USD"},
        ]

        transactions = statement_service.process_statement(make_pdf_file_storage(), TEST_USER_EMAIL, "card")

        assert transactions[0].category == "Other"

    def test_process_statement_unrecognized_category_falls_back_to_other(self, statement_service, mock_llm_service):
        mock_llm_service.extract_statement_transactions.return_value = [
            {
                "date": "2026-06-15", "description": "Corner Store", "amount": 12.50, "currency": "USD",
                "category": "Nonsense",
            },
        ]

        transactions = statement_service.process_statement(make_pdf_file_storage(), TEST_USER_EMAIL, "card")

        assert transactions[0].category == "Other"
