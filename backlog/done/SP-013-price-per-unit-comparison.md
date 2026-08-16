# SP-013: Price-Per-Unit for Comparison

**Priority**: High
**Status**: Done
**Fulfils**: Specification/BehaviorSpec.md#BS-026, #BS-027 (also corrects the sort-order description in #BS-023)
**Deployed**: cb773f5 (2026-08-16)

## Description
As a user I want to see a price-per-unit for each item (e.g. CHF/kg for loose produce, CHF/piece for packaged goods) so that I can compare prices for the same kind of product across different receipts — the original motivating case being loose items like tomatoes, where today the receipt only shows a total price for whatever weight was bought.

Add an `amount` (numeric, may be fractional) and `unit` ("piece" or "kg") to each extracted receipt item, alongside the existing `price`/`quantity`/`category` fields. Derive a price-per-unit from the item's existing line total, and display it on the History page.

## Acceptance Criteria
- [x] The LLM extraction step captures `amount` and `unit` for each item, in addition to the existing `price`/`quantity`/`category` fields
- [x] If no amount is printed/found for an item, it defaults to `amount = 1`, `unit = "piece"`
- [x] If an amount is present, is not a whole number, and no unit is identifiable, `unit` defaults to `"kg"`
- [x] Grams are normalized to kilograms (kg is the representative unit for weight); pieces are not converted (piece is already the representative unit)
- [x] Item names are never parsed for embedded package sizes (e.g. "Steinofenbrot 500G" is always `amount=1`, `unit="piece"`, regardless of the "500G" in the name) — confirmed out of scope with the account holder
- [x] The History page shows a "price per unit" value for each item (e.g. "CHF 19.49/kg" or "CHF 2.20/piece")
- [x] The SP-004 search-results view also shows price-per-unit for each result, and results are sorted by price-per-unit (not raw line price) so the cheapest match for a given item name comes first — this is the actual comparison use case search exists for
- [x] Receipts saved before this change (no stored amount/unit) still display correctly — fall back to the same piece/1 default so old data doesn't break or show a blank column

## Notes / Context
- **Real-world grounding** (two photos of the same Coop purchase, see conversation history): a weighed item ("Sardinenfilet Butterfly") showed `Menge = 0.743`/`0.744` on both the till receipt and the in-store scale label, but the till receipt's own "Preis" column just repeated the line `Total` (14.50) — **not** a true per-kg rate. The real per-kg price (19.50 CHF/kg) only appears on the separate scale label, which isn't what gets photographed/uploaded to the app.
- **Conclusion driving the design**: never trust a printed "unit price" for weighed items — only the printed amount (`Menge`) and the line total are reliably present on a till receipt, so `price_per_unit` must always be *derived* (`total ÷ amount`), never OCR'd directly as its own field.
- Because of this, **no changes are needed to the existing `price`/`quantity`/subtotal computation**. `item.price * item.quantity` already produces the correct line total today (quantity is currently floored to 1 for fractional amounts via `max(1, int(float(raw_qty)))` in `models.py`, and for weighed items the LLM already effectively reads the line total into `price`). `amount` and `unit` are purely new, additive fields — they don't replace `quantity` and don't change subtotal/total math anywhere.
- `price_per_unit = (item.price * item.quantity) / normalized_amount`, computed on read (route or a model helper), not stored.
- Possible implementation: extend the LLM prompt in `app/services/llm_service.py` (`_create_extraction_prompt`) with `amount`/`unit` fields and the fallback rules described above; extend `ReceiptItem`/`Receipt.from_llm_response` in `app/models.py` to store them (with safe defaults for older JSON records missing these keys); add the price-per-unit display to `templates/history.html`'s item rows.
- Not in scope: parsing product names for package sizes.
- **Scope correction** (added after initial implementation): the SP-004 search-results view *is* in scope after all — it's the primary place a user actually compares the same item across receipts, so showing price-per-unit only on History would defeat the point. `app/routes.py`'s search route now includes `price_per_unit`/`unit` in each result dict and sorts by `(name, price_per_unit)` instead of `(name, price)`, so identical items are grouped with the cheapest first.

## Implementation Notes
**Completed**: 2026-08-16

Six files changed:

- **`app/models.py`** — Added a module-level `_resolve_amount_unit(raw_amount, raw_unit)`
  helper implementing the fallback/normalization rules (no amount → 1 piece;
  recognized unit synonyms normalized, grams converted to kg; unrecognized/missing
  unit inferred from whether the amount is a whole number). Added `amount`/`unit`
  parameters to `ReceiptItem.__init__` (defaults `1.0`/`"piece"`), included them in
  `to_dict()`/`from_dict()` (with the same defaults in `from_dict` so pre-existing
  stored receipts load unchanged), and added a `price_per_unit` property —
  `(price * quantity) / amount`, guarded against a zero amount. `Receipt.from_llm_response()`
  now calls the new helper and passes the result into each `ReceiptItem`.

- **`app/services/llm_service.py`** — Extended `_create_extraction_prompt()` to ask
  for `amount`/`unit` per item (explicitly instructing the model never to infer
  them from the item name, only from a printed purchased quantity/weight), added
  the same fallback rules to the prompt's guidelines section, and added both keys
  to the JSON example.

- **`app/routes.py`** — `history()`'s search branch now includes `price_per_unit`/
  `unit` in each search-result dict and sorts by `(name, price_per_unit)` instead
  of `(name, price)` — added mid-implementation once it became clear that showing
  price-per-unit only on History (not in search results, where users actually
  compare the same item across stores) would defeat the point.

- **`templates/history.html`** — Added a price-per-unit span to both the normal
  item-row display and the search-result-row display.

- **`static/css/style.css`** — Added `.item-price-per-unit` (History) and
  `.search-result-price-per-unit` (search results, added to the existing CSS Grid
  column layout — `grid-template-columns` extended from 4 to 5 tracks). Added a
  mobile tweak so History's `.item-row` wraps instead of squeezing.

- **`tests/test_models.py`** / **`tests/test_routes.py`** — 30 new tests: unit
  tests for `_resolve_amount_unit()` covering every fallback branch and unit
  synonym, `ReceiptItem`/`price_per_unit` tests (including the real Coop numbers
  as a sanity check — `price=14.50, amount=0.744` → `price_per_unit ≈ 19.49`,
  matching the real in-store scale label's `19.50 CHF/kg` to within rounding),
  `Receipt.from_llm_response()` integration tests, and route tests confirming the
  display on both History and search results, plus a test proving search results
  now rank by price-per-unit rather than raw price (a bigger pack with a lower
  raw price but worse per-kg rate sorts after a smaller, cheaper-per-kg one).

**Tests**: 30 new tests added, all passing. Full suite: 159 passed, 1 pre-existing
unrelated failure (`test_fallback_to_saved_at_when_no_purchase_date`, a stale
hardcoded month assumption, already flagged separately).

No data migrations or new dependencies (the `opencv-python-headless` package used
during this session to attempt decoding a Coop receipt's Aztec code was a
throwaway diagnostic, never added to `requirements.txt`).
