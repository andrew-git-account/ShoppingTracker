# SP-003: Grouping Receipts by Month

**Priority**: Medium 
**Status**: Ready

## Description
Receipts should be grouped by month on the history page. Each group is labelled with the month in `YYYY-MM` format (e.g. `2026-05`). Groups are sorted newest-first (descending by month), and within each group receipts are sorted by purchase date descending.

## Acceptance Criteria
- [ ] Each group has a YYYY-MM header (e.g. 2026-05)
- [ ] When a user opens the History page, all receipts group by months 
- [ ] Groups are sorted by dates descending
- [ ] Receipts inside of a group are sorted by dates of purchase descending

## Notes / Context
Changes in grouping/sorting logic in routes.py, rendering in the template.

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
