import io
import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from werkzeug.datastructures import FileStorage

from app.models import Transaction

# Spec coverage:
#   TestHistoryRouteCategory      -> BehaviorSpec.md BS-006, BS-007, BS-011, BS-012
#   TestDeleteReceiptRoute        -> BehaviorSpec.md BS-008, BS-009
#   TestHistoryRouteGrouping      -> SP-003: Grouping Receipts by Month
#   TestStatisticsRoute           -> SP-012: Add Shopping Statistics
#   TestSearchRoute               -> SP-004: Filtering Purchases
#   TestHistoryPricePerUnit       -> SP-013: Price-Per-Unit for Comparison
#   TestHistoryTransactions       -> SP-029: Display Statement Transactions in History


def seed_receipt(app, category="Food & Groceries", purchase_date="2026-06-16", store_name="Test Store", user_email="test@example.com"):
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
        "user_email": user_email
    }
    return app.database.save_receipt(receipt_data)


def seed_transaction(app, date="2026-06-16", description="Test Merchant", amount=9.99,
                      currency="USD", direction="debit", category="Other", source="card",
                      statement_id=None, linked_receipt_id=None, user_email="test@example.com"):
    return app.transaction_service.save_transaction(Transaction(
        date=date, description=description, amount=amount, currency=currency,
        direction=direction, category=category, source=source, statement_id=statement_id,
        linked_receipt_id=linked_receipt_id, user_email=user_email
    ))


def seed_receipt_with_items(app, items, purchase_date="2026-06-16", store_name="Test Store", currency="USD", user_email="test@example.com"):
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
        "user_email": user_email
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

    def test_total_count_matches_displayed_receipt_cards(self, logged_in_client, app):
        seed_receipt(app)
        rid2 = seed_receipt(app)
        app.database.soft_delete_receipt(rid2, "test@example.com")
        response = logged_in_client.get("/history")
        assert b"Total receipts: <strong>1</strong>" in response.data

    def test_delete_receipt_decreases_total_count(self, logged_in_client, app):
        seed_receipt(app)
        rid2 = seed_receipt(app)
        response = logged_in_client.get("/history")
        assert b"Total receipts: <strong>2</strong>" in response.data
        logged_in_client.post(f"/delete-receipt/{rid2}")
        response = logged_in_client.get("/history")
        assert b"Total receipts: <strong>1</strong>" in response.data


class TestEditReceiptRoute:
    """SP-022: edit a saved receipt's items/currency/total, or remove items."""

    def test_edit_button_present_in_history(self, logged_in_client, app):
        seed_receipt(app)
        response = logged_in_client.get("/history")
        assert b"btn-edit" in response.data

    def test_edit_link_url_correct(self, logged_in_client, app):
        rid = seed_receipt(app)
        response = logged_in_client.get("/history")
        assert f"/receipt/{rid}/edit".encode() in response.data

    def test_get_edit_page_shows_current_data(self, logged_in_client, app):
        rid = seed_receipt(app)
        response = logged_in_client.get(f"/receipt/{rid}/edit")
        assert response.status_code == 200
        assert b"Milk" in response.data
        assert b"2.99" in response.data

    def test_get_edit_nonexistent_receipt_redirects(self, logged_in_client, app):
        response = logged_in_client.get("/receipt/no-such-id/edit")
        assert response.status_code == 302
        assert "/history" in response.headers["Location"]
        follow = logged_in_client.get("/history")
        assert b"Receipt not found" in follow.data

    def test_get_edit_other_users_receipt_redirects(self, logged_in_client, app):
        rid = seed_receipt(app, user_email="other@example.com")
        response = logged_in_client.get(f"/receipt/{rid}/edit")
        assert response.status_code == 302
        assert "/history" in response.headers["Location"]

    def test_post_edit_updates_item_name_category_price(self, logged_in_client, app):
        rid = seed_receipt(app)
        response = logged_in_client.post(f"/receipt/{rid}/edit", data={
            "currency": "USD",
            "total_amount": "4.50",
            "item_name": ["Oat Milk"],
            "item_category": ["Food & Groceries"],
            "item_price": ["4.50"],
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Oat Milk" in response.data
        assert b"Milk" in response.data  # substring of "Oat Milk", sanity check for the new name

    def test_post_edit_updates_currency_and_total(self, logged_in_client, app):
        rid = seed_receipt(app)
        logged_in_client.post(f"/receipt/{rid}/edit", data={
            "currency": "EUR",
            "total_amount": "9.99",
            "item_name": ["Milk"],
            "item_category": ["Food & Groceries"],
            "item_price": ["9.99"],
        })
        record = app.database.get_receipt_by_id(rid, "test@example.com")
        assert record["currency"] == "EUR"
        assert record["total_amount"] == 9.99

    def test_post_edit_does_not_duplicate_receipt(self, logged_in_client, app):
        rid = seed_receipt(app)
        logged_in_client.post(f"/receipt/{rid}/edit", data={
            "currency": "USD",
            "total_amount": "4.50",
            "item_name": ["Oat Milk"],
            "item_category": ["Food & Groceries"],
            "item_price": ["4.50"],
        })
        assert app.receipt_service.get_receipts_count("test@example.com") == 1

    def test_post_edit_removes_marked_item(self, logged_in_client, app):
        rid = seed_receipt_with_items(app, [
            ("Bread", 3.00, 1, "Food & Groceries"),
            ("Milk", 2.99, 1, "Food & Groceries"),
        ])
        logged_in_client.post(f"/receipt/{rid}/edit", data={
            "currency": "USD",
            "total_amount": "3.00",
            "item_name": ["Bread", "Milk"],
            "item_category": ["Food & Groceries", "Food & Groceries"],
            "item_price": ["3.00", "2.99"],
            "item_remove": ["1"],
        })
        record = app.database.get_receipt_by_id(rid, "test@example.com")
        assert len(record["items"]) == 1
        assert record["items"][0]["name"] == "Bread"

    def test_post_edit_removing_all_items_rejected(self, logged_in_client, app):
        rid = seed_receipt(app)
        response = logged_in_client.post(f"/receipt/{rid}/edit", data={
            "currency": "USD",
            "total_amount": "2.99",
            "item_name": ["Milk"],
            "item_category": ["Food & Groceries"],
            "item_price": ["2.99"],
            "item_remove": ["0"],
        })
        assert response.status_code == 200
        assert b"must have at least one item" in response.data.lower()
        record = app.database.get_receipt_by_id(rid, "test@example.com")
        assert len(record["items"]) == 1
        assert record["items"][0]["name"] == "Milk"

    def test_post_edit_negative_price_rejected_preserves_other_edits(self, logged_in_client, app):
        rid = seed_receipt_with_items(app, [
            ("Bread", 3.00, 1, "Food & Groceries"),
            ("Milk", 2.99, 1, "Food & Groceries"),
        ])
        response = logged_in_client.post(f"/receipt/{rid}/edit", data={
            "currency": "USD",
            "total_amount": "5.99",
            "item_name": ["Bread", "Chocolate Milk"],
            "item_category": ["Food & Groceries", "Food & Groceries"],
            "item_price": ["-5.00", "2.99"],
        })
        assert response.status_code == 200
        assert b"negative price" in response.data
        assert b"Chocolate Milk" in response.data  # the other edit wasn't lost
        record = app.database.get_receipt_by_id(rid, "test@example.com")
        assert record["items"][1]["name"] == "Milk"  # db unchanged

    def test_post_edit_invalid_price_input_rejected(self, logged_in_client, app):
        rid = seed_receipt(app)
        response = logged_in_client.post(f"/receipt/{rid}/edit", data={
            "currency": "USD",
            "total_amount": "2.99",
            "item_name": ["Milk"],
            "item_category": ["Food & Groceries"],
            "item_price": ["abc"],
        })
        assert response.status_code == 200
        assert b"Invalid price" in response.data

    def test_post_edit_negative_total_rejected(self, logged_in_client, app):
        rid = seed_receipt(app)
        response = logged_in_client.post(f"/receipt/{rid}/edit", data={
            "currency": "USD",
            "total_amount": "-1",
            "item_name": ["Milk"],
            "item_category": ["Food & Groceries"],
            "item_price": ["2.99"],
        })
        assert response.status_code == 200
        assert b"Total amount cannot be negative" in response.data

    def test_post_edit_cannot_edit_other_users_receipt(self, logged_in_client, app):
        rid = seed_receipt(app, user_email="other@example.com", store_name="Other User Store")
        response = logged_in_client.post(f"/receipt/{rid}/edit", data={
            "currency": "USD",
            "total_amount": "1.00",
            "item_name": ["Hacked"],
            "item_category": ["Food & Groceries"],
            "item_price": ["1.00"],
        })
        assert response.status_code == 302
        record = app.database.get_receipt_by_id(rid, "other@example.com")
        assert record["store_name"] == "Other User Store"

    def test_post_edit_success_redirects_to_history(self, logged_in_client, app):
        rid = seed_receipt(app)
        response = logged_in_client.post(f"/receipt/{rid}/edit", data={
            "currency": "USD",
            "total_amount": "2.99",
            "item_name": ["Milk"],
            "item_category": ["Food & Groceries"],
            "item_price": ["2.99"],
        })
        assert response.status_code == 302
        assert "/history" in response.headers["Location"]

    def test_post_edit_success_flash_shown(self, logged_in_client, app):
        rid = seed_receipt(app)
        response = logged_in_client.post(f"/receipt/{rid}/edit", data={
            "currency": "USD",
            "total_amount": "2.99",
            "item_name": ["Milk"],
            "item_category": ["Food & Groceries"],
            "item_price": ["2.99"],
        }, follow_redirects=True)
        assert b"Receipt updated" in response.data


class TestEditStatementRoute:
    """SP-030: edit every transaction in a statement at once, mirroring receipt item editing."""

    def test_edit_button_present_in_history(self, logged_in_client, app):
        seed_transaction(app, statement_id="stmt-1")
        seed_transaction(app, statement_id="stmt-1", description="Second Merchant")
        response = logged_in_client.get("/history")
        assert response.data.count(b"btn-edit") == 1

    def test_edit_link_url_correct(self, logged_in_client, app):
        seed_transaction(app, statement_id="stmt-1")
        response = logged_in_client.get("/history")
        assert b"/statement/stmt-1/edit" in response.data

    def test_get_edit_page_shows_all_transactions(self, logged_in_client, app):
        seed_transaction(app, statement_id="stmt-1", description="Corner Store", amount=12.50)
        seed_transaction(app, statement_id="stmt-1", description="Gas Station", amount=40.00)
        response = logged_in_client.get("/statement/stmt-1/edit")
        assert response.status_code == 200
        assert b"Corner Store" in response.data
        assert b"Gas Station" in response.data
        assert b"12.5" in response.data
        assert b"40.0" in response.data

    def test_get_edit_nonexistent_statement_redirects(self, logged_in_client, app):
        response = logged_in_client.get("/statement/no-such-id/edit")
        assert response.status_code == 302
        assert "/history" in response.headers["Location"]
        follow = logged_in_client.get("/history")
        assert b"Statement not found" in follow.data

    def test_get_edit_other_users_statement_redirects(self, logged_in_client, app):
        seed_transaction(app, statement_id="stmt-1", user_email="other@example.com")
        response = logged_in_client.get("/statement/stmt-1/edit")
        assert response.status_code == 302
        assert "/history" in response.headers["Location"]

    def test_post_edit_updates_all_rows(self, logged_in_client, app):
        id1 = seed_transaction(app, statement_id="stmt-1", description="Old A", date="2026-06-16",
                                category="Other", direction="debit", currency="USD", amount=9.99)
        id2 = seed_transaction(app, statement_id="stmt-1", description="Old B", date="2026-06-16",
                                category="Other", direction="debit", currency="USD", amount=5.00)
        logged_in_client.post("/statement/stmt-1/edit", data={
            "transaction_id": [id1, id2],
            "description": ["New A", "New B"],
            "date": ["2026-07-01", "2026-07-02"],
            "category": ["Food & Groceries", "Other"],
            "is_credit": ["0"],  # row 0 (id1) toggled to credit; row 1 (id2) left unchecked = debit
            "currency": ["EUR", "USD"],
            "amount": ["42.50", "10.00"],
        })
        updated1 = app.transaction_service.get_transaction_by_id(id1, "test@example.com")
        updated2 = app.transaction_service.get_transaction_by_id(id2, "test@example.com")
        assert updated1.description == "New A"
        assert updated1.date == "2026-07-01"
        assert updated1.category == "Food & Groceries"
        assert updated1.direction == "credit"
        assert updated1.currency == "EUR"
        assert updated1.amount == 42.50
        assert updated2.description == "New B"
        assert updated2.direction == "debit"
        assert updated2.amount == 10.00

    def test_post_edit_does_not_duplicate_transactions(self, logged_in_client, app):
        id1 = seed_transaction(app, statement_id="stmt-1")
        id2 = seed_transaction(app, statement_id="stmt-1", description="Second")
        logged_in_client.post("/statement/stmt-1/edit", data={
            "transaction_id": [id1, id2],
            "description": ["A", "B"],
            "date": ["2026-06-16", "2026-06-16"],
            "category": ["Other", "Other"],
            "currency": ["USD", "USD"],
            "amount": ["1.00", "2.00"],
        })
        assert len(app.transaction_service.get_all_transactions("test@example.com")) == 2

    def test_post_edit_negative_amount_in_one_row_rejects_whole_form(self, logged_in_client, app):
        id1 = seed_transaction(app, statement_id="stmt-1", description="Keep Me")
        id2 = seed_transaction(app, statement_id="stmt-1", description="Old Description")
        response = logged_in_client.post("/statement/stmt-1/edit", data={
            "transaction_id": [id1, id2],
            "description": ["Keep Me", "New Description"],
            "date": ["2026-06-16", "2026-06-16"],
            "category": ["Other", "Other"],
            "currency": ["USD", "USD"],
            "amount": ["9.99", "-5.00"],
        })
        assert response.status_code == 200
        assert b"negative" in response.data.lower()
        assert b"New Description" in response.data  # submitted edit preserved in re-rendered form
        assert app.transaction_service.get_transaction_by_id(id1, "test@example.com").description == "Keep Me"
        assert app.transaction_service.get_transaction_by_id(id2, "test@example.com").description == "Old Description"

    def test_post_edit_invalid_amount_input_rejected(self, logged_in_client, app):
        id1 = seed_transaction(app, statement_id="stmt-1")
        response = logged_in_client.post("/statement/stmt-1/edit", data={
            "transaction_id": [id1],
            "description": ["Test Merchant"],
            "date": ["2026-06-16"],
            "category": ["Other"],
            "currency": ["USD"],
            "amount": ["abc"],
        })
        assert response.status_code == 200
        assert b"valid amount" in response.data.lower()

    def test_post_edit_invalid_category_falls_back_to_other(self, logged_in_client, app):
        id1 = seed_transaction(app, statement_id="stmt-1", category="Food & Groceries")
        logged_in_client.post("/statement/stmt-1/edit", data={
            "transaction_id": [id1],
            "description": ["Test Merchant"],
            "date": ["2026-06-16"],
            "category": ["Nonsense"],
            "currency": ["USD"],
            "amount": ["9.99"],
        })
        updated = app.transaction_service.get_transaction_by_id(id1, "test@example.com")
        assert updated.category == "Other"

    def test_post_edit_unchecked_toggle_means_debit(self, logged_in_client, app):
        id1 = seed_transaction(app, statement_id="stmt-1", direction="credit")
        logged_in_client.post("/statement/stmt-1/edit", data={
            "transaction_id": [id1],
            "description": ["Test Merchant"],
            "date": ["2026-06-16"],
            "category": ["Other"],
            # is_credit omitted entirely - an unchecked checkbox submits nothing
            "currency": ["USD"],
            "amount": ["9.99"],
        })
        updated = app.transaction_service.get_transaction_by_id(id1, "test@example.com")
        assert updated.direction == "debit"

    def test_post_edit_checked_toggle_means_credit(self, logged_in_client, app):
        id1 = seed_transaction(app, statement_id="stmt-1", direction="debit")
        logged_in_client.post("/statement/stmt-1/edit", data={
            "transaction_id": [id1],
            "description": ["Test Merchant"],
            "date": ["2026-06-16"],
            "category": ["Other"],
            "is_credit": ["0"],
            "currency": ["USD"],
            "amount": ["9.99"],
        })
        updated = app.transaction_service.get_transaction_by_id(id1, "test@example.com")
        assert updated.direction == "credit"

    def test_post_edit_preserves_untouched_fields(self, logged_in_client, app):
        id1 = seed_transaction(app, statement_id="stmt-1", source="bank")
        logged_in_client.post("/statement/stmt-1/edit", data={
            "transaction_id": [id1],
            "description": ["New Description"],
            "date": ["2026-07-01"],
            "category": ["Other"],
            "currency": ["EUR"],
            "amount": ["50.00"],
        })
        updated = app.transaction_service.get_transaction_by_id(id1, "test@example.com")
        assert updated.source == "bank"
        assert updated.statement_id == "stmt-1"
        assert updated.transaction_id == id1
        assert updated.is_deleted is False

    def test_post_edit_cannot_edit_other_users_statement(self, logged_in_client, app):
        id1 = seed_transaction(app, statement_id="stmt-1", user_email="other@example.com", description="Original")
        response = logged_in_client.post("/statement/stmt-1/edit", data={
            "transaction_id": [id1],
            "description": ["Hacked"],
            "date": ["2026-06-16"],
            "category": ["Other"],
            "currency": ["USD"],
            "amount": ["1.00"],
        })
        assert response.status_code == 302
        record = app.transaction_service.get_transaction_by_id(id1, "other@example.com")
        assert record.description == "Original"

    def test_post_edit_tampered_transaction_id_rejects_whole_form(self, logged_in_client, app):
        own_id = seed_transaction(app, statement_id="stmt-1", description="Mine")
        foreign_id = seed_transaction(app, statement_id="stmt-2", user_email="other@example.com",
                                       description="Not Mine")
        response = logged_in_client.post("/statement/stmt-1/edit", data={
            "transaction_id": [own_id, foreign_id],
            "description": ["Mine Edited", "Hacked"],
            "date": ["2026-06-16", "2026-06-16"],
            "category": ["Other", "Other"],
            "currency": ["USD", "USD"],
            "amount": ["9.99", "1.00"],
        })
        assert response.status_code == 200
        assert b"not found" in response.data.lower()
        assert app.transaction_service.get_transaction_by_id(own_id, "test@example.com").description == "Mine"
        assert app.transaction_service.get_transaction_by_id(foreign_id, "other@example.com").description == "Not Mine"

    def test_post_edit_success_redirects_to_history(self, logged_in_client, app):
        id1 = seed_transaction(app, statement_id="stmt-1")
        response = logged_in_client.post("/statement/stmt-1/edit", data={
            "transaction_id": [id1],
            "description": ["Test Merchant"],
            "date": ["2026-06-16"],
            "category": ["Other"],
            "currency": ["USD"],
            "amount": ["9.99"],
        })
        assert response.status_code == 302
        assert "/history" in response.headers["Location"]

    def test_post_edit_amount_change_triggers_matcher(self, logged_in_client, app):
        id1 = seed_transaction(app, statement_id="stmt-1", amount=9.99, date="2026-06-16", currency="USD")
        rid = seed_receipt(app)  # default: total_amount=2.99, purchase_date=2026-06-16, currency=USD
        logged_in_client.post("/statement/stmt-1/edit", data={
            "transaction_id": [id1],
            "description": ["Test Merchant"],
            "date": ["2026-06-16"],
            "category": ["Other"],
            "currency": ["USD"],
            "amount": ["2.99"],
        })
        updated = app.transaction_service.get_transaction_by_id(id1, "test@example.com")
        assert updated.linked_receipt_id == rid

    def test_post_edit_does_not_clear_existing_link_when_edit_makes_it_stale(self, logged_in_client, app):
        rid = seed_receipt(app)  # total_amount=2.99
        id1 = seed_transaction(app, statement_id="stmt-1", amount=2.99, date="2026-06-16",
                                currency="USD", linked_receipt_id=rid)
        logged_in_client.post("/statement/stmt-1/edit", data={
            "transaction_id": [id1],
            "description": ["Test Merchant"],
            "date": ["2026-06-16"],
            "category": ["Other"],
            "currency": ["USD"],
            "amount": ["50.00"],
        })
        updated = app.transaction_service.get_transaction_by_id(id1, "test@example.com")
        assert updated.linked_receipt_id == rid

    def test_post_edit_one_row_only_still_works(self, logged_in_client, app):
        id1 = seed_transaction(app, statement_id="stmt-1", description="Solo")
        logged_in_client.post("/statement/stmt-1/edit", data={
            "transaction_id": [id1],
            "description": ["Solo Updated"],
            "date": ["2026-06-16"],
            "category": ["Other"],
            "currency": ["USD"],
            "amount": ["9.99"],
        })
        updated = app.transaction_service.get_transaction_by_id(id1, "test@example.com")
        assert updated.description == "Solo Updated"


def _stub_llm_extraction(app, reconciled: bool = True, **overrides):
    payload = {
        "store_name": "Corner Store",
        "purchase_date": "2026-06-16",
        "items": [{"name": "Gum", "price": 1.00, "quantity": 1, "category": "Food & Groceries"}],
        "tax_amount": 0.0,
        "discount_amount": 0.0,
        "total_amount": 1.00,
        "currency": "USD",
    }
    payload.update(overrides)
    app.receipt_service.llm_service = MagicMock()
    app.receipt_service.llm_service.extract_receipt_data.return_value = (payload, reconciled)
    return payload


def _upload_data(edit_before_save=False):
    data = {"receipt": (io.BytesIO(b"fake-image-bytes"), "receipt.jpg")}
    if edit_before_save:
        data["edit_before_save"] = "on"
    return data


def _make_upload_file():
    """FileStorage for calling receipt_service.process_receipt() directly (bypassing HTTP)."""
    return FileStorage(stream=io.BytesIO(b"fake-image-bytes"), filename="receipt.jpg", content_type="image/jpeg")


class TestEditBeforeSavingDraftFlow:
    """SP-023: 'Edit before saving' checkbox, draft review/save/discard."""

    def test_upload_form_has_edit_before_save_checkbox(self, logged_in_client):
        response = logged_in_client.get("/upload")
        assert b'<input type="checkbox" name="edit_before_save">' in response.data

    def test_upload_without_checkbox_saves_immediately_unchanged(self, logged_in_client, app):
        _stub_llm_extraction(app)
        response = logged_in_client.post(
            "/upload", data=_upload_data(edit_before_save=False), content_type="multipart/form-data"
        )
        assert response.status_code == 302
        assert "/history" in response.headers["Location"]
        assert any(
            r["store_name"] == "Corner Store"
            for r in app.database.get_all_receipts("test@example.com")
        )

    def test_upload_with_checkbox_checked_redirects_to_draft_edit(self, logged_in_client, app):
        _stub_llm_extraction(app)
        response = logged_in_client.post(
            "/upload", data=_upload_data(edit_before_save=True), content_type="multipart/form-data"
        )
        assert response.status_code == 302
        assert "/receipt/draft/" in response.headers["Location"]
        assert response.headers["Location"].endswith("/edit")
        assert app.database.get_all_receipts("test@example.com") == []

    def test_upload_with_checkbox_shows_review_flash_and_heading(self, logged_in_client, app):
        _stub_llm_extraction(app)
        response = logged_in_client.post(
            "/upload", data=_upload_data(edit_before_save=True), content_type="multipart/form-data",
            follow_redirects=True
        )
        assert b"Review the extracted receipt" in response.data
        assert b"Review Receipt" in response.data

    def _create_draft_via_upload(self, logged_in_client, app, **overrides):
        _stub_llm_extraction(app, **overrides)
        response = logged_in_client.post(
            "/upload", data=_upload_data(edit_before_save=True), content_type="multipart/form-data"
        )
        location = response.headers["Location"]
        return location.split("/")[-2]

    def test_draft_edit_get_shows_extracted_data_and_draft_controls(self, logged_in_client, app):
        draft_id = self._create_draft_via_upload(logged_in_client, app)
        response = logged_in_client.get(f"/receipt/draft/{draft_id}/edit")
        assert response.status_code == 200
        assert b"Gum" in response.data
        assert b"Discard" in response.data
        assert b"Save Receipt" in response.data
        assert b">Cancel<" not in response.data

    def test_draft_edit_get_nonexistent_draft_redirects(self, logged_in_client):
        response = logged_in_client.get("/receipt/draft/no-such-id/edit")
        assert response.status_code == 302
        assert "/history" in response.headers["Location"]
        follow = logged_in_client.get("/history")
        assert b"Draft not found" in follow.data

    def test_draft_edit_get_other_users_draft_redirects(self, logged_in_client, app):
        app.receipt_service.llm_service = MagicMock()
        app.receipt_service.llm_service.extract_receipt_data.return_value = ({
            "store_name": "Other User Store",
            "purchase_date": "2026-06-16",
            "items": [{"name": "Gum", "price": 1.00, "quantity": 1, "category": "Food & Groceries"}],
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 1.00,
            "currency": "USD",
        }, True)
        _, draft_id, _ = app.receipt_service.process_receipt(
            _make_upload_file(), "other@example.com", edit_before_save=True
        )
        response = logged_in_client.get(f"/receipt/draft/{draft_id}/edit")
        assert response.status_code == 302
        assert "/history" in response.headers["Location"]

    def test_draft_edit_post_creates_receipt_and_deletes_draft(self, logged_in_client, app):
        draft_id = self._create_draft_via_upload(logged_in_client, app)
        response = logged_in_client.post(f"/receipt/draft/{draft_id}/edit", data={
            "currency": "USD",
            "total_amount": "1.00",
            "item_name": ["Gum"],
            "item_category": ["Food & Groceries"],
            "item_price": ["1.00"],
        })
        assert response.status_code == 302
        assert "/history" in response.headers["Location"]
        assert len(app.database.get_all_receipts("test@example.com")) == 1
        assert app.receipt_service.get_draft(draft_id, "test@example.com") is None

    def test_draft_edit_post_removing_all_items_rejected(self, logged_in_client, app):
        draft_id = self._create_draft_via_upload(logged_in_client, app)
        response = logged_in_client.post(f"/receipt/draft/{draft_id}/edit", data={
            "currency": "USD",
            "total_amount": "1.00",
            "item_name": ["Gum"],
            "item_category": ["Food & Groceries"],
            "item_price": ["1.00"],
            "item_remove": ["0"],
        })
        assert response.status_code == 200
        assert b"must have at least one item" in response.data.lower()
        assert app.database.get_all_receipts("test@example.com") == []
        assert app.receipt_service.get_draft(draft_id, "test@example.com") is not None

    def test_draft_edit_post_negative_price_rejected(self, logged_in_client, app):
        draft_id = self._create_draft_via_upload(logged_in_client, app)
        response = logged_in_client.post(f"/receipt/draft/{draft_id}/edit", data={
            "currency": "USD",
            "total_amount": "1.00",
            "item_name": ["Gum"],
            "item_category": ["Food & Groceries"],
            "item_price": ["-1.00"],
        })
        assert response.status_code == 200
        assert b"negative price" in response.data
        assert app.database.get_all_receipts("test@example.com") == []

    def test_draft_edit_post_invalid_total_rejected(self, logged_in_client, app):
        draft_id = self._create_draft_via_upload(logged_in_client, app)
        response = logged_in_client.post(f"/receipt/draft/{draft_id}/edit", data={
            "currency": "USD",
            "total_amount": "-1",
            "item_name": ["Gum"],
            "item_category": ["Food & Groceries"],
            "item_price": ["1.00"],
        })
        assert response.status_code == 200
        assert b"Total amount cannot be negative" in response.data
        assert app.database.get_all_receipts("test@example.com") == []

    def test_draft_discard_deletes_draft_and_redirects(self, logged_in_client, app):
        draft_id = self._create_draft_via_upload(logged_in_client, app)
        response = logged_in_client.post(f"/receipt/draft/{draft_id}/discard")
        assert response.status_code == 302
        assert "/history" in response.headers["Location"]
        follow = logged_in_client.get("/history")
        assert b"Draft discarded" in follow.data
        follow_edit = logged_in_client.get(f"/receipt/draft/{draft_id}/edit")
        assert "/history" in follow_edit.headers["Location"]

    def test_draft_discard_unknown_id_does_not_error(self, logged_in_client):
        response = logged_in_client.post("/receipt/draft/no-such-id/discard")
        assert response.status_code == 302
        assert "/history" in response.headers["Location"]

    def test_draft_discard_other_users_draft_untouched(self, logged_in_client, app):
        app.receipt_service.llm_service = MagicMock()
        app.receipt_service.llm_service.extract_receipt_data.return_value = ({
            "store_name": "Other User Store",
            "purchase_date": "2026-06-16",
            "items": [{"name": "Gum", "price": 1.00, "quantity": 1, "category": "Food & Groceries"}],
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 1.00,
            "currency": "USD",
        }, True)
        _, draft_id, _ = app.receipt_service.process_receipt(
            _make_upload_file(), "other@example.com", edit_before_save=True
        )

        logged_in_client.post(f"/receipt/draft/{draft_id}/discard")

        assert app.receipt_service.get_draft(draft_id, "other@example.com") is not None


class TestForceEditOnBadExtraction:
    """SP-024: invalid or unreconciled extraction forces the draft-review flow."""

    def test_invalid_extraction_redirects_to_draft_with_error_flash(self, logged_in_client, app):
        _stub_llm_extraction(app, total_amount=-1.00)
        response = logged_in_client.post(
            "/upload", data=_upload_data(edit_before_save=False), content_type="multipart/form-data"
        )
        assert response.status_code == 302
        assert "/receipt/draft/" in response.headers["Location"]
        assert app.database.get_all_receipts("test@example.com") == []

        follow = logged_in_client.get("/history")
        assert b"This receipt has a problem" in follow.data
        assert b"alert-error" in follow.data

    def test_unreconciled_extraction_redirects_to_draft_with_error_flash(self, logged_in_client, app):
        _stub_llm_extraction(app, reconciled=False)
        response = logged_in_client.post(
            "/upload", data=_upload_data(edit_before_save=False), content_type="multipart/form-data"
        )
        assert response.status_code == 302
        assert "/receipt/draft/" in response.headers["Location"]
        assert app.database.get_all_receipts("test@example.com") == []

        follow = logged_in_client.get("/history")
        assert b"couldn&#39;t fully verify this receipt&#39;s totals" in follow.data or \
            b"couldn't fully verify this receipt's totals" in follow.data

    def test_invalid_extraction_with_checkbox_checked_still_shows_invalid_reason(self, logged_in_client, app):
        _stub_llm_extraction(app, total_amount=-1.00)
        response = logged_in_client.post(
            "/upload", data=_upload_data(edit_before_save=True), content_type="multipart/form-data",
            follow_redirects=True
        )
        assert b"This receipt has a problem" in response.data
        assert b"Review the extracted receipt before saving." not in response.data

    def test_draft_from_invalid_extraction_shows_prefilled_data_on_review_page(self, logged_in_client, app):
        _stub_llm_extraction(app, total_amount=-1.00)
        response = logged_in_client.post(
            "/upload", data=_upload_data(edit_before_save=False), content_type="multipart/form-data"
        )
        draft_id = response.headers["Location"].split("/")[-2]

        review_page = logged_in_client.get(f"/receipt/draft/{draft_id}/edit")

        assert response.status_code == 302
        assert b"Gum" in review_page.data
        assert b'value="-1.0"' in review_page.data

    def test_saving_from_forced_review_draft_creates_receipt_normally(self, logged_in_client, app):
        _stub_llm_extraction(app, total_amount=-1.00)
        response = logged_in_client.post(
            "/upload", data=_upload_data(edit_before_save=False), content_type="multipart/form-data"
        )
        draft_id = response.headers["Location"].split("/")[-2]

        save_response = logged_in_client.post(f"/receipt/draft/{draft_id}/edit", data={
            "currency": "USD",
            "total_amount": "1.00",
            "item_name": ["Gum"],
            "item_category": ["Food & Groceries"],
            "item_price": ["1.00"],
        })

        assert save_response.status_code == 302
        assert "/history" in save_response.headers["Location"]
        assert len(app.database.get_all_receipts("test@example.com")) == 1
        assert app.receipt_service.get_draft(draft_id, "test@example.com") is None


def _stub_statement_extraction(app, transactions=None):
    app.statement_service.llm_service = MagicMock()
    app.statement_service.llm_service.extract_statement_transactions.return_value = transactions or [
        {
            "date": "2026-06-15", "description": "Corner Store", "amount": 12.50, "currency": "USD",
            "direction": "debit", "category": "Food & Groceries",
        },
        {
            "date": "2026-06-16", "description": "Gas Station", "amount": 40.00, "currency": "USD",
            "direction": "debit", "category": "Other",
        },
    ]


def _pdf_upload_data(source="card", include_file=True):
    data = {}
    if include_file:
        data["statement"] = (io.BytesIO(b"%PDF-1.4 fake"), "statement.pdf")
    if source is not None:
        data["source"] = source
    return data


class TestUploadStatementRoute:
    """SP-025: upload a bank/card statement PDF, extract and store transactions."""

    def test_upload_statement_nav_tab_present(self, logged_in_client):
        response = logged_in_client.get("/history")
        assert b"Upload Statement" in response.data

    def test_upload_statement_get_shows_form(self, logged_in_client):
        response = logged_in_client.get("/upload-statement")
        assert response.status_code == 200
        assert b'name="statement"' in response.data
        assert b'value="bank"' in response.data
        assert b'value="card"' in response.data

    def test_upload_statement_post_saves_transactions_and_shows_count(self, logged_in_client, app):
        _stub_statement_extraction(app)
        response = logged_in_client.post(
            "/upload-statement", data=_pdf_upload_data(), content_type="multipart/form-data",
            follow_redirects=True
        )
        assert b"Found 2 transactions." in response.data
        saved = app.transaction_service.get_all_transactions("test@example.com")
        assert len(saved) == 2

    def test_upload_statement_success_redirects_to_history(self, logged_in_client, app):
        _stub_statement_extraction(app)
        response = logged_in_client.post(
            "/upload-statement", data=_pdf_upload_data(), content_type="multipart/form-data"
        )
        assert response.status_code == 302
        assert "/history" in response.headers["Location"]

    def test_upload_statement_post_without_source_shows_error(self, logged_in_client, app):
        _stub_statement_extraction(app)
        response = logged_in_client.post(
            "/upload-statement", data=_pdf_upload_data(source=None), content_type="multipart/form-data",
            follow_redirects=True
        )
        assert b"Please select whether this is a bank or credit card statement" in response.data
        assert app.transaction_service.get_all_transactions("test@example.com") == []

    def test_upload_statement_post_invalid_extension_rejected(self, logged_in_client, app):
        _stub_statement_extraction(app)
        data = {"statement": (io.BytesIO(b"not a pdf"), "statement.txt"), "source": "card"}
        response = logged_in_client.post(
            "/upload-statement", data=data, content_type="multipart/form-data", follow_redirects=True
        )
        assert b"Invalid file type" in response.data
        assert app.transaction_service.get_all_transactions("test@example.com") == []

    def test_upload_statement_post_no_file_selected_shows_error(self, logged_in_client, app):
        _stub_statement_extraction(app)
        response = logged_in_client.post(
            "/upload-statement", data=_pdf_upload_data(include_file=False), content_type="multipart/form-data",
            follow_redirects=True
        )
        assert b"No file selected" in response.data or b"No file uploaded" in response.data

    def test_upload_statement_tags_correct_source(self, logged_in_client, app):
        _stub_statement_extraction(app, transactions=[
            {"date": "2026-06-15", "description": "Corner Store", "amount": 12.50, "currency": "USD"},
        ])
        logged_in_client.post(
            "/upload-statement", data=_pdf_upload_data(source="bank"), content_type="multipart/form-data"
        )
        saved = app.transaction_service.get_all_transactions("test@example.com")
        assert saved[0].source == "bank"

    def test_upload_statement_scoped_to_uploading_user(self, logged_in_client, app):
        _stub_statement_extraction(app, transactions=[
            {"date": "2026-06-15", "description": "Corner Store", "amount": 12.50, "currency": "USD"},
        ])
        logged_in_client.post(
            "/upload-statement", data=_pdf_upload_data(), content_type="multipart/form-data"
        )
        saved = app.transaction_service.get_all_transactions("test@example.com")
        assert saved[0].user_email == "test@example.com"

    def test_upload_statement_direction_and_category_saved(self, logged_in_client, app):
        _stub_statement_extraction(app, transactions=[
            {
                "date": "2026-06-15", "description": "Corner Store", "amount": 12.50, "currency": "USD",
                "direction": "credit", "category": "Food & Groceries",
            },
        ])
        logged_in_client.post(
            "/upload-statement", data=_pdf_upload_data(), content_type="multipart/form-data"
        )
        saved = app.transaction_service.get_all_transactions("test@example.com")
        assert saved[0].direction == "credit"
        assert saved[0].category == "Food & Groceries"


class TestPerUserReceiptScoping:
    """
    SP-005: each logged-in user only sees/manages their own receipts.
    logged_in_client is logged in as "test@example.com" (see tests/conftest.py);
    seed_receipt(app, user_email=...) seeds a second user's data for comparison.
    """

    def test_history_excludes_another_users_receipt(self, logged_in_client, app):
        seed_receipt(app, user_email="other@example.com", store_name="Other User Store")
        response = logged_in_client.get("/history")
        assert b"Other User Store" not in response.data

    def test_history_total_count_only_counts_own_receipts(self, logged_in_client, app):
        seed_receipt(app)
        seed_receipt(app, user_email="other@example.com")
        seed_receipt(app, user_email="other@example.com")
        response = logged_in_client.get("/history")
        assert b"Total receipts: <strong>1</strong>" in response.data

    def test_statistics_excludes_another_users_receipts(self, logged_in_client, app):
        seed_receipt_with_items(
            app,
            items=[("Widget", 10.00, 1, "Electronics & Tech")],
            user_email="other@example.com",
        )
        response = logged_in_client.get("/statistics")
        assert b"No shopping data yet" in response.data
        assert b"Widget" not in response.data

    def test_search_excludes_another_users_items(self, logged_in_client, app):
        seed_receipt_with_items(
            app,
            items=[("Sourdough Bread", 4.50, 1, "Food & Groceries")],
            user_email="other@example.com",
        )
        response = logged_in_client.get("/history?q=sourdough")
        assert b"Sourdough" not in response.data

    def test_cannot_delete_another_users_receipt(self, logged_in_client, app):
        rid = seed_receipt(app, user_email="other@example.com")
        response = logged_in_client.post(f"/delete-receipt/{rid}")
        assert response.status_code == 302
        follow = logged_in_client.get("/history")
        assert b"Receipt not found" in follow.data
        assert app.database.get_receipt_by_id(rid, "other@example.com") is not None

    def test_cannot_view_another_users_receipt_detail(self, logged_in_client, app):
        rid = seed_receipt(app, user_email="other@example.com")
        response = logged_in_client.get(f"/receipt/{rid}")
        assert response.status_code == 302
        assert "/history" in response.headers["Location"]

    def test_session_missing_user_email_redirects_to_login(self, client, app):
        with client.session_transaction() as sess:
            sess['logged_in'] = True
            # user_email deliberately omitted - simulates a stale pre-SP-005 session
        response = client.get("/history")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_stale_session_does_not_redirect_loop_at_login(self, client, app):
        """
        A session with logged_in=True but no user_email (predates SP-005) must
        not bounce forever between / (blocked by the before_request guard) and
        /login (which used to treat logged_in alone as "already signed in").
        """
        with client.session_transaction() as sess:
            sess['logged_in'] = True
        redirect_response = client.get("/", follow_redirects=False)
        assert redirect_response.status_code == 302
        login_response = client.get(redirect_response.headers["Location"], follow_redirects=False)
        assert login_response.status_code == 200

    def test_uploaded_receipt_tagged_with_logged_in_users_email(self, logged_in_client, app):
        # app fixture builds a real LLMService (with __init__ skipped) - swap
        # in a mock so extract_receipt_data can be stubbed for this test.
        app.receipt_service.llm_service = MagicMock()
        app.receipt_service.llm_service.extract_receipt_data.return_value = ({
            "store_name": "Corner Store",
            "purchase_date": "2026-06-16",
            "items": [{"name": "Gum", "price": 1.00, "quantity": 1, "category": "Food & Groceries"}],
            "tax_amount": 0.0,
            "discount_amount": 0.0,
            "total_amount": 1.00,
            "currency": "USD",
        }, True)
        data = {"receipt": (io.BytesIO(b"fake-image-bytes"), "receipt.jpg")}
        logged_in_client.post("/upload", data=data, content_type="multipart/form-data")

        receipts = app.database.get_all_receipts("test@example.com")
        assert any(r["store_name"] == "Corner Store" for r in receipts)


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

        # Should group by saved_at month (the current month, since
        # purchase_date is missing)
        current_month = datetime.now().strftime("%Y-%m")
        assert current_month.encode() in response.data


class TestHistoryTransactions:
    """
    Tests for SP-029: Display Statement Transactions in History

    Covers transactions rendering as their own entries on History,
    interleaved with receipts by date, with direction/category/icon-by-source
    and a linked marker that never hides or deduplicates the entry.
    """

    def test_history_shows_transaction_entry(self, logged_in_client, app):
        seed_transaction(app, description="Corner Store", amount=12.50, currency="USD")

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        assert "Corner Store" in html
        assert "12.50" in html
        assert "USD" in html

    def test_history_shows_direction(self, logged_in_client, app):
        seed_transaction(app, description="Debit One", direction="debit")
        seed_transaction(app, description="Credit One", direction="credit")

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        assert "Debit" in html
        assert "Credit" in html

    def test_history_shows_category_for_transaction(self, logged_in_client, app):
        seed_transaction(app, category="Entertainment")

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        assert "Entertainment" in html

    def test_history_icon_differs_by_source(self, logged_in_client, app):
        seed_transaction(app, description="Bank Line", source="bank")
        seed_transaction(app, description="Card Line", source="card")

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        assert "🏦" in html
        assert "💳" in html

    def test_history_linked_transaction_shows_badge(self, logged_in_client, app):
        seed_transaction(app, description="Linked Txn", linked_receipt_id="some-receipt-id")
        seed_transaction(app, description="Unlinked Txn", linked_receipt_id=None)

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        # Exactly one badge - proves it renders for the linked transaction
        # and not for the unlinked one, regardless of their relative order
        assert html.count("🔗") == 1

    def test_history_linked_transaction_still_shown_as_own_entry(self, logged_in_client, app):
        seed_receipt(app, store_name="Original Store")
        seed_transaction(app, description="Its Statement Line", linked_receipt_id="whatever-id")

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        assert "Original Store" in html
        assert "Its Statement Line" in html

    def test_history_transactions_interleaved_with_receipts_by_date(self, logged_in_client, app):
        seed_receipt(app, store_name="Earlier Receipt", purchase_date="2026-06-10")
        seed_transaction(app, description="Later Transaction", date="2026-06-20")

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        assert html.find("Later Transaction") < html.find("Earlier Receipt")

    def test_history_month_with_only_transactions_gets_own_group(self, logged_in_client, app):
        seed_receipt(app, purchase_date="2026-06-10")
        seed_transaction(app, date="2026-07-05")

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        assert "2026-07" in html

    def test_history_no_empty_state_when_only_transactions_exist(self, logged_in_client, app):
        seed_transaction(app)

        response = logged_in_client.get("/history")

        assert b"No receipts yet" not in response.data

    def test_history_excludes_another_users_transaction(self, logged_in_client, app):
        seed_transaction(app, description="Someone Elses Txn", user_email="other@example.com")

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        assert "Someone Elses Txn" not in html

    def test_history_search_mode_unaffected_by_transactions(self, logged_in_client, app):
        seed_receipt_with_items(app, items=[("Milk", 2.99, 1, "Food & Groceries")])
        seed_transaction(app, description="Milk Delivery Service")

        response = logged_in_client.get("/history?q=Milk")
        html = response.data.decode('utf-8')

        assert "search-result-row" in html
        assert "Milk Delivery Service" not in html

    def test_history_statement_groups_multiple_transactions_under_one_card(self, logged_in_client, app):
        seed_transaction(app, description="Line One", statement_id="stmt-a")
        seed_transaction(app, description="Line Two", statement_id="stmt-a")
        seed_transaction(app, description="Line Three", statement_id="stmt-a")

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        assert "3 transactions" in html
        assert "Line One" in html
        assert "Line Two" in html
        assert "Line Three" in html

    def test_history_two_statements_render_as_separate_cards(self, logged_in_client, app):
        seed_transaction(app, description="A1", statement_id="stmt-a")
        seed_transaction(app, description="A2", statement_id="stmt-a")
        seed_transaction(app, description="B1", statement_id="stmt-b")

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        assert "2 transactions" in html
        assert "1 transaction" in html

    def test_history_statement_date_range_shown_when_dates_differ(self, logged_in_client, app):
        seed_transaction(app, date="2026-06-05", statement_id="stmt-a")
        seed_transaction(app, date="2026-06-25", statement_id="stmt-a")

        response = logged_in_client.get("/history")
        html = response.data.decode('utf-8')

        assert "2026-06-05" in html
        assert "2026-06-25" in html

    def test_history_legacy_transaction_without_statement_id_renders_as_own_card(self, logged_in_client, app):
        """A Transaction saved before SP-029 (no statement_id key at all) still renders."""
        app.transaction_service.database.save_transaction({
            "date": "2026-06-16",
            "description": "Legacy Txn",
            "amount": 5.00,
            "currency": "USD",
            "direction": "debit",
            "category": "Other",
            "source": "card",
            "user_email": "test@example.com"
        })

        response = logged_in_client.get("/history")
        assert response.status_code == 200
        html = response.data.decode('utf-8')

        assert "Legacy Txn" in html
        assert "1 transaction" in html


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


class TestLLMUsagePage:
    """SP-020: admin-only LLM usage/cost tracking page."""

    def test_non_admin_redirected_from_llm_usage(self, logged_in_client):
        response = logged_in_client.get("/llm-usage")
        assert response.status_code == 302
        follow = logged_in_client.get(response.headers["Location"])
        assert b"do not have access" in follow.data

    def test_admin_can_access_llm_usage(self, admin_client):
        response = admin_client.get("/llm-usage")
        assert response.status_code == 200

    def test_nav_link_hidden_for_non_admin(self, logged_in_client):
        response = logged_in_client.get("/history")
        assert b"LLM Usage" not in response.data

    def test_nav_link_shown_for_admin(self, admin_client):
        response = admin_client.get("/history")
        assert b"LLM Usage" in response.data

    def test_llm_usage_shows_empty_state_with_no_records(self, admin_client):
        response = admin_client.get("/llm-usage")
        assert b"No LLM usage recorded yet" in response.data

    def test_llm_usage_shows_totals_after_logging_calls(self, admin_client, app):
        app.usage_log_db.log_call("test@example.com", "claude-sonnet-4-6", 1_000_000, 1_000_000, True, False)

        response = admin_client.get("/llm-usage")

        assert b"<span>1</span>" in response.data
        assert b"$18.0000" in response.data
        assert b"100.0%" in response.data  # success rate

    def test_llm_usage_user_filter(self, admin_client, app):
        app.usage_log_db.log_call("userA@example.com", "claude-sonnet-4-6", 100, 100, True, False)
        app.usage_log_db.log_call("userB@example.com", "claude-sonnet-4-6", 100, 100, True, False)
        app.usage_log_db.log_call("userB@example.com", "claude-sonnet-4-6", 100, 100, True, False)

        response = admin_client.get("/llm-usage?user=userB@example.com")

        assert b"<span>2</span>" in response.data

    def test_llm_usage_month_filter(self, admin_client, app):
        records = [
            {"timestamp": "2026-06-15T10:00:00", "user_email": "test@example.com", "model": "claude-sonnet-4-6",
             "input_tokens": 100, "output_tokens": 100, "cost_usd": 0.0018, "success": True, "is_retry": False},
            {"timestamp": "2026-07-15T10:00:00", "user_email": "test@example.com", "model": "claude-sonnet-4-6",
             "input_tokens": 100, "output_tokens": 100, "cost_usd": 0.0018, "success": True, "is_retry": False},
            {"timestamp": "2026-07-20T10:00:00", "user_email": "test@example.com", "model": "claude-sonnet-4-6",
             "input_tokens": 100, "output_tokens": 100, "cost_usd": 0.0018, "success": True, "is_retry": False},
        ]
        with open(app.usage_log_db.file_path, "w", encoding="utf-8") as f:
            json.dump(records, f)

        response = admin_client.get("/llm-usage?month=2026-07")

        assert b"<span>2</span>" in response.data

    def test_llm_usage_combined_filters(self, admin_client, app):
        records = [
            {"timestamp": "2026-07-15T10:00:00", "user_email": "userA@example.com", "model": "claude-sonnet-4-6",
             "input_tokens": 100, "output_tokens": 100, "cost_usd": 0.0018, "success": True, "is_retry": False},
            {"timestamp": "2026-07-16T10:00:00", "user_email": "userB@example.com", "model": "claude-sonnet-4-6",
             "input_tokens": 100, "output_tokens": 100, "cost_usd": 0.0018, "success": True, "is_retry": False},
            {"timestamp": "2026-06-15T10:00:00", "user_email": "userA@example.com", "model": "claude-sonnet-4-6",
             "input_tokens": 100, "output_tokens": 100, "cost_usd": 0.0018, "success": True, "is_retry": False},
        ]
        with open(app.usage_log_db.file_path, "w", encoding="utf-8") as f:
            json.dump(records, f)

        response = admin_client.get("/llm-usage?user=userA@example.com&month=2026-07")

        assert b"<span>1</span>" in response.data


class TestUserManagementPage:
    """SP-021: admin-only user management (add/toggle-admin/toggle-blocked)."""

    def test_non_admin_redirected_from_users_page(self, logged_in_client):
        response = logged_in_client.get("/users")
        assert response.status_code == 302

    def test_admin_can_access_users_page(self, admin_client):
        response = admin_client.get("/users")
        assert response.status_code == 200

    def test_non_admin_cannot_post_add_user(self, logged_in_client, app):
        response = logged_in_client.post("/users/add", data={"email": "new@example.com"})
        assert response.status_code == 302
        assert not any(u["email"] == "new@example.com" for u in app.auth_service.get_all_users())

    def test_non_admin_cannot_toggle_admin(self, logged_in_client, app):
        app.auth_service.add_user("target@example.com")
        response = logged_in_client.post("/users/target@example.com/toggle-admin")
        assert response.status_code == 302
        assert app.auth_service.is_admin("target@example.com") is False

    def test_non_admin_cannot_toggle_blocked(self, logged_in_client, app):
        app.auth_service.add_user("target@example.com")
        response = logged_in_client.post("/users/target@example.com/toggle-blocked")
        assert response.status_code == 302
        assert app.auth_service.is_email_allowed("target@example.com") is True

    def test_nav_link_hidden_for_non_admin(self, logged_in_client):
        response = logged_in_client.get("/history")
        assert b'href="/users"' not in response.data

    def test_nav_link_shown_for_admin(self, admin_client):
        response = admin_client.get("/history")
        assert b'href="/users"' in response.data

    def test_add_user_creates_new_user(self, admin_client):
        admin_client.post("/users/add", data={"email": "new@example.com"})
        response = admin_client.get("/users")
        assert b"new@example.com" in response.data

    def test_add_user_duplicate_shows_error_flash(self, admin_client):
        admin_client.post("/users/add", data={"email": "dup@example.com"})
        response = admin_client.post("/users/add", data={"email": "dup@example.com"}, follow_redirects=True)
        assert b"already in the list" in response.data

    def test_toggle_admin_route_flips_flag(self, admin_client, app):
        app.auth_service.add_user("target@example.com")
        admin_client.post("/users/target@example.com/toggle-admin")
        response = admin_client.get("/users")
        assert b"target@example.com" in response.data
        assert app.auth_service.is_admin("target@example.com") is True

    def test_toggle_blocked_route_flips_flag(self, admin_client, app):
        app.auth_service.add_user("target@example.com")
        admin_client.post("/users/target@example.com/toggle-blocked")
        assert app.auth_service.is_email_allowed("target@example.com") is False

    def test_toggle_admin_rejects_last_admin_with_flash(self, admin_client, app):
        response = admin_client.post("/users/admin@example.com/toggle-admin", follow_redirects=True)
        assert b"no active admins" in response.data
        assert app.auth_service.is_admin("admin@example.com") is True

    def test_toggle_admin_unknown_email_shows_error(self, admin_client):
        response = admin_client.post("/users/nobody@example.com/toggle-admin", follow_redirects=True)
        assert b"User not found." in response.data

    def test_blocked_user_cannot_login(self, client, app):
        app.auth_service.add_user("blockme@example.com")
        app.auth_service.toggle_blocked("blockme@example.com")
        response = client.post("/login", data={"email": "blockme@example.com"}, follow_redirects=True)
        assert b"Email address not authorised" in response.data
