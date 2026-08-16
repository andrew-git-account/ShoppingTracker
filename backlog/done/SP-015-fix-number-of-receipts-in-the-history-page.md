# SP-015: Fix Number of Receipts in the History Page

**Priority**: Medium
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-029 (total receipts count excludes deleted receipts)

## Description
The number of receipts displayed in the History page is not correct because deleted receipts are taken into consideration.

## Acceptance Criteria
- [x] `get_receipts_count()` excludes soft-deleted receipts (`is_deleted: true`), matching the filter already used by `get_all_receipts()`
- [x] The "Total receipts: N" count on `/history` equals the number of receipt cards actually displayed on the page
- [x] Deleting a receipt decreases the displayed "Total receipts" count by 1 immediately (no page-reload quirk, no stale count)

## Notes / Context
- Confirmed root cause: `JSONDatabase.get_receipts_count()` in `app/database/json_db.py` returns `len(receipts)` over all stored records, including soft-deleted ones (`is_deleted: true`). `get_all_receipts()` in the same file already correctly filters those out (`if not r.get('is_deleted', False)`), so the "Total receipts: N" shown on `/history` (from `ReceiptService.get_receipts_count()` -> `app.receipt_service.get_receipts_count()` in `app/routes.py`) can be higher than the number of receipt cards actually displayed.
- Likely fix: make `get_receipts_count()` apply the same `is_deleted` filter as `get_all_receipts()`, e.g. `len(self.get_all_receipts())` or the equivalent filtered comprehension.

## Implementation Notes
_Completed 2026-08-17._

- `app/database/json_db.py` — `get_receipts_count()` now filters out soft-deleted receipts (`is_deleted: true`) before counting, matching the filter already applied in `get_all_receipts()`.
- `tests/test_database.py` — added `test_get_receipts_count_excludes_soft_deleted` and `test_get_receipts_count_matches_get_all_receipts_length` to `TestJSONDatabaseSoftDelete`.
- `tests/test_routes.py` — added `test_total_count_matches_displayed_receipt_cards` and `test_delete_receipt_decreases_total_count` to `TestDeleteReceiptRoute`. Also fixed an unrelated pre-existing failure in `test_fallback_to_saved_at_when_no_purchase_date`, which hardcoded the "current month" as a fixed string and broke on the month rollover — now computed dynamically.
- `Specification/BehaviorSpec.md` — added BS-029 covering the "Total receipts" count excluding deleted receipts and updating immediately on delete.
- No migrations or data changes.
- Tests: 4 added, 164 passed (full suite).
