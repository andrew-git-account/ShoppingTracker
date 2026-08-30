import json
import os

import pytest

from app.database.json_db import CategoryDatabase, JSONDatabase, _SEED_CATEGORIES
from app.database.sqlite_db import SqliteDatabase
from app.database.sqlite_category_db import SqliteCategoryDatabase
from app.database.usage_log_db import UsageLogDatabase
from app.database.sqlite_usage_log_db import SqliteUsageLogDatabase
from app.database.transaction_db import JSONTransactionDatabase
from app.database.sqlite_transaction_db import SqliteTransactionDatabase
from app.database.sqlite_feedback_db import SqliteFeedbackDatabase

# Spec coverage:
#   TestCategoryDatabaseInitialize   -> DataSchema.md (categories.json structure and seeding)
#   TestCategoryDatabaseGetAll       -> DataSchema.md (categories.json structure)
#   TestJSONDatabaseSoftDelete       -> BehaviorSpec.md BS-008 (soft delete, not permanent erasure)
#   TestSqliteDatabase*              -> SP-034 (receipt storage migrated to SQLite)
#   TestUsageLogDatabase             -> SP-020 (LLM usage/cost log)
#   TestJSONTransactionDatabase      -> SP-025 (statement transaction storage)
#   TestSqliteTransactionDatabase    -> SP-035 (transaction storage migrated to SQLite)

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


# SP-036: SqliteCategoryDatabase parity coverage. Reads state back through
# the public interface instead of raw-file-peeking (no SQLite equivalent of
# that). No id-related assertions - the schema drops the unused id column
# (nothing downstream ever reads it, confirmed during SP-036 verification).

class TestSqliteCategoryDatabase:

    def test_creates_table_when_absent(self, categories_db_path):
        SqliteCategoryDatabase(categories_db_path)
        assert os.path.exists(categories_db_path)

    def test_get_all_categories_returns_list(self, categories_db_path):
        db = SqliteCategoryDatabase(categories_db_path)
        assert isinstance(db.get_all_categories(), list)

    def test_seed_count_is_seven(self, categories_db_path):
        db = SqliteCategoryDatabase(categories_db_path)
        assert len(db.get_all_categories()) == EXPECTED_SEED_COUNT

    def test_seed_names_match_expected(self, categories_db_path):
        db = SqliteCategoryDatabase(categories_db_path)
        names = {c["name"] for c in db.get_all_categories()}
        assert names == EXPECTED_SEED_NAMES

    def test_other_category_is_present(self, categories_db_path):
        db = SqliteCategoryDatabase(categories_db_path)
        names = [c["name"] for c in db.get_all_categories()]
        assert "Other" in names

    def test_does_not_reseed_existing_table(self, categories_db_path):
        db = SqliteCategoryDatabase(categories_db_path)
        # Re-opening the same file must not duplicate the seed data
        db2 = SqliteCategoryDatabase(categories_db_path)
        assert len(db2.get_all_categories()) == EXPECTED_SEED_COUNT

    def test_creates_parent_directory(self, tmp_data_dir):
        nested_path = str(tmp_data_dir / "subdir" / "categories.db")
        SqliteCategoryDatabase(nested_path)
        assert os.path.exists(nested_path)


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


class TestJSONDatabaseUpdateReceipt:

    def test_update_returns_true_when_found(self, receipts_file):
        db = JSONDatabase(receipts_file)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        assert db.update_receipt(rid, _OWNER, {"store_name": "New Shop"}) is True

    def test_update_returns_false_when_not_found(self, receipts_file):
        db = JSONDatabase(receipts_file)
        assert db.update_receipt("nonexistent-id", _OWNER, {"store_name": "New Shop"}) is False

    def test_update_returns_false_when_not_owned(self, receipts_file):
        db = JSONDatabase(receipts_file)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        assert db.update_receipt(rid, "someone-else@example.com", {"store_name": "New Shop"}) is False

    def test_update_changes_fields_in_file(self, receipts_file):
        db = JSONDatabase(receipts_file)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        new_items = [{"name": "Banana", "price": 2.50, "quantity": 1, "category": "Food & Groceries"}]
        db.update_receipt(rid, _OWNER, {
            "store_name": "New Shop",
            "currency": "EUR",
            "total_amount": 2.50,
            "items": new_items,
        })
        with open(receipts_file, encoding="utf-8") as f:
            data = json.load(f)
        record = next(r for r in data if r["id"] == rid)
        assert record["store_name"] == "New Shop"
        assert record["currency"] == "EUR"
        assert record["total_amount"] == 2.50
        assert record["items"] == new_items

    def test_update_sets_linked_transaction_id(self, receipts_file):
        db = JSONDatabase(receipts_file)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        result = db.update_receipt(rid, _OWNER, {"linked_transaction_id": "txn-123"})
        assert result is True
        record = db.get_receipt_by_id(rid, _OWNER)
        assert record["linked_transaction_id"] == "txn-123"

    def test_update_preserves_id_saved_at_user_email_even_if_present_in_data(self, receipts_file):
        db = JSONDatabase(receipts_file)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        original = db.get_receipt_by_id(rid, _OWNER)
        original_saved_at = original["saved_at"]

        db.update_receipt(rid, _OWNER, {
            "id": "some-other-id",
            "saved_at": "2020-01-01T00:00:00",
            "user_email": "attacker@example.com",
            "is_deleted": True,
        })

        record = db.get_receipt_by_id(rid, _OWNER)
        assert record is not None
        assert record["id"] == rid
        assert record["saved_at"] == original_saved_at
        assert record["user_email"] == _OWNER
        # is_deleted in receipt_data (True) is ignored - preserved from the
        # original (unset/False) record, not overwritten by the caller's dict
        with open(receipts_file, encoding="utf-8") as f:
            data = json.load(f)
        raw_record = next(r for r in data if r["id"] == rid)
        assert raw_record["is_deleted"] is False

    def test_update_does_not_create_duplicate(self, receipts_file):
        db = JSONDatabase(receipts_file)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.update_receipt(rid, _OWNER, {"store_name": "New Shop"})
        assert db.get_receipts_count(_OWNER) == 1

    def test_update_preserves_is_deleted_flag(self, receipts_file):
        db = JSONDatabase(receipts_file)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.soft_delete_receipt(rid, _OWNER)
        db.update_receipt(rid, _OWNER, {"store_name": "New Shop"})
        with open(receipts_file, encoding="utf-8") as f:
            data = json.load(f)
        record = next(r for r in data if r["id"] == rid)
        assert record["is_deleted"] is True


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


# SP-034: SqliteDatabase parity coverage. Mirrors the TestJSONDatabase*
# classes above (same scenarios), but reads persisted state back exclusively
# through the public Database interface (get_receipt_by_id/get_all_receipts)
# instead of re-opening a raw file - there is no SQLite equivalent of
# "peek at the file's raw bytes". No TestSqliteDatabaseLegacyMigration
# equivalent - that class tests a JSON-file-specific backfill with no
# SQLite analog (a fresh SQLite table never has pre-SP-005 legacy rows).

class TestSqliteDatabaseSoftDelete:

    def test_soft_delete_returns_true_when_found(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        assert db.soft_delete_receipt(rid, _OWNER) is True

    def test_soft_delete_returns_false_when_not_found(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        assert db.soft_delete_receipt("nonexistent-id", _OWNER) is False

    def test_soft_delete_sets_flag(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.soft_delete_receipt(rid, _OWNER)
        record = db.get_receipt_by_id(rid, _OWNER)
        assert record["is_deleted"] is True

    def test_get_all_receipts_excludes_soft_deleted(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.soft_delete_receipt(rid, _OWNER)
        ids = [r["id"] for r in db.get_all_receipts(_OWNER)]
        assert rid not in ids

    def test_get_all_receipts_includes_non_deleted(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        rid1 = db.save_receipt(dict(_SAMPLE_RECEIPT))
        rid2 = db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.soft_delete_receipt(rid1, _OWNER)
        ids = [r["id"] for r in db.get_all_receipts(_OWNER)]
        assert rid2 in ids
        assert rid1 not in ids

    def test_get_receipts_count_excludes_soft_deleted(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        db.save_receipt(dict(_SAMPLE_RECEIPT))
        rid2 = db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.soft_delete_receipt(rid2, _OWNER)
        assert db.get_receipts_count(_OWNER) == 1

    def test_get_receipts_count_matches_get_all_receipts_length(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.save_receipt(dict(_SAMPLE_RECEIPT))
        rid3 = db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.soft_delete_receipt(rid3, _OWNER)
        assert db.get_receipts_count(_OWNER) == len(db.get_all_receipts(_OWNER))


class TestSqliteDatabaseUpdateReceipt:

    def test_update_returns_true_when_found(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        assert db.update_receipt(rid, _OWNER, {"store_name": "New Shop"}) is True

    def test_update_returns_false_when_not_found(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        assert db.update_receipt("nonexistent-id", _OWNER, {"store_name": "New Shop"}) is False

    def test_update_returns_false_when_not_owned(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        assert db.update_receipt(rid, "someone-else@example.com", {"store_name": "New Shop"}) is False

    def test_update_changes_fields(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        new_items = [{"name": "Banana", "price": 2.50, "quantity": 1, "category": "Food & Groceries"}]
        db.update_receipt(rid, _OWNER, {
            "store_name": "New Shop",
            "currency": "EUR",
            "total_amount": 2.50,
            "items": new_items,
        })
        record = db.get_receipt_by_id(rid, _OWNER)
        assert record["store_name"] == "New Shop"
        assert record["currency"] == "EUR"
        assert record["total_amount"] == 2.50
        assert [i["name"] for i in record["items"]] == ["Banana"]
        assert record["items"][0]["price"] == 2.50

    def test_update_without_items_key_leaves_existing_items_untouched(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        original_items = db.get_receipt_by_id(rid, _OWNER)["items"]

        db.update_receipt(rid, _OWNER, {"store_name": "New Shop"})

        record = db.get_receipt_by_id(rid, _OWNER)
        assert record["store_name"] == "New Shop"
        assert record["items"] == original_items

    def test_update_sets_linked_transaction_id(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        result = db.update_receipt(rid, _OWNER, {"linked_transaction_id": "txn-123"})
        assert result is True
        record = db.get_receipt_by_id(rid, _OWNER)
        assert record["linked_transaction_id"] == "txn-123"

    def test_update_preserves_id_saved_at_user_email_even_if_present_in_data(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        original = db.get_receipt_by_id(rid, _OWNER)
        original_saved_at = original["saved_at"]

        db.update_receipt(rid, _OWNER, {
            "id": "some-other-id",
            "saved_at": "2020-01-01T00:00:00",
            "user_email": "attacker@example.com",
            "is_deleted": True,
        })

        record = db.get_receipt_by_id(rid, _OWNER)
        assert record is not None
        assert record["id"] == rid
        assert record["saved_at"] == original_saved_at
        assert record["user_email"] == _OWNER
        # is_deleted in receipt_data (True) is ignored - it's not in the
        # updatable-columns allowlist, so it never reaches the SET clause
        assert record["is_deleted"] is False

    def test_update_does_not_create_duplicate(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.update_receipt(rid, _OWNER, {"store_name": "New Shop"})
        assert db.get_receipts_count(_OWNER) == 1

    def test_update_preserves_is_deleted_flag(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.soft_delete_receipt(rid, _OWNER)
        db.update_receipt(rid, _OWNER, {"store_name": "New Shop"})
        record = db.get_receipt_by_id(rid, _OWNER)
        assert record["is_deleted"] is True


class TestSqliteDatabaseUserScoping:

    def test_get_all_receipts_excludes_other_users_receipts(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        db.save_receipt(dict(_SAMPLE_RECEIPT))
        other = dict(_SAMPLE_RECEIPT)
        other["user_email"] = "other@example.com"
        db.save_receipt(other)

        emails = [r["user_email"] for r in db.get_all_receipts(_OWNER)]
        assert emails == [_OWNER]

    def test_get_receipts_count_excludes_other_users_receipts(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        db.save_receipt(dict(_SAMPLE_RECEIPT))
        other = dict(_SAMPLE_RECEIPT)
        other["user_email"] = "other@example.com"
        db.save_receipt(other)
        db.save_receipt(other)

        assert db.get_receipts_count(_OWNER) == 1

    def test_get_receipt_by_id_returns_none_for_wrong_owner(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        assert db.get_receipt_by_id(rid, "other@example.com") is None
        assert db.get_receipt_by_id(rid, _OWNER) is not None

    def test_soft_delete_fails_for_wrong_owner(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        assert db.soft_delete_receipt(rid, "other@example.com") is False
        ids = [r["id"] for r in db.get_all_receipts(_OWNER)]
        assert rid in ids


class TestSqliteDatabaseItemOrdering:

    def test_item_order_round_trips_through_save_and_read(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        receipt_data = dict(_SAMPLE_RECEIPT)
        receipt_data["items"] = [
            {"name": "Zebra", "price": 1.0, "quantity": 1, "category": "Other"},
            {"name": "Apple", "price": 2.0, "quantity": 1, "category": "Other"},
            {"name": "Mango", "price": 3.0, "quantity": 1, "category": "Other"},
        ]
        rid = db.save_receipt(receipt_data)

        record = db.get_receipt_by_id(rid, _OWNER)
        assert [i["name"] for i in record["items"]] == ["Zebra", "Apple", "Mango"]

    def test_item_order_round_trips_after_update(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        new_items = [
            {"name": "Third", "price": 1.0, "quantity": 1, "category": "Other"},
            {"name": "First", "price": 2.0, "quantity": 1, "category": "Other"},
            {"name": "Second", "price": 3.0, "quantity": 1, "category": "Other"},
        ]
        db.update_receipt(rid, _OWNER, {"items": new_items})

        record = db.get_receipt_by_id(rid, _OWNER)
        assert [i["name"] for i in record["items"]] == ["Third", "First", "Second"]


class TestSqliteDatabaseItemDefaults:
    """
    Regression coverage for a bug caught during planning: SQL DEFAULT only
    applies when a column is omitted from an INSERT, not when it's given an
    explicit NULL - so item fields must be defaulted in Python before
    binding, exactly like ReceiptItem.from_dict() does.
    """

    def test_legacy_item_missing_amount_unit_gets_python_side_defaults(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        receipt_data = dict(_SAMPLE_RECEIPT)
        # Mirrors a pre-SP-013 record: no amount/unit keys at all
        receipt_data["items"] = [{"name": "Old Item", "price": 5.00, "quantity": 1, "category": "Other"}]

        rid = db.save_receipt(receipt_data)

        record = db.get_receipt_by_id(rid, _OWNER)
        item = record["items"][0]
        assert item["amount"] == 1.0
        assert item["unit"] == "piece"

    def test_item_missing_category_defaults_to_other(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        receipt_data = dict(_SAMPLE_RECEIPT)
        receipt_data["items"] = [{"name": "No Category Item", "price": 1.00, "quantity": 1}]

        rid = db.save_receipt(receipt_data)

        record = db.get_receipt_by_id(rid, _OWNER)
        assert record["items"][0]["category"] == "Other"


class TestSqliteDatabaseDeleteReceipt:
    """
    Hard delete has no existing JSON-side test class to mirror, but its
    manual cross-table cascade (receipt_items has no ON DELETE CASCADE) is
    a genuinely new risk the JSON backend never had - worth its own coverage.
    """

    def test_delete_returns_true_when_found(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        assert db.delete_receipt(rid, _OWNER) is True

    def test_delete_returns_false_when_not_found(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        assert db.delete_receipt("nonexistent-id", _OWNER) is False

    def test_delete_returns_false_when_not_owned(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        assert db.delete_receipt(rid, "other@example.com") is False
        assert db.get_receipt_by_id(rid, _OWNER) is not None

    def test_delete_removes_receipt_and_items(self, receipts_db_path):
        db = SqliteDatabase(receipts_db_path)
        rid = db.save_receipt(dict(_SAMPLE_RECEIPT))
        db.delete_receipt(rid, _OWNER)

        assert db.get_receipt_by_id(rid, _OWNER) is None
        assert db.get_receipts_count(_OWNER) == 0

        # Confirm receipt_items was actually cleared, not just orphaned -
        # re-saving a receipt and checking its item count stays correct
        # rules out a stale join wrongly attaching old rows.
        rid2 = db.save_receipt(dict(_SAMPLE_RECEIPT))
        record = db.get_receipt_by_id(rid2, _OWNER)
        assert len(record["items"]) == len(_SAMPLE_RECEIPT["items"])


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


# SP-036: SqliteUsageLogDatabase parity coverage. Reads state back through
# the public interface instead of raw-file-peeking (no SQLite equivalent).

class TestSqliteUsageLogDatabase:

    def test_initialize_creates_empty_log(self, usage_log_db_path):
        db = SqliteUsageLogDatabase(usage_log_db_path)
        assert os.path.exists(usage_log_db_path)
        assert db.get_all_records() == []

    def test_log_call_appends_record_with_computed_cost(self, usage_log_db_path):
        db = SqliteUsageLogDatabase(usage_log_db_path)
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

    def test_log_call_unknown_model_uses_default_pricing(self, usage_log_db_path):
        db = SqliteUsageLogDatabase(usage_log_db_path)
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

    def test_get_all_records_preserves_insertion_order(self, usage_log_db_path):
        db = SqliteUsageLogDatabase(usage_log_db_path)
        db.log_call("first@example.com", "claude-sonnet-4-6", 10, 10, True, False)
        db.log_call("second@example.com", "claude-sonnet-4-6", 20, 20, True, False)
        records = db.get_all_records()
        assert [r["user_email"] for r in records] == ["first@example.com", "second@example.com"]


class TestSqliteFeedbackDatabase:

    def test_initialize_creates_empty_table(self, feedback_db_path):
        db = SqliteFeedbackDatabase(feedback_db_path)
        assert os.path.exists(feedback_db_path)
        assert db.get_all_feedback() == []

    def test_initialize_is_idempotent(self, feedback_db_path):
        SqliteFeedbackDatabase(feedback_db_path)
        db2 = SqliteFeedbackDatabase(feedback_db_path)
        assert db2.get_all_feedback() == []

    def test_save_feedback_returns_id_and_round_trips(self, feedback_db_path):
        db = SqliteFeedbackDatabase(feedback_db_path)
        feedback_id = db.save_feedback({
            "user_email": "user@example.com",
            "message_type": "Bug Report",
            "functionality": "History",
            "message": "Something broke",
            "image_filename": "123_screenshot.jpg",
        })
        assert feedback_id is not None

        records = db.get_all_feedback()
        assert len(records) == 1
        assert records[0]["id"] == feedback_id
        assert records[0]["user_email"] == "user@example.com"
        assert records[0]["message_type"] == "Bug Report"
        assert records[0]["functionality"] == "History"
        assert records[0]["message"] == "Something broke"
        assert records[0]["image_filename"] == "123_screenshot.jpg"
        assert records[0]["created_at"]

    def test_image_filename_omitted_stored_as_none(self, feedback_db_path):
        db = SqliteFeedbackDatabase(feedback_db_path)
        db.save_feedback({
            "user_email": "user@example.com",
            "message_type": "General Feedback",
            "functionality": "None",
            "message": "Just saying hi",
        })
        assert db.get_all_feedback()[0]["image_filename"] is None

    def test_get_all_feedback_preserves_insertion_order(self, feedback_db_path):
        db = SqliteFeedbackDatabase(feedback_db_path)
        db.save_feedback({
            "user_email": "first@example.com", "message_type": "Bug Report",
            "functionality": "History", "message": "First",
        })
        db.save_feedback({
            "user_email": "second@example.com", "message_type": "Bug Report",
            "functionality": "History", "message": "Second",
        })
        records = db.get_all_feedback()
        assert [r["user_email"] for r in records] == ["first@example.com", "second@example.com"]


_SAMPLE_TRANSACTION = {
    "date": "2026-06-15",
    "description": "Corner Store",
    "amount": 12.50,
    "currency": "USD",
    "source": "card",
    "user_email": "owner@example.com",
}

_TXN_OWNER = "owner@example.com"


class TestJSONTransactionDatabase:

    def test_save_transaction_returns_id(self, tmp_data_dir):
        db = JSONTransactionDatabase(str(tmp_data_dir / "transactions.json"))
        tid = db.save_transaction(dict(_SAMPLE_TRANSACTION))
        assert tid is not None

    def test_get_all_transactions_returns_saved_transaction(self, tmp_data_dir):
        db = JSONTransactionDatabase(str(tmp_data_dir / "transactions.json"))
        db.save_transaction(dict(_SAMPLE_TRANSACTION))
        transactions = db.get_all_transactions(_TXN_OWNER)
        assert len(transactions) == 1
        assert transactions[0]["description"] == "Corner Store"

    def test_get_all_transactions_excludes_other_users(self, tmp_data_dir):
        db = JSONTransactionDatabase(str(tmp_data_dir / "transactions.json"))
        db.save_transaction(dict(_SAMPLE_TRANSACTION))
        other = dict(_SAMPLE_TRANSACTION)
        other["user_email"] = "other@example.com"
        db.save_transaction(other)

        emails = [t["user_email"] for t in db.get_all_transactions(_TXN_OWNER)]
        assert emails == [_TXN_OWNER]

    def test_get_all_transactions_excludes_soft_deleted(self, tmp_data_dir):
        # update_transaction deliberately protects is_deleted from generic
        # updates (same as JSONDatabase.update_receipt) - there's no dedicated
        # soft-delete method for transactions yet (out of scope for SP-025),
        # so this seeds an already-deleted record directly via save_transaction,
        # which doesn't guard is_deleted, to test get_all_transactions' filter.
        db = JSONTransactionDatabase(str(tmp_data_dir / "transactions.json"))
        deleted = dict(_SAMPLE_TRANSACTION)
        deleted["is_deleted"] = True
        db.save_transaction(deleted)
        assert db.get_all_transactions(_TXN_OWNER) == []

    def test_get_transaction_by_id_returns_none_for_wrong_owner(self, tmp_data_dir):
        db = JSONTransactionDatabase(str(tmp_data_dir / "transactions.json"))
        tid = db.save_transaction(dict(_SAMPLE_TRANSACTION))
        assert db.get_transaction_by_id(tid, "other@example.com") is None
        assert db.get_transaction_by_id(tid, _TXN_OWNER) is not None

    def test_get_transaction_by_id_returns_none_for_unknown_id(self, tmp_data_dir):
        db = JSONTransactionDatabase(str(tmp_data_dir / "transactions.json"))
        assert db.get_transaction_by_id("nonexistent-id", _TXN_OWNER) is None

    def test_update_transaction_sets_arbitrary_field(self, tmp_data_dir):
        db = JSONTransactionDatabase(str(tmp_data_dir / "transactions.json"))
        tid = db.save_transaction(dict(_SAMPLE_TRANSACTION))
        result = db.update_transaction(tid, _TXN_OWNER, {"category": "Dining & Takeout"})
        assert result is True
        record = db.get_transaction_by_id(tid, _TXN_OWNER)
        assert record["category"] == "Dining & Takeout"

    def test_update_transaction_returns_false_when_not_found(self, tmp_data_dir):
        db = JSONTransactionDatabase(str(tmp_data_dir / "transactions.json"))
        assert db.update_transaction("nonexistent-id", _TXN_OWNER, {"category": "Other"}) is False

    def test_update_transaction_preserves_id_saved_at_user_email_even_if_present_in_data(self, tmp_data_dir):
        db = JSONTransactionDatabase(str(tmp_data_dir / "transactions.json"))
        tid = db.save_transaction(dict(_SAMPLE_TRANSACTION))
        original = db.get_transaction_by_id(tid, _TXN_OWNER)
        original_saved_at = original["saved_at"]

        db.update_transaction(tid, _TXN_OWNER, {
            "id": "some-other-id",
            "saved_at": "2020-01-01T00:00:00",
            "user_email": "attacker@example.com",
        })

        record = db.get_transaction_by_id(tid, _TXN_OWNER)
        assert record is not None
        assert record["id"] == tid
        assert record["saved_at"] == original_saved_at


# SP-035: SqliteTransactionDatabase parity coverage. Mirrors
# TestJSONTransactionDatabase's scenarios exactly - no raw-file-peeking to
# adapt away from here (that class already reads state back through the
# public interface), so this is a closer 1:1 mirror than TestSqliteDatabase's
# relationship to TestJSONDatabase was.

class TestSqliteTransactionDatabase:

    def test_save_transaction_returns_id(self, transactions_db_path):
        db = SqliteTransactionDatabase(transactions_db_path)
        tid = db.save_transaction(dict(_SAMPLE_TRANSACTION))
        assert tid is not None

    def test_get_all_transactions_returns_saved_transaction(self, transactions_db_path):
        db = SqliteTransactionDatabase(transactions_db_path)
        db.save_transaction(dict(_SAMPLE_TRANSACTION))
        transactions = db.get_all_transactions(_TXN_OWNER)
        assert len(transactions) == 1
        assert transactions[0]["description"] == "Corner Store"

    def test_get_all_transactions_excludes_other_users(self, transactions_db_path):
        db = SqliteTransactionDatabase(transactions_db_path)
        db.save_transaction(dict(_SAMPLE_TRANSACTION))
        other = dict(_SAMPLE_TRANSACTION)
        other["user_email"] = "other@example.com"
        db.save_transaction(other)

        emails = [t["user_email"] for t in db.get_all_transactions(_TXN_OWNER)]
        assert emails == [_TXN_OWNER]

    def test_get_all_transactions_excludes_soft_deleted(self, transactions_db_path):
        db = SqliteTransactionDatabase(transactions_db_path)
        deleted = dict(_SAMPLE_TRANSACTION)
        deleted["is_deleted"] = True
        db.save_transaction(deleted)
        assert db.get_all_transactions(_TXN_OWNER) == []

    def test_get_all_transactions_preserves_insertion_order(self, transactions_db_path):
        db = SqliteTransactionDatabase(transactions_db_path)
        first = dict(_SAMPLE_TRANSACTION)
        first["description"] = "First"
        second = dict(_SAMPLE_TRANSACTION)
        second["description"] = "Second"
        db.save_transaction(first)
        db.save_transaction(second)

        descriptions = [t["description"] for t in db.get_all_transactions(_TXN_OWNER)]
        assert descriptions == ["First", "Second"]

    def test_get_transaction_by_id_returns_none_for_wrong_owner(self, transactions_db_path):
        db = SqliteTransactionDatabase(transactions_db_path)
        tid = db.save_transaction(dict(_SAMPLE_TRANSACTION))
        assert db.get_transaction_by_id(tid, "other@example.com") is None
        assert db.get_transaction_by_id(tid, _TXN_OWNER) is not None

    def test_get_transaction_by_id_returns_none_for_unknown_id(self, transactions_db_path):
        db = SqliteTransactionDatabase(transactions_db_path)
        assert db.get_transaction_by_id("nonexistent-id", _TXN_OWNER) is None

    def test_update_transaction_sets_arbitrary_field(self, transactions_db_path):
        db = SqliteTransactionDatabase(transactions_db_path)
        tid = db.save_transaction(dict(_SAMPLE_TRANSACTION))
        result = db.update_transaction(tid, _TXN_OWNER, {"category": "Dining & Takeout"})
        assert result is True
        record = db.get_transaction_by_id(tid, _TXN_OWNER)
        assert record["category"] == "Dining & Takeout"

    def test_update_transaction_returns_false_when_not_found(self, transactions_db_path):
        db = SqliteTransactionDatabase(transactions_db_path)
        assert db.update_transaction("nonexistent-id", _TXN_OWNER, {"category": "Other"}) is False

    def test_update_transaction_returns_false_when_not_owned(self, transactions_db_path):
        db = SqliteTransactionDatabase(transactions_db_path)
        tid = db.save_transaction(dict(_SAMPLE_TRANSACTION))
        assert db.update_transaction(tid, "someone-else@example.com", {"category": "Other"}) is False

    def test_update_transaction_preserves_id_saved_at_user_email_even_if_present_in_data(self, transactions_db_path):
        db = SqliteTransactionDatabase(transactions_db_path)
        tid = db.save_transaction(dict(_SAMPLE_TRANSACTION))
        original = db.get_transaction_by_id(tid, _TXN_OWNER)
        original_saved_at = original["saved_at"]

        db.update_transaction(tid, _TXN_OWNER, {
            "id": "some-other-id",
            "saved_at": "2020-01-01T00:00:00",
            "user_email": "attacker@example.com",
            "is_deleted": True,
        })

        record = db.get_transaction_by_id(tid, _TXN_OWNER)
        assert record is not None
        assert record["id"] == tid
        assert record["saved_at"] == original_saved_at
        assert record["user_email"] == _TXN_OWNER
        assert record["is_deleted"] is False

    def test_soft_delete_transaction_returns_true_when_found(self, transactions_db_path):
        db = SqliteTransactionDatabase(transactions_db_path)
        tid = db.save_transaction(dict(_SAMPLE_TRANSACTION))
        assert db.soft_delete_transaction(tid, _TXN_OWNER) is True

    def test_soft_delete_transaction_returns_false_when_not_found(self, transactions_db_path):
        db = SqliteTransactionDatabase(transactions_db_path)
        assert db.soft_delete_transaction("nonexistent-id", _TXN_OWNER) is False

    def test_soft_delete_transaction_sets_flag(self, transactions_db_path):
        db = SqliteTransactionDatabase(transactions_db_path)
        tid = db.save_transaction(dict(_SAMPLE_TRANSACTION))
        db.soft_delete_transaction(tid, _TXN_OWNER)
        record = db.get_transaction_by_id(tid, _TXN_OWNER)
        assert record["is_deleted"] is True
        assert record["user_email"] == _TXN_OWNER
