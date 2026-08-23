# SP-026: Automatically Match Transactions to Receipts

**Priority**: High
**Status**: Open

## Description
When a statement upload creates new transactions, or a receipt is saved (created or edited), automatically try to link each unmatched transaction to a corresponding receipt (same user, exact date, exact amount, and — only when that's not enough to pick a single one — a partial match on store name) so the pair can later be excluded from double-counting in Statistics (SP-028). Runs both directions — a receipt can arrive before or after its statement line, per the discussion that motivated this feature. Auto-linking never asks for confirmation, but is always reversible via SP-027's manual link/unlink. Matching is deliberately conservative — an exact date/amount match only, no tolerance windows — since under-matching just means a transaction sits unlinked (safe: SP-028 still counts it), while over-matching would silently drop real spend from Statistics.

## Acceptance Criteria
- [ ] After a statement upload (SP-025) creates new transactions, each is checked against the uploading user's existing unlinked receipts for a match; a match sets `linked_receipt_id` immediately, no confirmation step.
- [ ] After a receipt is saved or edited — normal upload, a draft save (SP-023/024), or `update_receipt` (SP-022) — it's checked against the user's existing unlinked transactions for a match, covering both "the statement arrived first" and "an edit just made this receipt newly match."
- [ ] A match requires: same user, same currency, the *same* amount (exact, no tolerance), and the *same* date (exact — see the date-field note below).
- [ ] If exactly one unlinked receipt exact-matches a transaction on user/currency/amount/date, they're linked. If more than one does, fall back to a partial (case-insensitive substring) match between the transaction's description and each candidate's store name; link only if that narrows it to exactly one. If it's still ambiguous (zero or multiple store-name matches among the tied candidates), don't auto-link at all — leave it for SP-027's manual link.
- [ ] Matching is one-to-one — a receipt or transaction already linked is never offered as a candidate again, in either direction.
- [ ] This SP adds no UI of its own — matching runs silently as a side effect of the existing upload/edit flows (receipt upload, receipt edit, draft save, statement upload).

## Notes / Context

### Reopened — stale after SP-025 (2026-08-23)
SP-025 was still In Testing when this SP was verified Ready, and testing added two fields not present at verification time: `Transaction.direction` (`"debit"`/`"credit"`) and `Transaction.category`. Initial read: matching should filter to `direction == 'debit'` only, on the assumption a receipt always represents an outgoing purchase. **Corrected 2026-08-23** — that assumption is wrong for this app; a `credit` transaction (e.g. a refund) can legitimately be linked to a receipt for reconciliation. No direction filter is needed — matching criteria stays exactly as written below (user/currency/amount/date, then store-name tiebreak), regardless of `direction`. `category` is likewise irrelevant to matching. With this resolved, this SP has no outstanding content gap from SP-025's changes; it's re-verifiable as-is via `/sdlc-verify-requirement 026`.

**2026-08-23 addendum**: [[SP-027]] was redesigned to show transactions as their own entries on the History page (not a separate page), with a linked transaction visually marked rather than hidden. That marker relies entirely on `linked_receipt_id` — the field this SP already sets — so no new field or output is needed here; just keep in mind while implementing that this is the field a UI elsewhere depends on for correctness, not an internal-only detail.

### Matching logic
New shared matcher — a module-level function or small class (e.g. `app/services/transaction_matcher.py`, or a method on `TransactionService`, which SP-025 now settles as the home for transaction operations — not a raw `JSONTransactionDatabase` call from either service) — callable from all trigger points:
- After `StatementService.process_statement()` saves new transactions.
- After `ReceiptService.process_receipt()` (the direct-save branch) and `ReceiptService.save_draft()` save a new receipt.
- After `ReceiptService.update_receipt()` (SP-022) edits an existing receipt — an edit to `total_amount` is exactly the field matching keys off, so an edit can newly make a receipt matchable.

Matching, per candidate transaction (or receipt) against the opposite type's unlinked pool:
1. Filter to same `user_email`, same `currency`, exact `amount` equality, exact date equality. "Exact" amount equality means rounded to 2 decimal places before comparing (e.g. `round(a, 2) == round(b, 2)`), not raw `==` on floats — this is purely a float-representation safety measure (avoiding a false negative from binary floating-point rounding on values that are legitimately equal), not a business tolerance like the reconciliation window this SP deliberately avoids.
2. **Date field**: compare the transaction's `date` against `receipt.purchase_date or receipt.saved_at[:10]` — the same fallback `_month_key()` (`app/routes.py`) already uses for a receipt with no printed purchase date, so a receipt missing `purchase_date` still participates instead of being silently unmatchable.
3. If step 1 yields exactly one candidate, link it.
4. If it yields more than one, narrow using a case-insensitive substring check between the transaction's `description` and each candidate's `store_name` (either containing the other counts as a match — no fuzzy-matching library needed for v1). Link only if this narrows the set to exactly one.
5. Otherwise (zero candidates from step 1, or still ambiguous after step 4), don't link — leave unlinked for SP-027.

### One-to-one enforcement
Candidate pool for matching a given transaction/receipt is always "unlinked ones only" — once either side of a pair is set, both are excluded from all future candidate pools.

### Data layer
Uses `TransactionService.update_transaction` (SP-025) to set `linked_receipt_id` in place, which itself delegates to `JSONTransactionDatabase.update_transaction` — same shape as `JSONDatabase.update_receipt` (SP-022): find by id + user_email, overwrite the field, write back.

### Out of scope (this SP)
- Any UI for reviewing, confirming, or undoing a match (SP-027).
- Using matched/unmatched status in Statistics (SP-028).
- Cleaning up an existing link when its receipt is later edited outside an exact match (e.g. the amount changes) or soft-deleted (SP-002) — the link is not automatically broken or re-validated after the fact; a stale link left this way is a known gap, deferred to a later SP rather than solved here.

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
