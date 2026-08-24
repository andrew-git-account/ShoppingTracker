# SP-030: Edit a Saved Transaction

**Priority**: High
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-040

## Description
Add an "Edit" action to each statement card in History (SP-029), mirroring SP-022's receipt-editing pattern exactly: one edit icon on the card itself (not per transaction), opening one page that lists every transaction in that statement as an editable row — description (name), date, category, direction (debit/credit), currency, and amount per row, saved together. Saving updates each existing transaction in place via `TransactionService.update_transaction` (already exists from SP-025) — it does not create new transactions.

## Acceptance Criteria
- [x] Each statement card in History (SP-029) shows **one** edit icon on the card itself, same style/placement convention as the receipt card's existing edit icon (`.btn-edit`, pencil glyph, same slot relative to the card's summary) — not one icon per transaction.
- [x] Editing opens a form listing every transaction belonging to that statement, each pre-filled with its current values: description, date, category (from the same category list receipt items use), direction, currency, and amount.
- [x] Direction and category are constrained to the actual valid choices, not free text — direction via a compact debit/credit slider (a checkbox, not a 2-option select), category via a select from the app's category list — so an invalid value can't be submitted in the first place.
- [x] Currency uses the same curated ISO 4217 dropdown already built for receipt editing (`_CURRENCY_CODES` in `app/routes.py`), always including every row's current currency even if unusual.
- [x] Amount must be non-negative; a negative value on *any* row rejects the *entire* submission with a clear error naming the row, and the form re-renders with every row's submitted values preserved (not the original saved ones) — atomic, all-or-nothing save, matching receipt item editing's behavior for a bad price.
- [x] Saving changes updates each edited transaction in place (same `transaction_id` per row) and preserves fields the form doesn't expose — `statement_id`, `source`, `saved_at`, `is_deleted`, `linked_receipt_id`.
- [x] After a successful edit, each changed transaction is re-run through SP-026's matcher the same way an edited receipt already is — so, for example, correcting a transaction's amount to match an existing unlinked receipt can create a new link. This does **not** retroactively break or re-validate an existing link if the edit makes it stale — same deferred gap SP-026 already documented for receipt edits.
- [x] Editing is restricted to the statement's owner, enforced server-side (same ownership pattern as receipt editing, SP-005) — a row's hidden `transaction_id` is checked against the caller's own already-fetched transactions, not looked up fresh, so it can't be used to reach another user's record.

## Notes / Context

### Corrected 2026-08-25 — statement-level, not per-transaction
First pass put the edit icon and edit page on each individual transaction row. Feedback: that's not the right analogy to SP-022. A statement card is the aggregate equivalent of a receipt card, and its transactions are the equivalent of a receipt's items — so there should be **one** edit icon on the statement card, opening **one** page listing every transaction in it as an editable row, saved atomically, exactly like receipt item editing. The one structural difference from receipt items: a transaction is its own top-level record (its own `transaction_id`, its own row in `transactions.json`), not a sub-list rebuilt wholesale as part of one parent record, so each row carries a hidden `transaction_id` and is saved individually (`update_transaction` called once per row), and ownership is re-checked per row against the statement's own already-fetched transactions rather than trusted from the hidden field.

### Scope of editable fields
Every field on `Transaction` except identity/lifecycle ones: **description, date, category, direction, currency, amount**. Left untouched: `transaction_id`, `statement_id`, `source` (bank/card — set at upload time, not something a user corrects here), `saved_at`, `user_email`, `linked_receipt_id`, `is_deleted`.

### Data layer — no new method needed
Unlike SP-022 (which had to add `update_receipt` from scratch), `TransactionService.update_transaction(transaction_id, user_email, transaction) -> bool` and the underlying `JSONTransactionDatabase.update_transaction(...)` already exist (SP-025) and already do the right thing: find by `id`+`user_email`, merge in the new fields, restore `id`/`saved_at`/`user_email`/`is_deleted` from the original record afterward. This SP is route + template + validation only.

### Validation
`Transaction` has no `validate()` method today (unlike `Receipt`). Added, mirroring `Receipt.validate()`'s shape: reject a negative `amount`. Direction and category don't need validation here since the form constrains them to valid values via `<select>` — but if a route ever receives something else (e.g. a hand-crafted request), fall back the same way `StatementService.process_statement()` already does for extracted values (invalid direction → `debit`, invalid category → `Other`) rather than raising, for consistency with the rest of the codebase's handling of these two fields.

### Route (`app/routes.py`)
`GET/POST /statement/<statement_id>/edit`, following `receipt_edit`'s ownership pattern but scoped to a group of records instead of one:
- Both methods first fetch `[t for t in transaction_service.get_all_transactions(user_email) if t.statement_id == statement_id]` — the same grouping `history()` already does. Empty result (wrong owner or nonexistent `statement_id`) → flash "Statement not found." + redirect to `/history`, same not-found/not-owned indistinguishability as `receipt_edit`.
- **GET**: render one row per transaction, pre-filled.
- **POST**: read parallel lists via `request.form.getlist('transaction_id' | 'description' | 'date' | 'category' | 'currency' | 'amount')`, plus `is_credit` (see the direction-toggle note below), same convention `_parse_edit_form` uses for `item_name`/`item_category`/`item_price`. Each row's `transaction_id` is looked up in a dict built from the GET-time ownership-scoped fetch, not a fresh database call — a `transaction_id` not in that dict (tampered or foreign) is an invalid row, not a lookup into another user's data.
- Validation is all-or-nothing: any invalid row (bad amount, unrecognized `transaction_id`) rejects the whole submission, re-rendering every row's submitted values.
- On success: `transaction_service.update_transaction(...)` once per row, then `if app.transaction_matcher: app.transaction_matcher.match_transaction(updated)` once per row (mirrors how `ReceiptService.update_receipt` already re-runs the matcher after a receipt edit — see SP-026), flash success, redirect to `/history`.

### Form design (no JavaScript)
Same conventions as `templates/edit_receipt.html`'s items list (SP-022): `<ul class="edit-items"><li>`, reusing `.edit-items`/`.edit-item-field` CSS, plus a hidden `transaction_id` per row. New template `templates/edit_statement.html`. No receipt-wide-style fields section — a statement has no currency/total of its own (SP-029 deliberately never sums debit/credit together), so the page is just the row list plus Cancel/Save.

**Polished 2026-08-25** — one transaction per line, sized to fit: new `.edit-transaction-row` CSS grid (`app/routes.py`'s row uses this instead of `.edit-item-row`, whose 4-column template was built for receipt items and didn't have room for a statement row's extra fields) with column widths matched to actual content — description gets the flexible column, date/category/currency/amount get fixed widths sized to what they actually hold (a currency code is 3 characters; it doesn't need a full-width `<select>`). Direction became a compact debit/credit slider instead of a 2-option `<select>`, to save the width a select control needs for its own box-plus-label: a checkbox per row (`name="is_credit"`, `value=`row index — the exact same "checkbox per row, value=index" convention `edit_receipt.html`'s `item_remove` checkboxes already use, so `_parse_statement_edit_form` derives `direction` from index membership rather than reading a submitted string), styled as a sliding pill purely in CSS (`:checked + sibling`, no JavaScript) — red/left for a debit, green/right for a credit, reusing the exact colors `.transaction-direction-debit`/`.transaction-direction-credit` already use elsewhere in History. A side effect worth noting: direction can no longer be an out-of-range value at all (a checkbox is binary), so the earlier "invalid direction falls back to debit" fallback path is now unreachable — replaced with two tests confirming the toggle's checked/unchecked mapping directly. A `max-width: 480px` breakpoint stacks the row into two columns instead of shrinking the fixed-width fields further.

### Nav/UI placement
`templates/history.html`'s statement `<summary class="receipt-summary">` gets one edit icon in the same slot the receipt card's occupies (right after `.receipt-total`). The per-transaction `<li class="item-row">` itself has no action — editing happens for the whole statement at once. The history entry dict `history()` builds per statement group gained a `statement_id` key so the template can link to it.

### Out of scope (this SP)
- Link/Unlink actions on transaction rows — SP-027.
- Removing a transaction (soft-delete) — not asked for; no existing route or UI for it today either.
- Retroactively breaking or re-validating an existing `linked_receipt_id` when an edit makes it stale — deferred, same as SP-026's own documented gap.
- Reordering rows or moving a transaction to a different statement.

## Implementation Notes
Completed 2026-08-25.

- `app/models.py` — new `Transaction.validate()`, mirroring `Receipt.validate()`'s shape: rejects a negative `amount`.
- `app/routes.py` — new `GET/POST /statement/<statement_id>/edit` route plus `_parse_statement_edit_form`/`_render_statement_edit_form` helpers; `history()`'s per-statement entry dict gained a `statement_id` key. Direction is read from an `is_credit` checkbox-per-row (value=row index), not a submitted string, so there's no invalid-direction case to fall back from.
- `app/main.py` — `app.transaction_matcher = matcher`, exposed alongside the other `app.*_service` attributes so the new route can re-run SP-026's matcher after saving.
- `templates/edit_statement.html` (new) — one row per transaction, each with a hidden `transaction_id`, description/date/category/currency/amount fields, and a compact debit/credit slider (pure-CSS toggle, no JavaScript).
- `templates/history.html` — one edit icon added to each statement card's summary (same slot the receipt card's edit icon sits in).
- `static/css/style.css` — new `.edit-transaction-row` grid (column widths sized to actual content instead of reusing the 4-column receipt-item grid) and `.direction-toggle`/`.direction-toggle-slider` (pure-CSS sliding toggle, `:checked + sibling`), plus a mobile breakpoint that stacks the row into two columns.
- `CLAUDE.md` — SP counter corrected 028 → 030 (SP-029 had been created out-of-band without bumping it).
- Went through one design correction mid-implementation: the first pass put an edit icon/page on each individual transaction row; corrected to one icon per statement card opening one page listing every transaction in it, mirroring receipt item editing's aggregate-level pattern exactly (see the "Corrected 2026-08-25" note above). A follow-up design pass then replaced the direction `<select>` with the compact slider and resized every column to fit one transaction per line (see the "Polished 2026-08-25" note above).
- No migration or data changes — every field this SP touches already existed on `Transaction`.
- Tests: `tests/test_routes.py`'s `TestEditStatementRoute` (19 tests) — icon placement (exactly one per statement, not per row), form pre-fill across multiple rows, ownership (GET and POST, including a tampered hidden `transaction_id` that doesn't belong to the caller's own statement), all-or-nothing validation (negative/invalid amount rejects every row, not just the bad one), category fallback, the direction toggle's checked/unchecked mapping, preserved untouched fields, no duplication, redirect on success, the SP-026 matcher re-trigger (both creating a new match and correctly *not* clearing an existing one when an edit makes it stale), and a single-transaction statement (the common legacy case). Full suite: 392 passed (373 existing + 19 new).
- Verified manually: a scripted Flask-test-client run confirmed the end-to-end flow (icon → multi-row form → atomic save) before the automated tests were written, and the actual rendered page was checked in a real browser (via a local static-file server serving a saved render of the route, since login needs an email OTP that isn't reachable here) at both desktop (confirmed one line per transaction, correct toggle color/position via computed styles) and mobile widths (confirmed the two-column stack).
