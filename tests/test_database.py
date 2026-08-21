import json
import os

import pytest

from app.database.json_db import CategoryDatabase, JSONDatabase, _SEED_CATEGORIES
from app.database.usage_log_db import UsageLogDatabase

# Spec coverage:
#   TestCategoryDatabaseInitialize  -> DataSchema.md (categories.json structure and seeding)
#   TestCategoryDatabaseGetAll      -> DataSchema.md (categories.json structure)
#   TestJSONDatabaseSoftDelete      -> BehaviorSpec.md BS-008 (soft delete, not permanent erasure)
#   TestUsageLogDatabase            -> SP-020 (LLM usage/cost log)

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
    "user_email": "owner@example.com",
}

_OWNER = "owner@example.com"


class TestJSONDatabaseSoftDelete:

    def test_soft_delete_returns_true_when_found(self, receipts_file):
        db = JSONDatabase(receipts_file)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        assert db.soft_delete_receipt(rid, _OWNER) is True

    def test_soft_delete_returns_false_when_not_found(self, receipts_file):
        db = JSONDatabase(receipts_file)
        assert db.soft_delete_receipt("nonexistent-id", _OWNER) is False

    def test_soft_delete_sets_flag_in_file(self, receipts_file):
        db = JSONDatabase(receipts_file)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.soft_delete_receipt(rid, _OWNER)
        with open(receipts_file, encoding="utf-8") as f:
            data = json.load(f)
        record = next(r for r in data if r["id"] == rid)
        assert record["is_deleted"] is True

    def test_get_all_receipts_excludes_soft_deleted(self, receipts_file):
        db = JSONDatabase(receipts_file)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.soft_delete_receipt(rid, _OWNER)
        ids = [r["id"] for r in db.get_all_receipts(_OWNER)]
        assert rid not in ids

    def test_get_all_receipts_includes_non_deleted(self, receipts_file):
        db = JSONDatabase(receipts_file)
        rid1 = db.save_receipt(dict(_SAMPLE_RECEIPT))
        rid2 = db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.soft_delete_receipt(rid1, _OWNER)
        ids = [r["id"] for r in db.get_all_receipts(_OWNER)]
        assert rid2 in ids
        assert rid1 not in ids

    def test_get_receipts_count_excludes_soft_deleted(self, receipts_file):
        db = JSONDatabase(receipts_file)
        db.save_receipt(dict(_SAMPLE_RECEIPT))
        rid2 = db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.soft_delete_receipt(rid2, _OWNER)
        assert db.get_receipts_count(_OWNER) == 1

    def test_get_receipts_count_matches_get_all_receipts_length(self, receipts_file):
        db = JSONDatabase(receipts_file)
        db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.save_receipt(dict(_SAMPLE_RECEIPT))
        rid3 = db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.soft_delete_receipt(rid3, _OWNER)
        assert db.get_receipts_count(_OWNER) == len(db.get_all_receipts(_OWNER))


class TestJSONDatabaseUserScoping:

    def test_get_all_receipts_excludes_other_users_receipts(self, receipts_file):
        db = JSONDatabase(receipts_file)
        db.save_receipt(dict(_SAMPLE_RECEIPT))
        other = dict(_SAMPLE_RECEIPT)
        other["user_email"] = "other@example.com"
        db.save_receipt(other)

        ids = [r["user_email"] for r in db.get_all_receipts(_OWNER)]
        assert ids == [_OWNER]

    def test_get_receipts_count_excludes_other_users_receipts(self, receipts_file):
        db = JSONDatabase(receipts_file)
        db.save_receipt(dict(_SAMPLE_RECEIPT))
        other = dict(_SAMPLE_RECEIPT)
        other["user_email"] = "other@example.com"
        db.save_receipt(other)
        db.save_receipt(other)

        assert db.get_receipts_count(_OWNER) == 1

    def test_get_receipt_by_id_returns_none_for_wrong_owner(self, receipts_file):
        db = JSONDatabase(receipts_file)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        assert db.get_receipt_by_id(rid, "other@example.com") is None
        assert db.get_receipt_by_id(rid, _OWNER) is not None

    def test_soft_delete_fails_for_wrong_owner(self, receipts_file):
        db = JSONDatabase(receipts_file)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        assert db.soft_delete_receipt(rid, "other@example.com") is False
        ids = [r["id"] for r in db.get_all_receipts(_OWNER)]
        assert rid in ids


class TestJSONDatabaseLegacyMigration:

    def test_initialize_backfills_missing_user_email(self, tmp_data_dir):
        from app.database.json_db import _LEGACY_OWNER_EMAIL

        path = str(tmp_data_dir / "receipts.json")
        legacy_receipt = dict(_SAMPLE_RECEIPT)
        del legacy_receipt["user_email"]
        legacy_receipt["id"] = "legacy-1"
        with open(path, "w", encoding="utf-8") as f:
            json.dump([legacy_receipt], f)

        JSONDatabase(path)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data[0]["user_email"] == _LEGACY_OWNER_EMAIL

    def test_initialize_does_not_touch_receipts_that_already_have_user_email(self, tmp_data_dir):
        path = str(tmp_data_dir / "receipts.json")
        receipt = dict(_SAMPLE_RECEIPT)
        receipt["id"] = "existing-1"
        receipt["user_email"] = "other@example.com"
        with open(path, "w", encoding="utf-8") as f:
            json.dump([receipt], f)

        JSONDatabase(path)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data[0]["user_email"] == "other@example.com"

    def test_initialize_migration_is_idempotent(self, tmp_data_dir):
        from app.database.json_db import _LEGACY_OWNER_EMAIL

        path = str(tmp_data_dir / "receipts.json")
        legacy_receipt = dict(_SAMPLE_RECEIPT)
        del legacy_receipt["user_email"]
        legacy_receipt["id"] = "legacy-1"
        with open(path, "w", encoding="utf-8") as f:
            json.dump([legacy_receipt], f)

        JSONDatabase(path)
        with open(path, encoding="utf-8") as f:
            first_pass = json.load(f)

        JSONDatabase(path)
        with open(path, encoding="utf-8") as f:
            second_pass = json.load(f)

        assert first_pass == second_pass
        assert second_pass[0]["user_email"] == _LEGACY_OWNER_EMAIL


class TestUsageLogDatabase:

    def test_initialize_creates_empty_file(self, tmp_data_dir):
        path = str(tmp_data_dir / "llm_usage.json")
        UsageLogDatabase(path)
        assert os.path.exists(path)
        with open(path, encoding="utf-8") as f:
            assert json.load(f) == []

    def test_log_call_appends_record_with_computed_cost(self, tmp_data_dir):
        path = str(tmp_data_dir / "llm_usage.json")
        db = UsageLogDatabase(path)
        db.log_call(
            user_email="owner@example.com",
            model="claude-sonnet-4-6",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            success=True,
            is_retry=False,
        )
        records = db.get_all_records()
        assert len(records) == 1
        # 1M input @ $3.00/1M + 1M output @ $15.00/1M = $18.00
        assert records[0]["cost_usd"] == pytest.approx(18.00)
        assert records[0]["user_email"] == "owner@example.com"
        assert records[0]["success"] is True
        assert records[0]["is_retry"] is False

    def test_log_call_unknown_model_uses_default_pricing(self, tmp_data_dir):
        path = str(tmp_data_dir / "llm_usage.json")
        db = UsageLogDatabase(path)
        db.log_call(
            user_email="owner@example.com",
            model="some-future-model",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            success=True,
            is_retry=False,
        )
        records = db.get_all_records()
        assert records[0]["cost_usd"] > 0

    def test_get_all_records_preserves_insertion_order(self, tmp_data_dir):
        path = str(tmp_data_dir / "llm_usage.json")
        db = UsageLogDatabase(path)
        db.log_call("first@example.com", "claude-sonnet-4-6", 10, 10, True, False)
        db.log_call("second@example.com", "claude-sonnet-4-6", 20, 20, True, False)
        records = db.get_all_records()
        assert [r["user_email"] for r in records] == ["first@example.com", "second@example.com"]
