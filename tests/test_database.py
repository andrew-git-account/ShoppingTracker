import json
import os

import pytest

from app.database.json_db import CategoryDatabase, _SEED_CATEGORIES

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
