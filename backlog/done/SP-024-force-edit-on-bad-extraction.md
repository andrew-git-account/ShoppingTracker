# SP-024: Force Edit on Bad Extraction

**Priority**: High
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-036

## Description
When extraction produces data that fails validation (e.g. a negative total) or the SP-018 reconciliation retry's second attempt still doesn't reconcile, don't reject the upload or silently save bad data — route into the same not-yet-saved edit flow SP-023 built, pre-filled with whatever was extracted, so the user fixes it themselves before it's saved. Depends on SP-023's draft mechanism and route.

## Acceptance Criteria
- [x] A receipt whose extracted data fails `Receipt.validate()` (e.g. negative total, negative item price) no longer shows an error and discards the upload — it lands on the draft-edit page (SP-023) pre-filled with the extracted (invalid) data, with a flash explaining why review is needed.
- [x] A receipt whose SP-018 reconciliation retry still doesn't reconcile after the one retry no longer saves silently — it also lands on the draft-edit page, pre-filled with the unreconciled data, with a flash explaining why.
- [x] This happens regardless of whether the "Edit before saving" checkbox (SP-023) was checked — it's error recovery, not a preference.
- [x] A receipt that both validates cleanly and reconciles still saves immediately exactly as it does today (when the checkbox isn't checked) — this SP only changes the two failure paths above.
- [x] Saving from the resulting edit page behaves exactly as any other draft save (SP-023) — creates the receipt, cleans up the draft.

## Notes / Context

### `LLMService.extract_receipt_data()` needs to expose reconciliation outcome
Today `_check_reconciliation()` (`app/services/llm_service.py`, added in SP-018) is fully internal — `extract_receipt_data()` retries once on mismatch and returns the final dict regardless of whether that retry actually reconciled. Nothing outside `llm_service.py` can currently tell "did this end up reconciled or not."

Change `extract_receipt_data()` to return `(receipt_data: Dict, reconciled: bool)` instead of just `Dict`. This is a real breaking change to a shared method signature — every existing caller and test needs updating:
- `ReceiptService.process_receipt()`'s call site (`llm_data = self.llm_service.extract_receipt_data(...)`) becomes `llm_data, reconciled = self.llm_service.extract_receipt_data(...)`.
- `tests/test_llm_service.py` — every test that currently asserts `result == payload` on the return value needs updating for the tuple shape (mechanical, same kind of one-time cost SP-005/SP-020 already absorbed for comparable signature changes). Also add/extend coverage for the new `reconciled` value itself (`True` on a clean first attempt, `True` after a successful retry, `False` after a retry that still doesn't reconcile).

### `ReceiptService.process_receipt()` — extend the trigger condition SP-023 introduced
SP-023 introduces a `needs_review`-style branch keyed only on the `edit_before_save` checkbox. This SP extends that same branch to also fire on:
- `not is_valid` (the existing `Receipt.validate()` call, whose result today causes a `raise ValueError(...)` — that raise goes away for this case, replaced by routing to the draft flow)
- `not reconciled` (the new second element `extract_receipt_data()` now returns)

So the combined condition becomes roughly `edit_before_save or not is_valid or not reconciled` — all three reasons funnel into the exact same draft-creation path SP-023 already built; this SP does not add a second mechanism.

`process_receipt()`'s return shape needs to carry *which* reason triggered the draft, since the flash is set by the `/upload` route in `app/routes.py` (per SP-023's existing pattern of flashing right before redirecting to `receipt_draft_edit`), but the reason is only known inside `process_receipt()` - `reconciled` in particular never otherwise leaves `extract_receipt_data()`. The return becomes `(receipt: Optional[Receipt], draft_id: Optional[str], review_reason: Optional[str])`: `review_reason` is `None` on the normal save-immediately path, and one of `'checkbox'` / `'invalid'` / `'unreconciled'` when a draft was created instead. This is a further breaking change to a signature SP-023 just finished stabilizing - same one-time mechanical-update cost as before, now touching `/upload`'s call site and every `process_receipt(...)` call in `tests/test_receipt_service.py` a second time.

### Messaging
The `/upload` route picks the flash text from `review_reason`, distinct from SP-023's neutral "review before saving" framing (still used for `'checkbox'`):
- `'invalid'`: something like "This receipt has a problem ({error_message} from `Receipt.validate()`) — please review and fix it before saving."
- `'unreconciled'`: something like "We couldn't fully verify this receipt's totals — please double-check the items and total before saving."

### What doesn't change
- File-type/upload-level failures (wrong extension, no file selected) are unrelated to extraction quality — they still fail exactly as today, before extraction even runs.
- A validation failure unrelated to what `Receipt.validate()` already checks isn't in scope — this SP doesn't add new validation rules, it changes what happens when the *existing* rules fail.

## Implementation Notes
_Completed 2026-08-23._

- `app/services/llm_service.py` — `extract_receipt_data()` now returns `(receipt_data, reconciled)`. `reconciled` reflects the *final* attempt: `True` if the first attempt already reconciled, `True` if the one retry fixed it, `False` if the retry still didn't reconcile or the retry itself raised (in which case `reconciled` simply keeps the value from the original failed check, since the re-check line is never reached).
- `app/services/receipt_service.py` — `process_receipt()` now always calls `receipt.validate()` (previously skipped entirely when `edit_before_save=True`) and computes `review_reason` in priority order `'invalid'` > `'unreconciled'` > `'checkbox'` > `None`, so an actual data problem is surfaced even if the checkbox was also checked. Returns `(receipt, draft_id, review_reason)` — the old `raise ValueError(...)` on invalid data is gone, replaced by routing into SP-023's existing draft-creation path (no new mechanism).
- `app/routes.py` — `/upload`'s POST handler unpacks the 3-tuple and picks one of three flash messages/categories from `review_reason`: the existing neutral `'checkbox'` info flash (SP-023, unchanged), or a new `alert-error` flash for `'invalid'` ("This receipt has a problem — please review and fix it before saving.") or `'unreconciled'` ("We couldn't fully verify this receipt's totals — please double-check the items and total before saving."). `receipt_draft_edit`/`receipt_draft_discard` (SP-023) are untouched.
- Mechanical migration (both are real breaking signature changes, same one-time cost already absorbed for comparable changes in this project): every `extract_receipt_data()` call site now unpacks `(dict, reconciled)` — `conftest.py`'s `mock_llm_service` fixture, `tests/test_llm_service.py`'s 8 result-capturing tests (each now also asserts the `reconciled` value directly, covering all three documented cases), and every `.return_value = {...}` stub in `tests/test_receipt_service.py`/`tests/test_routes.py` became `({...}, True)`. Every existing `process_receipt(...)` call site now unpacks the added `review_reason` third element.
- No data migration — `review_reason`/`reconciled` are transient, in-memory values; nothing about the stored `receipts.json`/draft-file shapes changed.
- Tests: 12 added (`test_receipt_service.py`'s `TestReceiptServiceForceReview` — reason selection and priority ordering across all combinations of invalid/unreconciled/checkbox, plus a "draft is prefilled with the invalid data" check; `test_routes.py`'s `TestForceEditOnBadExtraction` — end-to-end flash/redirect behavior for both new reasons, checkbox-doesn't-override confirmation, prefilled review page, and saving from a forced-review draft). 313 passed (full suite).
- Verified manually against the real running app (not just mocks): generated a synthetic receipt image with a clearly negative item price/total, uploaded it through the actual UI (real Claude extraction, no LLM mocking) — confirmed it landed on "Review Receipt" with the `alert-error` "This receipt has a problem" flash instead of erroring or silently saving bad data.
