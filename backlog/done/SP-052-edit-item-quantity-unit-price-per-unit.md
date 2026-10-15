# SP-052: Edit Item Amount, Unit and Price per Unit

**Priority**: Medium
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-053
**Deployed**: c13c8f8 (2026-10-15)

## Description
On the receipt edit form (saved receipts and drafts), let the user correct each item's amount, unit type and price per unit, in addition to the name, category and price (the line total) that are already editable. Today amount and unit are copied unchanged from the original item, so an LLM misread (wrong weight, wrong unit) cannot be fixed without deleting and re-entering the receipt. Price per unit and the line total stay in sync automatically. There is no separate quantity field: an item is an amount of a unit (e.g. 2 piece, 0.5 kg) and a total price (see SP-053).

## Acceptance Criteria
- [x] Each item row on the edit form shows, in order: item name, category, amount, unit type, price per unit, total (the item's price), remove checkbox. A header row above the items names the columns (hidden on narrow screens, where fields have tooltips).
- [x] There is no quantity field on the form.
- [x] Amount is a numeric input (greater than 0), pre-filled from the item.
- [x] Unit type is a dropdown with exactly two options, `piece` and `kg`, pre-filled from the item. Any other stored unit is shown as an extra option and round-trips unchanged. (More units would need a separate SP, because `models.py` normalizes every unit to `kg` or `piece`.)
- [x] Price per unit is a numeric input, pre-filled with the item's current price per unit (`total / amount`).
- [x] Editing price per unit or amount updates the total live in the browser (`total = price_per_unit * amount`); editing the total updates price per unit (`price_per_unit = total / amount`). Example: an item of 1.5 kg with total 6.00 shows price per unit 4.00; changing price per unit to 5.00 sets the total to 7.50; changing the total back to 6.00 restores 4.00.
- [x] Displayed values are rounded to 2 decimals. The submitted total is stored exactly as entered, never recomputed from a rounded per-unit value.
- [x] The "Items subtotal" next to Total Price is the sum of the item totals and updates live as totals, amounts, per-unit prices and removals change.
- [x] Submitting the form saves each item's amount, unit and total (the server treats the total as the source of truth and ignores the submitted price per unit); items are saved with quantity 1.
- [x] Invalid input (non-numeric total, amount <= 0 or non-numeric, a unit that is neither `piece`, `kg` nor the item's own stored unit) re-renders the form with an error message and keeps all the user's edits; nothing is saved.
- [x] Removed rows and rows the user did not touch keep working exactly as before.
- [x] Works identically when editing an unsaved draft and an already saved receipt.
- [x] Number fields in item rows have no spinner arrows and are right-aligned.
- [x] Unit tests cover the form parsing (valid edit, invalid amount, invalid unit, unknown stored unit round-trip, per-unit field ignored, removed rows not validated, draft).
- [x] `Specification/BehaviorSpec.md` has a scenario for editing amount/unit/price per unit/total.

## Notes / Context
- Depends on SP-053 (quantity folded into the line total), which makes the total simply `price` and quantity always 1.
- Code touched: `_rows_from_receipt`, `_rows_subtotal`, `_parse_edit_form` in `app/routes.py`; `templates/edit_receipt.html` (which has the JS for the running total); `static/css/style.css`.
- The first version of this SP had an editable Quantity field. It was dropped because Quantity and Amount overlap and confuse users.
- Without JavaScript the form still submits; the server recomputes per-unit from the total, so the page degrades gracefully.

## Implementation Notes
Completed 2026-10-15.

- `app/routes.py`: edit-form helpers reworked for amount/unit/price per unit/total with no quantity: `_price_per_unit_text` (total / amount), `_rows_subtotal` (sum of item totals), `_rows_from_receipt`, and `_parse_edit_form` (validates amount > 0 and unit in piece/kg or the item's own stored unit; saves quantity 1; ignores the submitted price per unit). `_EDIT_UNITS` passed to the template.
- `templates/edit_receipt.html`: column header row; item rows Amount, Unit, Price per unit, Total, and a checkbox-only Remove; inline script keeps total and price per unit in sync (exact unrounded per-unit value kept in memory) and the items subtotal live.
- `static/css/style.css`: 7-column grid, narrow-screen wrap (header hidden below 900px), no spinner arrows, right-aligned numbers, centered remove checkbox.
- `Specification/BehaviorSpec.md`: BS-053.
- Design change during the work: the first version had an editable Quantity; it was dropped in favour of folding quantity into the total (SP-053).
- Tests: 21 added/rewritten (`TestEditItemAmountUnitPrice`, `TestEditFormHelpers` in tests/test_routes.py). Full suite: 713 passed. The browser-side sync script has no automated test.
