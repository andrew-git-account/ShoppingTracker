# SP-014: Beautify Login Page

**Priority**: Low
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-015, BehaviorSpec.md#BS-016 (login email input and verify OTP input restyled to match History search input)
**Deployed**: b6f3230 (2026-08-19)

## Description
Make the login page more visually appealing by restyling the email and OTP code text inputs. The inputs should resemble the search input already used on the History page.

## Acceptance Criteria
- [x] The email input on `/login` uses the same visual style as the History page's search input (padding, border, border-radius, font)
- [x] The OTP code input on `/verify` uses the same visual style as the History page's search input
- [x] Focus state on both inputs matches the search input's focus state (border color change on focus)
- [x] No functional change — email submission and OTP verification behave exactly as before

## Notes / Context
- Reuse the existing `.search-input` class from `static/css/style.css` (added for SP-004) rather than inventing new styles.
- Both inputs currently have no CSS class at all — `templates/login.html`'s email `<input>` and `templates/verify.html`'s code `<input>` just rely on unstyled browser defaults. The change is adding `class="search-input"` to each.

## Implementation Notes
_Completed 2026-08-17._

- `templates/login.html` — added `class="search-input"` to the `#email` input.
- `templates/verify.html` — added `class="search-input"` to the `#code` input.
- No new CSS — reused the existing `.search-input` class (and its `:focus` state) from `static/css/style.css`, added originally for SP-004.
- `tests/test_auth.py` — added `test_login_email_input_has_search_input_class` and `test_verify_code_input_has_search_input_class`. Existing auth tests (`test_allowed_email_redirects_to_verify`, OTP verification tests) continued to pass unchanged, confirming no functional regression.
- No migrations or data changes.
- Tests: 2 added, 166 passed (full suite).
