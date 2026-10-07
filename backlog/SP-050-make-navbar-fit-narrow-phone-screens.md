# SP-050: Make the Navigation Bar Fit Narrow Phone Screens

**Priority**: Low
**Status**: Open

## Description
On a phone-width screen (375px) the navigation tabs in `templates/base.html` are wider than the viewport (measured at 564px for a logged-in user), so every logged-in page scrolls horizontally. Make the navigation fit or wrap so that no page has horizontal scroll at 375px. This was found while checking SP-049; it is existing behavior, not caused by that story.

## Acceptance Criteria
- [ ] At a 375px-wide viewport, a logged-in non-admin user sees no horizontal page scroll on any page: the document's `scrollWidth` is not greater than the viewport width (measured on at least History, Statistics and What's New).
- [ ] The same holds for an admin, whose navbar has the most tabs (adds LLM Usage, Users and Categories): `scrollWidth` is not greater than the viewport width at 375px.
- [ ] Every tab remains visible and clickable at 375px (the tabs wrap onto further rows instead of being clipped, hidden or scrolled sideways), and no tab text is cut off.
- [ ] The nav links, their order, admin-only visibility, the Contact and Log out links, and the active-tab highlighting are unchanged.
- [ ] The desktop layout (above the existing 768px breakpoint) is unchanged.
- [ ] No JavaScript is added; the fix is CSS (and, only if needed, markup) in `static/css/style.css` / `templates/base.html`.
- [ ] A test confirms the mobile rule is in the stylesheet, and the 375px measurements above are recorded in the Implementation Notes.
- [ ] The full test suite passes.

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
_Filled in when the work is done, before moving to backlog/done/._
