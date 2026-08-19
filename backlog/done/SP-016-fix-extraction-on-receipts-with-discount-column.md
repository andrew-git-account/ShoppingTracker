# SP-016: Fix Item Extraction on Receipts with a Per-Item Discount Column

**Priority**: High
**Status**: Done
**Fulfils**: Specification/BehaviorSpec.md#BS-028
**Deployed**: b6f3230 (2026-08-19)

## Description
Receipts that include a per-item "savings" / discount column (e.g. Migros' "Gespart" column, shown alongside `Menge`/`Preis`/`Total`) are extracted incorrectly by the LLM: prices get shifted onto the wrong item, quantities are inflated, and duplicate item lines are fabricated. Improve the extraction prompt so it correctly handles this receipt layout.

## Acceptance Criteria
- [x] When a receipt includes a per-item discount/savings column, each item's extracted price reflects the actual amount charged for *that* item after its own discount — not shifted onto a neighboring item
- [x] No duplicate item lines are fabricated because a discount column is present
- [x] A rightmost VAT-rate/tax-category code column (or similar non-quantity trailing column) is never interpreted as item quantity — quantity comes only from the actual `Menge`/quantity column
- [x] Re-processing the documented Migros repro receipt extracts all 7 items correctly, confirmed via a real re-upload through the app after the fix and restart
- [x] For that same repro receipt, the extracted subtotal (sum of item price × quantity) reconciles with `total_amount` within tax + discount tolerance (no ~16 CHF unexplained gap like the original bad extraction)

## Notes / Context
**Confirmed real-world repro case** (Migros receipt, `Zürich Albisriederplatz`, 2026-08-03, uploaded 2026-08-16 — see conversation history for the photo). Ground truth from the receipt image vs. what was actually extracted and saved:

| Item | Real Menge | Real Preis/Total | Extracted (wrong) |
|---|---|---|---|
| Poulet Oberschenkel | 1 | 6.50 → 3.50 (discounted) | quantity **2**, price 3.50 |
| Schnitzel Caprese | 1 | 5.95 | price shifted to **6.50** |
| Eier Freiland | 1 | 3.20 | price shifted to **5.95**, quantity **2** |
| Knoblauch frisch | 1 | 1.95 | **duplicated**: one line at 3.20 (really Eier Freiland's price), one at 1.95 |

Two distinct root causes identified by comparing the extraction against the receipt image:
1. **The `Gespart` (savings) column threw off row/column alignment.** This receipt has a column layout (`Menge | Preis | Gespart | Total | #`) most other receipts don't have. Once the model hit the first discounted row (Poulet Oberschenkel), prices for several subsequent rows appear to have shifted by one row, and a phantom duplicate item was fabricated.
2. **The rightmost `#` column was misread as a quantity.** It's actually a Swiss VAT-rate code (the receipt footer has a rate table: code `1` = reduced/food rate, code `2` = standard/non-food rate — e.g. the two MCLEAN cleaning products both got code `2`). Every real `Menge` value on this receipt is `1`; the two "quantity 2" items in the bad extraction correspond exactly to rows where the VAT-code column happened to show `2`.
3. **Symptom that should have been an internal red flag**: the saved receipt has `subtotal: 37.60` vs `total_amount: 21.65` — a ~16 CHF gap far larger than `tax_amount` (0.77) or `discount_amount` (0.0) could explain. This kind of large subtotal/total mismatch is itself a signal something went wrong with the extraction and could potentially be used as a validation check independent of this specific fix.

Possible implementation: update `_create_extraction_prompt()` in `app/services/llm_service.py` to explicitly describe discount/savings columns (don't let a per-item discount shift which price/quantity belongs to which item name; the final per-item price should reflect the actual amount charged after any item-level discount) and to explicitly warn that a rightmost code/tax-category column is not a quantity. Consider also surfacing the existing subtotal-vs-total mismatch (point 3 above) as a diagnostic signal, e.g. a warning log when they diverge by more than tax+discount would explain, to make future misreads easier to notice.

Out of scope for this SP: correcting the specific bad receipt already stored in production — that's a separate, explicit action to take once this fix is verified.

## Implementation Notes
**Completed**: 2026-08-16

**`app/services/llm_service.py`** — `_create_extraction_prompt()` restructured
into an explicit two-step process, iterated three times against the real repro
image (`20260816_221453.jpg`) until verified correct:

1. **Round 1** (bulleted "watch out for" guidance added to the existing
   single-pass prompt): no effect at all — identical wrong output, byte-for-byte,
   confirming this needed a structural change, not just added caveats.
2. **Round 2** (restructured into "Step 1: transcribe every row exactly as
   printed" followed by "Step 2: convert the transcription to JSON," with
   `_parse_response()`'s existing ` ```json ` fence extraction handling the
   now-present prose before the JSON block with no code change needed): fixed
   the duplicate-item fabrication and the VAT-code-as-quantity misread
   completely, but Poulet Oberschenkel still grabbed the pre-discount "Preis"
   value instead of the post-discount "Total".
3. **Round 3** (added an explicit rule: when a row has both an original price
   and a line total, `price` always comes from the final "Total" column, never
   an earlier unit-price column): fixed the discount-column price selection;
   subtotal reconciled exactly with total (21.65 = 21.65).
   - A residual 3-item price rotation (Schnitzel Caprese / Emilio Grana Padano /
     MCLEANB Schwämme swapped among each other's real prices) persisted through
     round 3. Traced to the **Step 1 transcription itself**, not the JSON
     conversion — a genuine visual misread, not a reasoning error. Tested
     whether JPEG compression (quality 85, ~1.9MB) was contributing by
     re-running at quality 95 (~4.1MB, near-lossless) — identical wrong result,
     ruling that out. This looked like it might be a hard per-image limitation.
   - On the actual re-upload through the app after the round-3 fix (following a
     local dev server restart — Flask's dev server here runs without
     debug/auto-reload, so it was still serving the round-1 prompt from memory
     until restarted), the account holder confirmed the receipt now extracts
     correctly, including the previously-flagged rotation. The Claude API isn't
     guaranteed bit-exact deterministic across separate calls even at
     `temperature=0.0`, which likely explains the difference from the isolated
     test script runs.

**No other files changed** — `models.py`'s amount/unit handling (SP-013) and
`_parse_response()` were unaffected; this was purely a prompt-engineering fix.

**Tests**: none added. This is a vision-model prompt change; the existing test
suite mocks `LLMService` entirely (`tests/conftest.py`), so there's no
meaningful way to unit-test prompt wording against real model behavior.
Verification was manual: a direct `LLMService.extract_receipt_data()` script
against the real repro image (three iterations, shown above) plus a final
real end-to-end upload through the running app, confirmed by the account holder.

Out of scope, not done here: the original bad receipt already stored in
production data was not corrected — that remains a separate, explicit action.
