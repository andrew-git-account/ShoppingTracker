# SP-033: Clear Transaction Link on Receipt Deletion

**Priority**: Medium
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-044

## Description
When a receipt that's linked to a transaction (automatically via SP-026, or manually via SP-027) gets soft-deleted, clear that transaction's `linked_receipt_id` as part of the deletion — mirroring exactly what SP-031 already does in the opposite direction (deleting a statement clears the link on its transactions before they're soft-deleted). Closes a gap SP-026 explicitly documented and deferred: *"Cleaning up an existing link when its receipt is later edited outside an exact match or soft-deleted — the link is not automatically broken or re-validated after the fact; a stale link left this way is a known gap, deferred to a later SP."*

## Acceptance Criteria
- [x] Deleting a receipt that's linked to a transaction clears that transaction's `linked_receipt_id`, so the transaction becomes unlinked (visible as such in History, no longer excluded from Statistics as a duplicate).
- [x] Deleting a receipt with no linked transaction behaves exactly as today — no change for the common case.
- [x] If more than one transaction somehow points at the same receipt (shouldn't happen under the one-to-one rule, but isn't a schema-enforced invariant), all of them are cleared, not just the first found.
- [x] The receipt itself is still just soft-deleted (`is_deleted = True`) — this SP only adds the transaction-side cleanup, no change to receipt deletion's own behavior otherwise.
- [x] Ownership stays scoped the same way as today's `delete_receipt` — only the caller's own receipt (and only the caller's own transactions) are touched.

## Notes / Context

### Mirrors SP-031 exactly, opposite direction
SP-031 (`app/routes.py`'s `statement_delete`) already does this pattern when a statement is deleted: for each transaction being soft-deleted, if `linked_receipt_id` is set, clear it via `update_transaction` *before* the soft-delete. This SP is the same idea triggered from the other side — deleting the *receipt* instead of the *transaction*.

### Route (`app/routes.py`)
`delete_receipt` currently just calls `app.receipt_service.soft_delete_receipt(receipt_id, user_email)`. Add, before that call: find any transaction(s) owned by this user with `linked_receipt_id == receipt_id` (`[t for t in app.transaction_service.get_all_transactions(user_email) if t.linked_receipt_id == receipt_id]`), clear the field on each via `update_transaction`, then proceed with the existing soft-delete call unchanged.

### Where else this could live
Considered putting this in `ReceiptService.soft_delete_receipt` instead of the route, to keep it close to `TransactionService.soft_delete_transaction`'s SP-031 equivalent — but `ReceiptService` has no reference to `TransactionService` today (unlike `TransactionMatcher`, which explicitly holds both). Simplest to keep the cleanup in the route, same level SP-031's version lives at, rather than introducing a new cross-service dependency for one small fix.

### Out of scope (this SP)
- Any equivalent cleanup for `JSONDatabase.delete_receipt` (the hard-delete method) — it has no route/UI exposing it today (same as noted in SP-031), so nothing to wire up.
- Re-running `TransactionMatcher` after the unlink to see if the now-unlinked transaction matches some *other* receipt — out of scope; it simply becomes unlinked and available for a future statement upload or receipt save to match naturally, same as any other unlinked transaction.

## Implementation Notes
Completed 2026-08-25.

- `app/routes.py` — `delete_receipt` now finds every transaction owned by the caller with `linked_receipt_id == receipt_id`, clears the field via `update_transaction` on each, then proceeds with the existing `soft_delete_receipt` call unchanged. Mirrors `statement_delete`'s (SP-031) find-then-clear-then-delete shape from the opposite direction.
- `CLAUDE.md` — SP counter 031 → 033 (covers both this SP's and SP-032's creation).
- No model, service, or database changes — `get_all_transactions`/`update_transaction`/`soft_delete_receipt` all already existed.
- Tests: `tests/test_routes.py`'s `TestDeleteReceiptRoute` gained 3 tests — clearing a single linked transaction, clearing multiple transactions that (abnormally) point at the same receipt, and confirming the no-linked-transaction case is unaffected. Full suite: 429 passed (426 existing + 3 new).
