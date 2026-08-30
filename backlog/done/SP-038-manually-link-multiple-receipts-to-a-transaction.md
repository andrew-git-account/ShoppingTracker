# SP-038: Manually Link Multiple Receipts to a Transaction in One Action

**Priority**: High
**Status**: Done
**Fulfils**: Specification/BehaviorSpec.md#BS-043 (corrected: "picking a receipt links immediately" was stale, now stages), #BS-045 (new)
**Deployed**: 3164e4e (2026-08-31)

## Description
Extend SP-027's transaction-link page so a user can select *several* receipts to settle with one transaction (e.g. a running tab paid off in one card charge), not just one. "Select" stages a receipt instead of linking it immediately; a running list of staged receipts (with a live running total) shows above the results; each staged receipt has its own "Remove" action; a new "Add" button (next to "Cancel") commits the whole staged batch at once. Builds on SP-037's data model — this SP is the user-facing feature that actually creates a many-receipts-to-one-transaction link.

## Acceptance Criteria
- [x] Clicking "Select" on a receipt in the filter results no longer links immediately — it stages the receipt (adds it to a pending selection for this transaction) and re-renders the same filter page.
- [x] The page shows a "Selected" section above the filter results listing every currently-staged receipt (store name, date, amount) plus a running total of their amounts, in the transaction's own currency.
- [x] Each staged receipt has its own "Remove" action, removing just that one from the pending selection without discarding the rest.
- [x] A staged receipt no longer appears in the filter results below (same exclusion principle already used for a receipt already linked elsewhere).
- [x] Re-filtering (changing the search fields and submitting again) preserves the current staged selection — staging is not tied to one specific filter query.
- [x] A new "Add" button, next to the existing "Cancel", commits the whole staged batch: sets `linked_transaction_id` (SP-037) on every staged receipt to this transaction, clears the pending selection, flashes a success message naming how many receipts were linked, redirects to History.
- [x] "Cancel" discards the pending selection entirely (no partial commit) and returns to History, same as it does today.
- [x] The existing single-receipt case still works end-to-end through the same flow (stage one, click Add) — no separate "quick single-link" path.
- [x] All actions remain restricted server-side to the transaction's and receipts' owner, same ownership pattern as every other action in the app.
- [x] "Unlink" on a transaction's row (SP-027) clears `linked_transaction_id` on *every* receipt currently linked to that transaction, not just one — all-or-nothing for now. Unlinking a single receipt out of an already-committed group isn't supported; the user would unlink the whole group and re-stage the ones they want to keep.

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

Completed 2026-08-30.

- **`app/services/link_staging_service.py`** (new): `LinkStagingService`, a tiny file-backed store mirroring `ReceiptService`'s draft mechanism (`_save_draft`/`_load_draft`/`_delete_draft`), keyed by `transaction_id` rather than a generated id since only one in-progress multi-link per transaction makes sense at a time. Stores `pending_link_<transaction_id>.json` (`{"receipt_ids": [...]}`) in the same upload folder drafts already use. Methods: `get_staged_receipt_ids`, `stage_receipt`, `unstage_receipt`, `clear_staged`. Validates `transaction_id` as a well-formed UUID before building any filesystem path from it, same defensive style as `_load_draft`.
- **`app/services/__init__.py`** / **`app/main.py`**: wired `LinkStagingService` as its own service (not added to `TransactionService`, to avoid touching that class's constructor and the separate root-level `conftest.py` fixture that builds it directly) — `app.link_staging_service`, constructed with the same `upload_folder` already used by `ReceiptService`/`StatementService`.
- **`app/routes.py`**: `transaction_link` is now GET-only (was GET+POST); its old POST branch (immediate link-and-redirect) is replaced by four new routes: `POST /transactions/<id>/link/stage`, `/unstage`, `/confirm`, `/cancel`. `transaction_link`'s GET handler now also computes and passes `staged_receipts`, `staged_total`, and `staged_mismatch` (`abs(total - transaction.amount) > 0.01`) to the template, and excludes staged receipt ids from the filter results alongside already-linked ones. Added the currency-equality check to the results filter (`receipt.currency == transaction.currency`) that the SP's own notes flagged as missing from the original filter. `confirm` re-validates each staged receipt against ownership and the one-receipt-per-transaction rule at commit time (not just at staging time) and silently skips anything that fails re-validation rather than aborting the whole batch. Confirming with nothing staged flashes an error and redirects back to the link page rather than to History (confirmed with the user - not specified by the SP text itself).
- **`templates/transaction_link.html`**: new "Selected so far" block above the filter results (reuses `.receipt-pick-row`/`.search-result-*` markup with a "Remove" form in place of "Select"), a running-total line with a mismatch warning span, and the "Select" forms' actions now carry the current filter query params so a stage/unstage round-trip preserves the search. `.form-actions` is now two sibling one-button `<form>`s (Cancel / Add) instead of a link + nothing, mirroring `edit_receipt.html`'s Discard/Save pattern.
- **`static/css/style.css`**: added `.staged-section`, `.staged-total`, `.staged-total-mismatch` (using the existing `var(--warning)` token for the non-blocking mismatch note).
- **`tests/test_routes.py`**: rewrote the three `TestTransactionLinkRoute` tests that POSTed directly to the old single-step endpoint as stage-then-confirm two-step flows; added 15 new tests covering staging/unstaging, re-filter persistence, multi-receipt confirm + pending-file clearing, the zero-staged confirm case, cancel, the new currency-exclusion filter, and ownership/not-found checks on all four new routes.
- **`Specification/BehaviorSpec.md`**: corrected BS-043 (its "picking a receipt links immediately" line was stale) and added BS-045 documenting the full staging workflow.
- No migration needed (no stored-data shape change - `linked_transaction_id` already exists on `Receipt` since SP-037; the pending-selection file is transient, cleared on confirm/cancel).
- Test summary: 15 new tests added, 442 passed, 0 failed. Server boot verified (`GET /` → 200) after clearing `__pycache__`.
