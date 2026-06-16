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
def mock_llm_service(mocker, sample_llm_response):
    mock = mocker.MagicMock()
    mock.extract_receipt_data.return_value = sample_llm_response
    mock.valid_categories = list(VALID_CATEGORIES)
    return mock


@pytest.fixture
def receipt_service(tmp_path, mock_llm_service):
    from app.database.json_db import JSONDatabase
    from app.services.receipt_service import ReceiptService

    db_path = str(tmp_path / "receipts.json")
    database = JSONDatabase(db_path)
    upload_folder = str(tmp_path / "uploads")

    return ReceiptService(
        database=database,
        llm_service=mock_llm_service,
        upload_folder=upload_folder,
        allowed_extensions={"jpg", "jpeg", "png"},
        valid_categories=list(VALID_CATEGORIES),
    )


@pytest.fixture
def app(tmp_path):
    from flask import Flask
    from app.database.json_db import JSONDatabase, CategoryDatabase
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

    db_path = str(tmp_path / "receipts.json")
    database = JSONDatabase(db_path)

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
