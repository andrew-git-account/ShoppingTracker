# SP-045: Allow a 5-Day Date Window in Transaction Matching

**Priority**: High
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-039

## Description
The transaction date on a card account statement is often a few days later than the actual purchase (posting delay), so the current exact-date match in automatic matching finds nothing when a statement is loaded. Change the matching logic so a transaction matches a receipt when the transaction date falls between the receipt date and receipt date + 5 days (inclusive).

## Acceptance Criteria
- [x] `_core_match` in `app/services/transaction_matcher.py` accepts a transaction when `receipt_date <= transaction.date <= receipt_date + 5 days` (both ends inclusive), where `receipt_date` is `_date_for_receipt(receipt)`.
- [x] A transaction dated *before* the receipt date, or more than 5 days after it, is not matched.
- [x] The window applies in both directions of matching: a statement upload matching against existing receipts (`match_transaction`) and a receipt save/edit matching against existing transactions (`match_receipt`).
- [x] All other `_core_match` conditions are unchanged: debit only (SP-032), same currency, exact amount, one-to-one linking, and skipping receipts/transactions that are already linked.
- [x] When more than one candidate falls inside the window, the existing store-name substring tiebreak still applies, and no link is made if it doesn't narrow to exactly one (no guessing).
- [x] Manual link/unlink (SP-027, SP-038) is unaffected.
- [x] Tests in `tests/test_transaction_matcher.py` cover: same day, +5 days (matches), +6 days (no match), -1 day (no match), both matching directions, and an ambiguous two-candidate case inside the window.
- [x] Any existing test that asserts a different-date transaction does *not* match is updated to use a date outside the new window. The full suite passes.

## Notes / Context
- SP-026 deliberately chose exact-date matching (see the module docstring in `transaction_matcher.py`) to avoid over-matching, which would silently drop real spend from Statistics (SP-028). The window reverses that for date only; amount, currency and direction stay exact, and the ambiguity rule stays conservative, so over-matching risk remains low.
- Widening the window makes ambiguity more likely (e.g. two same-amount purchases within 5 days). `_narrow` already declines to guess in that case. Preferring the closest date as an extra tiebreak is deliberately out of scope here; add it in a follow-up if needed.
- The window length (5 days) should be a named module constant (e.g. `DATE_WINDOW_DAYS = 5`) rather than a magic number.
- Dates are stored as `YYYY-MM-DD` strings; parse with `datetime.date.fromisoformat` and handle unparseable values by treating them as no match.
- Update the module docstring ("exact date/amount only, no tolerance window") and BehaviorSpec `BS-039` to describe the date window. The BehaviorSpec update is handled at `/sdlc-done` time.

### Out of scope
- Making the window configurable by the user.
- Changing matching of amounts (tolerance) or currencies.
- Re-running matching over already-loaded, unmatched transactions (a one-time backfill).

## Implementation Notes
Completed 2026-10-07.

- `app/services/transaction_matcher.py` - added the `DATE_WINDOW_DAYS = 5` constant and an `_in_date_window()` helper (parses `YYYY-MM-DD` strings; unparseable values count as no match). `_core_match` now accepts a transaction dated from the receipt date to receipt date + 5 days (both inclusive) instead of requiring an exact date. Module and function docstrings updated. Both `match_transaction` and `match_receipt` go through `_core_match`, so the window applies in both directions; debit-only, currency, exact amount, one-to-one and the `_narrow` store-name tiebreak are unchanged.
- `tests/test_transaction_matcher.py` - new `TestDateWindow` class (12 test cases, some parametrized): same day, +3, +5 days match; +6 and -1 day do not; both matching directions; ambiguous two-receipt case unlinked when not narrowed, linked when the store name narrows it, and an out-of-window receipt not counting as a candidate. No existing test needed changing (all used identical dates).
- `Specification/BehaviorSpec.md` - BS-039 updated to describe the date window (it previously stated "exact same date, no tolerance window").
- No migrations, data changes or new dependencies.
- Tests: 12 added; full suite 612 passed.
