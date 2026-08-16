import pytest
from app.models import ReceiptItem, Receipt, _resolve_amount_unit

# Spec coverage:
#   TestReceiptItemCategory            -> DataSchema.md (items[].category field rules)
#   TestReceiptFromLLMResponse         -> BehaviorSpec.md BS-011, BS-012
#   TestResolveAmountUnit              -> SP-013: Price-Per-Unit for Comparison
#   TestReceiptItemAmountUnit          -> SP-013: Price-Per-Unit for Comparison
#   TestReceiptFromLLMResponseAmountUnit -> SP-013: Price-Per-Unit for Comparison


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


class TestResolveAmountUnit:

    def test_no_amount_defaults_to_one_piece(self):
        assert _resolve_amount_unit(None, None) == (1.0, "piece")

    def test_kg_unit_recognized(self):
        assert _resolve_amount_unit(0.5, "kg") == (0.5, "kg")

    @pytest.mark.parametrize("unit_str", ["kilogram", "kilograms", "KG", "Kg"])
    def test_kg_synonyms_recognized(self, unit_str):
        amount, unit = _resolve_amount_unit(0.5, unit_str)
        assert (amount, unit) == (0.5, "kg")

    def test_grams_converted_to_kg(self):
        amount, unit = _resolve_amount_unit(200, "g")
        assert unit == "kg"
        assert amount == pytest.approx(0.2)

    @pytest.mark.parametrize("unit_str", ["gram", "grams", "G"])
    def test_gram_synonyms_recognized(self, unit_str):
        amount, unit = _resolve_amount_unit(500, unit_str)
        assert unit == "kg"
        assert amount == pytest.approx(0.5)

    @pytest.mark.parametrize("unit_str", ["piece", "pieces", "stk", "stück", "pc", "pcs", "st"])
    def test_piece_synonyms_recognized(self, unit_str):
        assert _resolve_amount_unit(3, unit_str) == (3.0, "piece")

    def test_unrecognized_unit_with_fractional_amount_defaults_to_kg(self):
        assert _resolve_amount_unit(0.743, "boxes") == (0.743, "kg")

    def test_unrecognized_unit_with_whole_amount_defaults_to_piece(self):
        assert _resolve_amount_unit(3, "boxes") == (3.0, "piece")

    def test_fractional_amount_no_unit_defaults_to_kg(self):
        """The real Coop case: weighed item, no unit shown on the till receipt."""
        assert _resolve_amount_unit(0.743, None) == (0.743, "kg")

    def test_whole_amount_no_unit_defaults_to_piece(self):
        assert _resolve_amount_unit(2, None) == (2.0, "piece")

    def test_zero_or_negative_amount_falls_back_to_one(self):
        amount, _ = _resolve_amount_unit(0, "kg")
        assert amount == 1.0
        amount, _ = _resolve_amount_unit(-5, "piece")
        assert amount == 1.0

    def test_invalid_amount_type_falls_back_to_default(self):
        assert _resolve_amount_unit("not-a-number", "kg") == (1.0, "piece")


class TestReceiptItemAmountUnit:

    def test_default_amount_and_unit(self):
        item = ReceiptItem(name="Widget", price=1.00)
        assert item.amount == 1.0
        assert item.unit == "piece"

    def test_custom_amount_and_unit_stored(self):
        item = ReceiptItem(name="Sardines", price=14.50, amount=0.743, unit="kg")
        assert item.amount == 0.743
        assert item.unit == "kg"

    def test_to_dict_includes_amount_and_unit(self):
        item = ReceiptItem(name="Sardines", price=14.50, amount=0.743, unit="kg")
        d = item.to_dict()
        assert d["amount"] == 0.743
        assert d["unit"] == "kg"

    def test_from_dict_with_amount_and_unit(self):
        item = ReceiptItem.from_dict({
            "name": "Sardines", "price": 14.50, "quantity": 1,
            "category": "Food & Groceries", "amount": 0.743, "unit": "kg"
        })
        assert item.amount == 0.743
        assert item.unit == "kg"

    def test_from_dict_without_amount_unit_keys_defaults(self):
        """Simulates a receipt saved before SP-013 - no amount/unit keys at all."""
        item = ReceiptItem.from_dict({
            "name": "Milk", "price": 2.99, "quantity": 1, "category": "Food & Groceries"
        })
        assert item.amount == 1.0
        assert item.unit == "piece"

    def test_from_dict_roundtrip_preserves_amount_unit(self):
        original = ReceiptItem(name="Sardines", price=14.50, amount=0.743, unit="kg")
        restored = ReceiptItem.from_dict(original.to_dict())
        assert restored.amount == original.amount
        assert restored.unit == original.unit

    def test_price_per_unit_piece_item(self):
        item = ReceiptItem(name="Milk", price=2.99, quantity=1, amount=1.0, unit="piece")
        assert item.price_per_unit == pytest.approx(2.99)

    def test_price_per_unit_multi_quantity(self):
        """Real Couscous-Salat example: total 7.60 for 2 units -> 3.80/piece."""
        item = ReceiptItem(name="Couscous-Salat", price=3.80, quantity=2, amount=2.0, unit="piece")
        assert item.price_per_unit == pytest.approx(3.80)

    def test_price_per_unit_weighed_item(self):
        """Real Sardinenfilet Butterfly example: total 14.50 for 0.744kg."""
        item = ReceiptItem(name="Sardinenfilet Butterfly", price=14.50, quantity=1, amount=0.744, unit="kg")
        assert item.price_per_unit == pytest.approx(19.49, abs=0.01)

    def test_price_per_unit_zero_amount_guarded(self):
        item = ReceiptItem(name="Weird", price=5.00, quantity=1, amount=0, unit="kg")
        assert item.price_per_unit == 0.0


class TestReceiptFromLLMResponseAmountUnit:

    def _base_llm_data(self, amount=None, unit=None):
        item = {"name": "Sardinenfilet Butterfly", "price": 14.50, "quantity": 1, "category": "Food & Groceries"}
        if amount is not None:
            item["amount"] = amount
        if unit is not None:
            item["unit"] = unit
        return {
            "store_name": "Coop",
            "purchase_date": "2026-08-16",
            "items": [item],
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 14.50,
            "currency": "CHF",
        }

    def test_amount_and_unit_extracted_from_llm_data(self, valid_categories):
        receipt = Receipt.from_llm_response(
            self._base_llm_data(amount=0.744, unit="kg"), valid_categories=valid_categories
        )
        assert receipt.items[0].amount == 0.744
        assert receipt.items[0].unit == "kg"

    def test_missing_amount_key_defaults_to_piece(self, valid_categories):
        receipt = Receipt.from_llm_response(self._base_llm_data(), valid_categories=valid_categories)
        assert receipt.items[0].amount == 1.0
        assert receipt.items[0].unit == "piece"

    def test_llm_gram_unit_converted_to_kg_on_ingest(self, valid_categories):
        receipt = Receipt.from_llm_response(
            self._base_llm_data(amount=200, unit="g"), valid_categories=valid_categories
        )
        assert receipt.items[0].unit == "kg"
        assert receipt.items[0].amount == pytest.approx(0.2)

    def test_multiple_items_with_mixed_amount_units(self, valid_categories):
        data = {
            "store_name": "Coop",
            "purchase_date": "2026-08-16",
            "items": [
                {"name": "Milk", "price": 2.99, "quantity": 1, "category": "Food & Groceries"},
                {"name": "Sardines", "price": 14.50, "quantity": 1, "category": "Food & Groceries",
                 "amount": 0.744, "unit": "kg"},
                {"name": "Tomatoes", "price": 0.60, "quantity": 1, "category": "Food & Groceries",
                 "amount": 200, "unit": "g"},
            ],
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 18.09,
            "currency": "CHF",
        }
        receipt = Receipt.from_llm_response(data, valid_categories=valid_categories)
        assert (receipt.items[0].amount, receipt.items[0].unit) == (1.0, "piece")
        assert (receipt.items[1].amount, receipt.items[1].unit) == (0.744, "kg")
        assert receipt.items[2].unit == "kg"
        assert receipt.items[2].amount == pytest.approx(0.2)
