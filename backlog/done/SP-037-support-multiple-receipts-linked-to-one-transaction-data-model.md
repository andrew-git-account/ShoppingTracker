# SP-037: Support Multiple Receipts Linked to One Transaction (Data Model)

**Priority**: High
**Status**: Done
**Fulfils**: Specification/DataSchema.md#Receipt-JSON (adds `linked_transaction_id`); preserves BehaviorSpec.md BS-039, BS-042, BS-043, BS-044 unchanged (this SP is a data-model-only change, no user-visible behavior differs)
**Deployed**: 3164e4e (2026-08-31)

## Description
Flip the link from `Transaction.linked_receipt_id` (one transaction points at one receipt) to `Receipt.linked_transaction_id` (one receipt points at one transaction, but many receipts can point at the *same* transaction) — the natural relational shape for "a few receipts settled by one payment" (e.g. a running tab paid off in one card charge). Pure data-model change: every existing read/write site gets updated to the new field, with zero behavior change for today's existing one-receipt-per-transaction case. The manual multi-select UI that actually lets a user *create* a many-receipts-to-one link is a separate follow-up story (SP-038) — this SP only makes the model capable of representing it and keeps everything working exactly as before in the meantime.

## Acceptance Criteria
- [x] `Receipt` (`app/models.py`) gains `linked_transaction_id: Optional[str] = None`, with `to_dict()`/`from_dict()` support (`from_dict()` defaults a missing value to `None` — the established no-migration-needed convention already used for other added fields).
- [x] `Transaction.linked_receipt_id` is removed from the model entirely — no backwards-compatibility shim, no dual-field transition period.
- [x] `TransactionMatcher.match_transaction`/`match_receipt` (SP-026) set `linked_transaction_id` on the matched *receipt* instead of `linked_receipt_id` on the transaction. A transaction already claimed by one or more receipts is skipped by automatic matching (never adds a second receipt on top of an existing link, automatic or manual) — automatic matching still only ever proposes a single receipt per transaction, same as today.
- [x] A receipt already linked to *any* transaction is still excluded as a match candidate (the one-per-transaction constraint moves to "one receipt can't belong to more than one transaction," which is the same rule expressed from the other side).
- [x] Statistics' "a linked transaction contributes nothing on its own" rule (SP-028) becomes "a transaction with at least one receipt linked to it contributes nothing" — same outcome for today's one-receipt case, generalizes correctly once a transaction can have several.
- [x] History's linked badge (SP-029) shows on a transaction if *any* receipt links to it — computed once per `history()` call (a precomputed set of linked transaction ids), not a per-row lookup.
- [x] Statement deletion (SP-031) clears `linked_transaction_id` on *every* receipt referencing a transaction being deleted, not just one — a natural generalization of the existing loop (finds 0, 1, or many receipts now instead of assuming at most 1).
- [x] Receipt deletion (SP-033) simplifies to clearing `linked_transaction_id` on the one receipt being deleted directly — no more scanning transactions for a stale reference, since the field now lives on the receipt itself.
- [x] SP-027's existing manual link/unlink routes (`transaction_link`/`transaction_unlink`) are updated to read/write the new field, but keep their *current* single-receipt behavior unchanged — full existing test suite for SP-027 passes with no behavioral difference, just via the new field internally.
- [x] A one-off migration script converts existing production data: for every transaction with a (soon-to-be-removed) `linked_receipt_id`, set that receipt's new `linked_transaction_id` accordingly.
- [x] Full existing test suite passes end-to-end with no change to any test's observable assertions (only fixture/setup code touching the renamed/relocated field changes).

## Notes / Context

### Why the FK moves to the receipt side
One-to-many relationships are conventionally modeled with the foreign key on the "many" side. A transaction can now settle several receipts, but a receipt is still settled by at most one transaction — so `Receipt.linked_transaction_id` (singular) is the correct field, not a list anywhere. The multiplicity lives entirely in "several receipts can hold the same transaction id," never in a receipt holding several transaction ids.

### Nice simplification: receipt deletion (SP-033)
Today's `delete_receipt` scans all of the user's transactions looking for one whose `linked_receipt_id` matches the receipt being deleted (guarding against the "shouldn't happen but isn't schema-enforced" case of more than one). Under the new model this disappears entirely — the receipt being deleted just has its own `linked_transaction_id` field cleared directly, no scan needed.

### Automatic matching's guard needs a helper for "does this transaction already have a receipt"
Today's guard is `if transaction.linked_receipt_id: return` — a direct field check. The equivalent under the new model is a lookup: does any receipt for this user have `linked_transaction_id == transaction.transaction_id`? Same style as the existing `_already_linked_receipt_ids` helper in `app/routes.py`, just checking the other direction — worth adding an equivalent helper in `TransactionMatcher` rather than inlining the scan at each call site.

### Migration script
`migrate_receipt_transaction_links.py` (repo root, matching the existing `migrate_categories.py` convention): reads `transactions.json`, and for each transaction with a `linked_receipt_id`, sets that receipt's `linked_transaction_id` in `receipts.json`. Prints a before/after summary (links migrated). Leaves the old `linked_receipt_id` key sitting unused in `transactions.json` afterward (harmless, since nothing reads it anymore) rather than doing a separate cleanup pass — consistent with this project's general preference for additive, low-risk migrations over rewriting-in-place where not necessary.

### Interaction with the SQLite migration (SP-034/035/036)
If those land first, apply this same field flip directly in the `receipts`/`transactions` table schemas instead of writing a JSON-to-JSON migration script. If this SP lands first (as currently expected, given it's next up), the SQLite migration stories should pick up `Receipt.linked_transaction_id` as it exists at that point — no special handling needed either way, since the model/dict shape is what both migration paths read from.

### Out of scope (this SP)
- The manual multi-select UI (staging several receipts, a running total, a "Remove" per staged item, a final "Add") — SP-038.
- Any change to automatic matching's actual matching logic (still exact single-receipt, no subset-sum guessing across several receipts) — deliberately not extending SP-026's conservatism.

## Implementation Notes

Completed 2026-08-30.

- **`app/models.py`**: `Receipt` gains `linked_transaction_id: Optional[str] = None` (constructor, `to_dict()`, `from_dict()`). `Transaction.linked_receipt_id` removed entirely (constructor, `to_dict()`, `from_dict()`, docstring).
- **`app/services/transaction_matcher.py`**: `match_transaction`/`match_receipt` rewritten to read/write `linked_transaction_id` on the receipt side. `match_transaction` now skips a transaction already claimed by any receipt (via a scan over `get_all_receipts`) instead of a direct field check. `match_receipt` gained a guard against re-linking an already-linked receipt (a gap in the prior one-to-one code, closed as part of this AC).
- **`app/routes.py`**: `_already_linked_receipt_ids` now takes `receipt_service` and reads the new field. `statistics()` and `history()` each compute a `linked_transaction_ids` set once (from `receipts`) instead of reading a per-transaction field. `statement_delete` clears `linked_transaction_id` on every receipt referencing a deleted transaction (was a single-receipt assumption). `delete_receipt` simplified to clear its own `linked_transaction_id` directly (no more scanning all transactions). `transaction_link`/`transaction_unlink` write/clear the field on the receipt. Fixed two latent bugs found during implementation: `_parse_edit_form` (receipt edit) wasn't carrying `linked_transaction_id` forward, and the statement-edit transaction-row builder still referenced the removed `linked_receipt_id` constructor arg (would have raised `TypeError` on save).
- **`templates/history.html`**: both linked-badge/unlink-form conditionals switched from `transaction.linked_receipt_id` to `transaction.transaction_id in linked_transaction_ids`.
- **`migrate_receipt_transaction_links.py`** (new): one-off migration reading `linked_receipt_id` off each transaction in `data/transactions.json` and writing `linked_transaction_id` onto the matching receipt in `data/receipts.json`. Not yet run against production data (no data changes made this session beyond code).
- **Tests**: `tests/test_routes.py`, `tests/test_transaction_matcher.py`, `tests/test_database.py` updated to seed/assert via the new field (seed helpers gained/lost parameters; ~25 test methods reworked to fetch the receipt instead of the transaction for link assertions). Two tests whose premise no longer applied under the new model (multiple transactions pointing at one receipt) were replaced with the new model's equivalent multiplicity (multiple receipts pointing at one transaction). One new test added (`test_update_sets_linked_transaction_id`) for symmetry with the existing transaction-side update test.
- **`Specification/DataSchema.md`**: added the `linked_transaction_id` row to the Receipt field reference table (pre-existing gap: this document has no Transaction schema section at all, predating this SP — out of scope here).
- Test summary: 430 passed, 0 failed (1 test added net; several others reworked in place). Server boot verified (`GET /` → 200) after clearing `__pycache__`.


