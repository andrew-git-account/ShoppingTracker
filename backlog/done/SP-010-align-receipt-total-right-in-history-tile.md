# SP-010: Align Receipt Total Right in History Tile

**Priority**: Low
**Status**: Done
**Fulfils**: BS-006 (visual refinement — total amount presentation in history tile)

## Description
In the receipt history list, the total amount (e.g. "CHF 17.90") should be right-aligned within the tile so it visually anchors to the right edge, making amounts easy to scan and compare across receipts.

## Acceptance Criteria
- [x] The total amount in each collapsed receipt tile is visually aligned to the right edge of the tile
- [x] The store name and date remain left-aligned; the amount does not overlap them on any common screen width
- [x] The layout holds correctly on mobile (narrow screens) — amount either stays right-aligned or wraps cleanly below the store name without overlapping

## Notes / Context
- See screenshot: amounts like "CHF 17.90" and "CRC 46900.00" are currently left of the delete button but not pushed to the right edge
- The fix is CSS-only — the HTML structure of the history tile likely already has the amount in a separate element; applying `margin-left: auto` or `text-align: right` to it should be sufficient
- Check `templates/history.html` for the tile markup and `static/css/style.css` for existing receipt card styles

## Implementation Notes
**Completed:** 2026-06-26

**Modified files:**
- `static/css/style.css` — added `flex: 1` to `.receipt-header` so it absorbs all available space, pushing `.receipt-total` and the delete button to the right edge; added `margin-right: var(--spacing-md)` to `.receipt-total` for spacing between the amount and the × button
- `tests/conftest.py` — added `logged_in_client` fixture (authenticated test client) needed for route tests after SP-008 auth guard was added
- `tests/test_routes.py` — updated all route tests to use `logged_in_client` instead of `client` (they were broken by the SP-008 auth guard)

**No new dependencies. No data changes.**

**Tests:** 0 new tests added (CSS-only change); 83 total passed (fixed pre-existing test_routes.py breakage caused by SP-008 auth guard)
