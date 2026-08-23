# SP-027: Manually Link or Unlink a Transaction

**Priority**: High
**Status**: Open

## Description
Let a user manually link an unlinked transaction to a receipt, or unlink one that was linked — whether that link was made automatically by SP-026 or by hand here. The actions are surfaced on the transaction entries [[SP-029]] renders in History: an unlinked transaction gets a "Link to receipt" action, a linked one gets "Unlink". This is what makes SP-026's silent auto-matching safe — any wrong or missed match is one click away from being corrected. Depends on [[SP-029]] for the History surface these actions attach to.

## Acceptance Criteria
- [ ] An unlinked transaction's entry in History (SP-029) has a "Link to receipt" action that opens a filter form (name, date from/to, amount from/to) pre-filled with sensible defaults, listing the user's unlinked receipts matching the filter; picking one sets `linked_receipt_id`.
- [ ] The filter defaults to the narrowest useful search for that transaction: name empty (no filter), date-from and date-to both set to the transaction's own date, amount-from and amount-to both set to the transaction's own amount — so the default view is "receipts matching this transaction exactly," widened only if the user changes the fields.
- [ ] A linked transaction's entry has an "Unlink" action that clears `linked_receipt_id`, regardless of whether the link was automatic (SP-026) or manual.
- [ ] All actions are restricted server-side to the transaction's owner, same ownership pattern used everywhere else in the app (SP-005) — not found and not-owned look identical.
- [ ] Manually linking enforces the same one-to-one rule as automatic matching — a receipt already linked to a different transaction isn't offered as a choice (or is rejected server-side with a clear error if picked anyway).
- [ ] Linking or unlinking is reflected immediately in History's linked-marker for that transaction (SP-029's display).

## Notes / Context

### Reopened — stale after SP-025 (2026-08-23)
Original gap noted when this was reopened: `Transaction.direction`/`Transaction.category` (added during SP-025's testing) weren't accounted for in the original design. Resolved — see "Direction and linking" below. Separately, the display portion of the original design (a standalone `/transactions` list page) was split out into [[SP-029]] on 2026-08-23, since displaying transactions and manually linking/unlinking them turned out to be two separable deliverables — this SP is now the interactive-actions half only.

### Direction and linking
Resolved 2026-08-23: a `credit` transaction is linkable, same as a `debit` one — e.g. reconciling a refund credit against its original receipt is a legitimate use case, not an edge case to guard against. The "Link to receipt" action and filter apply uniformly regardless of `direction`; no restriction needed here, consistent with [[SP-026]]'s matching (also unrestricted by direction, per its own 2026-08-23 resolution).

### Routes (`app/routes.py`)
- `GET /transactions/<transaction_id>/link` — the filter-and-pick page (no JS, mirroring History's `GET /history?q=...` search pattern from SP-004). Reads `name`/`date_from`/`date_to`/`amount_from`/`amount_to` from the query string; when any are absent (first visit, no query string at all), fills in the defaults from the acceptance criteria (empty name, both dates = the transaction's date, both amounts = the transaction's amount) and renders with those instead of erroring. Filters `receipt_service.get_all_receipts(user_email)` down to receipts that are (a) not already linked to a different transaction and (b) within the name/date/amount filter, and lists them each with a small per-row "Select" form.
- `POST /transactions/<transaction_id>/link` — submitted by a result row's "Select" form (hidden `receipt_id` field); validates ownership of both the transaction and the receipt, and that the receipt isn't already linked elsewhere, before setting `linked_receipt_id` via `app.transaction_service.update_transaction(...)`.
- `POST /transactions/<transaction_id>/unlink` — clears `linked_receipt_id` via the same service, ownership-checked the same way.
- The "Link to receipt" / "Unlink" links/forms themselves live on History's transaction entries (SP-029's markup), pointing at the routes above — this SP doesn't own the entry's rendering, just the actions attached to it.

### Template
New `templates/transaction_link.html` (the filter-and-pick page) — follows `history.html`'s `.search-form`/`.search-input` pattern (SP-004), extended with the extra date/amount fields, and each result row's "Select" form mirrors `history.html`'s per-row delete form.

### Out of scope (this SP)
- Rendering transaction entries in History, icons, and the linked/unlinked visual marker — [[SP-029]].
- Transactions appearing in Statistics (SP-028).
- Bulk actions (link/unlink multiple at once).

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
