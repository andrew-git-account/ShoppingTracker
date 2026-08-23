# SP-027: Manually Link or Unlink a Transaction

**Priority**: High
**Status**: Ready

## Description
Add a page listing the user's transactions, where they can manually link an unlinked transaction to a receipt, or unlink one that was linked — whether that link was made automatically by SP-026 or by hand here. This is what makes SP-026's silent auto-matching safe: any wrong or missed match is one click away from being corrected.

## Acceptance Criteria
- [ ] A new page (e.g. `/transactions`) lists the logged-in user's transactions — date, description, amount, source (bank/card), and linked status (and which receipt, if linked).
- [ ] An unlinked transaction has a "Link to receipt" action that opens a filter form (name, date from/to, amount from/to) pre-filled with sensible defaults, listing the user's unlinked receipts matching the filter; picking one sets `linked_receipt_id`.
- [ ] The filter defaults to the narrowest useful search for that transaction: name empty (no filter), date-from and date-to both set to the transaction's own date, amount-from and amount-to both set to the transaction's own amount — so the default view is "receipts matching this transaction exactly," widened only if the user changes the fields.
- [ ] A linked transaction has an "Unlink" action that clears `linked_receipt_id`, regardless of whether the link was automatic (SP-026) or manual.
- [ ] All actions are restricted server-side to the transaction's owner, same ownership pattern used everywhere else in the app (SP-005) — not found and not-owned look identical.
- [ ] Manually linking enforces the same one-to-one rule as automatic matching — a receipt already linked to a different transaction isn't offered as a choice (or is rejected server-side with a clear error if picked anyway).

## Notes / Context

### Routes (`app/routes.py`)
- `GET /transactions` — lists the user's transactions via `app.transaction_service.get_all_transactions(user_email)` (SP-025).
- `GET /transactions/<transaction_id>/link` — the filter-and-pick page (no JS, mirroring History's `GET /history?q=...` search pattern from SP-004). Reads `name`/`date_from`/`date_to`/`amount_from`/`amount_to` from the query string; when any are absent (first visit from the transactions list, no query string at all), fills in the defaults from the acceptance criteria (empty name, both dates = the transaction's date, both amounts = the transaction's amount) and renders with those instead of erroring. Filters `receipt_service.get_all_receipts(user_email)` down to receipts that are (a) not already linked to a different transaction and (b) within the name/date/amount filter, and lists them each with a small per-row "Select" form.
- `POST /transactions/<transaction_id>/link` — submitted by a result row's "Select" form (hidden `receipt_id` field); validates ownership of both the transaction and the receipt, and that the receipt isn't already linked elsewhere, before setting `linked_receipt_id` via `app.transaction_service.update_transaction(...)`.
- `POST /transactions/<transaction_id>/unlink` — clears `linked_receipt_id` via the same service, ownership-checked the same way.

### Template
New `templates/transactions.html` (the list) and `templates/transaction_link.html` (the filter-and-pick page). The list reuses existing list/table markup conventions (`.stats-panel`/`.summary-row`, as used by `templates/users.html` in SP-021) rather than inventing new CSS; the filter form follows `history.html`'s `.search-form`/`.search-input` pattern (SP-004), extended with the extra date/amount fields, and each result row's "Select" form mirrors `history.html`'s per-row delete form.

### Nav
New "Transactions" link in `templates/base.html`, alongside History/Statistics.

### Out of scope (this SP)
- Transactions appearing in Statistics (SP-028).
- Bulk actions (link/unlink multiple at once).

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
