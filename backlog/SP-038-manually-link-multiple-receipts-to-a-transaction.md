# SP-038: Manually Link Multiple Receipts to a Transaction in One Action

**Priority**: High
**Status**: Open

## Description
Extend SP-027's transaction-link page so a user can select *several* receipts to settle with one transaction (e.g. a running tab paid off in one card charge), not just one. "Select" stages a receipt instead of linking it immediately; a running list of staged receipts (with a live running total) shows above the results; each staged receipt has its own "Remove" action; a new "Add" button (next to "Cancel") commits the whole staged batch at once. Builds on SP-037's data model — this SP is the user-facing feature that actually creates a many-receipts-to-one-transaction link.

## Acceptance Criteria
- [ ] Clicking "Select" on a receipt in the filter results no longer links immediately — it stages the receipt (adds it to a pending selection for this transaction) and re-renders the same filter page.
- [ ] The page shows a "Selected" section above the filter results listing every currently-staged receipt (store name, date, amount) plus a running total of their amounts, in the transaction's own currency.
- [ ] Each staged receipt has its own "Remove" action, removing just that one from the pending selection without discarding the rest.
- [ ] A staged receipt no longer appears in the filter results below (same exclusion principle already used for a receipt already linked elsewhere).
- [ ] Re-filtering (changing the search fields and submitting again) preserves the current staged selection — staging is not tied to one specific filter query.
- [ ] A new "Add" button, next to the existing "Cancel", commits the whole staged batch: sets `linked_transaction_id` (SP-037) on every staged receipt to this transaction, clears the pending selection, flashes a success message naming how many receipts were linked, redirects to History.
- [ ] "Cancel" discards the pending selection entirely (no partial commit) and returns to History, same as it does today.
- [ ] The existing single-receipt case still works end-to-end through the same flow (stage one, click Add) — no separate "quick single-link" path.
- [ ] All actions remain restricted server-side to the transaction's and receipts' owner, same ownership pattern as every other action in the app.
- [ ] "Unlink" on a transaction's row (SP-027) clears `linked_transaction_id` on *every* receipt currently linked to that transaction, not just one — all-or-nothing for now. Unlinking a single receipt out of an already-committed group isn't supported; the user would unlink the whole group and re-stage the ones they want to keep.

## Notes / Context

### Why staging has to be server-side
This app is deliberately JS-free. "Select a receipt, keep browsing, watch it accumulate above the table" can't be held in browser memory across page reloads — every click here is a full page navigation. The pending selection has to persist server-side between requests.

### Staging mechanism — reuse the existing draft pattern
SP-023 already has a precedent for exactly this shape: a small file-backed "not yet committed" record (`ReceiptService._save_draft`/`_load_draft`, keyed by a generated id). This SP's pending selection is keyed by the *transaction id* instead of a generated id (only one in-progress multi-link per transaction makes sense at a time) — e.g. `pending_link_<transaction_id>.json` holding `{"receipt_ids": [...]}`, stored in the same upload folder drafts already use. A small new service method pair (`stage_receipt_for_link`/`unstage_receipt`/`get_staged_receipts`/`clear_staged_receipts`) on `TransactionService` or a new tiny helper, mirroring `ReceiptService`'s existing draft methods' shape.

### Routes (`app/routes.py`)
- `GET /transactions/<id>/link` — as today, plus reads the pending selection and passes the staged receipts (with running total) to the template. Staged receipt ids are excluded from the filtered results the same way already-linked-elsewhere receipts are.
- `POST /transactions/<id>/link/stage` — adds `receipt_id` to the pending selection, redirects back to `GET /transactions/<id>/link` preserving the current query string (so the filter results don't reset).
- `POST /transactions/<id>/link/unstage` — removes `receipt_id` from the pending selection, same redirect-preserving-filter behavior.
- `POST /transactions/<id>/link/confirm` — the "Add" button: sets `linked_transaction_id` on every staged receipt, clears the pending selection, flashes success, redirects to `/history`.
- `POST /transactions/<id>/link/cancel` — the "Cancel" button becomes a form post (was a plain link before) so it can clear the pending selection as it leaves; redirects to `/history`.

### Template (`templates/transaction_link.html`)
New "Selected so far" block above the existing `.search-results`, listing staged receipts with a small per-row "Remove" form (mirrors the existing per-row "Select" form's shape) and a running-total line. "Add" and "Cancel" sit together at the bottom, same relative position `.form-actions` already uses elsewhere (e.g. `edit_statement.html`).

### Amount mismatch — warn, never block
If the staged receipts' running total doesn't match the transaction's amount, show it plainly (e.g. a "does not match transaction amount" note next to the total) but don't prevent clicking "Add" — real-world settlements can be partial, include a tip, or round differently. This is informational, not a validation gate.

### Currency
All staged receipts must share the transaction's currency — receipts in a different currency are excluded from the filter results the same way the filter already excludes non-matching currencies implicitly via the amount comparison; worth an explicit currency-equality check in the results filter too, independent of the amount range, since two different currencies could otherwise both fall inside a wide date/amount range filter.

### Resolved: "Unlink" is all-or-nothing for now
SP-027's existing Unlink icon lives on the *transaction's* row in History and clears its one link. SP-037 doesn't touch that UI, only the data model. Decided: extend the existing Unlink action to clear `linked_transaction_id` on every receipt currently linked to that transaction, rather than building a per-receipt unlink surface — simplest option, no new UI needed, and correcting a group down by one receipt (unlink all, re-stage the ones to keep) is an acceptable amount of friction for what should be a rare correction. Revisit with a per-receipt unlink SP later only if this turns out to matter in practice.

### Out of scope (this SP)
- A per-receipt unlink surface for an already-committed multi-receipt group — deferred per the above; Unlink stays all-or-nothing.
- Any change to automatic matching — still SP-026's exact single-receipt rule, unchanged.

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
