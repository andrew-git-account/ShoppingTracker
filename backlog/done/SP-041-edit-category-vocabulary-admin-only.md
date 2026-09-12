# SP-041: Edit Category Vocabulary (Admin Only)

**Priority**: Medium
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-049
**Deployed**: 4b94918 (2026-09-12)

## Description
Add the ability for administrators to add, rename, and hide/unhide categories in the category vocabulary. Categories are currently a seeded, read-only list (`SqliteCategoryDatabase` in `app/database/sqlite_category_db.py`) with no UI to manage them, and users have found the available category list too limited when categorizing receipt items and transactions. Only users with admin privileges (see the existing admin check pattern used for feedback in `app/services/auth_service.py` and `app/routes.py`) should be able to make these changes.

Category is never a true delete — a category can only be **hidden** (excluded from future selection), never removed, and a hidden category can be unhidden again. This was an explicit product decision: a category that's already in use shouldn't leave items/transactions in a broken or reassigned state just because an admin decided it's no longer wanted going forward.

Both rename and hide/unhide are now well-defined thanks to SP-044 (categories got a stable `id`; `receipt_items`/`transactions` reference it via `category_id` instead of duplicating the name as free text):
- **Rename** is a single-row update to `categories.name`. Every existing item/transaction that references that `category_id` automatically shows the new name on its next read (the display join resolves the current name, not a frozen copy) — no cascade code needed, this falls out of the schema for free.
- **Hide** only needs to affect what's offered for *future* assignment (the category dropdowns in the receipt/statement edit forms, and the list handed to the LLM for auto-categorization). An item/transaction already using a hidden category keeps its `category_id` untouched, so it keeps displaying that category's name completely normally everywhere (History, edit forms, statistics) — nothing needs to change display-side, since hidden-ness is only ever consulted when building the "categories available to newly assign" list, never when reading back what's already assigned.

## Acceptance Criteria
- [x] An admin-only page/section exists for managing categories, listing every category (visible and hidden)
- [x] An admin can add a new category name
- [x] An admin can rename an existing category; every receipt item/transaction already using it shows the new name immediately (no separate migration/cascade step — this is the read-side join behaving normally)
- [x] An admin can hide a category; it stops appearing in the category dropdown on the receipt/statement edit forms and is no longer offered to the LLM as a valid category for new extractions
- [x] An admin can unhide a previously hidden category, making it selectable again
- [x] A receipt item or transaction already assigned to a category continues to display that category's name normally, whether or not the category is currently hidden
- [x] The seeded "Other" category (the universal fallback used when no category matches) cannot be hidden — mirrors the existing last-admin safeguard pattern (SP-033/BS-033) for a category everything else depends on
- [x] A non-admin user cannot access category management (route rejects/hides it)
- [x] Renaming a category to a name that collides with an existing category name shows a clear validation error rather than a raw database constraint failure

## Notes / Context
Related to user-reported issue: "there is a lack of categories." Depends on SP-044 (category_id normalization), already done.

## Implementation Notes
Completed 2026-09-12.

- `app/database/sqlite_category_db.py` — `categories` gains a `hidden INTEGER NOT NULL DEFAULT 0` column, self-healed onto existing databases via `_ensure_hidden_column()` (checked/added from `ensure_categories_table()`, so every one of the three DB classes' `initialize()` heals it, including the real dev DB on next start — no separate migration script needed, unlike SP-044's `id` change, since `ADD COLUMN ... DEFAULT` is a trivial, safe alteration). `get_all_categories()` now returns `hidden` too. New CRUD: `get_category_by_id`, `get_category_by_name`, `add_category`, `rename_category`, `set_hidden`.
- New `app/services/category_service.py` (`CategoryService`) — mirrors `AuthService`'s shape: `get_all_categories()`/`get_visible_category_names()` for reads, and `add_category`/`rename_category`/`toggle_hidden` returning `(success, error)` tuples with duplicate-name and not-found validation, plus a hard-coded guard rejecting hiding the `"Other"` category.
- `app/main.py` — `valid_categories` fed to `LLMService`/`ReceiptService`/`StatementService` is now the **visible-only** list; `CategoryService` is constructed and attached as `app.category_service`.
- `app/routes.py` — new admin-gated routes `GET /categories`, `POST /categories/add`, `POST /categories/<id>/rename`, `POST /categories/<id>/toggle-hidden` (same inline `if not session.get('is_admin')` guard used everywhere else). A new `_refresh_valid_categories()` helper reassigns the three services' cached `valid_categories` list after every successful mutation, so changes take effect live without a server restart. `_parse_edit_form`/`_parse_statement_edit_form` gained an `all_categories` parameter (visible + hidden) used only for the submitted-value fallback check, kept separate from the `categories` (visible-only) list used for the dropdown — this was a real correctness bug caught during implementation: without the split, re-saving a receipt with a hidden category (without touching that row) would have silently downgraded it to `"Other"`.
- `templates/categories.html` (new) — admin page mirroring `users.html`'s structure; each row is a 3-column CSS grid (input | Rename | Hide/Unhide) sized against actual measured button content, since each row is its own independent grid instance (auto-sized columns don't share width across rows) and "Hide"/"Unhide" differ in length. The input/buttons are plain grid siblings pointing at externally-declared `<form>` elements via the HTML `form="..."` attribute (same technique as the receipt-edit page's Save/Discard buttons) rather than `display: contents` on a wrapping form, which was tried first and reverted after user-reported cross-browser inconsistencies.
- `templates/edit_receipt.html`/`templates/edit_statement.html` — each category `<select>` gains one extra conditional `<option>` for a row's own category if it's hidden (marked "(hidden)"), so a row already on a hidden category still round-trips correctly instead of the browser silently defaulting the `<select>` to its first option.
- `templates/base.html` — "Categories" nav link added next to "Users", admin-only.
- `static/css/style.css` — `.btn-warning` (Unhide button), `.category-rename-form`/`.summary-row.category-row` grid layout, scoped so it doesn't affect `.summary-row`'s other uses (receipt/statistics/users rows).
- `Specification/BehaviorSpec.md` — added BS-049 (Admins Manage the Category Vocabulary); no BS scenario previously covered this.
- Verified end-to-end against a scratch copy of the real dev data: hiding a category live-updates the LLM/dropdown lists without restart, a hidden category's existing assignment survives an unrelated re-save (the bug the `all_categories` split prevents), renaming reflects immediately in History, and hiding "Other" is rejected.
- Tests: 45 added (`tests/test_category_service.py` — 13; `tests/test_database.py` — 17 covering the `hidden` column, self-healing, and new CRUD; `tests/test_routes.py` — 15 covering the admin page, admin-gating, and the hidden-category correctness behaviors). Full suite: 587 passed.
