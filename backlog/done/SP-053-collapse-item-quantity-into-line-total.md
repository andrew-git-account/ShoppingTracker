# SP-053: Collapse Item Quantity into the Line Total

**Priority**: Medium
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-054, DataSchema.md (items[].price / items[].quantity)

## Description
Today an item has both a `quantity` (how many) and an `amount` (how much in kg or pieces), which describe the same thing from two angles and confuse users. Simplify the item model: an item is an `amount` of a `unit` with a `price` that is the whole line total (what the receipt prints). Existing quantity values are folded into price and amount so nothing is lost, and new receipts coming from the LLM are stored the same way.

## Acceptance Criteria
- [x] A new function in `app/models.py` folds a legacy (price, quantity, amount, unit) into (line total, amount): total = `price * quantity`; if the unit is `piece` and amount is exactly 1.0 and quantity > 1, amount becomes the quantity; otherwise amount is unchanged. With quantity 1 (or less) nothing changes.
- [x] `ReceiptItem.from_llm_response` path (`Receipt.from_llm_response`) applies it, so every item from a new extraction has quantity 1, price = line total.
- [x] `ReceiptItem.from_dict` applies it, so receipts already saved with quantity > 1 load as quantity 1 with the folded price/amount, with no migration needed for the app to behave correctly.
- [x] `ReceiptItem.price_per_unit` gives the same value for a folded item as the old `price * quantity / amount` did for the unfolded one (0.0 if amount <= 0).
- [x] The reconciliation check against the receipt's own total in `llm_service.py` still passes for extractions it passed before (it runs on the raw LLM data, before folding).
- [x] A one-time script `migrate_collapse_item_quantity.py` rewrites every `receipt_items` row with quantity > 1 in `data/shopping_tracker.db` using the same fold rule and sets quantity to 1. It makes a backup copy of the database file first, prints how many rows it changed, is a dry run (changes nothing, prints what it would do) unless run with `--apply`, and running it twice changes nothing the second time.
- [x] After the script runs, every receipt's sum of item prices is unchanged compared with the sum of `price * quantity` before (verified by the script's own before/after check and printed).
- [x] Unit tests cover the fold rule (quantity 1, piece with amount 1, piece with amount not 1, kg), `from_dict`, the LLM path, `price_per_unit`, and the migration script on a temporary database (including the dry run and a second run).
- [x] `Specification/DataSchema.md` documents that `quantity` is always 1 and `price` is the line total.

## Notes / Context
- Decision from the SP-052 discussion: having both Quantity and Amount does not make sense to users. The `quantity` column stays in the table (always 1) to avoid a schema change; code that multiplies by it keeps working.
- Real data today (210 items): 25 have quantity > 1, of which 13 are `piece` with amount 1.0 (amount becomes the quantity) and 2 are `kg` (amount unchanged).
- The History page still has `(xN)` display code; it never triggers once quantity is always 1. Removing it is optional cleanup.
- The LLM prompt is unchanged: the model still reports quantity and price per item, and the fold happens when the response is turned into a Receipt.
- Prerequisite for SP-052.

## Implementation Notes
Completed 2026-10-15.

- `app/models.py`: new `fold_quantity_into_total()` (line total = price x quantity; a `piece` item with the default amount 1.0 takes the quantity as its amount). Applied in `ReceiptItem.from_dict` (so old saved receipts load folded) and in `Receipt.from_llm_response` (new extractions are stored with quantity 1 and price = line total). `price_per_unit` is unchanged and gives the same values.
- `migrate_collapse_item_quantity.py` (new): one-time script, dry run by default, `--apply` backs up the DB, updates rows in one transaction and verifies each receipt's item total is unchanged. Run with `--apply` on 2026-10-15: 23 items updated (a dry run just before had listed 25; two were evidently fixed by hand through the new edit form), totals unchanged, backup at `data/shopping_tracker.db.bak-sp053`; a second run changes nothing.
- `Specification/DataSchema.md`: `items[].price` is the line total, `items[].quantity` is always 1, LLM quantity rule updated.
- `Specification/BehaviorSpec.md`: added BS-054.
- `quantity` column and the History `(xN)` display code are intentionally left in place (never triggers now).
- Tests: 14 added (`TestFoldQuantityIntoTotal` in tests/test_models.py, `tests/test_migrate_collapse_item_quantity.py`). Full suite: 713 passed.
