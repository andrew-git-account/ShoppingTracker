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
**When:** They submit an email address not present in `data/allowed_users.json`.
**Then:**
- An error message is shown: "Email address not authorised".
- The user stays on the login page.
- No OTP is generated.

---

## BS-015: Login — Allowed Email Triggers OTP

**Scenario:** A user enters an allowed email address.

**Given:** The user is on the login page (`/login`).
**When:** They submit an email address that exists in `data/allowed_users.json`.
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
- Results are ordered by item name, then price, so identical items are easy to compare side by side.

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
