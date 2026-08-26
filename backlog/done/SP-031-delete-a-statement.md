# SP-031: Delete a Statement

**Priority**: Medium
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-041
**Deployed**: 41e8c91 (2026-08-26)

## Description
Add a delete (×) action to each statement card in History, mirroring SP-002's receipt-deletion pattern: a confirmation dialog, then a soft-delete (the record stays in the database, just excluded from view). Since a statement is a group of transactions sharing a `statement_id` rather than its own record, deleting it soft-deletes every transaction in that group in one action. Any transaction being deleted that was linked to a receipt (SP-026's automatic matching) has that link explicitly cleared first, so the receipt becomes available again for future matching rather than carrying a stale reference on a now-invisible transaction.

## Acceptance Criteria
- [x] Each statement card in History shows a delete (`×`) button, same style and placement convention as the receipt card's existing delete button (`.btn-delete`).
- [x] Clicking it shows a confirmation dialog before anything happens, same native-browser-confirm pattern as receipt deletion (SP-002) — naming how many transactions will be removed.
- [x] Confirming soft-deletes every transaction sharing that statement's `statement_id` in one action — not a physical removal from the JSON file, and not just the first/one transaction.
- [x] Once every transaction in a statement is soft-deleted, the statement card no longer appears in History at all (falls out naturally, since `get_all_transactions()` already excludes soft-deleted records everywhere).
- [x] Any transaction being deleted that has `linked_receipt_id` set has that field cleared *before* the soft-delete, so the previously-matched receipt is genuinely available again for a future automatic match (SP-026) — not just hidden alongside a stale reference.
- [x] Deleting is restricted to the statement's owner, enforced server-side (same ownership pattern as every other action in the app, SP-005) — not found and not-owned look identical.
- [x] A single-transaction "statement" (a legacy record whose `statement_id` defaults to its own `id`, per SP-029) deletes correctly through the same action, not just a multi-transaction statement.

## Notes / Context

### Data layer — new soft-delete method (mirrors SP-002 for receipts)
`JSONTransactionDatabase` has no delete method today. Add `soft_delete_transaction(transaction_id, user_email) -> bool`, the exact same shape as `JSONDatabase.soft_delete_receipt` (`app/database/json_db.py`): find by `id`+`user_email`, set `is_deleted = True`, write back; returns `False` if not found or not owned (not found and not-owned intentionally indistinguishable, same as every other action in the app). `TransactionService.soft_delete_transaction(...)` is a thin passthrough, mirroring `ReceiptService.soft_delete_receipt`.

### Route (`app/routes.py`)
New `POST /statement/<statement_id>/delete`:
- Fetch `[t for t in transaction_service.get_all_transactions(user_email) if t.statement_id == statement_id]` — the same ownership-scoped grouping `statement_edit`/`history()` already use. Empty → flash "Statement not found." + redirect to `/history`, matching `delete_receipt`'s not-found handling.
- For each transaction in the group: if `linked_receipt_id` is set, clear it via `update_transaction` first (a copy of the transaction with `linked_receipt_id=None`, everything else unchanged), *then* call `soft_delete_transaction` on it. Two explicit steps in a fixed order, not a single combined call.
- Flash a success message naming how many transactions were removed, redirect to `/history`.

### Form design
Same `onsubmit="return confirm(...)"` pattern as `delete_receipt` (SP-002) — no JavaScript beyond the native browser confirm dialog already used there. New delete `<form>` added to the statement's `<summary class="receipt-summary">`, right after the edit icon SP-030 added (the same relative position a receipt's delete-form occupies after its own edit icon). Reuses the existing `.btn-delete`/`.delete-form` CSS — no new classes needed.

### Why explicitly clear the link rather than relying on the is_deleted filter
`get_all_transactions()` already excludes soft-deleted transactions everywhere (History, the matcher's candidate pools, and presumably a future SP-028's statistics), so a deleted transaction's stale `linked_receipt_id` would never actually surface through any of today's existing read paths. But leaving it set would misrepresent the data if inspected directly, and — more importantly — is what makes the receipt available again to `TransactionMatcher`: its "already-claimed receipts" set (`match_transaction`'s `linked_receipt_ids`) is built only from non-deleted transactions, so once this transaction is excluded by the delete, the receipt it pointed to would already be free for a future match even without this step. Clearing the field explicitly is therefore about correctness of intent and data hygiene, not a functional bug being patched in matching itself — but it's the more honest, explicit thing to do rather than depending on every future reader of `transactions.json` re-deriving that a deleted record's fields don't mean anything anymore.

### Out of scope (this SP)
- Restoring ("undeleting") a soft-deleted statement — no such capability exists for receipts either.
- Permanently (hard) deleting a statement — `JSONDatabase.delete_receipt` exists but has no route/UI exposing it for receipts either; same story for transactions.
- Deleting a single transaction within a statement rather than the whole statement — not asked for. SP-027 (manual unlink) is the closest related existing capability, but unlinking isn't deleting.
- Any interaction with SP-028 (Statistics) beyond the fact that a soft-deleted transaction already won't be counted, the same way a soft-deleted receipt already isn't.

## Implementation Notes
Completed 2026-08-25.

- `app/database/transaction_db.py` — new `soft_delete_transaction(transaction_id, user_email)`, exact mirror of `JSONDatabase.soft_delete_receipt`.
- `app/services/transaction_service.py` — new `soft_delete_transaction(...)` thin passthrough, mirroring `ReceiptService.soft_delete_receipt`.
- `app/routes.py` — new `POST /statement/<statement_id>/delete`: fetches the statement's transactions via the same ownership-scoped grouping `statement_edit` already uses, clears `linked_receipt_id` via `update_transaction` before calling `soft_delete_transaction` on each one, flashes a count-naming success message.
- `templates/history.html` — delete form/button added to each statement card's summary, right after the SP-030 edit icon, reusing the existing `.btn-delete`/`.delete-form` CSS with no new classes.
- `CLAUDE.md` — SP counter 030 → 031 (for this SP's own creation).
- No model or matcher changes needed — `Transaction.linked_receipt_id`, `update_transaction`, and the existing `is_deleted` filtering in `get_all_transactions()` were already sufficient.
- Tests: `tests/test_routes.py`'s `TestDeleteStatementRoute` (11 tests) — icon/URL presence, redirect and flash messaging, batch soft-delete across every transaction in a statement (not just the first), explicit link-clearing verified via the raw stored record, ownership (a foreign statement is untouched), a single-transaction legacy statement, and that deleting one statement doesn't touch a different one. Full suite: 403 passed (392 existing + 11 new).
- Verified manually against the live app with real data: the user deleted a real statement they'd uploaded earlier (used for manually testing SP-026's matcher) and asked for a check of leftover connections. Confirmed directly against `data/transactions.json`/`data/receipts.json`: all 4 of that statement's transactions were soft-deleted, none retained a `linked_receipt_id`, and the 3 receipts that had been auto-linked to them were confirmed genuinely unclaimed by any remaining live transaction afterward.
