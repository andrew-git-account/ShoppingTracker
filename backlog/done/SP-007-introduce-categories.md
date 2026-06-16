# SP-007: Introduce Categories

**Priority**: Medium
**Status**: Done
**Fulfils**: Specification/BehaviorSpec.md#BS-011, #BS-012 | Specification/DataSchema.md (category field, categories.json)

## Description
Allow the system to automatically assign categories to purchase line items (e.g. "Food & Groceries", "Electronics & Tech").
This enables better organization and future filtering/analytics of spending by category.

## Acceptance Criteria
- [x] A predefined list of 7 categories is available: Food & Groceries, Household & Cleaning, Personal Care & Health, Electronics & Tech, Clothing & Apparel, Dining & Takeout, Other
- [x] When a receipt is successfully processed, the LLM assigns a category to each line item from the predefined list
- [x] When the LLM cannot determine a category for a line item, it is assigned "Other"
- [x] History page displays the assigned category for each line item on a receipt
- [x] All previously uploaded line items are assigned "Other" on first run

## Notes / Context
Fixed list of categories (no user-defined categories yet) to keep V1 simple. "Other" is the default/fallback when the LLM cannot determine a category.

Possible changes:
- database - creating a vocabulary table with categories, adding category to purchase line items, migration of existing data (assigning "Other" as default)
- UI - showing category per line item on the history page
- LLM - updating prompt to recognize and return a category from the predefined list

## Implementation Notes
Completed 2026-06-17.

- `app/database/json_db.py`: Added `CategoryDatabase` class with `initialize()` (seeds `data/categories.json` with 7 categories on first run) and `get_all_categories()`.
- `app/main.py`: `create_app()` initialises `CategoryDatabase`, loads category names into `valid_categories`, and injects them into both `LLMService` and `ReceiptService`.
- `app/models.py`: Added `category: str = "Other"` to `ReceiptItem`; updated `to_dict()`, `from_dict()`, and `Receipt.from_llm_response()` (validates against `valid_categories`, falls back to `"Other"`).
- `app/services/llm_service.py`: Accepts `valid_categories` at init; injects the list dynamically into `_create_extraction_prompt()`.
- `app/services/receipt_service.py`: Accepts `valid_categories` at init; passes it to `Receipt.from_llm_response()`.
- `templates/history.html`: Added `<span class="item-category">` badge per line item.
- `static/css/style.css`: Added `.item-category` badge style.
- `migrate_categories.py`: One-time script; assigns `"Other"` to all 78 existing line items in `receipts.json`.
- Tests: 56 pytest tests across `tests/test_models.py`, `tests/test_database.py`, `tests/test_receipt_service.py`, `tests/test_routes.py` — all passing.
