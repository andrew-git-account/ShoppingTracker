# SP-003: Grouping Receipts by Month

**Priority**: Medium 
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-019
**Deployed**: cb773f5 (2026-08-16)

## Description
Receipts should be grouped by month on the history page. Each group is labelled with the month in `YYYY-MM` format (e.g. `2026-05`). Groups are sorted newest-first (descending by month), and within each group receipts are sorted by purchase date descending.

## Acceptance Criteria
- [x] Each group has a YYYY-MM header (e.g. 2026-05)
- [x] When a user opens the History page, all receipts group by months 
- [x] Groups are sorted by dates descending
- [x] Receipts inside of a group are sorted by dates of purchase descending

## Notes / Context
Changes in grouping/sorting logic in routes.py, rendering in the template.

## Implementation Notes
**Completed**: 2026-07-10

**Changes made**:
- `app/routes.py`: Added grouping logic to `history()` route using `defaultdict` to group receipts by YYYY-MM, then sorting groups descending and receipts within each group descending by date
- `templates/history.html`: Wrapped receipt list with month group structure (`<div class="month-group">`) and added month headers (`<h2 class="month-header">`)
- `static/css/style.css`: Added `.month-group` and `.month-header` styles for visual separation and formatting of month sections
- `tests/test_routes.py`: Enhanced `seed_receipt()` helper to accept `purchase_date` and `store_name` parameters; added `TestHistoryRouteGrouping` class with 6 comprehensive tests

**Tests**: Added 6 new tests, all passing (83 total tests pass)
