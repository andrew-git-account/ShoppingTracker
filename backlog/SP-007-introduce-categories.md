# SP-007: Introduce Categories

**Priority**: Medium
**Status**: Open

## Description
Allow users to assign categories to purchases (e.g. "Food", "Household", "Electronics"). This enables better organization and future filtering/analytics of spending by category.

## Acceptance Criteria
- [ ] A predefined list of categories is available in the system
- [ ] User can assign a category when uploading a receipt (or editing after the fact)
- [ ] Category is stored with the receipt in the database
- [ ] History page displays the category for each receipt

## Notes / Context
Consider starting with a fixed list of categories (no user-defined categories yet) to keep V1 simple. Categories could be shown as a dropdown on the upload form. The LLM could potentially suggest a category based on receipt contents.

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
