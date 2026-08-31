# Behavior Specification — Shopping Tracker

This document defines the expected system behavior for each scenario in the core workflow.
Each scenario is named and written from the user's perspective so it can be verified manually
or referenced in automated tests.

---

## BS-001: Upload a Valid Receipt

**Scenario:** User uploads a supported image file of a receipt.

**Given:** The user is on the Upload page.  
**When:** They select a JPG, JPEG, or PNG file under 5 MB and click "Upload Receipt."  
**Then:**
- A success flash message appears confirming the upload.
- The receipt appears at the top of the History page.
- All extracted fields are stored: store name, purchase date, items (name, price, quantity, category), currency, subtotal, tax, discount, total.
- The uploaded image file is deleted from `uploads/` after processing.

---

## BS-002: Upload File with Unsupported Format

**Scenario:** User tries to upload a non-image file (e.g. PDF, DOCX).

**Given:** The user is on the Upload page.  
**When:** They select a file with an extension other than JPG, JPEG, or PNG and submit.  
**Then:**
- An error flash message is shown explaining the file type is not supported.
- No receipt is saved to the database.
- The user remains on the Upload page.

---

## BS-003: Upload File Exceeding Size Limit

**Scenario:** User uploads an image that is too large for the Claude API.

**Given:** The user is on the Upload page.  
**When:** They upload an image whose base64-encoded size would exceed 5 MB.  
**Then:**
- The system automatically compresses the image before sending it to the LLM.
- Processing continues as normal — the user sees the same success flow as BS-001.
- The user never sees an error about image size.

---

## BS-004: LLM Cannot Read the Receipt

**Scenario:** The receipt image is unreadable (blurry, wrong side, not a receipt).

**Given:** The user uploads an image.  
**When:** The LLM returns no recognizable receipt data.  
**Then:**
- An error flash message is shown explaining that the receipt could not be processed.
- No receipt is saved to the database.
- The user is prompted to try again.

---

## BS-005: LLM Cannot Determine Currency

**Scenario:** The receipt has no visible currency symbol or country indicator.

**Given:** A readable receipt is uploaded.  
**When:** The LLM cannot identify the currency.  
**Then:**
- The receipt is saved with currency defaulted to `"USD"`.
- All prices on the History page display with the `USD` code.

---

## BS-006: View Receipt History

**Scenario:** User navigates to the History page.

**Given:** At least one receipt has been saved.  
**When:** The user clicks the "History" tab.  
**Then:**
- All saved receipts are listed, most recent at the top.
- Each receipt shows: store name, purchase date, and total (collapsed by default).
- Clicking a receipt expands it to show: item list (name, price, quantity, category), subtotal, tax, discount, total, and the date it was saved.

---

## BS-007: History Page — No Receipts

**Scenario:** User opens History when no receipts have been uploaded yet.

**Given:** The database is empty (or all receipts have been deleted).  
**When:** The user navigates to `/history`.  
**Then:**
- A "No receipts yet" message is shown.
- No receipt cards are rendered.

---

## BS-008: Delete a Receipt

**Scenario:** User removes a receipt they no longer want.

**Given:** At least one receipt is visible in History.  
**When:** The user clicks the "×" button on a receipt and confirms the browser dialog.  
**Then:**
- The receipt disappears from the History list immediately.
- A "Receipt removed" flash message is shown.
- The receipt is marked `is_deleted: true` in the database (not permanently erased).

---

## BS-009: Delete a Receipt — Cancel Confirmation

**Scenario:** User clicks "×" but then cancels the confirmation dialog.

**Given:** At least one receipt is visible in History.  
**When:** The user clicks "×" and dismisses the browser confirm dialog.  
**Then:**
- Nothing changes — the receipt remains in the list.
- No request is sent to the server.

---

## BS-010: Currency Displayed Per Receipt

**Scenario:** Receipts with different currencies are stored and shown correctly.

**Given:** One receipt with `USD` and one with `EUR` are in the database.  
**When:** The user opens History.  
**Then:**
- The USD receipt shows all prices with `USD`.
- The EUR receipt shows all prices with `EUR`.
- No receipt shows a hardcoded `$` symbol.

---

## BS-011: Item Category Assigned

**Scenario:** LLM assigns a category to each line item.

**Given:** A readable receipt is uploaded.  
**When:** The LLM returns a category for each item from the predefined list.  
**Then:**
- Each item is saved with the assigned category.
- The category badge is visible next to each item on the History page.

---

## BS-012: Item Category Falls Back to "Other"

**Scenario:** LLM returns an unrecognized or missing category.

**Given:** A readable receipt is uploaded.  
**When:** The LLM returns a category that is not in the predefined list, or omits the field.  
**Then:**
- The item is saved with category `"Other"`.
- `"Other"` is shown as the category badge on the History page.

---

## BS-013: Unauthenticated Access Redirected to Login

**Scenario:** A visitor tries to access the app without being logged in.

**Given:** The user is not authenticated (no active session).
**When:** They navigate to `/`, `/upload`, or `/history`.
**Then:**
- They are redirected to `/login`.
- The requested page is not shown.

---

## BS-014: Login — Email Not Authorised

**Scenario:** A user enters an email that is not in the allowed list.

**Given:** The user is on the login page (`/login`).
**When:** They submit an email address not on the allowed users list.
**Then:**
- An error message is shown: "Email address not authorised".
- The user stays on the login page.
- No OTP is generated.

---

## BS-015: Login — Allowed Email Triggers OTP

**Scenario:** A user enters an allowed email address.

**Given:** The user is on the login page (`/login`).
**When:** They submit an email address that is on the allowed users list.
**Then:**
- A 5-digit OTP code is generated and written to `server.log`.
- A flash message confirms that a code has been sent.
- The user is redirected to the code-entry page (`/verify`).

---

## BS-016: Login — Correct OTP Code Grants Access

**Scenario:** A user enters the correct OTP code on the verify page.

**Given:** The user is on `/verify` after requesting a code.
**When:** They enter the correct 5-digit code within 10 minutes.
**Then:**
- Their session is marked as authenticated.
- They are redirected to the Upload page.
- All protected pages are now accessible.

---

## BS-017: Login — Wrong OTP Code Rejected

**Scenario:** A user enters an incorrect OTP code.

**Given:** The user is on `/verify` after requesting a code.
**When:** They enter a code that does not match the generated OTP.
**Then:**
- An error message is shown: "Invalid code, please try again".
- The user stays on the verify page.
- Their session is not marked as authenticated.

---

## BS-018: Logout

**Scenario:** An authenticated user logs out.

**Given:** The user is logged in and viewing any page.
**When:** They click "Log out" in the navigation bar.
**Then:**
- Their session is cleared.
- They are redirected to `/login`.
- Navigating to any protected page redirects back to `/login`.

---

## BS-019: History Page Groups Receipts by Month

**Scenario:** User views the history page with receipts from multiple months.

**Given:** The user has uploaded multiple receipts with different purchase dates spanning several months.
**When:** They navigate to the History page (`/history`).
**Then:**
- Receipts are grouped under month headers in `YYYY-MM` format (e.g., "2026-05").
- Month groups appear in descending order (newest month first).
- Within each month group, receipts are sorted by purchase date descending (newest receipt first within the group).
- Each group displays all receipts from that month.
- If a receipt has no purchase date, it is grouped by its saved timestamp date.

---

## BS-020: View Shopping Statistics by Month

**Scenario:** User checks how much they spent per category in a given month.

**Given:** The user has uploaded receipts spanning one or more months.
**When:** They navigate to the Statistics page (`/statistics`) and select a month from the list.
**Then:**
- The month list shows every month that has receipts, newest first.
- The most recent month is selected by default when no month is chosen.
- For the selected month, each spending category is listed with the total amount spent and the percentage of that month's spend it represents.
- Selecting a different month from the list updates the category breakdown to that month's data.

---

## BS-021: Statistics Page — No Receipts

**Scenario:** User opens Statistics before uploading any receipts.

**Given:** The database is empty (or all receipts have been deleted).
**When:** The user navigates to `/statistics`.
**Then:**
- A "No shopping data yet" message is shown instead of a month list.
- No category breakdown is rendered.

---

## BS-022: Statistics Amounts Grouped by Currency

**Scenario:** A selected month contains receipts in more than one currency.

**Given:** The selected month has at least one receipt in one currency (e.g. `CHF`) and at least one receipt in a different currency (e.g. `USD`).
**When:** The user views the Statistics page for that month.
**Then:**
- Categories are grouped under a separate block per currency, each labeled with its currency code and its own subtotal.
- Each category's percentage is calculated relative to its own currency's subtotal, not a combined total across currencies.
- Percentages within each currency group sum to ~100%.

---

## BS-023: Search for Items Across Receipts

**Scenario:** User searches for an item name to compare prices across receipts.

**Given:** The user has uploaded receipts containing items whose names match a search term (at least 3 characters), possibly from different stores and dates.
**When:** They type the term into the search box on the History page and press Enter or click "Search".
**Then:**
- Every matching item, from every receipt, is listed — not receipt cards, individual line items.
- The match is case-insensitive and matches anywhere in the item name (substring match).
- Each result shows the item name, price, store name, and purchase date.
- No subtotal or total amount is shown for the result set.
- Results are ordered by item name, then price-per-unit (see BS-027), so identical items are easy to compare side by side with the cheapest first.

---

## BS-024: Search Term Too Short

**Scenario:** User submits a search term under the minimum length.

**Given:** The user is on the History page.
**When:** They submit a search term of 1 or 2 characters.
**Then:**
- No search is performed.
- A message tells the user the minimum length is 3 characters.
- The normal grouped-by-month History view is shown, unaffected.
- The typed term remains in the search box.

---

## BS-025: Search With No Matches

**Scenario:** User searches for a term that matches no items.

**Given:** The user is on the History page.
**When:** They submit a search term (3+ characters) that matches no item name in any receipt.
**Then:**
- A "No matches found" message is shown instead of an empty page.
- No receipt or item data is rendered.

---

## BS-026: Price-Per-Unit Shown on History

**Scenario:** User views their receipt history and wants to compare prices for items sold by weight versus by piece.

**Given:** At least one receipt has been saved, with items that may or may not have a purchased amount/unit (weight or piece count) extracted from the receipt.
**When:** The user views the History page.
**Then:**
- Each item shows a price-per-unit value alongside its existing total price — e.g. "CHF 19.49/kg" for a weighed item, "CHF 2.20/piece" for a counted item.
- The price-per-unit is derived from the item's existing total price divided by its purchased amount — never trusted from a printed "unit price" on the receipt, since that is not reliably present for weighed items.
- An item with no extracted amount (including receipts saved before this feature existed) is treated as 1 piece, so its price-per-unit equals its total price.

---

## BS-027: Price-Per-Unit Ranks Search Results

**Scenario:** User searches for an item to find the cheapest option across receipts.

**Given:** The user has uploaded receipts containing the same kind of item at different purchased amounts and prices (e.g. one store's item sold in a larger amount at a lower total price but a worse rate, another in a smaller amount at a higher total price but a better rate).
**When:** They search for that item on the History page.
**Then:**
- Each result shows its price-per-unit (e.g. "CHF 1.50/kg"), not just its total line price.
- Results for the same item name are ordered by price-per-unit ascending, so the actual cheapest option per unit appears first — not the one with the lowest raw total price.

---

## BS-028: Item Extraction Handles Per-Item Discount Columns

**Scenario:** User uploads a receipt where some items have a per-item discount/savings column in addition to the regular price and total columns (e.g. a "Gespart"/"Savings" column).

**Given:** The user uploads a receipt with this layout, where at least one item's price was reduced by a per-item discount, and the receipt includes a trailing non-quantity code column (e.g. a tax/VAT-rate category code) unrelated to how many were purchased.
**When:** The receipt is processed.
**Then:**
- Each item's extracted price reflects the actual amount charged for that item after its own discount, not a pre-discount unit price and not a neighboring item's price.
- No duplicate item lines are fabricated because of the extra discount column.
- Item quantity is taken only from an actual quantity/count column — a trailing tax/category code column is never interpreted as quantity.
- The sum of extracted item prices reconciles with the receipt's total amount, within tax and discount tolerance.

---

## BS-029: Total Receipts Count Excludes Deleted Receipts

**Scenario:** User views the receipt count on the History page after deleting a receipt.

**Given:** The user has one or more receipts, and at least one has been deleted (soft-deleted).
**When:** The user views `/history`.
**Then:**
- The "Total receipts: N" count reflects only non-deleted receipts.
- N equals the number of receipt cards actually displayed on the page.
- Deleting a receipt decreases the displayed count by 1 immediately, with no stale value and no page-reload quirk.

---

## BS-030: Extraction Self-Corrects on a Mismatched Total

**Scenario:** User uploads a receipt where the first extraction attempt's item prices don't add up to the receipt's own printed total (e.g. a quantity/unit-price sub-line was attributed to the wrong item row).

**Given:** The user uploads a receipt image.
**When:** The initial extraction's items don't reconcile with the receipt's `total_amount` (checking both a VAT-inclusive and a VAT-exclusive formula, within a small tolerance).
**Then:**
- The system re-examines the same image once more, telling the model specifically what didn't add up (the expected total, what was computed, and the gap) so it can look for a misattributed price or quantity.
- If the second attempt reconciles, the corrected data is what gets saved.
- If the second attempt still doesn't reconcile, its result is no longer saved silently — see BS-036, which routes it to review instead.
- No third attempt is made, and no receipt upload takes noticeably longer except for the one retry's extra round-trip.

---

## BS-031: Receipts Are Scoped to the Logged-In User

**Scenario:** Two different allowed users are logged into the app with their own receipts.

**Given:** User A has uploaded receipts, and User B (a different allowed email) has uploaded separate receipts of their own.
**When:** User A views History, Statistics, or searches for an item; or attempts to delete or view the detail page of one of User B's receipts by ID.
**Then:**
- History, Statistics, and search results only ever show User A's own receipts — User B's store names, items, and totals never appear, and the "Total receipts" count only reflects User A's receipts.
- A receipt User A uploads is recorded as owned by User A's email.
- Attempting to delete or view the detail page of a receipt owned by User B fails exactly the same way as if that receipt ID didn't exist at all (the same "Receipt not found" flash) — User A can't tell the difference between "doesn't exist" and "belongs to someone else."
- A session authenticated before this feature existed (missing the new per-user identity) is treated as not fully logged in and is sent back to a fresh login, rather than showing an empty or broken page.

---

## BS-032: LLM Usage Page Is Admin-Only

**Scenario:** A logged-in user, admin or not, interacts with the LLM Usage page.

**Given:** The user is logged in, and their allowed-users record is flagged either as admin or not.
**When:** A non-admin user navigates directly to `/llm-usage`, or an admin views the page and applies the User and/or Month filters.
**Then:**
- A non-admin never sees the "LLM Usage" nav link, and if they navigate to `/llm-usage` directly by URL, they're redirected away with a "you do not have access" message rather than seeing any usage data.
- An admin sees total requests, total cost, retry rate, and success rate for every LLM call logged so far (across all users, not just their own — this page is for cost monitoring, unlike the per-user-scoped receipt data).
- Selecting a specific user and/or a specific month narrows the totals to just that scope; leaving either filter unset shows all users and/or all time.
- With no LLM calls logged yet, the page shows an empty state instead of zeros with no explanation.

---

## BS-033: Admins Manage Users, With a Last-Admin Safeguard

**Scenario:** An admin adds, promotes, and blocks users from the admin-only Users page.

**Given:** The admin is on `/users`, which lists every allowed user with their admin and blocked status.
**When:** The admin adds a new email, toggles a user's admin flag, or toggles a user's blocked flag — including on themselves, and including when they are the only active admin.
**Then:**
- Adding an email already in the list (case-insensitive) is rejected with a clear error instead of creating a duplicate; a genuinely new email is added as a regular, unblocked, non-admin user.
- Toggling admin or blocked status updates immediately and is reflected in the list.
- A blocked user can no longer request a login code — attempting to log in with a blocked email is rejected the same way an unrecognized email is — but their existing session (if any) keeps working until it naturally ends; blocking doesn't force them out mid-session.
- Unblocking a user immediately restores their ability to log in.
- Removing the admin flag from a user, or blocking a user, is refused with a clear error if doing so would leave zero active (admin AND not blocked) admins — this applies the same way whether the admin is acting on themselves or on someone else, so the app can never end up with no one able to manage users.
- A non-admin who navigates to `/users` directly, or POSTs to any of its action endpoints, is denied server-side the same way as on the LLM Usage page — not just kept from seeing the nav link.

---

## BS-034: Edit a Saved Receipt

**Scenario:** A user corrects mistakes in an already-saved receipt.

**Given:** The user has at least one saved receipt in History.
**When:** They click "Edit" on a receipt card, change an item's name/category/price, the receipt's currency/total, or mark an item for removal, and save — or submit invalid data (a negative price/total, or every item marked for removal), or try to edit a receipt ID that isn't theirs.
**Then:**
- The edit form opens pre-filled with the receipt's current item names/categories/prices and its currency/total.
- Saving valid changes updates the same receipt in place (same ID, no duplicate) and the new values immediately show in History.
- Marking every item for removal is rejected — the form re-renders with an error instead of saving an empty receipt.
- A negative item price or negative total is rejected with a clear error; the form re-renders with the user's other submitted edits intact rather than reverting to the original saved values.
- Editing a receipt ID that doesn't exist, or belongs to another user, fails the same way as viewing/deleting one does — the same "Receipt not found" flash, indistinguishable from a truly nonexistent ID.

---

## BS-035: Review a Receipt Before Saving

**Scenario:** A user wants to double-check the extracted data before it's saved.

**Given:** The user is on the upload page, with an "Edit before saving" checkbox available (unchecked by default).
**When:** They upload a receipt with the checkbox checked, then review the resulting page and either save, discard, or submit invalid corrections.
**Then:**
- With the checkbox left unchecked, upload behaves exactly as before — the receipt is saved immediately and the user lands on History.
- With the checkbox checked, after extraction the user lands on a "Review Receipt" page pre-filled with the extracted item names/categories/prices and the receipt's currency/total — nothing is saved to permanent storage yet.
- Saving from that page creates the receipt for the first time (a new ID, now visible in History), reusing the same non-negative-price/total and "at least one item" checks as editing an already-saved receipt; an invalid submission re-renders the review page with the user's edits preserved instead of losing them.
- An explicit "Discard" action deletes the pending review data without ever saving it.
- The review page is reachable only by the user who uploaded it — visiting another user's still-pending review link fails the same way an unknown link would.

---

## BS-036: Force Edit on Bad Extraction

**Scenario:** Extraction produces data that's actually wrong, rather than just something the user opted to double-check.

**Given:** The user uploads a receipt, with the "Edit before saving" checkbox either checked or unchecked.
**When:** The extracted data fails validation (e.g. a negative total or negative item price), or the reconciliation retry's second attempt still doesn't reconcile with the receipt's printed total.
**Then:**
- Instead of showing an error and discarding the upload (the old behavior for invalid data) or saving silently anyway (the old behavior for an unreconciled retry), the user lands on the same "Review Receipt" page BS-035 describes, pre-filled with whatever was actually extracted - including the bad values, so the user can see and fix exactly what's wrong.
- The flash message explains why review is needed, distinctly for each reason: a validation problem ("This receipt has a problem — please review and fix it before saving.") versus an unverified total ("We couldn't fully verify this receipt's totals — please double-check the items and total before saving.").
- This happens whether or not the "Edit before saving" checkbox was checked - an actual data problem always wins over the neutral "review before saving" preference.
- A receipt whose data is both valid and reconciled still saves immediately exactly as before, when the checkbox isn't checked.
- Saving from this page behaves exactly like saving any other reviewed receipt (BS-035) - creates the receipt, cleans up the pending draft.

---

## BS-037: Upload a Bank or Card Statement

**Scenario:** A user wants to track expenses that only show up on a bank or credit-card statement, not as a scanned receipt.

**Given:** The user is on the "Upload Statement" page (a separate nav tab from receipt Upload), with a PDF file picker and a Bank/Credit Card type selector.
**When:** They upload a statement PDF and pick which type it is.
**Then:**
- The statement is read locally for its text (not sent to the AI as an image or document) and analyzed in a dedicated extraction call, separate from receipt extraction.
- Every transaction line on the statement becomes its own record - date, merchant/payee description, amount, currency, direction (`"debit"` for money out, `"credit"` for money in - independent of amount, which always stays positive), and a best-effort category from the same list receipt items use, defaulting to "Other" when unclear.
- These records are tagged with the statement type (bank/card) and the uploading user, and are entirely separate from receipts - not itemized into any receipt's own item list, though they do appear in History as their own statement cards (BS-038).
- The user sees a confirmation of how many transactions were found, then lands on History to see the result.
- Only PDF files are accepted; anything else is rejected with a clear error, the same way receipt upload rejects the wrong file type.
- A PDF with no extractable text (e.g. a scanned/image-only statement) is rejected with a clear error rather than silently producing nothing.

---

## BS-038: Statement Transactions Appear in History

**Scenario:** User views History after uploading one or more bank/card statements.

**Given:** The user has uploaded at least one statement (BS-037).
**When:** They view the History page (`/history`).
**Then:**
- Each statement upload appears as its own collapsed card, interleaved with receipt cards by date within the same month grouping — one card per upload, not one per transaction.
- The card's icon and label reflect the statement type — one for a bank statement, a different one for a card statement — both distinct from a receipt's icon.
- The collapsed card shows the date span of its transactions (a single date if they share one, otherwise the earliest–latest range) and a count of transactions, not a summed amount.
- Expanding the card lists every transaction it contains: date, description, category, direction (debit/credit), and amount with currency.
- A transaction already matched to a receipt is marked as linked within the list, but is still shown — never hidden or merged away, since History is a complete record rather than a de-duplicated view.
- A transaction saved before this feature existed (with no record of which statement it came from) still renders correctly, as its own single-transaction card.

---

## BS-039: Transactions and Receipts Are Automatically Matched

**Scenario:** A user has both a receipt and a statement transaction describing the same real-world purchase, and wants them recognized as the same spend rather than counted twice.

**Given:** The user has an unlinked receipt and/or unlinked statement transaction (BS-037) on their account.
**When:** They save a new receipt, edit an existing receipt, or upload a statement that creates new transactions — in either order, since a receipt or its statement line can arrive first.
**Then:**
- The newly-saved or newly-edited side is checked against the user's existing unlinked records on the other side (receipts checked against transactions, or vice versa).
- A match requires the transaction to be a debit (money out) — a credit (refund, incoming transfer, salary) is never matched automatically, only by hand (BS-043) — plus the same currency, the exact same amount, and the exact same date. No tolerance window, so a near-miss stays unlinked rather than being guessed at.
- If exactly one unlinked candidate matches, the two are linked immediately with no confirmation step.
- If more than one candidate matches on amount/date/currency, the transaction's description and each candidate's store name are compared (case-insensitive, either containing the other); the pair is linked only if this narrows it to exactly one candidate — otherwise nothing is linked, left for the user to resolve manually.
- Editing a receipt's total can newly create a match that didn't exist when it was first saved (e.g. correcting the amount to match a transaction already on file).
- A receipt or transaction already linked is never offered as a candidate for a different match — matching is strictly one-to-one.
- This happens silently, with no UI of its own; the result is visible only via the linked marker on History (BS-038).

---

## BS-040: Edit a Statement's Transactions

**Scenario:** A user notices a statement transaction has the wrong date, category, amount, or other detail, and wants to correct it without deleting and re-uploading the whole statement.

**Given:** The user has uploaded a statement, shown as a card in History (BS-038).
**When:** They click the statement card's edit icon.
**Then:**
- One edit page opens listing every transaction in that statement as its own editable row — description, date, category, direction, currency, and amount - not a separate page per transaction.
- Direction is shown as a compact debit/credit toggle rather than a dropdown; category and currency are constrained to the app's existing valid choices.
- Saving applies every row's changes together - if any row has an invalid amount, none of the rows are saved, and the form is shown again with everything the user typed still in place.
- A successful save updates each transaction in place and re-checks it against BS-039's automatic matching, so correcting a row's amount or date can newly link it to an existing receipt. An edit never breaks or re-checks a link that already exists.
- Editing is restricted to the statement's owner, the same as every other record in the app.

---

## BS-041: Delete a Statement

**Scenario:** A user uploaded a statement by mistake, or no longer wants it tracked, and wants it gone from History the same way a receipt can be removed.

**Given:** The user has a statement card in History (BS-038).
**When:** They click the card's delete (×) button and confirm.
**Then:**
- Every transaction belonging to that statement is removed from view at once, not just one - the whole card disappears from History.
- The transactions aren't permanently erased - they're marked removed, the same soft-delete already used for receipts (BS-008).
- Any transaction in the statement that had been automatically matched to a receipt (BS-039) has that match cleared as part of the deletion, so the receipt is genuinely free to match a different transaction later rather than staying tied to one that no longer shows up anywhere.
- Deleting is restricted to the statement's owner, the same as every other record in the app.

---

## BS-042: Unmatched Statement Transactions Count in Statistics

**Scenario:** A user has both scanned receipts and bank/card statement transactions, and wants their total spending to reflect both without double-counting a purchase that shows up as both a receipt and a matched transaction.

**Given:** The user has uploaded receipts and/or a statement (BS-037), and Statistics groups spend by month and currency (BS-020, BS-022).
**When:** They view Statistics for a given month.
**Then:**
- An unlinked transaction's amount is added into the same category total its own category names - a transaction and a receipt item in the same category, currency, and month combine into one total, not two separate lines.
- Only debit transactions count as spend this way - a credit (a refund, incoming transfer, salary) is never added in, even if it's unlinked.
- A month, currency, or category that only has unlinked debit transactions - no receipts at all - still shows up in Statistics with the correct total, the same as if it came from receipts.
- A transaction that's already matched to a receipt (BS-039) contributes nothing on its own - only the receipt's items are counted, so the same purchase is never counted twice.

---

## BS-043: Manually Link or Unlink a Transaction

**Scenario:** Automatic matching (BS-039) missed a real match or got one wrong, and the user wants to fix it by hand.

**Given:** The user has a transaction in History (BS-038), either linked or unlinked to a receipt.
**When:** They use the Link or Unlink icon shown on that transaction's row.
**Then:**
- An unlinked transaction's icon opens a dedicated page to search for a receipt to link - filterable by store name, a date range, and an amount range. The first time it opens, the filter is already narrowed to that transaction's own date and amount, showing only exact matches; the user can widen it from there.
- Picking a receipt from the results stages it rather than linking it immediately - see BS-045 for the full staging workflow, which also covers linking several receipts to one transaction.
- A receipt already linked to a different transaction is never offered as a choice, whether it would otherwise match the filter or not, and neither is a receipt in a different currency than the transaction.
- A linked transaction's icon unlinks it after a confirmation prompt, regardless of whether the link was made automatically or by hand - this clears every receipt currently linked to that transaction at once, not just one.
- Both actions only work on the user's own transactions and receipts.

---

## BS-044: Deleting a Receipt Clears Its Transaction Link

**Scenario:** A user deletes a receipt that's currently matched to a statement transaction (automatically via BS-039, or by hand via BS-043), and wants the transaction freed up rather than left pointing at a receipt that's gone.

**Given:** A receipt in History is linked to a transaction.
**When:** The user deletes that receipt (BS-008).
**Then:**
- The transaction's link is cleared as part of the deletion - it shows as unlinked afterward, the same as if it had never been matched.
- The receipt itself is still just marked removed, same as deleting any other receipt - this doesn't change.
- A receipt with no linked transaction deletes exactly as before - nothing extra happens.

---

## BS-045: Manually Link Several Receipts to One Transaction

**Scenario:** A few receipts were left unpaid and later settled together by a single card charge (a running tab), and the user wants to link all of them to that one transaction rather than being limited to one receipt per transaction.

**Given:** The user is on an unlinked transaction's link page (BS-043).
**When:** They pick one or more receipts from the filtered results before deciding they're done.
**Then:**
- Picking a receipt from the results stages it - it moves into a "Selected so far" list shown above the filter results, and no longer appears among the results itself.
- The "Selected so far" list shows each staged receipt's store name, date, and amount, plus a running total in the transaction's own currency.
- If the running total doesn't match the transaction's amount, that's shown plainly next to the total, but never blocks committing the selection - real settlements can be partial, include a tip, or round differently.
- Each staged receipt has its own removal action, taking just that one back out of the selection while leaving the rest staged.
- Changing the filter and searching again does not discard the staged selection - it's tied to the transaction being linked, not to any one search.
- An "Add" action commits the entire staged selection at once: every staged receipt becomes linked to the transaction, the pending selection is cleared, and a confirmation names how many receipts were linked, before returning to History.
- Clicking "Add" with nothing staged does nothing except say so - it leaves the page exactly as it was rather than silently returning to History.
- A "Cancel" action discards the entire staged selection with no partial commit, and returns to History - the same outcome as before any receipt was staged.
- Staging a single receipt and committing it works the same way as staging several - there is no separate one-receipt shortcut.

---

## BS-046: Send Feedback to Admins

**Scenario:** A user notices a bug or has a suggestion, and wants to report it to the app's admins without leaving the app or looking up an email address by hand.

**Given:** The user is logged in, on any page.
**When:** They use the "Contact" link (always visible in the nav) and submit the feedback form.
**Then:**
- The feedback form defaults its "functionality" field to whichever page the user came from, but the user can change it to any other listed functionality, or to "All" or "None".
- The type field defaults to "Bug Report", with "Enhancement Proposal" and "General Feedback" also selectable.
- A screenshot image is optional; the message text is required - submitting without a message re-shows the form with the type, functionality, and message text the user already entered still in place, plus an error.
- On a valid submission, the feedback is saved, and every current admin (not just one) receives an email with the user's own email address, the type, the functionality, the message, and the screenshot attached if one was provided.
- The user sees a confirmation and returns to History either way - even if the admin email couldn't be sent for some reason, the feedback itself is not lost, and the user is told the email step specifically didn't go through.

---

## BS-047: Nav Shows the Logged-In Email

**Scenario:** A user wants to be sure which account they're using, without a username/password to check - this app logs in by email and a one-time code, so the email address itself is the identifying credential.

**Given:** The user is logged in.
**When:** They view any page of the app.
**Then:**
- Their email address is shown in the nav's top row, on the opposite side from the app name, on every authenticated page.
- It is plain text, not a link - clicking it does nothing.
- It disappears the moment the user is logged out, and never appears on the login or verification-code pages.
