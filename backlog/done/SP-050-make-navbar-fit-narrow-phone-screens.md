# SP-050: Make the Navigation Bar Fit Narrow Phone Screens

**Priority**: Low
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-052

## Description
On a phone-width screen (375px) the navigation tabs in `templates/base.html` are wider than the viewport (measured at 564px for a logged-in user), so every logged-in page scrolls horizontally. Make the navigation fit or wrap so that no page has horizontal scroll at 375px. This was found while checking SP-049; it is existing behavior, not caused by that story.

## Acceptance Criteria
- [x] At a 375px-wide viewport, a logged-in non-admin user sees no horizontal page scroll on any page: the document's `scrollWidth` is not greater than the viewport width (measured on at least History, Statistics and What's New).
- [x] The same holds for an admin, whose navbar has the most tabs (adds LLM Usage, Users and Categories): `scrollWidth` is not greater than the viewport width at 375px.
- [x] Every tab remains visible and clickable at 375px (the tabs wrap onto further rows instead of being clipped, hidden or scrolled sideways), and no tab text is cut off.
- [x] The nav links, their order, admin-only visibility, the Contact and Log out links, and the active-tab highlighting are unchanged.
- [x] The desktop layout (above the existing 768px breakpoint) is unchanged.
- [x] No JavaScript is added; the fix is CSS (and, only if needed, markup) in `static/css/style.css` / `templates/base.html`.
- [x] A test confirms the mobile rule is in the stylesheet, and the 375px measurements above are recorded in the Implementation Notes.
- [x] The full test suite passes.

## Notes / Context
- Cause: `.nav-tabs` in `static/css/style.css` is a flex row with no wrapping, and its links use `white-space: nowrap`, so with 5 to 9 tabs plus padding the row is wider than a phone. The existing `@media (max-width: 768px)` block only centers the tabs and does not allow them to wrap.
- Likely fix: allow wrapping (`flex-wrap: wrap`) and tighten the gap and link padding inside the existing mobile media query. A collapsing hamburger menu is out of scope (it would need JavaScript or a checkbox hack).
- Measuring at exactly 375px: the browser pane's mobile emulation can report a wider layout viewport, so measure inside a 375px-wide iframe (as done for SP-049) or in a real device-size window. The pages need a logged-in session, so either log in in the browser pane or render the page to a standalone file with the test client.
- Found while checking SP-049: with the What's New content itself fitting, only the navbar items extended past the viewport (rightmost edges 450px and 564px).

### Out of scope
- A hamburger or collapsible menu.
- Redesigning the navbar, renaming tabs or changing their order.
- Any other mobile layout work beyond horizontal overflow.

## Implementation Notes
Completed 2026-10-07.

- `static/css/style.css` - inside the existing `@media (max-width: 768px)` block, `.nav-tabs` now has `flex-wrap: wrap` and `gap: var(--spacing-sm)`, and `.nav-tabs a` gets tighter padding (`sm md` instead of the desktop `sm lg`). Nothing outside the media query changed, so the desktop navbar is untouched. No markup, JavaScript or route changes.
- `tests/test_navbar.py` (new) - 7 tests: the wrapping rule and link padding are inside the 768px media block; the top-level (desktop) `.nav-tabs` rules still have no `flex-wrap`, the `lg` padding and `nowrap`; nav links and order unchanged for a normal user (6 tabs) and an admin (9 tabs); only the current tab is highlighted; the logged-out page has no tabs.
- `Specification/BehaviorSpec.md` - added BS-052 (navigation bar wraps on narrow screens).
- No migrations, data changes or new dependencies.
- Measured at exactly 375px (History, Statistics and What's New rendered with the real templates and CSS for a normal user and an admin, loaded in a 375px iframe in the browser pane): before the fix `scrollWidth` was 556px (user) and 738px (admin), tabs overflowing; after the fix every page fits (375px, 360px on What's New), all tabs lie inside the viewport, no tab text is clipped, and the tabs take 2 rows (user, 6 tabs) or 3 rows (admin, 9 tabs). A mobile screenshot of the admin navbar confirmed the layout. At a 1200px viewport the navbar is identical before and after (one row, 24px link padding, `nowrap`, same positions).
- Observation, out of scope: at 1200px the admin's nine-tab navbar is already wider than the viewport (last tab ends at 1253px) because the desktop row does not wrap; this is the same before and after this change and is not covered by this story.
- Tests: 7 added; full suite 674 passed.
