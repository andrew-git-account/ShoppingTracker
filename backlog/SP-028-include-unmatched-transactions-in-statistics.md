# SP-028: Include Unmatched Transactions in Statistics

**Priority**: Medium
**Status**: Ready

## Description
Extend the Statistics page so an unlinked transaction counts as its own un-itemized expense, while a linked transaction contributes nothing on its own (its linked receipt already accounts for that money at the item level). This is the payoff of the whole statement-import feature: total spend reflects receipts *and* statement-only expenses, without ever double-counting a purchase that shows up in both.

## Acceptance Criteria
- [ ] Statistics' per-month, per-currency totals include unlinked transactions as an additional un-itemized amount, shown separately from the existing per-category receipt breakdown.
- [ ] A month where the user has unlinked transactions but no receipts at all still appears in the month selector and shows the correct un-itemized total — Statistics is not receipt-gated for month visibility. (Today's `/statistics` builds its month dropdown from receipts only; this SP must widen that, not just add totals underneath it.)
- [ ] Likewise, a currency that appears only in unlinked transactions (no receipts) for the selected month still gets its own currency group, not just an addition to currency groups that already exist from receipts.
- [ ] A linked transaction contributes nothing to Statistics by itself — only its linked receipt's items are counted, exactly as today (SP-012). Counting both would double the spend for that purchase.
- [ ] Unlinked-transaction totals are grouped by currency the same way category totals already are — a transaction never gets summed together with amounts in a different currency.
- [ ] Transactions are grouped into the same month buckets as receipts, using the transaction's own date and the same month-key logic already used for receipts (`_month_key` in `app/routes.py`, generalized — see below).

## Notes / Context

### Route (`app/routes.py`)
The current `/statistics` builds `months` and `currency_groups` entirely from receipts — `months = sorted({_month_key(r) for r in receipts}, reverse=True)`, and the per-currency loop only ever sees currencies that had at least one receipt that month. Both need to become **unions** of receipt data and unlinked-transaction data, not receipt-driven structures with transaction totals bolted on afterward:
- `months`: union of `{_month_key(r.purchase_date or r.saved_at[:10]) for r in receipts}` and `{_month_key(t.date) for t in unlinked_transactions}`.
- Per selected month: alongside the existing `totals_by_currency` category breakdown (built from receipts), compute a second `{currency: amount}` mapping from the user's transactions filtered to `linked_receipt_id is None` and that month. When building `currency_groups`, iterate over the **union** of currencies present in either mapping — a currency with only unlinked-transaction data for that month still gets its own group, with `categories: []` and the un-itemized amount as its total.
- Render the un-itemized amount as an additional line/section per currency group — e.g. "Un-itemized (from statements): {currency} {amount}" — rather than inventing a fake category, since a statement line has no item-level category to assign (out of scope to add one here — see below).

`_month_key()` itself needs generalizing: it currently hardcodes receipt attribute access (`def _month_key(receipt): date_str = receipt.purchase_date or receipt.saved_at[:10]; ...`), which doesn't work against a `Transaction` (SP-025's model has a single `date` field, not `purchase_date`/`saved_at`). Change its signature to take a plain date string — `_month_key(date_str: str) -> str`  — and update its existing receipt call sites to pass `receipt.purchase_date or receipt.saved_at[:10]` themselves; transaction call sites then just pass `transaction.date`.

### Template (`templates/statistics.html`)
Add the un-itemized total to each currency group's existing summary, following the current category-list/percentage-bar markup conventions.

### Explicitly out of scope
- Per-transaction categorization (assigning a category to an un-itemized transaction, e.g. by guessing from the merchant description) — a real potential follow-up, but adding it here would blur this SP's one job (get the totals right without double-counting) with a second, harder problem (category inference from a bare merchant string).
- Search (`/history?q=`) including transactions — search is item-based today and transactions have no items; left untouched.

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
