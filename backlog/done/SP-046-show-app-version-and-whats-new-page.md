# SP-046: Show App Version and a What's New Page

**Priority**: Medium
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-051
**Deployed**: 0273459 (2026-10-07)

## Description
Give the application a visible release version and a release history. The version and the list of changes per release live in one file, `releases.json`. The footer shows the current version, and logged-in users can click it to open a "What's New" page listing every release, newest first. The file starts with a single entry, version 10 (the release that ships this SP); the nine earlier deployments are added afterwards by SP-048.

## Acceptance Criteria
- [x] `releases.json` exists at the repo root: a JSON list, newest release first. Each entry has `version` (plain integer), `date` (`YYYY-MM-DD`) and `changes` (a list of `{"sp": "NNN", "text": "..."}`). It holds no commit SHAs.
- [x] `releases.json` contains one entry, version 10, whose `changes` describe this SP (SP-046). Versions 1-9 are not part of this SP (see SP-048); the app works with any number of entries.
- [x] The current version is the `version` of the first entry in `releases.json`. It is read in one place and supplied to every template through a context processor, so no template or route reads the file itself.
- [x] The footer in `templates/base.html` reads `Â© 2026 Shopping Tracker | Version 10` (replacing "An educational project"). The version is a plain integer, with no padding or minor part.
- [x] For a logged-in user, "Version 10" in the footer is a link to `/whats-new`.
- [x] For a user who is not logged in (e.g. the login page), the footer shows "Version 10" as plain text, with no link.
- [x] `GET /whats-new` requires login like every other page (an unauthenticated request redirects to `/login`) and is available to every logged-in user, not just admins.
- [x] The What's New page lists all releases newest first, each with its version, date and its list of changes.
- [x] If `releases.json` is missing or unreadable, the app still starts and every page renders, with the footer showing no version text; it never crashes a request.
- [x] No JavaScript is added.
- [x] Tests cover: the version from the first entry; footer text and link for a logged-in user; footer text without a link on `/login`; `/whats-new` redirects when logged out and returns 200 for a normal (non-admin) user, listing releases newest first (tests point the app at a temporary `releases.json` with several entries, so ordering is verified without depending on the real file); a missing or malformed `releases.json` does not break page rendering.

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
Completed 2026-10-07.

- `releases.json` (new, repo root) - one entry, version 10, dated 2026-10-07, describing this SP; no commit SHAs.
- `app/releases.py` (new) - `load_releases(path)` reads the file and returns `[]` for a missing/unreadable/malformed/non-list file, skipping malformed entries; `current_version()` returns the first entry's version or `None`.
- `app/main.py` - added `app.config['RELEASES_FILE']` (defaults to `releases.json` in the project root) so tests can point the app at a temporary file.
- `app/routes.py` - a context processor injects `app_version` into every template (read per request, so a changed file takes effect immediately); new `GET /whats-new` route. It is not in `_PUBLIC_ENDPOINTS`, so the existing login guard protects it; no admin check.
- `templates/base.html` - footer now reads "(c) 2026 Shopping Tracker | Version N"; N links to `/whats-new` for logged-in users and is plain text otherwise; nothing is shown if there is no version.
- `templates/whats_new.html` (new) - one card per release (version, date, changes with SP numbers), with an empty-state message; no JavaScript.
- `static/css/style.css` - footer link colour and release-card styles.
- `Specification/BehaviorSpec.md` - added BS-051 for the footer version and What's New page.
- No migrations, data changes or new dependencies. Versions 1-9 are added by SP-048; automatic version bumping on deploy is SP-047.
- Tests: 19 added in `tests/test_releases.py` (loader and bad-file handling, footer link vs plain text, `/whats-new` access for anonymous/non-admin/admin users, newest-first order, no JavaScript, the real shipped `releases.json`); full suite 631 passed.
