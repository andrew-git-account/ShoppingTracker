# SP-002: Removing a Receipt

**Priority**: Medium
**Status**: Done

## Description
Possibility to remove already uploaded receipt from the list. The user should be able to delete a receipt they no longer want, removing it from the user view.

Proposed solution: 
- every receipt has a button X on the right to remove it 
- a confirmation should be shown to a user 
- receipt is not completely removed from the database but marked as removed 

## Acceptance Criteria
- [x] An X button is display on the right on every uploaded receipt 
- [x] When X button is clicked a user sees confirmation of deletion 
- [x] When X button is clicked and deletion is confirmed, a receipt is removed from the list of receipts in UI 
- [x] When X button is clicked and deletion is confirmed, a receipt is marked as removed in the DB  

## Notes / Context
Changes in UI, database and backend 

## Implementation Notes
Completed: 2026-06-17

- `app/database/json_db.py` — Added `soft_delete_receipt()` method; updated `get_all_receipts()` to filter out entries where `is_deleted: true`
- `app/services/receipt_service.py` — Added `soft_delete_receipt()` delegating to the database layer
- `app/routes.py` — Added POST `/delete-receipt/<receipt_id>` route with flash messages and redirect to history
- `templates/history.html` — Added delete form with `×` button inside each receipt summary; native browser confirm dialog via `onsubmit`
- `static/css/style.css` — Added `.btn-delete` and `.delete-form` styles; button turns red on hover

Tests: 12 new tests added across `test_database.py`, `test_receipt_service.py`, and `test_routes.py`. Final suite: 68 passed.
