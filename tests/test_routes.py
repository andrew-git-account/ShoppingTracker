import pytest

# Spec coverage:
#   TestHistoryRouteCategory      -> BehaviorSpec.md BS-006, BS-007, BS-011, BS-012
#   TestDeleteReceiptRoute        -> BehaviorSpec.md BS-008, BS-009


def seed_receipt(app, category="Food & Groceries"):
    receipt_data = {
        "store_name": "Test Store",
        "purchase_date": "2026-06-16",
        "items": [
            {"name": "Milk", "price": 2.99, "quantity": 1, "category": category}
        ],
        "subtotal": 2.99,
        "tax_amount": 0.0,
        "discount_amount": 0.0,
        "total_amount": 2.99,
        "currency": "USD",
    }
    return app.database.save_receipt(receipt_data)


class TestHistoryRouteCategory:

    def test_history_shows_category_for_item(self, logged_in_client, app):
        seed_receipt(app, "Food & Groceries")
        response = logged_in_client.get("/history")
        assert response.status_code == 200
        assert b"Food &amp; Groceries" in response.data or b"Food & Groceries" in response.data

    def test_history_shows_other_category_as_fallback(self, logged_in_client, app):
        seed_receipt(app, "Other")
        response = logged_in_client.get("/history")
        assert response.status_code == 200
        assert b"Other" in response.data

    def test_history_renders_all_categories_when_multiple_receipts(self, logged_in_client, app):
        seed_receipt(app, "Food & Groceries")
        seed_receipt(app, "Electronics & Tech")
        response = logged_in_client.get("/history")
        assert response.status_code == 200
        assert b"Electronics" in response.data

    def test_history_empty_state_renders(self, logged_in_client):
        response = logged_in_client.get("/history")
        assert response.status_code == 200
        assert b"No receipts yet" in response.data

    def test_history_item_category_span_present(self, logged_in_client, app):
        seed_receipt(app, "Dining & Takeout")
        response = logged_in_client.get("/history")
        assert b"item-category" in response.data

    @pytest.mark.parametrize("category", [
        "Other",
        "Food & Groceries",
        "Household & Cleaning",
        "Personal Care & Health",
        "Electronics & Tech",
        "Clothing & Apparel",
        "Dining & Takeout",
    ])
    def test_each_seed_category_renders_in_history(self, logged_in_client, app, category):
        seed_receipt(app, category)
        response = logged_in_client.get("/history")
        assert response.status_code == 200
        assert category.encode() in response.data or category.replace("&", "&amp;").encode() in response.data


class TestDeleteReceiptRoute:

    def test_delete_button_present_in_history(self, logged_in_client, app):
        seed_receipt(app)
        response = logged_in_client.get("/history")
        assert b"btn-delete" in response.data

    def test_delete_form_action_url_correct(self, logged_in_client, app):
        seed_receipt(app)
        response = logged_in_client.get("/history")
        assert b"delete-receipt" in response.data

    def test_delete_receipt_redirects_to_history(self, logged_in_client, app):
        rid = seed_receipt(app)
        response = logged_in_client.post(f"/delete-receipt/{rid}")
        assert response.status_code == 302
        assert "/history" in response.headers["Location"]

    def test_delete_receipt_shows_success_flash(self, logged_in_client, app):
        rid = seed_receipt(app)
        logged_in_client.post(f"/delete-receipt/{rid}")
        response = logged_in_client.get("/history")
        assert b"Receipt removed" in response.data

    def test_delete_receipt_removed_from_history(self, logged_in_client, app):
        rid = seed_receipt(app)
        logged_in_client.post(f"/delete-receipt/{rid}")
        response = logged_in_client.get("/history")
        assert b"Test Store" not in response.data

    def test_delete_receipt_not_found_shows_error_flash(self, logged_in_client, app):
        logged_in_client.post("/delete-receipt/no-such-id")
        response = logged_in_client.get("/history")
        assert b"Receipt not found" in response.data
