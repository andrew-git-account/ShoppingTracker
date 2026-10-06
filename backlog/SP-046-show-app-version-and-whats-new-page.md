# SP-046: Show App Version and a What's New Page

**Priority**: Medium
**Status**: Ready

## Description
Give the application a visible release version and a release history. The version and the list of changes per release live in one file, `releases.json`. The footer shows the current version, and logged-in users can click it to open a "What's New" page listing every release, newest first. The file starts with a single entry, version 10 (the release that ships this SP); the nine earlier deployments are added afterwards by SP-048.

## Acceptance Criteria
- [ ] `releases.json` exists at the repo root: a JSON list, newest release first. Each entry has `version` (plain integer), `date` (`YYYY-MM-DD`) and `changes` (a list of `{"sp": "NNN", "text": "..."}`). It holds no commit SHAs.
- [ ] `releases.json` contains one entry, version 10, whose `changes` describe this SP (SP-046). Versions 1-9 are not part of this SP (see SP-048); the app works with any number of entries.
- [ ] The current version is the `version` of the first entry in `releases.json`. It is read in one place and supplied to every template through a context processor, so no template or route reads the file itself.
- [ ] The footer in `templates/base.html` reads `© 2026 Shopping Tracker | Version 10` (replacing "An educational project"). The version is a plain integer, with no padding or minor part.
- [ ] For a logged-in user, "Version 10" in the footer is a link to `/whats-new`.
- [ ] For a user who is not logged in (e.g. the login page), the footer shows "Version 10" as plain text, with no link.
- [ ] `GET /whats-new` requires login like every other page (an unauthenticated request redirects to `/login`) and is available to every logged-in user, not just admins.
- [ ] The What's New page lists all releases newest first, each with its version, date and its list of changes.
- [ ] If `releases.json` is missing or unreadable, the app still starts and every page renders, with the footer showing no version text; it never crashes a request.
- [ ] No JavaScript is added.
- [ ] Tests cover: the version from the first entry; footer text and link for a logged-in user; footer text without a link on `/login`; `/whats-new` redirects when logged out and returns 200 for a normal (non-admin) user, listing releases newest first (tests point the app at a temporary `releases.json` with several entries, so ordering is verified without depending on the real file); a missing or malformed `releases.json` does not break page rendering.

## Notes / Context
- A single file holds both the version and the release notes, so they cannot drift apart. The release process that bumps it automatically is SP-047, which depends on this SP.
- The deployment marker on the Azure share (`deployment_state.json`) is unchanged and remains the deploy tool's own record.
- The earlier deployments (versions 1-9) are backfilled by SP-048. Until that ships, the What's New page shows only version 10; the version number in the footer is still correct because 10 is the next number after the nine past deployments.
- Version 10's date is the planned deploy date; set it to the actual date when the release is committed.
- The footer currently lives in `templates/base.html` (the `<footer class="footer">` block). `/login` and `/verify` are public endpoints (`_PUBLIC_ENDPOINTS` in `app/routes.py`), so the context processor must work when there is no session user. Use `session.get('logged_in')` to decide whether to render the link.
- `/whats-new` must not be added to `_PUBLIC_ENDPOINTS`; the existing `before_request` guard then enforces login for free.
- Keep it simple for a beginner project: load `releases.json` with `json.load` once at startup (or on each request, which is cheap at this size) and explain why in comments.
- A new BehaviorSpec scenario for this feature is added at `/sdlc-done` time.

### Out of scope
- Backfilling versions 1-9 from the deploy history (SP-048).
- Automatically bumping the version or writing release entries during deployment (SP-047).
- Editing releases from the UI.
- Showing an unread "new version" notification.

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
