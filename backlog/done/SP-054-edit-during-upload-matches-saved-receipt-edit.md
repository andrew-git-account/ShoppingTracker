# SP-054: Edit During Upload Matches Editing a Saved Receipt

**Priority**: Medium
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-035
**Deployed**: c13c8f8 (2026-10-15)

## Description
When a receipt is edited during upload (the "Edit before saving" review page, or the review page shown after a bad extraction), every field, rule and behaviour of the form must be the same as when editing an already saved receipt. The only intended differences are the buttons: Discard and Save Receipt when reviewing an upload, Cancel and Save Changes when editing a saved receipt. This keeps the two flows from drifting apart as the edit form gets new features (as happened with SP-052).

## Acceptance Criteria
- [x] Both pages render the same item grid: the same header row, columns in the same order, the same field types and attributes, the same unit and category dropdowns, and the same live sync script. Verified by a test that renders both pages for equivalent data, removes the `<h2>` title, the form `action` attribute and the `.form-actions` block from each, and expects the remaining page HTML to be identical.
- [x] Both pages accept and reject the same input: a shared test table of valid and invalid submissions (empty item list, negative price, amount of 0, bad unit, non-numeric total, negative total, removed rows) runs against both routes and expects the same outcome and the same error message on each.
- [x] A valid submission saves the same item values on both flows (name, category, amount, unit, total, quantity 1), the same receipt currency and total, and keeps the extracted store name, date, tax and discount.
- [x] Both flows run the automatic statement-transaction matching after saving.
- [x] After an invalid submission, both pages re-render with the user's edits kept and a flash error.
- [x] The upload review page keeps its Discard and Save Receipt buttons, and the saved-receipt page keeps Cancel and Save Changes; the page titles stay "Review Receipt" and "Edit Receipt".
- [x] The Implementation Notes list every difference found between the two flows beyond the title and buttons (or state that none was found). Each one is either fixed so both behave like the saved-receipt edit page, with a test, or explicitly accepted by the requester.
- [x] `Specification/BehaviorSpec.md` BS-035 states that the review page is the same form, with the same fields and rules, as editing a saved receipt.

## Notes / Context
- Today both routes already share `templates/edit_receipt.html`, `_parse_edit_form` and `_render_edit_form` in `app/routes.py`; they differ only in `is_draft`/`draft_id`, which switches the title and buttons, and in how the result is saved (`save_draft` vs `update_receipt`). So this story may find that the code is already equivalent and mostly adds the tests that keep it that way.
- No specific difference between the two flows is known today; the story exists to guarantee parity and to keep the flows from drifting apart.
- The page title is left as is ("Review Receipt" for uploads, "Edit Receipt" for saved receipts); changing it is out of scope unless asked.
- Related: SP-022 (edit receipt), SP-023 (edit before saving), SP-024/BS-036 (forced review after bad extraction), SP-052 (item fields).

## Implementation Notes
Completed 2026-10-15.

- No application code changed: the upload review page and the saved-receipt edit page already share `templates/edit_receipt.html`, `_parse_edit_form` and `_render_edit_form`, and both run the statement matching after saving. The work was proving this and locking it in.
- Differences found beyond the page title and the buttons (all accepted as legitimate, since the first save differs from an update): the form action URL; the success message ("Receipt saved! Found N items totaling ..." vs "Receipt updated."); the not-found message ("Draft not found." vs "Receipt not found."). No other difference was found.
- `tests/test_routes.py`: new class `TestEditParityBetweenDraftAndSavedReceipt` (14 tests): identical `<main>` markup apart from title/action/buttons; titles and buttons stay different; nine valid/invalid submissions give the same outcome and error on both routes with edits kept; same saved values (including store, date, tax, discount) on both flows; both call the matcher after saving; an invalid submission saves nothing in either flow.
- `Specification/BehaviorSpec.md`: BS-035 states the review page is the same form as editing a saved receipt.
- Tests: 14 added. Full suite: 727 passed.
