# SP-032: Restrict Automatic Matching to Debit Transactions

**Priority**: Medium
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-039
**Deployed**: 41e8c91 (2026-08-26)

## Description
Reverse SP-026's "no direction filter" decision: `TransactionMatcher.match_transaction` and `match_receipt` should only consider `debit` transactions as match candidates, never `credit` ones (refunds, incoming transfers, salary), on both directions of matching (a statement upload matching against existing receipts, and a receipt upload/edit matching against existing transactions).

## Acceptance Criteria
- [x] `_core_match` in `app/services/transaction_matcher.py` requires `transaction.direction == 'debit'`, in addition to the existing currency/amount/date checks — the single choke point both `match_transaction` and `match_receipt` call, so one change covers both directions.
- [x] A `credit` transaction is never automatically linked to a receipt, whether it's the transaction side or the receipt side that just got saved/edited.
- [x] A `debit` transaction continues to match exactly as before (currency/amount/date exact match, store-name substring tiebreak when ambiguous, one-to-one enforcement) — no behavior change for the common case.
- [x] Manual linking (SP-027) is unaffected — a user can still deliberately link a `credit` transaction to a receipt by hand (e.g. reconciling a refund); this SP only tightens *automatic* matching.
- [x] The existing test asserting a credit transaction *does* match (`test_credit_direction_still_matches` in `tests/test_transaction_matcher.py`) is updated to assert the new debit-only behavior instead of the old one, not left contradicting the shipped code.

## Notes / Context

### Why this reverses SP-026's original call
SP-026 deliberately allowed any `direction` to match, reasoning that a refund credit reconciling against its original receipt was a legitimate case worth supporting automatically. Revisited: automatic matching should stay conservative and cover the common case only (a receipt represents an outgoing purchase, i.e. a debit line) — a refund is comparatively rare and its match is not always obvious (a $50 refund isn't necessarily *the* $50 receipt from three purchases ago), so it's safer left to a human's judgment. SP-027's manual link page already exists for exactly this — a user who wants to reconcile a credit against a receipt still can, deliberately, one click away; this SP only removes it from the *silent, automatic* path.

### Implementation (`app/services/transaction_matcher.py`)
```python
def _core_match(transaction: Transaction, receipt: Receipt) -> bool:
    return (
        transaction.direction == 'debit'
        and transaction.currency == receipt.currency
        and round(transaction.amount, 2) == round(receipt.total_amount, 2)
        and transaction.date == _date_for_receipt(receipt)
    )
```
No other change needed in `match_transaction`/`match_receipt` — both already funnel every candidate through `_core_match`.

### Test updates needed
- `tests/test_transaction_matcher.py::test_credit_direction_still_matches` currently seeds a `credit` transaction and asserts it links — invert to assert it does *not* link, and rename to reflect the new behavior (e.g. `test_credit_direction_never_matches`).
- Add a companion test confirming a `credit` transaction with an otherwise-exact date/amount/currency match against a receipt does NOT get linked via either `match_transaction` or `match_receipt`.
- `tests/test_routes.py`'s SP-030 edit tests (`test_post_edit_amount_change_triggers_matcher`, etc.) use `direction='debit'` by default already (via `seed_transaction`'s default) — should be unaffected, but worth a full-suite run to confirm nothing else implicitly relied on credit-matching.

### BehaviorSpec update
`BS-039` ("Transactions and Receipts Are Automatically Matched") currently doesn't mention direction at all as a filter — it should gain a line noting only debit transactions are auto-matched, credit ones aren't (handled at `/sdlc-done` time, per the existing gap-check step).

### Out of scope (this SP)
- Any change to SP-027 (manual link/unlink) — a credit transaction remains fully linkable by hand.
- Any change to SP-028 (Statistics) — it already filters to `debit` transactions independently for its own totals; unaffected either way.
- Surfacing unlinked `credit` transactions anywhere new (e.g. an "income" line) — unrelated to this SP.

## Implementation Notes
Completed 2026-08-25.

- `app/services/transaction_matcher.py` — `_core_match` now requires `transaction.direction == 'debit'`, in addition to the existing currency/amount/date checks. Single choke point both `match_transaction` and `match_receipt` already funneled every candidate through, so this one line covers both matching directions.
- No other source changes — `match_transaction`/`match_receipt` didn't need to change at all.
- Tests: `tests/test_transaction_matcher.py` — renamed and inverted `test_credit_direction_still_matches` → `test_credit_direction_never_matches_statement_to_receipt` (now asserts the credit transaction stays unlinked instead of getting linked), and added `test_credit_direction_never_matches_receipt_to_statement` covering the mirror direction. No other existing test needed changes, since all of them already used `direction="debit"` by default. Full suite: 426 passed (424 existing + 2 in the credit-direction area, one renamed).
- No migration or data changes.
