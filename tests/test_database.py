import json
import os

import pytest

from app.database.json_db import CategoryDatabase, JSONDatabase, _SEED_CATEGORIES

# Spec coverage:
#   TestCategoryDatabaseInitialize  -> DataSchema.md (categories.json structure and seeding)
#   TestCategoryDatabaseGetAll      -> DataSchema.md (categories.json structure)
#   TestJSONDatabaseSoftDelete      -> BehaviorSpec.md BS-008 (soft delete, not permanent erasure)

EXPECTED_SEED_COUNT = 7
EXPECTED_SEED_NAMES = {c["name"] for c in _SEED_CATEGORIES}


class TestCategoryDatabaseInitialize:

    def test_creates_file_when_absent(self, categories_file):
        CategoryDatabase(categories_file).initialize()
        assert os.path.exists(categories_file)

    def test_file_contains_valid_json(self, categories_file):
        CategoryDatabase(categories_file).initialize()
        with open(categories_file, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)

    def test_seed_count_is_seven(self, categories_file):
        CategoryDatabase(categories_file).initialize()
        with open(categories_file, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == EXPECTED_SEED_COUNT

    def test_each_seed_has_id_and_name(self, categories_file):
        CategoryDatabase(categories_file).initialize()
        with open(categories_file, encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            assert "id" in entry
            assert "name" in entry

    def test_seed_ids_are_unique(self, categories_file):
        CategoryDatabase(categories_file).initialize()
        with open(categories_file, encoding="utf-8") as f:
            data = json.load(f)
        ids = [c["id"] for c in data]
        assert len(ids) == len(set(ids))

    def test_seed_names_match_expected(self, categories_file):
        CategoryDatabase(categories_file).initialize()
        with open(categories_file, encoding="utf-8") as f:
            data = json.load(f)
        names = {c["name"] for c in data}
        assert names == EXPECTED_SEED_NAMES

    def test_does_not_overwrite_existing_file(self, tmp_data_dir):
        path = str(tmp_data_dir / "categories.json")
        custom_data = [{"id": 99, "name": "Custom"}]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(custom_data, f)

        CategoryDatabase(path).initialize()

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data == custom_data

    def test_creates_parent_directory(self, tmp_path):
        nested_path = str(tmp_path / "subdir" / "categories.json")
        CategoryDatabase(nested_path).initialize()
        assert os.path.exists(nested_path)


class TestCategoryDatabaseGetAll:

    def test_returns_list(self, categories_file):
        db = CategoryDatabase(categories_file)
        db.initialize()
        assert isinstance(db.get_all_categories(), list)

    def test_returns_seven_entries(self, categories_file):
        db = CategoryDatabase(categories_file)
        db.initialize()
        assert len(db.get_all_categories()) == EXPECTED_SEED_COUNT

    def test_entries_have_id_and_name(self, categories_file):
        db = CategoryDatabase(categories_file)
        db.initialize()
        for cat in db.get_all_categories():
            assert "id" in cat
            assert "name" in cat
            assert isinstance(cat["name"], str)
            assert isinstance(cat["id"], int)

    def test_other_category_is_present(self, categories_file):
        db = CategoryDatabase(categories_file)
        db.initialize()
        names = [c["name"] for c in db.get_all_categories()]
        assert "Other" in names

    @pytest.mark.parametrize("name", list(EXPECTED_SEED_NAMES))
    def test_all_seed_names_retrievable(self, categories_file, name):
        db = CategoryDatabase(categories_file)
        db.initialize()
        names = [c["name"] for c in db.get_all_categories()]
        assert name in names


_SAMPLE_RECEIPT = {
    "store_name": "Test Shop",
    "purchase_date": "2026-06-17",
    "items": [{"name": "Apple", "price": 1.00, "quantity": 1, "category": "Food & Groceries"}],
    "subtotal": 1.00,
    "tax_amount": 0.0,
    "discount_amount": 0.0,
    "total_amount": 1.00,
    "currency": "USD",
}


class TestJSONDatabaseSoftDelete:

    def test_soft_delete_returns_true_when_found(self, receipts_file):
        db = JSONDatabase(receipts_file)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        assert db.soft_delete_receipt(rid) is True

    def test_soft_delete_returns_false_when_not_found(self, receipts_file):
        db = JSONDatabase(receipts_file)
        assert db.soft_delete_receipt("nonexistent-id") is False

    def test_soft_delete_sets_flag_in_file(self, receipts_file):
        db = JSONDatabase(receipts_file)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.soft_delete_receipt(rid)
        with open(receipts_file, encoding="utf-8") as f:
            data = json.load(f)
        record = next(r for r in data if r["id"] == rid)
        assert record["is_deleted"] is True

    def test_get_all_receipts_excludes_soft_deleted(self, receipts_file):
        db = JSONDatabase(receipts_file)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.soft_delete_receipt(rid)
        ids = [r["id"] for r in db.get_all_receipts()]
        assert rid not in ids

    def test_get_all_receipts_includes_non_deleted(self, receipts_file):
        db = JSONDatabase(receipts_file)
        rid1 = db.save_receipt(dict(_SAMPLE_RECEIPT))
        rid2 = db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.soft_delete_receipt(rid1)
        ids = [r["id"] for r in db.get_all_receipts()]
        assert rid2 in ids
        assert rid1 not in ids
