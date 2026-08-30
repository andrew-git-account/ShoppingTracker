# SP-040: Show Logged-In Email in Nav

**Priority**: Low
**Status**: Open

## Description
As a user, I want to see my logged-in email address so I can be sure I'm using the correct account. This app uses OTP-based login (email + a one-time code), not a username/password, so there's no password to display — the email address is the identifying credential. Display the current user's email in the navbar/header on every authenticated page.

## Acceptance Criteria
- [ ] The current user's email is visible in the nav on every authenticated page (`templates/base.html`, inside the existing `{% if session.get('logged_in') %}` block).
- [ ] Not shown on the login/verify pages (no session yet) or to a logged-out visitor.
- [ ] Displaying it requires no route changes — `session['user_email']` is already set at login and available to every template via Flask's session object.

## Notes / Context

### Placement
Likely alongside the "Contact"/"Log out" links already in the nav (see SP-039), e.g. a small `<span>` or `<li>` showing the email, not styled as a clickable link since it's informational only.

### Out of scope
- Any account/profile management page.
- Editing the email itself (not a thing in this app - the allowed-users list is admin-managed, see SP-021).

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
