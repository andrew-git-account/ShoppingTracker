import io
import json
import os
from unittest.mock import MagicMock

import pytest

collect_ignore = ["test_setup.py"]

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

VALID_CATEGORIES = [
    "Other",
    "Food & Groceries",
    "Household & Cleaning",
    "Personal Care & Health",
    "Electronics & Tech",
    "Clothing & Apparel",
    "Dining & Takeout",
]

SAMPLE_LLM_RESPONSE = {
    "store_name": "Test Mart",
    "purchase_date": "2026-06-16",
    "items": [
        {"name": "Milk", "price": 2.99, "quantity": 1, "category": "Food & Groceries"},
        {"name": "Shampoo", "price": 5.49, "quantity": 1, "category": "Personal Care & Health"},
    ],
    "tax_amount": 0.50,
    "discount_amount": 0.0,
    "total_amount": 8.98,
    "currency": "USD",
}

SAMPLE_RECEIPT_DICT = {
    "id": "test-receipt-001",
    "store_name": "Test Mart",
    "purchase_date": "2026-06-16",
    "items": [
        {"name": "Milk", "price": 2.99, "quantity": 1, "category": "Food & Groceries"},
        {"name": "Shampoo", "price": 5.49, "quantity": 1, "category": "Personal Care & Health"},
    ],
    "subtotal": 8.48,
    "tax_amount": 0.50,
    "discount_amount": 0.0,
    "total_amount": 8.98,
    "saved_at": "2026-06-16T10:00:00",
    "currency": "USD",
}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_categories():
    return list(VALID_CATEGORIES)


@pytest.fixture
def sample_llm_response():
    return dict(SAMPLE_LLM_RESPONSE)


@pytest.fixture
def sample_receipt_dict():
    return dict(SAMPLE_RECEIPT_DICT)


@pytest.fixture
def tmp_data_dir(tmp_path):
    return tmp_path


@pytest.fixture
def categories_file(tmp_data_dir):
    return str(tmp_data_dir / "categories.json")


@pytest.fixture
def receipts_file(tmp_data_dir):
    path = str(tmp_data_dir / "receipts.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump([], f)
    return path


@pytest.fixture
def receipts_db_path(tmp_data_dir):
    """
    Path for a SqliteDatabase under test (see SP-034) - deliberately does
    NOT pre-create the file, unlike receipts_file above: SqliteDatabase's
    own initialize() must be the first thing to touch the path, since a
    pre-existing non-SQLite file (e.g. receipts_file's literal b"[]") would
    make initialize() raise sqlite3.DatabaseError: file is not a database.
    """
    return str(tmp_data_dir / "receipts.db")


@pytest.fixture
def transactions_db_path(tmp_data_dir):
    """Path for a SqliteTransactionDatabase under test (see SP-035) - same
    not-pre-created reasoning as receipts_db_path above."""
    return str(tmp_data_dir / "transactions.db")


@pytest.fixture
def categories_db_path(tmp_data_dir):
    """Path for a SqliteCategoryDatabase under test (see SP-036) - same
    not-pre-created reasoning as receipts_db_path above."""
    return str(tmp_data_dir / "categories.db")


@pytest.fixture
def usage_log_db_path(tmp_data_dir):
    """Path for a SqliteUsageLogDatabase under test (see SP-036) - same
    not-pre-created reasoning as receipts_db_path above."""
    return str(tmp_data_dir / "usage_log.db")


@pytest.fixture
def mock_llm_service(mocker, sample_llm_response):
    mock = mocker.MagicMock()
    mock.extract_receipt_data.return_value = (sample_llm_response, True)
    mock.valid_categories = list(VALID_CATEGORIES)
    return mock


@pytest.fixture
def receipt_service(tmp_path, mock_llm_service):
    from app.database.sqlite_db import SqliteDatabase
    from app.services.receipt_service import ReceiptService

    db_path = str(tmp_path / "receipts.db")
    database = SqliteDatabase(db_path)
    upload_folder = str(tmp_path / "uploads")

    return ReceiptService(
        database=database,
        llm_service=mock_llm_service,
        upload_folder=upload_folder,
        allowed_extensions={"jpg", "jpeg", "png"},
        valid_categories=list(VALID_CATEGORIES),
    )


@pytest.fixture
def statement_service(tmp_path, mock_llm_service):
    from app.database.sqlite_transaction_db import SqliteTransactionDatabase
    from app.services.transaction_service import TransactionService
    from app.services.statement_service import StatementService

    db_path = str(tmp_path / "transactions.db")
    transaction_db = SqliteTransactionDatabase(db_path)
    transaction_service = TransactionService(database=transaction_db)
    upload_folder = str(tmp_path / "uploads")

    return StatementService(
        transaction_service=transaction_service,
        llm_service=mock_llm_service,
        upload_folder=upload_folder,
        allowed_extensions={"pdf"},
        valid_categories=list(VALID_CATEGORIES),
    )


@pytest.fixture
def app(tmp_path):
    from flask import Flask
    from app.database.json_db import CategoryDatabase
    from app.database.sqlite_db import SqliteDatabase
    from app.services.receipt_service import ReceiptService

    project_root = os.path.dirname(os.path.abspath(__file__))

    flask_app = Flask(
        "test",
        template_folder=os.path.join(project_root, "templates"),
        static_folder=os.path.join(project_root, "static"),
    )
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"

    cat_path = str(tmp_path / "categories.json")
    category_db = CategoryDatabase(cat_path)
    category_db.initialize()
    categories = [c["name"] for c in category_db.get_all_categories()]

    db_path = str(tmp_path / "receipts.db")
    database = SqliteDatabase(db_path)

    fake_llm = MagicMock()
    fake_llm.valid_categories = categories

    upload_folder = str(tmp_path / "uploads")
    receipt_service = ReceiptService(
        database=database,
        llm_service=fake_llm,
        upload_folder=upload_folder,
        allowed_extensions={"jpg", "jpeg", "png"},
        valid_categories=categories,
    )

    flask_app.receipt_service = receipt_service
    flask_app.database = database

    from app import routes
    routes.register_routes(flask_app)

    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()
