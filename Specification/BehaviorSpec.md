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
