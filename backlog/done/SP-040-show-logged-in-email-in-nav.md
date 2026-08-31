# SP-040: Show Logged-In Email in Nav

**Priority**: Low
**Status**: Done
**Fulfils**: Specification/BehaviorSpec.md#BS-047 (new)

## Description
As a user, I want to see my logged-in email address so I can be sure I'm using the correct account. This app uses OTP-based login (email + a one-time code), not a username/password, so there's no password to display — the email address is the identifying credential. Display the current user's email in the navbar/header on every authenticated page.

## Acceptance Criteria
- [x] The current user's email is visible in the nav on every authenticated page (`templates/base.html`, inside the existing `{% if session.get('logged_in') %}` block).
- [x] Not shown on the login/verify pages (no session yet) or to a logged-out visitor.
- [x] Displaying it requires no route changes — `session['user_email']` is already set at login and available to every template via Flask's session object.

## Notes / Context

### Placement
Likely alongside the "Contact"/"Log out" links already in the nav (see SP-039), e.g. a small `<span>` or `<li>` showing the email, not styled as a clickable link since it's informational only.

### Out of scope
- Any account/profile management page.
- Editing the email itself (not a thing in this app - the allowed-users list is admin-managed, see SP-021).

## Implementation Notes

Completed 2026-08-31.

- **`templates/base.html`**: added a `.navbar-top` row (app name left, `session.get('user_email')` right, plain `<span>` not a link) above `.nav-tabs`, both inside `.navbar .container`. Only rendered when `session.get('logged_in')` is set, same guard the rest of the authenticated nav already uses.
- **`static/css/style.css`**: `.navbar .container` restructured to a two-row column layout (`flex-direction: column`) with a new `.navbar-top` (app name/email, `justify-content: space-between`) above the existing `.nav-tabs` row. Follow-up from user feedback on the first pass: the email was initially placed inline among the `.nav-tabs` `<li>` items, which visually crowded it into the middle of the tab row — moved to its own top row instead, matching a mockup the user provided.
- **`tests/test_routes.py`**: new `TestNavShowsLoggedInEmail` (4 tests) — shown on multiple authenticated pages, absent on the login page, absent to a logged-out visitor requesting a protected page.
- No route, service, or storage changes — purely template/CSS, exactly as scoped.
- **`Specification/BehaviorSpec.md`**: added BS-047 (no scenario existed for this).
- Test summary: 4 new tests, 528 passed, 0 failed. Server boot verified after both the initial layout and the two-row restructure.
