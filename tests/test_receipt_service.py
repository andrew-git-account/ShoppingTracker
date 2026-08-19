import io

import pytest
from PIL import Image as _PIL_Image
from werkzeug.datastructures import FileStorage

# Spec coverage:
#   TestReceiptServiceProcessWithCategories -> BehaviorSpec.md BS-001, BS-002, BS-011, BS-012
#   TestReceiptServiceSoftDelete            -> BehaviorSpec.md BS-008

# Tiny 1x1 white JPEG — small enough to skip compression, valid enough for Pillow
_buf = io.BytesIO()
_PIL_Image.new("RGB", (1, 1), (255, 255, 255)).save(_buf, "JPEG")
TINY_JPEG = _buf.getvalue()

TEST_USER_EMAIL = "owner@example.com"


def make_file_storage(content: bytes = TINY_JPEG, filename: str = "test.jpg") -> FileStorage:
    return FileStorage(
        stream=io.BytesIO(content),
        filename=filename,
        content_type="image/jpeg",
    )


class TestReceiptServiceProcessWithCategories:

    def test_valid_category_saved_to_db(self, receipt_service, mock_llm_service):
        mock_llm_service.extract_receipt_data.return_value = {
            "store_name": "Grocery Co",
            "purchase_date": "2026-06-16",
            "items": [{"name": "Bread", "price": 3.00, "quantity": 1, "category": "Food & Groceries"}],
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 3.00,
            "currency": "USD",
        }
        receipt = receipt_service.process_receipt(make_file_storage(), TEST_USER_EMAIL)

        assert receipt.items[0].category == "Food & Groceries"
        saved = receipt_service.database.get_receipt_by_id(receipt.receipt_id, TEST_USER_EMAIL)
        assert saved["items"][0]["category"] == "Food & Groceries"

    def test_invalid_category_falls_back_in_saved_receipt(self, receipt_service, mock_llm_service):
        mock_llm_service.extract_receipt_data.return_value = {
            "store_name": "Misc Store",
            "purchase_date": "2026-06-16",
            "items": [{"name": "Widget", "price": 5.00, "quantity": 1, "category": "Nonsense"}],
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 5.00,
            "currency": "USD",
        }
        receipt = receipt_service.process_receipt(make_file_storage(), TEST_USER_EMAIL)

        assert receipt.items[0].category == "Other"
        saved = receipt_service.database.get_receipt_by_id(receipt.receipt_id, TEST_USER_EMAIL)
        assert saved["items"][0]["category"] == "Other"

    def test_missing_category_from_llm_falls_back(self, receipt_service, mock_llm_service):
        mock_llm_service.extract_receipt_data.return_value = {
            "store_name": "Store",
            "purchase_date": "2026-06-16",
            "items": [{"name": "Soap", "price": 1.50, "quantity": 1}],
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 1.50,
            "currency": "USD",
        }
        receipt = receipt_service.process_receipt(make_file_storage(), TEST_USER_EMAIL)
        assert receipt.items[0].category == "Other"

    def test_multiple_items_categories_all_saved(self, receipt_service, mock_llm_service):
        mock_llm_service.extract_receipt_data.return_value = {
            "store_name": "Superstore",
            "purchase_date": "2026-06-16",
            "items": [
                {"name": "Milk", "price": 2.99, "quantity": 1, "category": "Food & Groceries"},
                {"name": "Shampoo", "price": 5.49, "quantity": 1, "category": "Personal Care & Health"},
                {"name": "Cable", "price": 9.99, "quantity": 1, "category": "Electronics & Tech"},
            ],
            "tax_amount": 0.50,
            "discount_amount": 0.0,
            "total_amount": 18.97,
            "currency": "USD",
        }
        receipt = receipt_service.process_receipt(make_file_storage(), TEST_USER_EMAIL)
        categories = [item.category for item in receipt.items]
        assert categories == ["Food & Groceries", "Personal Care & Health", "Electronics & Tech"]

    def test_invalid_file_extension_rejected(self, receipt_service):
        with pytest.raises(ValueError, match="Invalid file type"):
            receipt_service.process_receipt(
                make_file_storage(filename="receipt.pdf", content=b"%PDF"), TEST_USER_EMAIL
            )

    def test_process_receipt_tags_receipt_with_given_user_email(self, receipt_service, mock_llm_service):
        mock_llm_service.extract_receipt_data.return_value = {
            "store_name": "Grocery Co",
            "purchase_date": "2026-06-16",
            "items": [{"name": "Bread", "price": 3.00, "quantity": 1, "category": "Food & Groceries"}],
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 3.00,
            "currency": "USD",
        }
        receipt = receipt_service.process_receipt(make_file_storage(), TEST_USER_EMAIL)

        assert receipt.user_email == TEST_USER_EMAIL
        saved = receipt_service.database.get_receipt_by_id(receipt.receipt_id, TEST_USER_EMAIL)
        assert saved["user_email"] == TEST_USER_EMAIL


class TestReceiptServiceSoftDelete:

    def test_soft_delete_delegates_to_database(self, receipt_service):
        rid = receipt_service.database.save_receipt({
            "store_name": "Deli",
            "purchase_date": "2026-06-17",
            "items": [{"name": "Sandwich", "price": 5.00, "quantity": 1, "category": "Food & Groceries"}],
            "subtotal": 5.00,
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 5.00,
            "currency": "USD",
            "user_email": TEST_USER_EMAIL,
        })
        result = receipt_service.soft_delete_receipt(rid, TEST_USER_EMAIL)
        assert result is True
        all_ids = [r.receipt_id for r in receipt_service.get_all_receipts(TEST_USER_EMAIL)]
        assert rid not in all_ids

    def test_soft_delete_does_not_delegate_across_users(self, receipt_service):
        rid = receipt_service.database.save_receipt({
            "store_name": "Deli",
            "purchase_date": "2026-06-17",
            "items": [{"name": "Sandwich", "price": 5.00, "quantity": 1, "category": "Food & Groceries"}],
            "subtotal": 5.00,
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 5.00,
            "currency": "USD",
            "user_email": TEST_USER_EMAIL,
        })
        result = receipt_service.soft_delete_receipt(rid, "someone-else@example.com")
        assert result is False
        all_ids = [r.receipt_id for r in receipt_service.get_all_receipts(TEST_USER_EMAIL)]
        assert rid in all_ids
