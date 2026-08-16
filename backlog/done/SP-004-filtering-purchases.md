# SP-004: Filtering Purchases

**Priority**: High
**Status**: Done
**Fulfils**: Specification/BehaviorSpec.md#BS-023, #BS-024, #BS-025
**Deployed**: cb773f5 (2026-08-16)

## Description
As a user I want to search for a specific item across all my receipts so that I can compare prices for similar articles across different shops and purchases.

Add a search box to the Receipt History page. The user enters a search term (minimum 3 characters) and either presses Enter or clicks a "Search" button. The application then displays every line item, across all uploaded receipts, whose name matches the search term — not receipt cards, individual matching items. Since the results are a cross-receipt list of items rather than whole receipts, no subtotal or total is shown for the result set.

## Acceptance Criteria
- [x] A search input and "Search" button are present on the History page
- [x] Submitting a search term via the Search button or pressing Enter runs the search
- [x] Search terms shorter than 3 characters are rejected (no search performed; user is told the minimum length)
- [x] Matching results show every item, from every receipt, whose name contains the search term (case-insensitive)
- [x] Each result shows enough context to compare prices: item name, price, store name, and purchase date (or receipt date)
- [x] No subtotal or total amount is displayed for the search results
- [x] A search with no matches shows a clear "no results" state instead of an empty page
- [x] The normal (non-search) History view is unaffected — search is a separate mode/view, not a permanent filter

## Notes / Context
- Core use case is price comparison: the same item bought at different stores/times should be easy to spot side-by-side once matched.
- Possible implementation: a GET query param (e.g. `/history?q=milk`) so results are a real page, no JavaScript needed (consistent with the rest of the app); a minimum-length check both client-side (basic HTML `minlength` / `pattern`) and server-side (authoritative).
- Reuses receipt/item data already loaded via `ReceiptService.get_all_receipts()` — no new storage needed.

## Implementation Notes
**Completed**: 2026-08-05

Four files changed:

- **`app/routes.py`** — Extended `history()` (no new route) to read `?q=` from the query
  string. Empty/missing `q` → today's grouped-by-month view, unchanged. 1-2 character
  `q` → flash a "must be at least 3 characters" error and fall back to the normal view,
  keeping the raw typed value so the search box doesn't clear itself. `q` ≥3 characters →
  search mode: scans every receipt's items for a case-insensitive substring match on
  `item.name`, builds a flat list (name, price, quantity, currency, store, date), and
  sorts by item name then price so identical items land next to each other for easy
  price comparison.

- **`templates/history.html`** — Added a GET `<form>` (input `name="q"` + Search button,
  no JavaScript — Enter submits natively) under the page heading. Added a search-results
  branch showing the flat item list (or a "No matches found" empty state) instead of the
  normal grouped/month view when `search_mode` is true; the normal view's markup is
  otherwise untouched.

- **`static/css/style.css`** — Added `.search-form`/`.search-input`/`.search-clear` and a
  `.search-results`/`.search-result-row` grid layout. Went through two rounds of fixing a
  real alignment bug found via user testing: `display: flex` with `flex: 2/1/1` ratios
  let each row's content width shift the columns independently; switching to `display:
  grid` per row still let the `auto`-sized price column vary the `fr` track widths
  row-to-row (confirmed via `getBoundingClientRect()` — store/date columns were off by
  ~5-8px between rows). Fixed by giving the price column a fixed `6.5rem` width instead
  of `auto`, verified afterward with identical `left` offsets across all rows.

- **`tests/test_routes.py`** — Added `TestSearchRoute` with 10 tests covering all 8
  acceptance criteria plus two supporting checks (results sorted by name/price, and the
  normal History view unaffected by the new feature).

**Tests**: 10 new tests added, all passing. Full suite: 116 passed, 1 pre-existing
unrelated failure (`test_fallback_to_saved_at_when_no_purchase_date`, a stale hardcoded
month assumption, already flagged separately).

**Data note**: manual verification scripts initially wrote 9 test receipts into the real
`data/receipts.json` due to a `DATA_FOLDER` isolation gap in ad hoc scripts
(`load_dotenv(override=True)` in `app/main.py` overrides any env var set before import).
Those 9 entries (`user_email: "test@example.com"`) were identified and removed; the 16
genuine receipts were confirmed intact. No production code change was needed — the
existing `tests/conftest.py` fixture pattern (manual app construction, no
`load_dotenv`) was already safe and unaffected.

No data migrations or new dependencies.
