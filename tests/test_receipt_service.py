import io

import pytest
from PIL import Image as _PIL_Image
from werkzeug.datastructures import FileStorage

from app.models import Receipt, ReceiptItem

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
        receipt, draft_id = receipt_service.process_receipt(make_file_storage(), TEST_USER_EMAIL)

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
        receipt, draft_id = receipt_service.process_receipt(make_file_storage(), TEST_USER_EMAIL)

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
        receipt, draft_id = receipt_service.process_receipt(make_file_storage(), TEST_USER_EMAIL)
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
        receipt, draft_id = receipt_service.process_receipt(make_file_storage(), TEST_USER_EMAIL)
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
        receipt, draft_id = receipt_service.process_receipt(make_file_storage(), TEST_USER_EMAIL)

        assert receipt.user_email == TEST_USER_EMAIL
        saved = receipt_service.database.get_receipt_by_id(receipt.receipt_id, TEST_USER_EMAIL)
        assert saved["user_email"] == TEST_USER_EMAIL


class TestReceiptServiceDraft:
    """SP-023: 'Edit before saving' draft mechanism on ReceiptService."""

    def _create_draft(self, receipt_service, mock_llm_service, **overrides):
        payload = {
            "store_name": "Corner Store",
            "purchase_date": "2026-06-16",
            "items": [{"name": "Gum", "price": 1.00, "quantity": 1, "category": "Food & Groceries"}],
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 1.00,
            "currency": "USD",
        }
        payload.update(overrides)
        mock_llm_service.extract_receipt_data.return_value = payload
        receipt, draft_id = receipt_service.process_receipt(
            make_file_storage(), TEST_USER_EMAIL, edit_before_save=True
        )
        assert receipt is None
        return draft_id

    def test_process_receipt_edit_before_save_returns_draft_not_receipt(self, receipt_service, mock_llm_service):
        receipt, draft_id = receipt_service.process_receipt(
            make_file_storage(), TEST_USER_EMAIL, edit_before_save=True
        )
        assert receipt is None
        assert draft_id is not None

    def test_process_receipt_default_still_returns_none_draft_id(self, receipt_service, mock_llm_service):
        receipt, draft_id = receipt_service.process_receipt(make_file_storage(), TEST_USER_EMAIL)
        assert receipt is not None
        assert draft_id is None

    def test_draft_not_saved_to_database(self, receipt_service, mock_llm_service):
        self._create_draft(receipt_service, mock_llm_service)
        assert receipt_service.get_receipts_count(TEST_USER_EMAIL) == 0

    def test_get_draft_returns_receipt_with_extracted_data(self, receipt_service, mock_llm_service):
        draft_id = self._create_draft(receipt_service, mock_llm_service, store_name="Corner Store")
        draft = receipt_service.get_draft(draft_id, TEST_USER_EMAIL)
        assert draft is not None
        assert draft.store_name == "Corner Store"
        assert draft.items[0].name == "Gum"

    def test_get_draft_returns_none_for_wrong_owner(self, receipt_service, mock_llm_service):
        draft_id = self._create_draft(receipt_service, mock_llm_service)
        assert receipt_service.get_draft(draft_id, "someone-else@example.com") is None

    def test_get_draft_returns_none_for_unknown_id(self, receipt_service):
        assert receipt_service.get_draft("nonexistent-id", TEST_USER_EMAIL) is None

    def test_save_draft_creates_receipt_and_deletes_draft_file(self, receipt_service, mock_llm_service):
        draft_id = self._create_draft(receipt_service, mock_llm_service)
        draft = receipt_service.get_draft(draft_id, TEST_USER_EMAIL)

        saved = receipt_service.save_draft(draft_id, TEST_USER_EMAIL, draft)

        assert saved is not None
        assert saved.receipt_id is not None
        assert receipt_service.get_receipts_count(TEST_USER_EMAIL) == 1
        assert receipt_service.get_draft(draft_id, TEST_USER_EMAIL) is None

    def test_save_draft_returns_none_for_wrong_owner(self, receipt_service, mock_llm_service):
        draft_id = self._create_draft(receipt_service, mock_llm_service)
        draft = receipt_service.get_draft(draft_id, TEST_USER_EMAIL)

        result = receipt_service.save_draft(draft_id, "someone-else@example.com", draft)

        assert result is None
        assert receipt_service.get_receipts_count(TEST_USER_EMAIL) == 0

    def test_save_draft_returns_none_for_unknown_id(self, receipt_service):
        receipt = Receipt(items=[ReceiptItem(name="X", price=1.0)], total_amount=1.0)
        assert receipt_service.save_draft("nonexistent-id", TEST_USER_EMAIL, receipt) is None

    def test_discard_draft_deletes_file_and_returns_true(self, receipt_service, mock_llm_service):
        draft_id = self._create_draft(receipt_service, mock_llm_service)
        assert receipt_service.discard_draft(draft_id, TEST_USER_EMAIL) is True
        assert receipt_service.get_draft(draft_id, TEST_USER_EMAIL) is None

    def test_discard_draft_returns_false_for_wrong_owner(self, receipt_service, mock_llm_service):
        draft_id = self._create_draft(receipt_service, mock_llm_service)
        assert receipt_service.discard_draft(draft_id, "someone-else@example.com") is False
        assert receipt_service.get_draft(draft_id, TEST_USER_EMAIL) is not None

    def test_discard_draft_returns_false_for_unknown_id(self, receipt_service):
        assert receipt_service.discard_draft("nonexistent-id", TEST_USER_EMAIL) is False

    def test_get_draft_rejects_path_traversal_id(self, receipt_service):
        assert receipt_service.get_draft("../../etc/passwd", TEST_USER_EMAIL) is None


class TestReceiptServiceUpdateReceipt:

    def _seed(self, receipt_service, user_email=TEST_USER_EMAIL):
        return receipt_service.database.save_receipt({
            "store_name": "Deli",
            "purchase_date": "2026-06-17",
            "items": [{"name": "Sandwich", "price": 5.00, "quantity": 1, "category": "Food & Groceries"}],
            "subtotal": 5.00,
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 5.00,
            "currency": "USD",
            "user_email": user_email,
        })

    def test_update_receipt_returns_true_and_persists_changes(self, receipt_service):
        rid = self._seed(receipt_service)
        updated = Receipt(
            items=[ReceiptItem(name="Wrap", price=6.50, quantity=1, category="Food & Groceries")],
            store_name="Deli",
            purchase_date="2026-06-17",
            tax_amount=0.0,
            discount_amount=0.0,
            total_amount=6.50,
            receipt_id=rid,
            currency="USD",
            user_email=TEST_USER_EMAIL,
        )

        result = receipt_service.update_receipt(rid, TEST_USER_EMAIL, updated)

        assert result is True
        saved = receipt_service.get_receipt_by_id(rid, TEST_USER_EMAIL)
        assert saved.items[0].name == "Wrap"
        assert saved.total_amount == 6.50

    def test_update_receipt_returns_false_when_not_found(self, receipt_service):
        updated = Receipt(
            items=[ReceiptItem(name="Wrap", price=6.50, quantity=1, category="Food & Groceries")],
            total_amount=6.50,
            receipt_id="nonexistent-id",
            user_email=TEST_USER_EMAIL,
        )
        assert receipt_service.update_receipt("nonexistent-id", TEST_USER_EMAIL, updated) is False

    def test_update_receipt_returns_false_when_not_owned(self, receipt_service):
        rid = self._seed(receipt_service)
        updated = Receipt(
            items=[ReceiptItem(name="Wrap", price=6.50, quantity=1, category="Food & Groceries")],
            total_amount=6.50,
            receipt_id=rid,
            user_email="someone-else@example.com",
        )
        assert receipt_service.update_receipt(rid, "someone-else@example.com", updated) is False


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
