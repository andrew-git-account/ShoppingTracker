# SP-012: Add Shopping Statistics

**Priority**: High
**Status**: Done
**Fulfils**: Specification/BehaviorSpec.md#BS-020, #BS-021, #BS-022
**Deployed**: cb773f5 (2026-08-16)

## Description
As a user I want to see monthly statistics of my shopping so that I can understand where my money is going.

Add a new **Statistics** tab to the application. The page shows a month-selection list, ordered descending by the most recent month found in the receipts. When the user selects a month, the page displays the list of categories for that month, each with the amount of money spent on that category and the percentage of the month's total spend it represents.

## Acceptance Criteria
- [x] A new "Statistics" tab/link is available in the site navigation
- [x] The Statistics page shows a list/dropdown of months, derived from receipt dates, ordered from most recent to oldest
- [x] Selecting a month displays each category present in that month's receipts, along with the total amount spent on that category
- [x] Each category row also shows the percentage of that month's total spend it represents
- [x] Percentages across all categories for the selected month sum to ~100%
- [x] A month with no receipts (or no categorized items) is handled gracefully (e.g. not shown, or shown with an empty state)

## Notes / Context
- Builds on the existing category assignment work (SP-007) and monthly grouping work (SP-003) already used on the History page.
- Possible implementation: reuse the month-grouping logic from the History page to populate the month list; aggregate item totals by category for the selected month.

## Implementation Notes
**Completed**: 2026-08-05

Six files changed:

- **`app/routes.py`** — Added a new `/statistics` route (`statistics()`). Extracted the
  existing month-key logic out of `history()` into a shared module-level `_month_key()`
  helper (used by both routes, no behavior change to History). The route builds a list of
  months (newest-first) from all receipts, defaults to the most recent month (or falls
  back to it if an unknown `?month=` is requested), then aggregates item totals **grouped
  by currency first, then by category** — each currency gets its own subtotal, and each
  category's percentage is relative to that currency's subtotal, not a cross-currency
  total. This avoids summing incompatible currencies together (confirmed against real
  data, which has receipts in CHF, CRC, and USD in the same month).

- **`templates/statistics.html`** (new) — Renders a month-selector link list (no
  JavaScript, consistent with the rest of the app) and, for the selected month, one block
  per currency showing the currency code, its subtotal, and a list of categories with
  amount, percentage, and a CSS proportion bar. Shows an empty state when there are no
  receipts at all.

- **`templates/base.html`** — Added a "Statistics" nav tab between "History" and "Log out".

- **`static/css/style.css`** — Added styling for the statistics page: two-column
  desktop layout (month sidebar + stats panel), stacking to a horizontal wrapped list on
  mobile/tablet (≤768px, reusing the existing breakpoint), currency-group headers, and
  category rows with proportion bars.

- **`tests/test_routes.py`** — Added `seed_receipt_with_items()` helper (multi-item,
  multi-currency receipts with exact known amounts) and a new `TestStatisticsRoute` class
  with 11 tests covering all six acceptance criteria plus the currency-grouping behavior
  (`test_statistics_groups_by_currency_independently`, seeding a CHF and a USD receipt in
  the same month and asserting each shows 100% of its own currency rather than a mixed
  30%/70% split).

- **`CLAUDE.md`** — Bumped "Last SP number" from 011 to 012.

**Tests**: 11 new tests added, all passing. Full suite: 106 passed, 1 pre-existing
unrelated failure (`test_fallback_to_saved_at_when_no_purchase_date`, a stale hardcoded
month assumption unaffected by this change — already flagged separately for a fix).

No data migrations or new dependencies.
