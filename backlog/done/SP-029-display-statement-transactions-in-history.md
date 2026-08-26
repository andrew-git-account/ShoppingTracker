# SP-029: Display Statement Transactions in History

**Priority**: High
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-038
**Deployed**: 41e8c91 (2026-08-26)

## Description
Show each statement upload as its own expandable entry on the History page (SP-004), interleaved with receipts by date — mirroring exactly how a receipt is shown: a collapsed summary card that expands to a list of the lines inside it. A receipt expands to its items; a statement expands to its transactions. This is not a per-transaction entry — it's one card per upload, grouped by a new `statement_id` shared by every transaction extracted from that one PDF (SP-025's `StatementService.process_statement()` generates it). The card's icon and label differ by statement `source` (bank vs card), and each transaction line inside shows its own date, category, `direction` (debit/credit), amount, and a linked marker if it's matched to a receipt (SP-026 automatic, or SP-027 manual) — never hidden or deduplicated, since History is a complete record, not a de-duplicated view (that's Statistics/SP-028's job). This SP is display-only; the interactive Link/Unlink actions themselves are [[SP-027]], which will attach to the transaction rows this SP renders.

## Acceptance Criteria
- [x] Every transaction extracted from the same statement upload shares one `statement_id`, assigned once per upload (not once per transaction) in `StatementService.process_statement()`.
- [x] History (`/history`) shows one entry per `statement_id` — a collapsed card, expandable to reveal the list of that statement's transactions — grouped into the same month buckets as receipts and sorted by date descending together with them (using the statement's most recent transaction date as its position). Not a separate list, and not one entry per individual transaction.
- [x] The statement card's collapsed view shows: an icon and label distinct by `source` (one for a bank statement, one for a card statement, both distinct from a receipt's icon), and its date span (a single date if all its transactions share one date, otherwise the earliest–latest range).
- [x] Expanding a statement card lists each of its transactions, each showing: date, description, category, `direction` (debit/credit), and amount + currency.
- [x] A transaction with `linked_receipt_id` set is visually marked as linked within its statement's expanded list — but is still listed, never hidden or omitted.
- [x] A `Transaction` record saved before this SP (no `statement_id` in storage) still renders correctly — as its own single-transaction statement card — rather than erroring or being silently dropped.
- [x] History's search (`/history?q=`) is unaffected — it stays item-based and continues to search only receipt items, not transactions.
- [x] After a successful statement upload, the user is redirected to History (`/history`) to see the result — matching receipt upload's existing behavior (`app/routes.py::upload`), rather than back to the upload form.

## Notes / Context

### Redesigned 2026-08-23 (second pass)
First implementation (now superseded) rendered each transaction as its own flat card, like a lightweight receipt-without-items. Feedback: this didn't match the intended shape — a statement should display like a receipt does, as one expandable card per upload with its transactions listed inside, the same relationship a receipt has to its items. This version reflects that correction. The route/template/CSS from the first pass are being reworked, not kept alongside.

### Model (`app/models.py::Transaction`)
New field: `statement_id: Optional[str] = None`. Add to constructor, `to_dict()`, and `from_dict()`. In `from_dict()`, default a missing `statement_id` to the transaction's own `id` (`data.get('statement_id') or data.get('id')`) — the established convention in this codebase for schema changes (see `sdlc-deploy`'s migration-free pattern: model `from_dict()` supplies defaults, no active migration needed). This makes every transaction belong to *some* statement group even if it predates this field, satisfying the "renders correctly" acceptance criterion above without a migration script.

### Statement service (`app/services/statement_service.py`)
`process_statement()` currently builds one `Transaction` per extracted line with no shared identifier. Generate one `statement_id = str(uuid.uuid4())` at the top of the method (before the extraction loop), and pass it into every `Transaction(...)` constructed from that upload's extracted lines.

### Route (`app/routes.py::history`)
- Fetch transactions as before, but group them by `transaction.statement_id` (not shown individually).
- For each `statement_id` group: sort its transactions by date descending; the group's representative date (for month-bucketing and inter-card sort order, same role `receipt.purchase_date or receipt.saved_at[:10]` plays for a receipt) is its most recent transaction's date; `source` and the date span (earliest/latest) come from the same group.
- Union these statement-groups with receipts into the same per-month `entries` list as before, sorted together by date descending.

### Template (`templates/history.html`)
A statement entry reuses the receipt card shell almost entirely — `<details class="receipt-card">` / `<summary class="receipt-summary">` with the same `receipt-header`/`receipt-icon`/`receipt-info`/`store-name`/`receipt-date` classes (icon and label driven by `source`; date is the span), and `receipt-total`'s slot shows a transaction count (e.g. "12 transactions") rather than an amount, since summing debit and credit together would misrepresent the statement — not in scope to solve here. The expanded body reuses `items-section`/`items-list`/`item-row`/`item-name`/`item-category`/`item-price` exactly as a receipt's item list does, plus this SP's existing `transaction-direction`/`transaction-direction-debit`/`transaction-direction-credit`/`linked-badge` CSS classes (kept from the first pass) for the direction badge and linked marker on each row, and one new small class for the per-row date (styled like `item-quantity`, but named for what it actually is).

### Direction
No filtering by `direction` — both debit and credit transactions are listed, consistent with [[SP-026]]/[[SP-027]]'s resolution that a credit transaction (e.g. a refund) is a legitimate, linkable transaction, not a special case to hide or exclude.

### Out of scope (this SP)
- The "Link to receipt" / "Unlink" actions themselves — [[SP-027]]. This SP only renders the entries and their linked/unlinked state; it adds no write actions.
- Any per-statement or per-currency debit/credit total math — the collapsed card shows a transaction count, not a sum.
- Transactions appearing in Statistics (SP-028) — unaffected by this SP, since Statistics reads from `transaction_service` directly rather than from how History renders things.
- History search (`/history?q=`) including transactions — search stays item-based; transactions have no items to search.

## Implementation Notes
Completed 2026-08-23.

- `app/models.py` — `Transaction` gained `statement_id` (constructor, `to_dict()`, `from_dict()`); `from_dict()` defaults a missing value to the transaction's own `id`, so pre-existing records (no migration) still group correctly, each as its own singleton.
- `app/services/statement_service.py` — `process_statement()` generates one `statement_id` (`uuid.uuid4()`) per upload and assigns it to every `Transaction` built from that upload's extracted lines.
- `app/routes.py` — `history()` groups transactions by `statement_id` into one entry per statement (sorted transactions, representative date = most recent, date span = earliest–latest), unioned with receipts into the existing per-month structure. `upload_statement()` now redirects to `/history` on success (was redirecting back to the upload form) — matches receipt upload's existing behavior.
- `templates/history.html` — statement entries render as `<details class="receipt-card">`, reusing the receipt card's classes throughout: icon/label by `source` (🏦 Bank Statement / 💳 Card Statement), date span in the header, transaction count in the total slot, and each transaction listed inside as an item row (date, category, direction badge, amount, linked badge).
- `static/css/style.css` — added `.item-date`, `.transaction-direction` (+`-debit`/`-credit` variants), `.linked-badge`.
- Went through two implementation passes: the first rendered each transaction as its own flat card; user feedback (it should mirror a receipt — one card per upload, itemized inside) drove the `statement_id`-based rework described above. A separate follow-up fix folded in after that: pre-existing local test data predated `statement_id` entirely, so `data/transactions.json` was cleared (backed up first) to let fresh uploads exercise real grouping.
- Tests: `tests/test_routes.py` — `seed_transaction()` helper added (with `statement_id` param), `TestHistoryTransactions` (15 tests: entry display, direction, category, icon-by-source, linked badge, no-dedup, month interleaving/grouping, empty-state, ownership, search-unaffected, multi-transaction grouping, multiple separate statement cards, date-range display, legacy no-`statement_id` records), plus `test_upload_statement_success_redirects_to_history`. Full suite: 365 passed.
