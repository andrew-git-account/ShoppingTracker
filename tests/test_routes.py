import pytest

# Spec coverage:
#   TestHistoryRouteCategory      -> BehaviorSpec.md BS-006, BS-007, BS-011, BS-012
#   TestDeleteReceiptRoute        -> BehaviorSpec.md BS-008, BS-009
#   TestHistoryRouteGrouping      -> SP-003: Grouping Receipts by Month


def seed_receipt(app, category="Food & Groceries", purchase_date="2026-06-16", store_name="Test Store"):
    receipt_data = {
        "store_name": store_name,
        "purchase_date": purchase_date,
        "items": [
            {"name": "Milk", "price": 2.99, "quantity": 1, "category": category}
        ],
        "subtotal": 2.99,
        "tax_amount": 0.0,
        "discount_amount": 0.0,
        "total_amount": 2.99,
        "currency": "USD",
        "user_email": "test@example.com"
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


class TestHistoryRouteGrouping:
    """
    Tests for SP-003: Grouping Receipts by Month

    Covers:
    - Receipts grouped by month on history page
    """

    def test_receipts_grouped_by_month(self, logged_in_client, app):
        """Groups receipts from different months separately."""
        seed_receipt(app, category="Food & Groceries", purchase_date="2026-05-15")
        seed_receipt(app, category="Food & Groceries", purchase_date="2026-06-10")

        response = logged_in_client.get("/history")
        assert response.status_code == 200

        # Both month headers should appear
        assert b"2026-05" in response.data
        assert b"2026-06" in response.data

    def test_groups_sorted_descending(self, logged_in_client, app):
        """Month groups appear newest-first."""
        seed_receipt(app, purchase_date="2026-03-01")
        seed_receipt(app, purchase_date="2026-05-01")
        seed_receipt(app, purchase_date="2026-04-01")

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        # Find positions of month headers in HTML
        pos_may = html.find("2026-05")
        pos_apr = html.find("2026-04")
        pos_mar = html.find("2026-03")

        # Verify descending order (May before Apr before Mar)
        assert pos_may < pos_apr < pos_mar

    def test_receipts_within_group_sorted_descending(self, logged_in_client, app):
        """Receipts within same month appear newest-first."""
        seed_receipt(app, store_name="Store A", purchase_date="2026-06-05")
        seed_receipt(app, store_name="Store B", purchase_date="2026-06-15")
        seed_receipt(app, store_name="Store C", purchase_date="2026-06-10")

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        # Find positions of store names in HTML
        pos_a = html.find("Store A")
        pos_b = html.find("Store B")
        pos_c = html.find("Store C")

        # Verify descending order (B=15th, C=10th, A=5th)
        assert pos_b < pos_c < pos_a

    def test_month_header_format(self, logged_in_client, app):
        """Each group has a YYYY-MM header."""
        seed_receipt(app, purchase_date="2026-06-10")

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        # Should have month-header class and YYYY-MM format
        assert 'class="month-header"' in html
        assert "2026-06" in html

    def test_empty_history_still_works(self, logged_in_client):
        """Empty state displays when no receipts exist."""
        response = logged_in_client.get("/history")
        assert response.status_code == 200
        assert b"No receipts yet" in response.data

    def test_fallback_to_saved_at_when_no_purchase_date(self, logged_in_client, app):
        """Uses saved_at date when purchase_date is missing."""
        receipt_data = {
            "store_name": "Test Store",
            "purchase_date": None,
            "items": [
                {"name": "Item", "price": 5.00, "quantity": 1, "category": "Food & Groceries"}
            ],
            "subtotal": 5.00,
            "tax_amount": 0.00,
            "discount_amount": 0.00,
            "total_amount": 5.00,
            "currency": "USD",
            "user_email": "test@example.com"
        }
        app.database.save_receipt(receipt_data)

        response = logged_in_client.get("/history")
        assert response.status_code == 200

        # Should group by saved_at month (2026-07, current month per CLAUDE.md)
        assert b"2026-07" in response.data
