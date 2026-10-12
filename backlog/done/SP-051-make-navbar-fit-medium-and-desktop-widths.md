# SP-051: Make the Navigation Bar Fit Medium and Desktop Widths

**Priority**: Low
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-052

## Description
On screens wider than 768px the navigation tabs still never wrap. An admin's nine-tab navbar is about 1195px wide, which is wider than its 1100px container, so at a 1200px viewport the last tab ends at 1253px and the page scrolls sideways. A normal user's six tabs are about 807px wide and are likely to overflow at tablet widths between 769px and roughly 840px. Make the tabs wrap whenever they do not fit, at every screen width, without changing the layout where they already fit on one row. This was found while checking SP-050, which fixed widths up to 768px; it is existing behavior, not caused by that story.

## Acceptance Criteria
- [x] For a logged-in admin (nine tabs), the document's `scrollWidth` is not greater than the viewport width at each of 800px, 1024px, 1200px and 1440px, on at least History and What's New.
- [x] For a logged-in non-admin user (six tabs), the document's `scrollWidth` is not greater than the viewport width at each of 769px, 800px, 1024px and 1200px, on at least History and What's New.
- [x] Every tab stays visible and unclipped at those widths (each tab's bounding box lies within the viewport and no tab text is cut off); tabs wrap onto a further row only when they do not fit within the page container.
- [x] Where the tabs fit within the page container on one row (a non-admin user at 900px and wider, which leaves a safe margin over the roughly 840px at which six tabs just fit), the navbar looks exactly as before: one row, same tab positions, same spacing. An admin's nine tabs (about 1195px) are wider than the 1100px page container (1068px inside its padding), so they wrap onto a second row at every width above 768px; this is accepted.
- [x] The nav links, their order, admin-only visibility, the Contact and Log out links, and the active-tab highlighting are unchanged; the mobile layout from SP-050 (768px and below) is unchanged.
- [x] No JavaScript is added; the fix is CSS in `static/css/style.css`.
- [x] The test in `tests/test_navbar.py` that asserts the desktop `.nav-tabs` rule has no `flex-wrap` (added by SP-050) is updated to match the new behavior, and a test confirms the wrapping rule applies outside the mobile media query as well.
- [x] The measurements above are recorded in the Implementation Notes, and the full test suite passes.

## Notes / Context
- Measured while checking SP-050 (admin, 1200px viewport): tab row about 1195px wide, first tab at 58px, last tab ends at 1253px, `scrollWidth` 1254px. Non-admin tab row about 807px wide. The overflow ranges for other widths are estimates; criteria 1-2 are the actual check.
- Why the admin wraps at every desktop width: `.container` is capped at `max-width: 1100px` with 16px side padding, leaving 1068px for the tabs, and the admin's tab row is about 1195px. Flex wrapping is decided by the container's width, so after the fix an admin's navbar is two rows even on a very wide screen. Before the fix it was one row that overflowed the container (visible overflow to the right, and a sideways page scroll below about 1250px). Keeping one row for admins would need tighter desktop link padding/gap (about 144px of savings, e.g. 24px to 16px horizontal padding) and is a deliberate non-goal of this story.
- A non-admin's six tabs (about 807px) fit within the container once the viewport is about 840px or wider, so their navbar stays unchanged there.
- Cause: `.nav-tabs` in `static/css/style.css` is a `display: flex` row with no wrapping, and its links use `white-space: nowrap`. SP-050 added `flex-wrap: wrap` only inside the `@media (max-width: 768px)` block.
- Likely fix: add `flex-wrap: wrap` (and a suitable row gap) to the base `.nav-tabs` rule instead of only the mobile query. Wrapping only takes effect when the tabs do not fit, so widths where they already fit are unchanged. Check that the wrapped admin navbar still looks tidy at 800-1200px (for example, whether `justify-content: center` or the desktop left-aligned start looks better) and adjust only if needed.
- SP-050's `test_desktop_navbar_rules_are_unchanged` in `tests/test_navbar.py` currently requires the top-level `.nav-tabs` rule to have no `flex-wrap`; it must be revised as part of this story.
- Measuring: render the pages with the Flask test client and the real CSS into standalone HTML files, serve them locally and load them into iframes of the exact widths (as done for SP-049 and SP-050), so no login is needed.

### Out of scope
- A hamburger or collapsible menu.
- Redesigning the navbar, renaming tabs or changing their order.
- Any layout issue other than the navbar overflowing its container or the viewport.

## Implementation Notes
Completed 2026-10-07.

- `static/css/style.css` - the base `.nav-tabs` rule now has `flex-wrap: wrap` and `gap: var(--spacing-sm) var(--spacing-md)` (8px between wrapped rows, the original 16px between tabs on a row), with a comment explaining why. Wrapping has no effect while the tabs fit on one row, so those layouts are unchanged; an admin's nine tabs (about 1195px) never fit the 1100px container (1068px inside padding), so they wrap onto a second row at every width above 768px, as accepted in the story. The SP-050 `@media (max-width: 768px)` rules are untouched. No markup or JavaScript change.
- `tests/test_navbar.py` - replaced SP-050's "desktop rule must not wrap" test with `test_base_nav_tabs_rule_wraps_outside_the_mobile_query` and `test_desktop_link_style_and_column_gap_unchanged` (row gap 8px / column gap 16px, link padding `lg`, `nowrap`), and added `test_mobile_layout_rules_from_sp_050_are_untouched`. The links/order/highlight tests are unchanged.
- `Specification/BehaviorSpec.md` - BS-052 reworded and renamed "Navigation Bar Wraps Instead of Overflowing": it previously said the navigation is a single row above 768px, which this story changes.
- `CLAUDE.md` - SP counter 051 (the story was created before this commit).
- No migrations, data changes or new dependencies.
- Measured with the real pages (History and What's New, normal user and admin, real CSS, loaded into iframes of exact widths in the browser pane), before and after: admin at 800/1024/1200px was 1211-1254px wide (scrolled sideways) and now fits at every width with all tabs inside the viewport, no clipped text and 2 rows (also at 1440px, which used to fit as one row overflowing the container); a normal user at 769 and 800px was 822px wide and now fits with 2 rows; a normal user at 900, 1024 and 1200px has identical tab positions before and after (one row); at 375px both roles are identical to before (2 and 3 rows). A 1200px screenshot of the admin navbar shows a tidy two-row, left-aligned layout.
- Found and fixed along the way (committed separately): SP files edited with PowerShell `Set-Content -Encoding utf8` had gained a UTF-8 BOM, which made `backfill_releases.py` fail on the real history once the SP-046 to SP-050 deploy commit existed. The BOM was stripped from SP-046 to SP-051 and the script now reads SP files with `utf-8-sig` (with a regression test).
- Tests: 3 navbar tests changed/added (9 in the file); full suite 677 passed.
