# SP-028: Include Unmatched Transactions in Statistics

**Priority**: Medium
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-042
**Deployed**: 41e8c91 (2026-08-26)

## Description
Extend the Statistics page so an unlinked debit transaction's amount is folded into the same per-category, per-currency breakdown receipt items already build — using the transaction's own `category` field (SP-025 already assigns one, same vocabulary receipt items use) — while a linked transaction contributes nothing on its own (its linked receipt already accounts for that money at the item level). This is the payoff of the whole statement-import feature: total spend reflects receipts *and* statement-only expenses, correctly categorized and never double-counted for a purchase that shows up in both.

## Acceptance Criteria
- [x] An unlinked transaction's amount is added into the *same* per-category total its `category` field names, in the same currency group receipt items of that category already contribute to — not a separate "Un-itemized" line. A "Food & Groceries" transaction and a "Food & Groceries" receipt item in the same month/currency land in one combined category total.
- [x] Only `debit` transactions count toward this total. A `credit` transaction (refund, incoming transfer, salary) is excluded — even though it's unlinked, it isn't spend, and counting it would inflate the total with money that never left the account.
- [x] A month where the user has unlinked debit transactions but no receipts at all still appears in the month selector and shows the correct category totals — Statistics is not receipt-gated for month visibility. (Today's `/statistics` builds its month dropdown from receipts only; this SP must widen that, not just add totals underneath it.)
- [x] Likewise, a currency that appears only in unlinked debit transactions (no receipts) for the selected month still gets its own currency group, not just an addition to currency groups that already exist from receipts.
- [x] A category that appears only in unlinked debit transactions (no receipt items) for that currency/month still gets its own category line, not just an addition to categories that already have receipt items.
- [x] A linked transaction contributes nothing to Statistics by itself — only its linked receipt's items are counted, exactly as today (SP-012). Counting both would double the spend for that purchase.
- [x] Transactions are grouped into the same month buckets as receipts, using the transaction's own date and the same month-key logic already used for receipts (`_month_key` in `app/routes.py`, generalized — see below).

## Notes / Context

### Reopened — stale after SP-025 (2026-08-23)
SP-025 was still In Testing when this SP was verified Ready, and testing added two fields not present at verification time: `Transaction.direction` (`"debit"`/`"credit"`) and `Transaction.category`. Two gaps:
- **Correctness bug (fixed above)**: the original ACs summed *every* unlinked transaction's `amount`, with no `direction` filter — a `credit` transaction would have inflated spend with money the user never spent. Now fixed: only `debit` transactions count.
- **Resolved 2026-08-25 — merge by category, not a lump line**: the original design treated every unlinked transaction as one undifferentiated "Un-itemized" amount, on the assumption a statement line has no category to work with. That assumption predates SP-025, which already extracts a `category` per transaction from the same vocabulary receipt items use. Decision: merge an unlinked debit transaction's amount directly into the existing `{currency: {category: amount}}` breakdown by its own `category` — no separate section, no fake "Un-itemized" category. Per-transaction categorization is not a new problem this SP has to solve; the data already exists, this SP just has to read it.

### Route (`app/routes.py`)
The current `/statistics` builds `months` and `currency_groups` entirely from receipts — `months = sorted({_month_key(r) for r in receipts}, reverse=True)`, and `totals_by_currency = defaultdict(lambda: defaultdict(float))` is filled only from `receipt.items` (`for item in receipt.items: totals_by_currency[receipt.currency][item.category] += item.price * item.quantity`). Both need to become **unions** of receipt data and unlinked-debit-transaction data, not receipt-driven structures with transaction totals bolted on afterward:
- `months`: union of `{_month_key(r.purchase_date or r.saved_at[:10]) for r in receipts}` and `{_month_key(t.date) for t in unlinked_debit_transactions}`.
- Per selected month: after the existing receipt-items loop populates `totals_by_currency`, add one more loop over the user's transactions filtered to `direction == 'debit' and linked_receipt_id is None` and that month: `totals_by_currency[transaction.currency][transaction.category] += transaction.amount` — the *same* dict receipt items already populate, so a shared currency/category combination merges automatically with no special-casing. The rest of `currency_groups`' construction (sorting categories by amount, computing percentages, currency totals) is unchanged, since it already just iterates whatever `totals_by_currency` contains.

`_month_key()` itself needs generalizing: it currently hardcodes receipt attribute access (`def _month_key(receipt): date_str = receipt.purchase_date or receipt.saved_at[:10]; ...`), which doesn't work against a `Transaction` (SP-025's model has a single `date` field, not `purchase_date`/`saved_at`). Change its signature to take a plain date string — `_month_key(date_str: str) -> str`  — and update its existing receipt call sites to pass `receipt.purchase_date or receipt.saved_at[:10]` themselves; transaction call sites then just pass `transaction.date`.

### Template (`templates/statistics.html`)
No changes needed — a category originating partly or entirely from unlinked transactions renders through the exact same category-list/percentage-bar markup as any other category, since it's the same `categories` list structure by the time the template sees it.

### Explicitly out of scope
- Inferring a category for a transaction that has none — doesn't arise: `StatementService.process_statement()` already defaults an unrecognized/missing category to `"Other"` at extraction time (SP-025), so every transaction always has a valid category by the time Statistics reads it.
- Surfacing unlinked `credit` transactions anywhere (e.g. an "income" line) — a reasonable follow-up, not this SP's job.
- Search (`/history?q=`) including transactions — search is item-based today and transactions have no items; left untouched.

## Implementation Notes
Completed 2026-08-25.

- `app/routes.py` — `_month_key()` generalized from `_month_key(receipt)` to `_month_key(date_str: str)`, with its 3 existing call sites (in `history()` and `statistics()`) updated to pass the date string themselves. `statistics()` now fetches `unlinked_debit_transactions` (`direction == 'debit' and not linked_receipt_id`), unions their months into the month selector, and adds each one's amount directly into the existing `totals_by_currency[currency][category]` dict right after the receipt-items loop — no separate structure, no special-casing for a category/currency that exists only via transactions.
- `templates/statistics.html` — no changes; confirmed the existing category-list markup is already generic enough to render a transaction-sourced or merged category the same as any other.
- No model, service, or database changes — every field this SP reads (`direction`, `category`, `linked_receipt_id`, `amount`) already existed.
- Tests: `tests/test_routes.py`'s `TestStatisticsIncludesTransactions` (8 tests) — merging into an existing category, a month/currency/category that exists only via transactions, credit-transaction exclusion, and a linked transaction contributing nothing beyond its receipt. Full suite: 411 passed (403 existing + 8 new).
- This SP went through a requirement-verification correction before implementation: the original design (written before SP-025 added a `category` field to `Transaction`) planned a separate lump "Un-itemized" line; re-verification resolved it to merge by category into the existing breakdown instead, once it was clear the category data already existed and needed no new inference logic.
