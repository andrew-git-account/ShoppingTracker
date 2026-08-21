# SP-021: Admin User Management Page

**Priority**: Medium
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-033

## Description
Add an admin-only page listing every allowed user, where admins can add new users by email, toggle a user's admin flag, and block/unblock a user (deactivating/restoring their ability to log in, without deleting their record). Builds directly on SP-020's admin infrastructure (`session['is_admin']`, `AuthService.is_admin()`, the `allowed_users.json` schema). Emails are unique — adding a duplicate (case-insensitive) is rejected.

## Acceptance Criteria
- [x] A new page (e.g. `/users`), admin-only via the same `session['is_admin']` gate as SP-020's `/llm-usage` (server-side denial for non-admins hitting it directly, not just a hidden nav link), lists every user with their email, admin status, and blocked status.
- [x] Admins can add a new user by email. A duplicate email (case-insensitive, matching the existing comparison in `AuthService.is_email_allowed()`) is rejected with a clear error instead of creating a second entry. A newly added user starts as non-admin and not blocked.
- [x] Admins can toggle a user's admin flag on and off.
- [x] Admins can toggle a user's blocked flag on and off. A blocked email is rejected at `/login` even though it's still present in `allowed_users.json` (blocking deactivates, it doesn't delete). Unblocking restores login access.
- [x] Removing admin status from a user, or blocking a user, is rejected server-side with a clear error if it would leave zero *active* admins (admin flag set AND not blocked) — regardless of whether the action targets the acting admin themselves or someone else. Every other combination of self/other × admin/block action is allowed.
- [x] A user who is currently logged in when they get blocked keeps their existing session until it ends naturally (matches the existing `is_admin`/`user_email` session-caching precedent from SP-005/SP-020 — nothing re-checks block status mid-session); only their *next* login attempt is rejected.

## Notes / Context

### Schema change — smaller than SP-020's
Add an `is_blocked` boolean to each `allowed_users.json` entry. Unlike SP-020 (which changed bare strings into objects, requiring a real data migration), this only adds a *new optional key* to shapes that already exist — no forced migration or manual data edit is needed, locally or in production. Extend `AuthService._load_allowed_users()`'s existing tolerant-normalization loop (`app/services/auth_service.py`) to also default a missing `is_blocked` to `False`, exactly like it already does for `is_admin`. Both the bare-string and `{email, is_admin}`-only shapes that already exist in the real data files continue to load correctly with `is_blocked: False`, with no edits required before this ships.

### AuthService changes (`app/services/auth_service.py`)
- `_load_allowed_users()` — add `'is_blocked': bool(entry.get('is_blocked', False))` to both normalization branches (string and object).
- `is_email_allowed()` — must also exclude blocked users (a blocked-but-technically-listed email should fail login the same way an unknown one does).
- New `add_user(email: str) -> bool` — returns `False` (or raises — implementer's call, but the route needs to distinguish this case to show a clear error) if the email already exists case-insensitively; otherwise appends `{"email": ..., "is_admin": False, "is_blocked": False}` and persists.
- New `set_admin(email: str, is_admin: bool) -> bool` and `set_blocked(email: str, is_blocked: bool) -> bool` — persist the change; return `False` (or raise) if the change would leave zero active admins, per the lockout rule below. `True`/success otherwise.
- New `get_all_users() -> List[Dict]` — returns the normalized list (email, is_admin, is_blocked) for the page to render.
- New `_save_allowed_users(users: List[Dict]) -> None` — write-back helper (mirrors the existing read side), writing the object shape.
- **Last-admin lockout rule**: before applying `set_admin(email, False)` or `set_blocked(email, True)`, count how many *other* users (or the same user, post-change) would remain with `is_admin=True and is_blocked=False`. If that count would hit zero, reject the change. This applies uniformly to self-targeted and other-targeted actions — no special-casing "is this the acting admin."

### Routes (`app/routes.py`)
- `GET /users` — admin-gated (same pattern as `/llm-usage`: check `session.get('is_admin')`, flash + redirect if not), renders the user list.
- `POST /users/add` — form field `email`; flash success or the duplicate-email error; redirect back to `/users`.
- `POST /users/<email>/toggle-admin` — flips the flag; flash the lockout error if rejected.
- `POST /users/<email>/toggle-blocked` — flips the flag; flash the lockout error if rejected.
- Nav: add a "Users" link in `templates/base.html`, gated by `{% if session.get('is_admin') %}` exactly like the "LLM Usage" link added in SP-020.

### Page design
- New `templates/users.html`. Reuse existing CSS/markup patterns rather than inventing new ones — e.g. the add-user form can follow the same `<form method="POST">` + `.search-input`/`.btn.btn-primary` styling already used elsewhere, and each user row's toggle buttons can be small `<form method="POST">`s posting to the toggle routes (same pattern as `history.html`'s per-receipt delete form).
- Show each user's email, an admin toggle (button or checkbox reflecting current state), and a blocked toggle, plus a visual indicator for blocked users (e.g. dimmed row or a "Blocked" badge) so it's obvious at a glance.

### Out of scope
- No hard delete of users — only block/unblock (matches this app's existing soft-delete philosophy from SP-002/receipts).
- No email notification sent when a user is added — they simply become able to request an OTP at `/login` going forward.
- No live mid-session revocation for blocked users — see the last acceptance criterion.

## Implementation Notes
_Completed 2026-08-21._

- `app/services/auth_service.py` — `_load_allowed_users()` now also normalizes `is_blocked` (default `False`) for both entry shapes; `is_email_allowed()` excludes blocked users. New methods: `add_user()`, `set_admin()`/`set_blocked()` (mutate-check-revert last-admin lockout logic, `_count_active_admins()` helper), `toggle_admin()`/`toggle_blocked()` (thin wrappers), `get_all_users()`, `_find_user()`, `_save_allowed_users()`. All mutation methods return `(bool, Optional[str])`, mirroring the existing `Receipt.validate()` pattern in `app/models.py`.
- `app/routes.py` — new `GET /users`, `POST /users/add`, `POST /users/<email>/toggle-admin`, `POST /users/<email>/toggle-blocked`, each independently checking `session.get('is_admin')` (not just relying on the GET page's check or a hidden nav link).
- `templates/base.html` — "Users" nav link, gated the same way as "LLM Usage".
- `templates/users.html` (new) — add-user form + a `.stats-panel`/`.summary-row` list of users with toggle buttons, reusing existing classes throughout.
- `static/css/style.css` — one small new rule, `.user-actions { display: flex; align-items: center; gap: var(--spacing-sm); }`, to lay out each row's two toggle-button forms — the only new CSS needed.
- **No data migration** — `is_blocked` is a purely additive optional key; the existing tolerant parser already defaults it to `False` for every shape already in the real data files, locally and in production.
- Verified live by the account holder directly: added a test user via the real `/users` page and blocked them — confirmed the resulting `allowed_users.json` on disk matches the expected schema exactly (`{"email": ..., "is_admin": false, "is_blocked": true}`).
- Tests: 36 added (`test_auth_service.py`'s `TestAuthServiceUserManagement`, `test_routes.py`'s `TestUserManagementPage`). 248 passed (full suite).
