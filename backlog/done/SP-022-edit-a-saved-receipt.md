# SP-022: Edit a Saved Receipt

**Priority**: High
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-034
**Deployed**: 6f2a14b (2026-08-22)

## Description
Add an "Edit" button next to the existing "×" delete button on each receipt card in History. Editing opens a form where the user can change, per item, the name/category/price, and receipt-wide the currency/total price, plus remove individual items entirely. This is the foundation both SP-023 ("edit before saving") and SP-024 (force-edit on bad extraction) reuse.

## Acceptance Criteria
- [x] Each receipt card in `/history` shows an "Edit" button next to its existing delete ("×") button.
- [x] Editing opens a form pre-filled with the receipt's current data: for each item, its name, category (from the same category list used elsewhere), and price; and for the receipt, its currency and total price.
- [x] Saving changes updates the existing receipt in place (same `receipt_id`) — it does not create a new receipt or duplicate it.
- [x] Each item row has a way to mark it for removal; on save, marked items are dropped from the receipt. Removing every item is rejected (same "must have at least one item" rule `Receipt.validate()` already enforces) — the form re-renders with an error instead of silently failing.
- [x] Price (per item) and total price must be non-negative; a negative value is rejected with a clear error and the form re-renders with the user's other inputs preserved, rather than losing their edits.
- [x] Editing is restricted to the receipt's owner, enforced server-side (same ownership pattern as `/receipt/<id>` and `/delete-receipt/<id>` from SP-005) — not just a hidden button.

## Notes / Context

### Scope of editable fields
Matches exactly what was asked, not more: per item — **name, category, price**. `price` is what this app's own LLM extraction prompt already calls "price per unit" (`app/services/llm_service.py`'s `_create_extraction_prompt()`) — this is *not* the same thing as `ReceiptItem.price_per_unit`, a separate computed property (`(price * quantity) / amount`, added in SP-013 for weight-based price comparison on the History page). Editing is on the stored `price` field; quantity/amount/unit are left untouched. Receipt-wide — **currency, total_amount** ("total price"). `tax_amount`/`discount_amount` are not part of this SP.

### Data layer — new `update_receipt` method
No update path exists today — `Database`/`JSONDatabase` only have `save_receipt` (always creates a new record with a fresh UUID), `get_receipt_by_id`, `soft_delete_receipt`, `delete_receipt`. Add:
- `Database.update_receipt(receipt_id, user_email, receipt_data) -> bool` (new abstract method, `app/database/base.py`)
- `JSONDatabase.update_receipt(...)` (`app/database/json_db.py`) — find the record matching `id` and `user_email` (same ownership-matching pattern already used by `soft_delete_receipt`), overwrite its editable fields in place (keep `id`, `saved_at`, `is_deleted`, `user_email` untouched), write back. Returns `False` if not found/not owned — same "don't leak existence" behavior as delete.
- `ReceiptService.update_receipt(receipt_id, user_email, receipt) -> bool` (`app/services/receipt_service.py`) — thin passthrough, mirroring `soft_delete_receipt`'s shape.

### Route
New `GET/POST /receipt/<receipt_id>/edit` in `app/routes.py`, following the existing `receipt_detail`/`delete_receipt` ownership pattern:
- **GET**: fetch via `receipt_service.get_receipt_by_id(receipt_id, session['user_email'])`; "Receipt not found" + redirect to history if missing/not owned (same as `receipt_detail`); otherwise render the edit form.
- **POST**: read the submitted fields, rebuild the items list (dropping any row marked for removal), rebuild the receipt's `currency`/`total_amount`, run `Receipt.validate()` (already checks non-negative price/total and "at least one item" — no new validation logic needed, just reusing it), and:
  - Invalid → re-render the edit form with the error flashed and the user's submitted values preserved (not their original saved values) so a mistake doesn't erase their other edits.
  - Valid → `update_receipt(...)`, flash success, redirect to `/history`.

### Form design (no JavaScript)
This project's frontend is explicitly JS-free (`CLAUDE.md`: "no JavaScript required") except one existing `onsubmit="return confirm(...)"` on the delete button. Keep the edit form JS-free too:
- Use repeated same-named inputs per item row (e.g. `name="item_name"`, `name="item_category"`, `name="item_price"`, `name="item_remove"` as a checkbox) and read them server-side with `request.form.getlist(...)`, which returns parallel lists in row order — no per-row indexed field names needed.
- Item removal is a **checkbox per row, applied only when the whole form is submitted** — not a separate instant-delete button/action. An instant per-row delete would require its own POST+redirect, which (without JS) would discard any *other* in-progress edits on the page since the browser reloads a fresh form. A checkbox avoids that entirely: one submit applies every change (edits + removals) atomically.
- New template `templates/edit_receipt.html`, extending `base.html`. Reuse existing form/input classes (`.search-input`-style inputs, `.btn.btn-primary`) rather than inventing new CSS, matching this project's established pattern (see SP-014, SP-020, SP-021).

### Nav/UI placement
`templates/history.html`'s existing delete `<form>` sits inside `.receipt-summary`, right after `.receipt-total`. Add the Edit link/button in the same spot (a plain link to `url_for('receipt_edit', receipt_id=receipt.receipt_id)` styled as a small button is enough — no confirmation dialog needed since editing isn't destructive the way delete is).

## Implementation Notes
_Completed 2026-08-22._

- `app/database/base.py` — new abstract method `Database.update_receipt(receipt_id, user_email, receipt_data) -> bool`.
- `app/database/json_db.py` — `JSONDatabase.update_receipt(...)`: finds the record by `id`+`user_email` (same match loop as `soft_delete_receipt`), applies `receipt_data`, then restores `id`/`saved_at`/`user_email`/`is_deleted` from the original record afterward so those can never be clobbered even if a caller's dict happened to include them. Returns `False` if not found/not owned.
- `app/services/receipt_service.py` — `ReceiptService.update_receipt(receipt_id, user_email, receipt)`: thin passthrough to the database layer, mirroring `soft_delete_receipt`'s shape.
- `app/routes.py` — new `GET/POST /receipt/<receipt_id>/edit`, ownership-checked the same way as `receipt_detail`/`delete_receipt`. POST parses per-row `item_name`/`item_category`/`item_price`/`item_remove` (checkbox-per-row removal, applied only on submit — no JS required for the core form), rebuilds a `Receipt`, and reuses `Receipt.validate()` for the non-negative-price/total and "at least one item" checks. On any error, re-renders with the user's *submitted* values preserved rather than the original saved ones. Also added: a curated ISO 4217 `_CURRENCY_CODES` list for the currency dropdown (always includes the receipt's own current code, so an unusual existing value is never dropped from the option list), and `_rows_subtotal()`, a best-effort per-row price×quantity sum shown as a reference "Items subtotal" next to Total Price.
- `templates/edit_receipt.html` (new) — the edit form, extending `base.html`, reusing existing `.search-input`/`.btn` classes. Includes a Cancel link back to History and a small inline `<script>` that recalculates the "Items subtotal" display live as prices/removals/currency change — added after initial manual testing showed the fully server-only version was awkward to sanity-check numbers against before saving. This is the one deviation from the SP's original "no JavaScript" framing; it's progressive enhancement only (same pattern already used by `upload.html`'s filename display) — the form is fully functional and server-validated without it, and the script never affects what actually gets submitted or saved.
- `templates/history.html` — added an Edit link/button next to the existing delete form in `.receipt-summary`.
- `static/css/style.css` — `.btn-edit` (mirrors `.btn-delete`'s styling, primary-color hover instead of error-color); `.edit-receipt-page`/`.edit-items`/`.edit-item-row`/`.edit-item-field`/`.edit-item-remove`/`.form-actions` for the edit form's layout (a CSS grid per item row instead of reusing `.search-input`'s fixed 200px min-width, which was overflowing its container on receipts with several items — found and fixed during manual testing).
- No data migration needed — `update_receipt` only changes fields already present in the receipt schema.
- Tests: 26 added (`test_database.py`'s `TestJSONDatabaseUpdateReceipt`, `test_receipt_service.py`'s `TestReceiptServiceUpdateReceipt`, `test_routes.py`'s `TestEditReceiptRoute`). 274 passed (full suite).
- Verified manually against the running dev server: edit form layout, Cancel button, currency dropdown, and the live-updating items subtotal all confirmed working after the post-testing UX fixes above.
