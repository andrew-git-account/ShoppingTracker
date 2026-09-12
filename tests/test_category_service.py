from app.services.category_service import CategoryService

# Spec coverage:
#   TestCategoryServiceReadAccess  -> SP-041 (visible vs all categories)
#   TestCategoryServiceManagement  -> SP-041 (add/rename/hide-unhide + "Other" safeguard)


def _make_category_service(tmp_data_dir) -> CategoryService:
    return CategoryService(str(tmp_data_dir / "shopping_tracker.db"))


class TestCategoryServiceReadAccess:

    def test_get_all_categories_returns_seven_visible_entries(self, tmp_data_dir):
        service = _make_category_service(tmp_data_dir)
        categories = service.get_all_categories()
        assert len(categories) == 7
        assert all(c["hidden"] is False for c in categories)

    def test_get_visible_category_names_excludes_hidden(self, tmp_data_dir):
        service = _make_category_service(tmp_data_dir)
        categories = service.get_all_categories()
        target = next(c for c in categories if c["name"] == "Dining & Takeout")

        service.toggle_hidden(target["id"])

        assert "Dining & Takeout" not in service.get_visible_category_names()
        assert "Other" in service.get_visible_category_names()


class TestCategoryServiceManagement:

    def test_add_category_success(self, tmp_data_dir):
        service = _make_category_service(tmp_data_dir)
        success, error = service.add_category("Pets")
        assert success is True
        assert error is None
        assert "Pets" in service.get_visible_category_names()

    def test_add_category_duplicate_rejected(self, tmp_data_dir):
        service = _make_category_service(tmp_data_dir)
        success, error = service.add_category("Other")
        assert success is False
        assert error is not None

    def test_add_category_blank_name_rejected(self, tmp_data_dir):
        service = _make_category_service(tmp_data_dir)
        success, error = service.add_category("   ")
        assert success is False
        assert error is not None

    def test_rename_category_success(self, tmp_data_dir):
        service = _make_category_service(tmp_data_dir)
        target = next(c for c in service.get_all_categories() if c["name"] == "Dining & Takeout")

        success, error = service.rename_category(target["id"], "Restaurants")

        assert success is True
        assert error is None
        assert "Restaurants" in service.get_visible_category_names()
        assert "Dining & Takeout" not in service.get_visible_category_names()

    def test_rename_category_to_its_own_name_allowed(self, tmp_data_dir):
        service = _make_category_service(tmp_data_dir)
        target = next(c for c in service.get_all_categories() if c["name"] == "Dining & Takeout")

        success, error = service.rename_category(target["id"], "Dining & Takeout")

        assert success is True
        assert error is None

    def test_rename_category_unknown_id_rejected(self, tmp_data_dir):
        service = _make_category_service(tmp_data_dir)
        success, error = service.rename_category(999999, "Whatever")
        assert success is False
        assert error is not None

    def test_rename_category_duplicate_name_rejected(self, tmp_data_dir):
        service = _make_category_service(tmp_data_dir)
        target = next(c for c in service.get_all_categories() if c["name"] == "Dining & Takeout")

        success, error = service.rename_category(target["id"], "Other")

        assert success is False
        assert error is not None
        # Unchanged
        assert any(c["name"] == "Dining & Takeout" for c in service.get_all_categories())

    def test_toggle_hidden_flips_flag_both_directions(self, tmp_data_dir):
        service = _make_category_service(tmp_data_dir)
        target = next(c for c in service.get_all_categories() if c["name"] == "Dining & Takeout")

        service.toggle_hidden(target["id"])
        hidden_now = next(c for c in service.get_all_categories() if c["id"] == target["id"])
        assert hidden_now["hidden"] is True

        service.toggle_hidden(target["id"])
        visible_again = next(c for c in service.get_all_categories() if c["id"] == target["id"])
        assert visible_again["hidden"] is False

    def test_toggle_hidden_unknown_id_rejected(self, tmp_data_dir):
        service = _make_category_service(tmp_data_dir)
        success, error = service.toggle_hidden(999999)
        assert success is False
        assert error is not None

    def test_toggle_hidden_rejects_hiding_other(self, tmp_data_dir):
        service = _make_category_service(tmp_data_dir)
        other = next(c for c in service.get_all_categories() if c["name"] == "Other")

        success, error = service.toggle_hidden(other["id"])

        assert success is False
        assert "Other" in error
        assert "hidden" in error.lower()
        still_visible = next(c for c in service.get_all_categories() if c["id"] == other["id"])
        assert still_visible["hidden"] is False
