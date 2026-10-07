# SP-049: Show SP Number Before the Description on the What's New Page

**Priority**: Low
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-051
**Deployed**: 0273459 (2026-10-07)

## Description
On the What's New page (SP-046), each change is currently shown as its description followed by a small muted SP label. Show the story number first and the description after it, in the form "SP-NNN: description" (for example "SP-002: Removing a Receipt"), so the list reads like the backlog.

## Acceptance Criteria
- [x] Each change on `/whats-new` is rendered as `SP-NNN: <description>`, with the story number before the description (e.g. `SP-002: Removing a Receipt`).
- [x] A change that has no `sp` value is rendered as just its description, with no `SP-` prefix and no stray colon.
- [x] The `SP-NNN:` prefix is rendered inside the existing `release-sp` span (muted, smaller text) and the description follows it in the normal text style, so a test can locate the prefix. At a 375px-wide viewport the What's New content wraps: no change line extends past the viewport's right edge (checked in the browser pane). Horizontal scroll caused by the navigation bar is existing behavior and is handled separately in SP-050.
- [x] The release heading (version and date), the newest-first order, the empty-state message and the "no JavaScript" rule are unchanged.
- [x] The existing test in `tests/test_releases.py` that checks the SP number on the page is updated, and a test covers both cases: with an `sp` the text `SP-050: Twelfth release change` appears in that order, and a change without `sp` shows only its text.
- [x] The full test suite passes.

## Notes / Context
- UI-only change: `templates/whats_new.html` (the `<li>` inside the changes loop) and, if needed, the `.release-sp` rule in `static/css/style.css`. No change to `releases.json`, `app/releases.py` or any route.
- Independent of SP-048 (the backfill script); that story only adds data and has no UI.
- The BehaviorSpec scenario BS-051 mentions "(with the SP number where known)"; update its wording at `/sdlc-done` time to say the SP number is shown first ("SP-NNN: description").

### Out of scope
- Horizontal page scroll at 375px caused by the navbar (SP-050).
- Rewording the release texts themselves (they are SP titles).
- Linking the SP number to the backlog file.

## Implementation Notes
Completed 2026-10-07.

- `templates/whats_new.html` - each change now renders as `SP-NNN: description`: the `SP-NNN:` prefix (colon included) is inside the existing `release-sp` span, followed by the description. The colon is inside the `if`, so a change with no `sp` shows just its text. No CSS change was needed.
- `tests/test_releases.py` - updated the existing SP assertion to check the `<span class="release-sp">SP-050:</span>` markup; added `test_sp_number_shown_before_description` (visible text reads "SP-050: Twelfth release change", number first) and `test_change_without_sp_shows_only_text` (no `SP-`, no span, no stray colon).
- `Specification/BehaviorSpec.md` - BS-051 reworded: each change reads "SP-NNN: description"; a change with no SP number shows just its description.
- No migrations, data changes or new dependencies.
- 375px check: rendered the real What's New page (real `releases.json` and CSS, 10 releases, 46 change lines) to a standalone file and measured it in a 375px-wide iframe in the browser pane: all 46 lines start with `SP-NNN:` (prefix muted, 14px), no change line extends past the right edge (rightmost content edge 367px). The page as a whole still scrolls horizontally (563px) because of the navigation bar, existing behavior now tracked as SP-050.
- Tests: 2 added and 1 updated; full suite 655 passed.
