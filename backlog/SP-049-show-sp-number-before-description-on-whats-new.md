# SP-049: Show SP Number Before the Description on the What's New Page

**Priority**: Low
**Status**: Open

## Description
On the What's New page (SP-046), each change is currently shown as its description followed by a small muted SP label. Show the story number first and the description after it, in the form "SP-NNN: description" (for example "SP-002: Removing a Receipt"), so the list reads like the backlog.

## Acceptance Criteria
- [ ] Each change on `/whats-new` is rendered as `SP-NNN: <description>`, with the story number before the description (e.g. `SP-002: Removing a Receipt`).
- [ ] A change that has no `sp` value is rendered as just its description, with no `SP-` prefix and no stray colon.
- [ ] The SP number part keeps a visually distinct (muted/smaller) style, or the style is removed if it no longer looks right; either way the line stays readable on a narrow screen.
- [ ] The release heading (version and date), the newest-first order, the empty-state message and the "no JavaScript" rule are unchanged.
- [ ] The existing test in `tests/test_releases.py` that checks the SP number on the page is updated, and a test covers both cases: with an `sp` the text `SP-050: Twelfth release change` appears in that order, and a change without `sp` shows only its text.
- [ ] The full test suite passes.

## Notes / Context
- UI-only change: `templates/whats_new.html` (the `<li>` inside the changes loop) and, if needed, the `.release-sp` rule in `static/css/style.css`. No change to `releases.json`, `app/releases.py` or any route.
- Independent of SP-048 (the backfill script); that story only adds data and has no UI.
- The BehaviorSpec scenario BS-051 mentions "(with the SP number where known)"; update its wording at `/sdlc-done` time to say the SP number is shown first ("SP-NNN: description").

### Out of scope
- Rewording the release texts themselves (they are SP titles).
- Linking the SP number to the backlog file.

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
