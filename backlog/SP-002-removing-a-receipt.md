# SP-002: Removing a Receipt

**Priority**: Medium
**Status**: Ready

## Description
Possibility to remove already uploaded receipt from the list. The user should be able to delete a receipt they no longer want, removing it from the user view.

Proposed solution: 
- every receipt has a button X on the right to remove it 
- a confirmation should be shown to a user 
- receipt is not completely removed from the database but marked as removed 

## Acceptance Criteria
- [ ] An X button is display on the right on every uploaded receipt 
- [ ] When X button is clicked a user sees confirmation of deletion 
- [ ] When X button is clicked and deletion is confirmed, a receipt is removed from the list of receipts in UI 
- [ ] When X button is clicked and deletion is confirmed, a receipt is marked as removed in the DB  

## Notes / Context
Changes in UI, database and backend 

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
