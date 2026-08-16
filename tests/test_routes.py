import pytest

# Spec coverage:
#   TestHistoryRouteCategory      -> BehaviorSpec.md BS-006, BS-007, BS-011, BS-012
#   TestDeleteReceiptRoute        -> BehaviorSpec.md BS-008, BS-009
#   TestHistoryRouteGrouping      -> SP-003: Grouping Receipts by Month
#   TestStatisticsRoute           -> SP-012: Add Shopping Statistics
#   TestSearchRoute               -> SP-004: Filtering Purchases
#   TestHistoryPricePerUnit       -> SP-013: Price-Per-Unit for Comparison


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


def seed_receipt_with_items(app, items, purchase_date="2026-06-16", store_name="Test Store", currency="USD"):
    """
    Seed a receipt with multiple items of known price/category, for tests
    that need exact totals (e.g. percentage math).

    items: list of (name, price, quantity, category) tuples.
    """
    item_dicts = [
        {"name": name, "price": price, "quantity": quantity, "category": category}
        for name, price, quantity, category in items
    ]
    subtotal = sum(i["price"] * i["quantity"] for i in item_dicts)
    receipt_data = {
        "store_name": store_name,
        "purchase_date": purchase_date,
        "items": item_dicts,
        "subtotal": subtotal,
        "tax_amount": 0.0,
        "discount_amount": 0.0,
        "total_amount": subtotal,
        "currency": currency,
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


class TestStatisticsRoute:
    """
    Tests for SP-012: Add Shopping Statistics

    Covers the Statistics tab: month selection (newest-first, default to most
    recent), per-category amounts and percentages, and grouping by currency
    so mixed-currency months don't produce a misleading combined total.
    """

    def test_statistics_tab_in_nav(self, logged_in_client, app):
        seed_receipt(app)
        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')
        assert 'href="/statistics"' in html
        assert "Statistics" in html

    def test_statistics_page_loads(self, logged_in_client):
        response = logged_in_client.get("/statistics")
        assert response.status_code == 200

    def test_statistics_months_ordered_descending(self, logged_in_client, app):
        seed_receipt(app, purchase_date="2026-03-01")
        seed_receipt(app, purchase_date="2026-05-01")
        seed_receipt(app, purchase_date="2026-04-01")

        response = logged_in_client.get("/statistics")
        html = response.data.decode('utf-8')

        pos_may = html.find("2026-05")
        pos_apr = html.find("2026-04")
        pos_mar = html.find("2026-03")

        assert pos_may < pos_apr < pos_mar

    def test_statistics_defaults_to_most_recent_month(self, logged_in_client, app):
        seed_receipt(app, category="Electronics & Tech", purchase_date="2026-05-01")
        seed_receipt(app, category="Clothing & Apparel", purchase_date="2026-06-01")

        response = logged_in_client.get("/statistics")
        html = response.data.decode('utf-8')

        assert "Clothing" in html
        assert "Electronics" not in html

    def test_statistics_selecting_older_month_switches_categories(self, logged_in_client, app):
        seed_receipt(app, category="Electronics & Tech", purchase_date="2026-05-01")
        seed_receipt(app, category="Clothing & Apparel", purchase_date="2026-06-01")

        response = logged_in_client.get("/statistics?month=2026-05")
        html = response.data.decode('utf-8')

        assert "Electronics" in html
        assert "Clothing" not in html

    def test_statistics_shows_amount_per_category(self, logged_in_client, app):
        seed_receipt_with_items(app, [("Item", 12.50, 1, "Food & Groceries")])

        response = logged_in_client.get("/statistics")
        assert b"12.50" in response.data

    def test_statistics_shows_percentage_per_category(self, logged_in_client, app):
        seed_receipt_with_items(app, [
            ("A", 75.00, 1, "Food & Groceries"),
            ("B", 25.00, 1, "Household & Cleaning"),
        ])

        response = logged_in_client.get("/statistics")
        html = response.data.decode('utf-8')

        assert "75.0%" in html
        assert "25.0%" in html

    def test_statistics_percentages_sum_to_100(self, logged_in_client, app):
        seed_receipt_with_items(app, [
            ("A", 50.00, 1, "Food & Groceries"),
            ("B", 30.00, 1, "Household & Cleaning"),
            ("C", 20.00, 1, "Electronics & Tech"),
        ])

        response = logged_in_client.get("/statistics")
        html = response.data.decode('utf-8')

        assert "50.0%" in html
        assert "30.0%" in html
        assert "20.0%" in html

    def test_statistics_groups_by_currency_independently(self, logged_in_client, app):
        """
        A CHF receipt and a USD receipt in the same month must not be summed
        together. Each currency's categories should show 100% of their own
        currency's total, not a share of a combined (meaningless) total.
        """
        seed_receipt_with_items(
            app, [("A", 30.00, 1, "Food & Groceries")], currency="CHF"
        )
        seed_receipt_with_items(
            app, [("B", 70.00, 1, "Electronics & Tech")], currency="USD"
        )

        response = logged_in_client.get("/statistics")
        html = response.data.decode('utf-8')

        assert "CHF" in html
        assert "USD" in html
        # Each currency's single category is 100% of its own group, not 30%/70%.
        # (Search the labeled percentage span specifically — the CSS bar's
        # "width: 100.0%" style also happens to contain the substring "100.0%".)
        assert html.count('category-percentage">100.0%') == 2

    def test_statistics_empty_state_when_no_receipts(self, logged_in_client):
        response = logged_in_client.get("/statistics")
        assert response.status_code == 200
        assert b"No shopping data yet" in response.data

    def test_statistics_unknown_month_falls_back_gracefully(self, logged_in_client, app):
        seed_receipt(app, category="Food & Groceries", purchase_date="2026-06-01")

        response = logged_in_client.get("/statistics?month=2099-01")
        assert response.status_code == 200
        assert b"Food" in response.data


class TestSearchRoute:
    """
    Tests for SP-004: Filtering Purchases

    Covers item search on the History page: minimum-length validation,
    case-insensitive substring matching across all receipts, showing
    price/store/date context without subtotal/total, and leaving the
    normal (non-search) History view unaffected.
    """

    def test_search_form_present_on_history_page(self, logged_in_client):
        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')
        assert 'name="q"' in html
        assert "Search" in html

    def test_search_too_short_shows_error_and_normal_view(self, logged_in_client, app):
        seed_receipt(app, purchase_date="2026-06-10")

        response = logged_in_client.get("/history?q=ab")
        html = response.data.decode('utf-8')

        assert "at least 3 characters" in html
        assert 'class="month-header"' in html

    def test_search_too_short_retains_typed_term(self, logged_in_client, app):
        seed_receipt(app, purchase_date="2026-06-10")

        response = logged_in_client.get("/history?q=ab")
        assert b'value="ab"' in response.data

    def test_search_matches_case_insensitive(self, logged_in_client, app):
        seed_receipt_with_items(app, [("Milk 1L", 1.50, 1, "Food & Groceries")], store_name="Store A")
        seed_receipt_with_items(app, [("MILK Chocolate", 2.50, 1, "Food & Groceries")], store_name="Store B")

        response = logged_in_client.get("/history?q=milk")
        html = response.data.decode('utf-8')

        assert "Milk 1L" in html
        assert "MILK Chocolate" in html

    def test_search_matches_substring_anywhere_in_name(self, logged_in_client, app):
        seed_receipt_with_items(app, [("Almond Milk", 2.20, 1, "Food & Groceries")])

        response = logged_in_client.get("/history?q=milk")
        assert b"Almond Milk" in response.data

    def test_search_result_shows_price_store_and_date(self, logged_in_client, app):
        seed_receipt_with_items(
            app, [("Sourdough Bread", 4.25, 1, "Food & Groceries")],
            store_name="Bakery Nine", purchase_date="2026-06-12"
        )

        response = logged_in_client.get("/history?q=sourdough")
        html = response.data.decode('utf-8')

        assert "Sourdough Bread" in html
        assert "Bakery Nine" in html
        assert "2026-06-12" in html
        assert "4.25" in html

    def test_search_hides_subtotal_and_total(self, logged_in_client, app):
        seed_receipt_with_items(app, [("Sourdough Bread", 4.25, 1, "Food & Groceries")])

        response = logged_in_client.get("/history?q=sourdough")
        assert b"Subtotal" not in response.data
        assert b"Total receipts" not in response.data

    def test_search_no_matches_shows_empty_state(self, logged_in_client, app):
        seed_receipt(app, purchase_date="2026-06-10")

        response = logged_in_client.get("/history?q=zzz999")
        assert response.status_code == 200
        assert b"No matches found" in response.data

    def test_search_results_sorted_by_name_then_price(self, logged_in_client, app):
        seed_receipt_with_items(app, [("Milk 1L", 1.50, 1, "Food & Groceries")], store_name="Coop")
        seed_receipt_with_items(app, [("Milk 1L", 1.30, 1, "Food & Groceries")], store_name="Migros")

        response = logged_in_client.get("/history?q=milk")
        html = response.data.decode('utf-8')

        pos_130 = html.find("1.30")
        pos_150 = html.find("1.50")
        assert pos_130 < pos_150

    def test_search_shows_price_per_unit_for_weighed_item(self, logged_in_client, app):
        seed_receipt_with_item_dict(app, {
            "name": "Sardinenfilet Butterfly", "price": 14.50, "quantity": 1,
            "category": "Food & Groceries", "amount": 0.744, "unit": "kg"
        })

        response = logged_in_client.get("/history?q=sardinenfilet")
        html = response.data.decode('utf-8')

        assert "19.49/kg" in html

    def test_search_results_sorted_by_price_per_unit_not_raw_price(self, logged_in_client, app):
        """
        A larger pack with a lower raw total price but a worse per-kg rate
        should sort AFTER a smaller pack with a higher raw price but better
        per-kg rate - proves results are ranked by price_per_unit, not price.
        """
        seed_receipt_with_item_dict(app, {
            "name": "Tomatoes", "price": 3.00, "quantity": 1,
            "category": "Food & Groceries", "amount": 2.0, "unit": "kg"
        }, store_name="CheapPerKg")  # 1.50/kg - better rate, higher raw price
        seed_receipt_with_item_dict(app, {
            "name": "Tomatoes", "price": 2.00, "quantity": 1,
            "category": "Food & Groceries", "amount": 0.5, "unit": "kg"
        }, store_name="ExpensivePerKg")  # 4.00/kg - worse rate, lower raw price

        response = logged_in_client.get("/history?q=tomatoes")
        html = response.data.decode('utf-8')

        pos_cheap = html.find("CheapPerKg")
        pos_expensive = html.find("ExpensivePerKg")
        assert pos_cheap < pos_expensive

    def test_normal_history_view_unaffected_by_search_feature(self, logged_in_client, app):
        seed_receipt(app, purchase_date="2026-06-10")

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        assert 'class="month-header"' in html
        assert "Total receipts" in html
        assert "No matches found" not in html


def seed_receipt_with_item_dict(app, item_dict, purchase_date="2026-06-16", store_name="Test Store", currency="CHF"):
    """Seed a receipt with a single, fully custom item dict - used for
    amount/unit tests that need control over raw stored JSON shape (including
    simulating pre-SP-013 records with no amount/unit keys at all)."""
    price = item_dict.get("price", 0.0)
    quantity = item_dict.get("quantity", 1)
    total = price * quantity
    receipt_data = {
        "store_name": store_name,
        "purchase_date": purchase_date,
        "items": [item_dict],
        "subtotal": total,
        "tax_amount": 0.0,
        "discount_amount": 0.0,
        "total_amount": total,
        "currency": currency,
        "user_email": "test@example.com"
    }
    return app.database.save_receipt(receipt_data)


class TestHistoryPricePerUnit:
    """
    Tests for SP-013: Price-Per-Unit for Comparison

    Covers the price-per-unit display on the History page, including the
    real-world weighed-item case and backward compatibility with receipts
    saved before this feature existed.
    """

    def test_price_per_unit_shown_for_weighed_item(self, logged_in_client, app):
        seed_receipt_with_item_dict(app, {
            "name": "Sardinenfilet Butterfly", "price": 14.50, "quantity": 1,
            "category": "Food & Groceries", "amount": 0.744, "unit": "kg"
        })

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        assert "19.49/kg" in html

    def test_price_per_unit_shown_for_piece_item(self, logged_in_client, app):
        seed_receipt_with_item_dict(app, {
            "name": "Milk", "price": 2.99, "quantity": 1,
            "category": "Food & Groceries", "amount": 1.0, "unit": "piece"
        })

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        assert "2.99/piece" in html

    def test_price_per_unit_shown_for_legacy_item_without_amount_unit(self, logged_in_client, app):
        """Simulates a receipt saved before SP-013 - no amount/unit keys."""
        seed_receipt_with_item_dict(app, {
            "name": "Old Item", "price": 5.00, "quantity": 1, "category": "Other"
        })

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        assert response.status_code == 200
        assert "5.00/piece" in html

    def test_item_price_per_unit_css_class_present(self, logged_in_client, app):
        seed_receipt_with_item_dict(app, {
            "name": "Milk", "price": 2.99, "quantity": 1, "category": "Food & Groceries"
        })

        response = logged_in_client.get("/history")
        assert b"item-price-per-unit" in response.data
