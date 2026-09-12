# SP-042: Exclude Transaction Items from Statistics

**Priority**: Medium
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-050
**Deployed**: 4b94918 (2026-09-12)

## Description
Add the ability to exclude an individual transaction from the `/statistics` category breakdown without deleting the underlying record. The `/statistics` route (`app/routes.py:795-796`) currently counts every unlinked debit transaction as real spending — but a transfer between the user's own accounts shows up as an outgoing debit transaction that currently counts toward statistics even though it isn't real spending. The user needs a way to exclude that one transaction.

The toggle is a small icon on each transaction row in History (`templates/history.html`), placed next to the existing Link/Unlink icon (`.link-action`, `app/routes.py`'s `transaction_link`/`transaction_unlink` routes) — the same established pattern for a per-transaction boolean toggle in this codebase, rather than a checkbox added to the statement edit form.

## Acceptance Criteria
- [x] Each transaction row in History shows a toggle icon (mirroring `.link-action`'s style, distinct from the Link/Unlink icon) that flips an `excluded_from_stats` flag via a direct POST route (mirroring `transaction_unlink`'s single-click-POST pattern, not a separate staging page like `transaction_link`'s)
- [x] Excluded transactions are skipped when building the per-category totals in the `/statistics` route (`app/routes.py`, statistics route ~line 745-815)
- [x] Excluded transactions remain visible/editable elsewhere (e.g. History, statement edit) — the flag only affects statistics, it does not delete or hide the record
- [x] The exclusion flag can be toggled back off, using the same icon
- [x] Data schema/migration for the new flag is documented in `Specification/DataSchema.md`

## Notes / Context
Related to user-reported issue: "some items are counted twice, for example, transfer from one account to another." Relevant existing code: `app/services/transaction_service.py`, `app/database/sqlite_transaction_db.py`.

## Implementation Notes
Completed 2026-09-12.

- `app/database/sqlite_transaction_db.py` — `transactions` gains `excluded_from_stats INTEGER NOT NULL DEFAULT 0`, self-healed onto existing databases (including the real dev DB, confirmed on next start) via `_ensure_excluded_from_stats_column()`, same pattern as SP-041's `_ensure_hidden_column`. Added to `_UPDATABLE_TRANSACTION_COLUMNS` — a plain bool needs no special resolution the way `category` does, so the existing generic update mechanism handles it for free. `save_transaction`/`_row_to_dict` updated to persist/return it.
- `app/models.py` (`Transaction`) — `excluded_from_stats: bool = False` added to `__init__`/`to_dict`/`from_dict`, same treatment as `is_deleted`.
- `app/routes.py` — new `POST /transactions/<id>/toggle-excluded-from-stats` route (`toggle_transaction_excluded_from_stats`), mirroring `transaction_unlink`'s exact shape (ownership check, mutate, `update_transaction`, flash, redirect), but with no confirmation dialog since it's a single click to reverse. The `/statistics` route's `unlinked_debit_transactions` filter now also excludes `t.excluded_from_stats`. `_parse_statement_edit_form`'s `Transaction(...)` reconstruction now carries `excluded_from_stats=original.excluded_from_stats` through explicitly — without this, saving any edit to a statement would have silently cleared the flag on every transaction in it (caught and covered by a dedicated regression test).
- `templates/history.html` — a 📊/🚫 toggle icon added next to each transaction's existing Link/Unlink icon, reusing the `.link-action`/`.link-action-form` CSS classes as-is (no new CSS needed).
- `Specification/DataSchema.md` — documented the new `excluded_from_stats` column.
- `Specification/BehaviorSpec.md` — added BS-050 (Exclude a Transaction from Statistics); no existing scenario covered this.
- Verified end-to-end: the real dev database's `transactions` table self-healed the new column on server restart.
- Tests: 13 added (`tests/test_database.py` — 4, covering the self-heal, save/default/update of the new column; `tests/test_routes.py` — 9, covering the toggle route, ownership, the History icon's two states, statistics exclusion/re-inclusion, and the statement-edit preservation regression). Full suite: 600 passed.
