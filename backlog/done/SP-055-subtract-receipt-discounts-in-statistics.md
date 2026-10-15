# SP-055: Subtract Receipt Discounts in Statistics

**Priority**: Medium
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-020

## Description
The Statistics page adds up each item's price per category, so a receipt-level discount (for example a 2-for-1 offer, where the receipt's `discount_amount` is the price of the free item) is never subtracted and the statistics show more spending than was actually paid. Subtract the discount from the category totals, but only for receipts where the discount really is missing from the item prices, so receipts whose item prices already include the savings are not reduced twice.

## Acceptance Criteria
- [x] For a receipt whose item prices add up to more than it was paid, and where `sum(item prices) - discount_amount` equals `total_amount` within 0.02, the Statistics page subtracts the discount from that receipt's spending. Example: Dal Rice Fish 2 x 40.00 plus 8.90 and 4.50 (items 93.40), discount 40.00, total 53.40 adds 53.40 to the statistics, not 93.40.
- [x] The discount is spread over the categories of that receipt's items in proportion to each category's share of the receipt's item total, so the receipt contributes exactly `item total - discount` in all. Amounts are kept as unrounded numbers (only the page display rounds), and tests compare with a tolerance of 0.005. Item prices are never negative (the model rejects them), so every share is positive. Example: items Food 60.00 and Household 40.00, discount 10.00 gives Food 54.00 and Household 36.00.
- [x] A receipt where `sum(item prices)` already equals `total_amount` within 0.02 (item prices already net of the savings) is not reduced, even if its `discount_amount` is above 0.
- [x] A receipt where neither of the two checks above holds (the discount cannot be explained from the totals) is not reduced; it is counted at its item prices as today.
- [x] A receipt with `discount_amount` 0 or no items is counted exactly as today.
- [x] The per-category percentages and the per-currency total on the Statistics page are calculated from the reduced amounts. Unlinked debit transactions are unaffected.
- [x] The rule is one small function used by the Statistics route (no copy of the logic in the template), with the tolerance defined once as a named constant.
- [x] Unit tests cover the rule (2-for-1 example, proportional split across categories, already-net receipt, unexplained discount, zero discount, rounding to the cent) and the Statistics page end to end (a month containing a discounted receipt shows the reduced category amounts and totals).
- [x] `Specification/BehaviorSpec.md` BS-020 (View Shopping Statistics by Month) states that receipt discounts are subtracted when they are part of what makes the receipt total, and how.

## Notes / Context
- Where the sum happens today: the loop in `app/routes.py` that does `totals_by_currency[currency][item.category] += item.price * item.quantity` (about line 908).
- How discounts are stored: `receipts.discount_amount` (one value per receipt), never per item. See the explanation given with this story: History shows it as a Discount line, extraction reconciliation accepts either `sum(items) = total` or `sum(items) + tax - discount = total`, and nothing else uses it.
- Why the "only when it explains the total" rule: on the current production data, 14 of 42 receipts have a discount. In 8 of them (mostly Coop) the item prices already match the total, so subtracting the discount would under-count; in 5 (Spice Village, STAM Burgers, La Rosa Pizza Kurier, Johnny's Asian Cuisine, La Capricciosa) the discount is exactly the gap between items and total; in L'Artista Oerlikon the items minus the discount also equal the total (the 0.65 tax is already inside the item prices). The rest (ALDI, Le Mouton) cannot be explained and stay as they are.
- Tax is not part of the check because item prices are tax-inclusive on Swiss receipts, and statistics already ignore tax.
- Out of scope: showing discounts per item on History, making the discount editable on the edit form, and changing what the LLM extracts.
- Expected effect on current data: the 6 receipts that satisfy the rule go down by their discount. Five are in 2024-09 (Spice Village -40.00, La Capricciosa -23.00, STAM Burgers -23.50, La Rosa Pizza Kurier -26.00, Johnny's Asian Cuisine -29.50) and L'Artista Oerlikon in 2026-09 (-25.50).

## Implementation Notes
Completed 2026-10-15.

- `app/models.py`: new constant `DISCOUNT_MATCH_TOLERANCE` (0.02, same as the extraction reconciliation) and new `Receipt.category_spend()`. It sums item totals per category and, when `discount_amount > 0` and `items - discount` equals `total_amount` within the tolerance, spreads the discount over the categories in proportion to their share. Receipts whose items already equal the total, or whose discount does not explain the total, are left as they were. Tax is not part of the check. Amounts are unrounded floats.
- `app/routes.py`: `statistics()` now adds up `receipt.category_spend()` instead of summing item prices itself; percentages and per-currency totals follow from the reduced amounts; unlinked transactions are untouched.
- `Specification/BehaviorSpec.md`: BS-020 describes the discount rule.
- No data change or migration: it is a calculation at display time. Expected effect on production data: six receipts go down by their discount (five in 2024-09 and L'Artista Oerlikon in 2026-09); to be checked on the production Statistics page after deploying.
- Tests: 13 added (`TestReceiptCategorySpend` in tests/test_models.py, `TestStatisticsDiscounts` in tests/test_routes.py). Full suite: 740 passed.
