# SP-018: Reconcile Item Totals with Retry

**Priority**: Medium
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-030

## Description
Add a reconciliation check with a single bounded retry: after extracting receipt data, if the sum of item prices doesn't reconcile with the receipt's `total_amount` (checking both VAT-inclusive — `sum(items) ≈ total` — and VAT-exclusive — `sum(items) + tax - discount ≈ total` — within a small tolerance), re-call the LLM exactly once, passing back the specific discrepancy so it can re-examine misattributed prices/quantities on the receipt image. If the retry still doesn't reconcile, accept its result as-is (no further retries, no error surfaced to the user).

## Acceptance Criteria
- [x] After extraction, the app checks whether the receipt reconciles: `sum(items)` is within tolerance of `total_amount` (VAT-inclusive case) OR `sum(items) + tax_amount - discount_amount` is within tolerance of `total_amount` (VAT-exclusive case). Reconciled if either check passes.
- [x] If neither check passes, the LLM is called a second time on the same image, with an added message stating the specific discrepancy (which formula was used, the expected total, the computed sum, and the gap) and asking it to re-examine its transcription for a misattributed price/quantity line.
- [x] The retry happens **at most once** per upload — a still-unreconciled second attempt is accepted and saved without a third call.
- [x] No error or warning is shown to the user when the retry's result still doesn't reconcile — the receipt is saved normally either way.
- [x] A receipt that reconciles on the first attempt does not trigger a second LLM call (no wasted API cost/latency on already-correct extractions).

## Notes / Context
- **Root cause example** (what motivated this SP): a real upload, `20260819_014216.jpg` (Shell Rautistrasse / Shopolino GmbH receipt), was mis-extracted. The receipt has two items with an indented quantity/unit-price sub-line beneath them (e.g. `2 St  1,60 CHF/St` under "MMSCThonsMex. 160g", meaning that item is 2 × 1.60 = the 3.20 CHF already printed on its own line). The LLM attributed the sub-line to the **next** item in the list ("TGFMLaugbrGruy190g") instead of the one above it, recording that item as price 1.60 × qty 2 = 3.20 CHF when the receipt actually shows it as a single item worth 6.90 CHF — a 3.70 CHF understatement. Nothing in the code currently checks that item totals reconcile with the receipt's own total, so this saved silently.
- This is the same *category* of bug as SP-016 (per-item discount columns confusing row alignment), triggered by a different receipt layout (a quantity sub-line instead of a discount column). SP-018 doesn't try to fix prompt-level row misattribution directly — it adds a safety net that catches it after the fact and gives the LLM one more chance with concrete feedback.
- **Why check both formulas**: item prices are VAT-inclusive on some receipts (e.g. Swiss/EU retail, where `sum(items)` already equals `total_amount` and tax is purely informational) and VAT-exclusive on others (e.g. US sales tax added at checkout, where `sum(items) + tax - discount == total_amount`). A single rigid formula would false-positive on legitimate receipts using the other convention.
- Relevant existing code:
  - `app/services/llm_service.py` — `LLMService.extract_receipt_data()` builds the prompt and calls the Claude API once; `_create_extraction_prompt()` already asks the LLM to self-check reconciliation, but there's no code-level enforcement.
  - `app/models.py` — `Receipt.get_subtotal()` computes `sum(item.price * item.quantity for item in items)`; `Receipt._calculate_total()` implements the VAT-exclusive formula only.
  - `app/services/receipt_service.py` — `ReceiptService.process_receipt()` orchestrates the single call to `llm_service.extract_receipt_data()` today.
- Tolerance should account for floating-point/rounding noise (e.g. a cent or two), not be so tight that harmless rounding differences trigger a retry.
- Tests must mock the Anthropic client for both the first call and the (conditional) retry call — no real API calls.

## Implementation Notes
_Completed 2026-08-19._

- `app/services/llm_service.py`:
  - `extract_receipt_data()` refactored to make a first extraction attempt, then check reconciliation, then (conditionally) retry once. Image encoding happens once and is reused across both attempts.
  - New `_attempt_extraction(image_data, media_type, retry_mismatch=None)` — extracted from the old inline API-call/parse logic; builds the prompt and calls Claude, unchanged error handling.
  - New `_check_reconciliation(receipt_data)` — checks `sum(items)` against `total_amount` under both the VAT-inclusive and VAT-exclusive (`+ tax - discount`) formulas, tolerance `_RECONCILIATION_TOLERANCE = 0.02`. Reconciled if either formula's gap is within tolerance; otherwise returns the closer formula's expected/computed/gap for the retry prompt.
  - New `_safe_float()` static helper for defensive numeric coercion of LLM-extracted values.
  - `_create_extraction_prompt()` gained an optional `retry_mismatch` param that prepends a note stating the specific discrepancy and pointing at the likely cause (misattributed price/quantity row).
  - If the retry API call itself fails, the exception is caught and the first attempt's (unreconciled) result is kept rather than losing the upload.
  - `extract_receipt_data()`'s public signature is unchanged, so `receipt_service.py` and all its callers/tests needed no changes.
- `tests/test_llm_service.py` (new file) — 7 tests mocking the Anthropic client boundary directly (a new pattern for this codebase, since existing tests mock `LLMService` wholesale): reconciliation via each formula, tolerance absorbing rounding noise, one retry on mismatch (using a scenario mirroring the real bug), the retry prompt containing the discrepancy figures, the retry cap at one call, and resilience when the retry call itself fails.
- `Specification/BehaviorSpec.md` — added BS-030 (Extraction Self-Corrects on a Mismatched Total).
- No migrations or data changes.
- Tests: 7 added, 173 passed (full suite).
