# SP-015: Fix Number of Receipts in the History Page

**Priority**: Medium
**Status**: Ready

## Description
The number of receipts displayed in the History page is not correct because deleted receipts are taken into consideration.

## Acceptance Criteria
- [ ] `get_receipts_count()` excludes soft-deleted receipts (`is_deleted: true`), matching the filter already used by `get_all_receipts()`
- [ ] The "Total receipts: N" count on `/history` equals the number of receipt cards actually displayed on the page
- [ ] Deleting a receipt decreases the displayed "Total receipts" count by 1 immediately (no page-reload quirk, no stale count)

## Notes / Context
- Confirmed root cause: `JSONDatabase.get_receipts_count()` in `app/database/json_db.py` returns `len(receipts)` over all stored records, including soft-deleted ones (`is_deleted: true`). `get_all_receipts()` in the same file already correctly filters those out (`if not r.get('is_deleted', False)`), so the "Total receipts: N" shown on `/history` (from `ReceiptService.get_receipts_count()` -> `app.receipt_service.get_receipts_count()` in `app/routes.py`) can be higher than the number of receipt cards actually displayed.
- Likely fix: make `get_receipts_count()` apply the same `is_deleted` filter as `get_all_receipts()`, e.g. `len(self.get_all_receipts())` or the equivalent filtered comprehension.

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
