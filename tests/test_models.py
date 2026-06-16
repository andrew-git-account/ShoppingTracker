import pytest
from app.models import ReceiptItem, Receipt


class TestReceiptItemCategory:

    def test_default_category_is_other(self):
        item = ReceiptItem(name="Widget", price=1.00)
        assert item.category == "Other"

    def test_custom_category_stored(self):
        item = ReceiptItem(name="Milk", price=2.99, category="Food & Groceries")
        assert item.category == "Food & Groceries"

    def test_to_dict_includes_category(self):
        item = ReceiptItem(name="Milk", price=2.99, category="Food & Groceries")
        d = item.to_dict()
        assert "category" in d
        assert d["category"] == "Food & Groceries"

    def test_to_dict_default_category(self):
        item = ReceiptItem(name="Widget", price=1.00)
        assert item.to_dict()["category"] == "Other"

    def test_from_dict_with_category(self):
        item = ReceiptItem.from_dict({
            "name": "Shampoo", "price": 5.49, "quantity": 1,
            "category": "Personal Care & Health"
        })
        assert item.category == "Personal Care & Health"

    def test_from_dict_without_category_key(self):
        item = ReceiptItem.from_dict({"name": "Unknown", "price": 1.00})
        assert item.category == "Other"

    def test_from_dict_category_roundtrip(self):
        original = ReceiptItem(name="Laptop", price=999.00, category="Electronics & Tech")
        restored = ReceiptItem.from_dict(original.to_dict())
        assert restored.category == original.category


class TestReceiptFromLLMResponse:

    def _base_llm_data(self, category="Food & Groceries"):
        return {
            "store_name": "Mart",
            "purchase_date": "2026-06-16",
            "items": [{"name": "Milk", "price": 2.99, "quantity": 1, "category": category}],
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 2.99,
            "currency": "USD",
        }

    def test_valid_category_preserved(self, valid_categories):
        receipt = Receipt.from_llm_response(
            self._base_llm_data("Food & Groceries"),
            valid_categories=valid_categories
        )
        assert receipt.items[0].category == "Food & Groceries"

    def test_invalid_category_falls_back_to_other(self, valid_categories):
        receipt = Receipt.from_llm_response(
            self._base_llm_data("Junk Category"),
            valid_categories=valid_categories
        )
        assert receipt.items[0].category == "Other"

    def test_missing_category_key_falls_back_to_other(self, valid_categories):
        data = self._base_llm_data()
        del data["items"][0]["category"]
        receipt = Receipt.from_llm_response(data, valid_categories=valid_categories)
        assert receipt.items[0].category == "Other"

    def test_no_valid_categories_falls_back_to_other(self):
        receipt = Receipt.from_llm_response(
            self._base_llm_data("Food & Groceries"),
            valid_categories=None
        )
        assert receipt.items[0].category == "Other"

    def test_empty_valid_categories_falls_back_to_other(self):
        receipt = Receipt.from_llm_response(
            self._base_llm_data("Food & Groceries"),
            valid_categories=[]
        )
        assert receipt.items[0].category == "Other"

    @pytest.mark.parametrize("category", [
        "Other",
        "Food & Groceries",
        "Household & Cleaning",
        "Personal Care & Health",
        "Electronics & Tech",
        "Clothing & Apparel",
        "Dining & Takeout",
    ])
    def test_all_valid_categories_are_accepted(self, category, valid_categories):
        receipt = Receipt.from_llm_response(
            self._base_llm_data(category),
            valid_categories=valid_categories
        )
        assert receipt.items[0].category == category

    def test_multiple_items_with_mixed_categories(self, valid_categories):
        data = {
            "store_name": "Mixed Store",
            "purchase_date": "2026-06-16",
            "items": [
                {"name": "Milk", "price": 2.99, "quantity": 1, "category": "Food & Groceries"},
                {"name": "Gadget", "price": 9.99, "quantity": 1, "category": "INVALID"},
                {"name": "Soap", "price": 1.50, "quantity": 1, "category": "Personal Care & Health"},
            ],
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 14.48,
            "currency": "USD",
        }
        receipt = Receipt.from_llm_response(data, valid_categories=valid_categories)
        assert receipt.items[0].category == "Food & Groceries"
        assert receipt.items[1].category == "Other"
        assert receipt.items[2].category == "Personal Care & Health"
