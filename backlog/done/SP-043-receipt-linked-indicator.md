# SP-043: Show Linked Indicator on Receipts

**Priority**: Low
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-048
**Deployed**: 4b94918 (2026-09-12)

## Description
Add a visual indicator on a receipt showing that it is linked to a statement transaction. Transactions already show a link badge (🔗, "Linked to a receipt") in `templates/history.html` (~lines 96-97) when `transaction.transaction_id in linked_transaction_ids`, but the receipt card itself (rendered further down in the same template, ~line 130+) shows no equivalent indicator even though the `Receipt` model already carries `linked_transaction_id` (see `app/routes.py:158` and SP-037). Users currently have no way to tell, from looking at a receipt, whether it's already linked to a transaction.

## Acceptance Criteria
- [x] A receipt that has a non-null `linked_transaction_id` displays a visual badge/icon in the history view (mirroring the existing transaction-side badge style)
- [x] An unlinked receipt shows no such badge
- [x] The indicator has a tooltip/title clarifying what it means (e.g. "Linked to a statement transaction")
- [x] Works consistently whether the receipt was linked automatically (matching) or manually (SP-027 manual linking)

## Notes / Context
Related to user-reported issue: "there are no visual indicator that a receipt is linked to a transaction from a statement." Relevant existing code: `templates/history.html`, `app/routes.py` (history route, ~line 670-732).

## Implementation Notes
Completed 2026-09-10.

- `templates/history.html` — added a `.linked-badge` 🔗 span next to the receipt's store name when `receipt.linked_transaction_id` is set, with `title="Linked to a statement transaction"` (distinct from the transaction-side badge's `title="Linked to a receipt"`). Reuses the existing `.linked-badge` CSS class (`static/css/style.css:983-986`) — no CSS changes needed. No `app/routes.py` or `app/models.py` changes were needed since `linked_transaction_id` was already populated on every `Receipt` object passed to the template.
- `tests/test_routes.py` — added `test_history_linked_receipt_shows_badge` and `test_history_unlinked_receipt_no_badge` to `TestHistoryTransactions`. Fixed the pre-existing `test_history_linked_transaction_shows_badge`, which asserted a raw `html.count("🔗") == 1`; that assumption broke once a linked receipt started rendering its own badge too, so the assertion was narrowed to the transaction badge's own title text (`title="Linked to a receipt"`) to keep testing what it originally intended.
- `Specification/BehaviorSpec.md` — added BS-048 (Receipt Shows a Linked Indicator), documenting the new receipt-side badge; BS-038 previously only covered the transaction-side marker.
- No migrations or data changes — purely a template/test change.
- Tests: 2 added, 1 fixed, full suite 530 passed.
