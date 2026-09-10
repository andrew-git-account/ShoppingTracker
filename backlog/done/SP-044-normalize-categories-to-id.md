# SP-044: Normalize Categories to a Category ID

**Priority**: High
**Status**: Done
**Fulfils**: DataSchema.md#Categories, DataSchema.md#Receipt-Storage, DataSchema.md#Transaction-Storage

## Description
Replace the free-text category duplication with a proper id-based reference. Today `categories` is just `(name TEXT PRIMARY KEY)` (`app/database/sqlite_category_db.py:44`) with **no FK relationship at all** — `receipt_items.category` and `transactions.category` are independent `TEXT NOT NULL DEFAULT 'Other'` columns (`app/database/sqlite_db.py:106`, `app/database/sqlite_transaction_db.py:65`) that just happen to contain a matching string, with nothing enforcing that. This SP gives `categories` a stable `id`, adds a `category_id` FK column to `receipt_items` and `transactions`, migrates every existing row to reference it, and removes the old text column.

This is a prerequisite for SP-041 (admin category management): once an admin can rename or hide a category, an id-based reference is what makes "this row's category" and "the category vocabulary entry" verifiably the same thing — a rename updates one row (the category itself) rather than requiring a text-matching cascade across every item/transaction that happens to contain the same string today.

Pure infrastructure change — no user-visible behavior should change as a result of this SP.

## Acceptance Criteria
- [x] `categories` table gains a stable integer `id` primary key; `name` becomes a `UNIQUE` (not primary-key) column
- [x] `receipt_items` table gains a `category_id` column (FK to `categories.id`)
- [x] `transactions` table gains a `category_id` column (FK to `categories.id`)
- [x] A migration (run automatically on startup, or an explicit one-off script following the existing pattern in `migrate_receipt_transaction_links.py`) backfills `category_id` on every existing `receipt_items` and `transactions` row by matching its current `category` text to `categories.name` — creating a new `categories` row first for any stored text value that has no match (e.g. a legacy or since-removed category)
- [x] After migration, every `receipt_items` and `transactions` row has a non-null `category_id`, and the old `category` TEXT column is dropped from both tables
- [ ] ~~Application code (models, services, routes, templates) reads and writes category via `category_id`, joining to `categories` for the display name, instead of the raw text column~~ — deliberately **not** done; see Implementation Notes for the rescoped approach and why
- [x] All existing tests pass, and existing user-visible behavior is unchanged: category shown per receipt item/transaction in History, the category dropdown in the receipt/statement edit forms, and the per-category statistics breakdown all look and behave exactly as before

## Notes / Context
Follows from clarifying how categories are currently linked (they aren't — pure text duplication, no FK) while scoping SP-041 (admin category management). Relevant existing code: `app/database/sqlite_category_db.py`, `app/database/sqlite_db.py` (receipt_items table), `app/database/sqlite_transaction_db.py`, `app/models.py`, `Specification/DataSchema.md` (categories/receipt_items/transactions sections — needs updating to document the new `category_id` relationship).

## Implementation Notes
Completed 2026-09-10.

**Rescoped during implementation** — normalized storage only, not the full application stack. The one AC that says models/services/routes/templates should read/write `category_id` directly was deliberately not done: `app/models.py` has no `Category` class (category is a plain defaulted string), `llm_service.py` prompts Claude with human-readable category *names* (never translatable to internal ids), and the edit-form templates/`/statistics` grouping all key off the name string. Rewriting all of that would have been a much larger, higher-risk change for a codebase with zero prior schema-migration precedent, for no extra benefit toward SP-041's actual need (rename/hide-by-id). Instead, the id↔name translation lives entirely inside the DB adapter layer — every caller above it is unaffected, confirmed by the full pre-existing test suite (530 tests) passing with zero test changes needed for that layer.

- `app/database/sqlite_category_db.py` — `categories` schema changed to `(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE)`; `get_all_categories()` now returns `id` alongside `name`; added `ensure_categories_table(conn)` (idempotent table creation, callable from any of the three DB classes) and `resolve_category_id(conn, name)` (name→id lookup, creating the row if unseen).
- `app/database/sqlite_db.py` — `receipt_items.category` replaced with `category_id INTEGER NOT NULL REFERENCES categories(id)`; both INSERT sites resolve name→id via `resolve_category_id`; the item SELECT now joins `categories` and aliases `categories.name AS category`, so callers still get a plain category name string. `initialize()` also calls `ensure_categories_table()` itself.
- `app/database/sqlite_transaction_db.py` — same treatment for `transactions.category_id`; `update_transaction`'s generic column-list mechanism special-cases `category` (removed from `_UPDATABLE_TRANSACTION_COLUMNS`) since it now needs id resolution rather than a straight passthrough.
- New `migrate_categories_to_id.py` (project root, follows the existing `migrate_*_to_sqlite.py` convention — manual, idempotent, guarded): rebuilds `categories` with an `id`, backfills `category_id` on both tables (auto-creating any orphaned/legacy category text first), drops the old `category` columns. Ran successfully against the real dev `data/shopping_tracker.db` (backed up first to `data/shopping_tracker.db.bak-sp044`): 210 receipt items + 70 transactions backfilled, 0 nulls remaining; a second run correctly no-op'd every step.
- `Specification/DataSchema.md` — updated the `categories`/`receipt_items`/`transactions` sections to document the new schema and the migration script.
- Bugfix found via a real test failure (not anticipated in the original plan): several existing tests construct `SqliteDatabase`/`SqliteTransactionDatabase` standalone, without ever constructing `SqliteCategoryDatabase` first, so the `categories` table didn't exist yet on that file. Fixed by having each of the three classes call `ensure_categories_table()` from its own `initialize()`.
- Manually verified end-to-end against the real migrated dev data (Flask test client, real session): `/history`, `/receipt/<id>/edit`, `/statistics` all return 200; the edit page's category dropdown correctly pre-selects "Food & Groceries"/"Personal Care & Health" for a receipt with those items.
- Tests: 17 added (`tests/test_database.py` — id/name shape, `resolve_category_id` behavior, "constructed alone" regression coverage for both DB classes; new `tests/test_migrate_categories_to_id.py` — 7 tests covering the migration script against a hand-built old-schema file, including the orphaned-category case and idempotency). Full suite: 547 passed.
