# SP-014: Beautify Login Page

**Priority**: Low
**Status**: Ready

## Description
Make the login page more visually appealing by restyling the email and OTP code text inputs. The inputs should resemble the search input already used on the History page.

## Acceptance Criteria
- [ ] The email input on `/login` uses the same visual style as the History page's search input (padding, border, border-radius, font)
- [ ] The OTP code input on `/verify` uses the same visual style as the History page's search input
- [ ] Focus state on both inputs matches the search input's focus state (border color change on focus)
- [ ] No functional change — email submission and OTP verification behave exactly as before

## Notes / Context
- Reuse the existing `.search-input` class from `static/css/style.css` (added for SP-004) rather than inventing new styles.
- Both inputs currently have no CSS class at all — `templates/login.html`'s email `<input>` and `templates/verify.html`'s code `<input>` just rely on unstyled browser defaults. The change is adding `class="search-input"` to each.

## Implementation Notes
_Filled in when the work is done, before moving to backlog/done/._
