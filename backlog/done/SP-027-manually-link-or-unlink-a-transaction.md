# SP-027: Manually Link or Unlink a Transaction

**Priority**: High
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-043
**Deployed**: 41e8c91 (2026-08-26)

## Description
Let a user manually link an unlinked transaction to a receipt, or unlink one that was linked — whether that link was made automatically by SP-026 or by hand here. A separate dedicated page handles the filter-and-pick flow (mirroring History's existing search pattern), reached via a small "Link"/"Unlink" text action on the transaction's row in History. This is what makes SP-026's silent auto-matching safe — any wrong or missed match is one click away from being corrected.

## Acceptance Criteria
- [x] Each transaction row in History (SP-029) shows a "Link" action if unlinked, or an "Unlink" action if linked — a small icon (🔗 for Link; 🔗 with a small × badge overlaid for Unlink, sharing the same fixed-size button footprint so the row stays visually steady either way), with the action name as hover `title` text, since a transaction row today (post SP-030) has no other per-row actions.
- [x] "Link" opens a dedicated filter-and-pick page (`GET /transactions/<transaction_id>/link`) listing the user's unlinked receipts matching a filter (name, date from/to, amount from/to); picking one sets `linked_receipt_id`.
- [x] The filter defaults to the narrowest useful search for that transaction: name empty (no filter), date-from and date-to both set to the transaction's own date, amount-from and amount-to both set to the transaction's own amount — so the default view is "receipts matching this transaction exactly," widened only if the user changes the fields.
- [x] "Unlink" clears `linked_receipt_id` via a POST from History, behind a confirmation dialog (same native-browser-confirm pattern as receipt deletion) — added after initial manual testing, since a bare click felt too easy to trigger by accident for something that silently changes Statistics' totals.
- [x] All actions are restricted server-side to the transaction's owner, same ownership pattern used everywhere else in the app (SP-005) — not found and not-owned look identical.
- [x] Manually linking enforces the same one-to-one rule as automatic matching — a receipt already linked to a different transaction isn't offered as a choice, and is rejected server-side with a clear error if picked anyway (never trust the filtered list alone for this).
- [x] Linking or unlinking is reflected immediately in History's linked-marker for that transaction (SP-029's display).

## Notes / Context

### Confirmed still valid after SP-030/SP-031 (2026-08-25)
Re-checked against what's actually shipped since this was last touched: SP-030 (statement-level editing) added no per-transaction actions to History's row markup — only one edit icon per *statement* — so "Link"/"Unlink" have a clear, uncluttered place to live on the row itself. SP-031 (statement deletion) already establishes the precedent of clearing `linked_receipt_id` before a transaction becomes unreachable; this SP is the user-facing, one-transaction-at-a-time counterpart to that same field. Considered and rejected: folding link/unlink into SP-030's statement-edit page as an expandable per-row filter form — with several transactions per statement each needing a multi-field filter, that page would get very tall and cluttered; a separate page keeps editing and linking as two focused flows, and mirrors History's existing search-page pattern (SP-004) instead of inventing a new one.

### Direction and linking
A `credit` transaction is linkable, same as a `debit` one — e.g. reconciling a refund credit against its original receipt is a legitimate use case, not an edge case to guard against. The "Link" action and filter apply uniformly regardless of `direction`, consistent with SP-026's matching (also unrestricted by direction).

### One-to-one enforcement reuses SP-026's own logic
"Not already linked to a different transaction" is the same check `TransactionMatcher.match_transaction` already computes (`linked_receipt_ids = {t.linked_receipt_id for t in transaction_service.get_all_transactions(user_email) if t.linked_receipt_id}`, `app/services/transaction_matcher.py`) — the filter route excludes any receipt whose id is in that set, and the POST re-checks it server-side before saving, since the GET-time list could be stale by the time the form is submitted.

### Routes (`app/routes.py`)
- `GET /transactions/<transaction_id>/link` — the filter-and-pick page (no JS, mirroring History's `GET /history?q=...` search pattern from SP-004). Reads `name`/`date_from`/`date_to`/`amount_from`/`amount_to` from the query string; when absent (first visit, no query string at all), fills in the defaults from the acceptance criteria (empty name, both dates = the transaction's date, both amounts = the transaction's amount) and renders with those instead of erroring. Filters `receipt_service.get_all_receipts(user_email)` down to receipts that are (a) not already linked to a different transaction (see above) and (b) within the name/date/amount filter, and lists them each with a small per-row "Select" form.
- `POST /transactions/<transaction_id>/link` — submitted by a result row's "Select" form (hidden `receipt_id` field); validates ownership of both the transaction and the receipt, and re-checks the receipt isn't already linked elsewhere, before setting `linked_receipt_id` via `app.transaction_service.update_transaction(...)`. Flash + redirect to `/history`.
- `POST /transactions/<transaction_id>/unlink` — clears `linked_receipt_id` via the same service, ownership-checked the same way. Flash + redirect to `/history`.
- The "Link" / "Unlink" links/forms themselves live on History's transaction entries (`templates/history.html`), pointing at the routes above.

### Template
New `templates/transaction_link.html` (the filter-and-pick page) — follows `history.html`'s existing `.search-form`/`.search-input` pattern (SP-004), extended with the extra date/amount fields, and each result row's "Select" form mirrors `history.html`'s per-row delete form.

### Out of scope (this SP)
- Rendering transaction entries in History, icons, and the linked/unlinked visual marker — already done (SP-029).
- Transactions appearing in Statistics — already done (SP-028).
- Bulk actions (link/unlink multiple at once).
- Any change to the statement-edit page (SP-030) — linking stays a separate flow, not folded into it (see "Confirmed still valid" above).

## Implementation Notes
Completed 2026-08-25.

- `app/routes.py` — new module-level `_already_linked_receipt_ids(transaction_service, user_email, excluding_transaction_id)` helper (reuses the exact one-to-one check `TransactionMatcher.match_transaction` already computes). New `GET/POST /transactions/<transaction_id>/link` (filter-and-pick page, defaults to the transaction's own date/amount on first visit, re-validates ownership and the one-to-one rule server-side on POST) and `POST /transactions/<transaction_id>/unlink`.
- `templates/transaction_link.html` (new) — the filter-and-pick page, reusing History's existing `.search-form`/`.search-input` classes.
- `templates/history.html` — Link/Unlink icon actions added to each transaction row.
- `static/css/style.css` — `.link-action`/`.link-action-form`/`.link-action-badge` (icon-button styling, with a fixed-size footprint shared by both states — Unlink overlays a small × badge on the same 🔗 glyph rather than showing a second full-size character), `.receipt-pick-row` (grid layout for the filter results), and an explicit `gap` added to `.item-row` (previously had none — the flex-grow on `.item-name` was silently absorbing all free space, leaving zero visual breathing room between the other row elements).
- No model, service, or database changes — `get_transaction_by_id`, `get_all_transactions`, `update_transaction`, `get_all_receipts`, `get_receipt_by_id` all already existed.
- Went through two rounds of design polish after initial manual testing: (1) icon buttons with hover-title text instead of plain "Link"/"Unlink" text links, with the Unlink icon sharing the Link icon's glyph plus a small badge rather than a second full-size character, so both states occupy the same footprint; (2) a confirmation dialog added to Unlink, and a `.item-row` spacing fix, both found by eyeballing the real rendered page.
- Tests: `tests/test_routes.py`'s `TestTransactionLinkRoute` (14 tests) — icon/URL presence per state, filter defaults and widening, name filtering, already-linked-receipt exclusion (using a receipt that would otherwise match exactly, so the test actually isolates the one-to-one check rather than passing for an unrelated reason), ownership on both GET and POST, the server-side re-check on POST (not just trusting the GET-time filtered list), and unlink clearing the field. Full suite: 425 passed (411 existing + 14 new).
- Verified manually beyond the automated suite: a scripted end-to-end run against the real Flask app (default filter excludes/includes correctly, link/unlink both persist), and the actual rendered pages (History and the filter page) inspected in a real browser via a local static-file server, confirming the icon sizing, badge overlay, and grid alignment fixes all look right — not a real logged-in browser session, since login needs an email OTP that isn't reachable here.
