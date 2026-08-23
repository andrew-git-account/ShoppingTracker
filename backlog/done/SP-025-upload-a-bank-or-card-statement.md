# SP-025: Upload a Bank or Card Statement

**Priority**: High
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-037

## Description
Add a new "Upload Statement" page, separate from receipt upload, where the user uploads a PDF bank or credit-card statement and picks which type it is. A dedicated LLM extraction call (not the receipt-extraction prompt) reads the PDF and produces a list of transactions (date, merchant description, amount, currency, direction, category), each saved as its own record. This SP only gets transactions extracted and stored — matching them to receipts is SP-026, a manual link/unlink UI is SP-027, and Statistics inclusion is SP-028.

## Acceptance Criteria
- [x] A new "Upload Statement" nav tab/page lets the user upload a PDF and select whether it's a bank or credit-card statement.
- [x] On submit, the PDF is sent to Claude in a dedicated extraction call (separate prompt and method from receipt extraction) that returns a list of transactions (date, description, amount, currency, direction, category).
- [x] Each extracted transaction is saved as its own record, tagged with the statement's type (bank/card) and the uploading user — not merged into `receipts.json`, not itemized like a receipt.
- [x] Only PDF files are accepted; other file types are rejected with a clear error, mirroring the receipt upload's file-type validation.
- [x] After upload, the user sees a confirmation of how many transactions were extracted (e.g. "Found 42 transactions").
- [x] Each transaction records its direction — `"debit"` (money out) or `"credit"` (money in) — independent of `amount`, which always stays positive; an unrecognized/missing value from extraction defaults to `"debit"`.
- [x] Each transaction gets a best-effort category from the same category vocabulary receipt items use, falling back to `"Other"` when extraction doesn't return a recognized one (mirrors `Receipt.from_llm_response`'s existing item-category fallback).

## Notes / Context

### Data model
New `Transaction` class in `app/models.py`, parallel in spirit to `Receipt` but deliberately thinner (a statement line is never itemized):
- `transaction_id`, `date` (purchase/transaction date as printed), `description` (merchant string as printed, not normalized), `amount`, `currency`, `direction` (`'debit'`/`'credit'`, default `'debit'`), `category` (default `'Other'`), `source` (`'bank'` or `'card'`), `user_email`, `saved_at`.
- `linked_receipt_id: Optional[str] = None` — added now (defaulting to `None`) even though nothing sets it until SP-026, so the schema doesn't need a second migration later.
- `is_deleted` — soft-delete, same spirit as `Receipt` (SP-002).

**Direction and category added after initial manual testing**: reviewing a real statement upload surfaced that `amount`-always-positive alone loses whether money left or arrived (an incoming "CREDIT ..." line looked identical to an outgoing payment), and that a statement line carries no category the way a receipt item does. `direction` (`'debit'`/`'credit'`, validated against that exact set, defaulting to `'debit'` if extraction returns anything else) and `category` (from the same `valid_categories` vocabulary already used for receipts, falling back to `'Other'`) close both gaps.

### Storage
New `app/database/transaction_db.py` with a `JSONTransactionDatabase` class, storing `transactions.json` — its own file, mirroring `usage_log_db.py`'s shape (a separate concern gets its own small file) rather than folding into `json_db.py`. Needs `save_transaction`, `get_all_transactions(user_email)`, `get_transaction_by_id`, `update_transaction` (sets `linked_receipt_id` in place — same shape as `JSONDatabase.update_receipt`, SP-022), ownership-scoped the same way `JSONDatabase` scopes receipts.

### Transaction service layer
New `app/services/transaction_service.py` with a `TransactionService`, mirroring `ReceiptService`'s thin-wrapper shape (`get_all_transactions`, `get_transaction_by_id`, `save_transaction`, `update_transaction`, each just delegating to `JSONTransactionDatabase`). Attached to the app the same way as the other services (`app.transaction_service`, alongside `app.receipt_service`/`app.auth_service` in `app/main.py`). Settling this here (rather than leaving it to whichever of SP-026/SP-027 gets built first) matters because *every* existing route talks to a `*_service` object, never a raw database — `app/routes.py`'s own module docstring: "Routes should be 'thin' - they handle HTTP stuff and delegate the actual work to services." SP-026's matching logic and SP-027's routes should both call `app.transaction_service.*`, not `JSONTransactionDatabase` directly.

### LLM extraction
`LLMService` (`app/services/llm_service.py`) gains `extract_statement_transactions(pdf_path: str, user_email: str) -> List[Dict]` — a new method and a new prompt, **not** a reuse of `_create_extraction_prompt()` (that prompt is receipt-shaped: single store, single total, itemized).

**Extract text locally, don't send the PDF itself to Claude.** The pinned `anthropic==0.34.2` (confirmed via the installed SDK's type stubs) predates PDF/`document`-content-block support entirely, and there's no reason to take on that dependency-upgrade risk anyway: bank/card statements are near-universally text-based PDFs (generated by the bank's own software, not photographed), so plain text extraction is both simpler and a better fit for this data source than vision ever was for receipts. Add a PDF-text-extraction library (`pypdf` — lightweight, pure Python, already the kind of small well-maintained dependency this project takes on) to `requirements.txt`; read the PDF's text page by page and join it. Build a text-only prompt embedding that extracted text (asking for a JSON list of `{date, description, amount, currency, direction, category}` objects - `_create_statement_extraction_prompt` takes `valid_categories` too, same as `_create_extraction_prompt` does for receipts) and send it through the *existing* text-only path already used for the `retry_notice`/instructions portion of receipt prompts — a `{"type": "text", "text": prompt}` content block, no image block at all, so this needs no SDK feature this project doesn't already rely on. Reuse the existing `usage_logger` call for cost tracking (SP-020), same as receipt extraction. If the extracted text is empty or near-empty (e.g. a scanned/image-only PDF, which text extraction can't read), fail with a clear error rather than sending Claude an empty prompt — image-only statements are out of scope for this SP.

Response parsing: `_parse_response()` currently hardcodes `required_fields = ['items', 'total_amount']`, which is receipt-shaped. Either generalize it to accept a `required_fields` parameter, or add a small sibling parser for the transaction-list shape — implementer's call, but note the JSON-in-markdown-fence extraction logic itself is already generic and reusable as-is.

### Statement service layer
New `app/services/statement_service.py` with a `StatementService`, mirroring `ReceiptService`'s shape (including taking `valid_categories` in its constructor): `process_statement(file, user_email, source) -> List[Transaction]` — validate the file is a PDF, save it temporarily, call `extract_statement_transactions`, build and save one `Transaction` per extracted line (validating `direction` against `{'debit', 'credit'}` and `category` against `valid_categories`, same fallback shape `Receipt.from_llm_response` already uses for item categories), clean up the temp file.

### Route / template / nav
- New `GET/POST /upload-statement` in `app/routes.py`.
- New `templates/upload_statement.html`, following `upload.html`'s structure — file input (PDF only) plus a statement-type selector (Bank / Credit Card).
- New nav tab in `templates/base.html`, alongside Upload/History/Statistics.

### Open technical risk — file size
`MAX_CONTENT_LENGTH` today is one global Flask config value sized for receipt images (~5MB). A multi-page statement PDF could plausibly be larger, and unlike a JPEG there's no `_compress_to_limit`-style fallback for a PDF. Whoever implements this should check whether the existing limit is workable for a real statement or needs its own, higher ceiling.

### Out of scope (this SP)
- Matching a transaction to a receipt (SP-026).
- Any UI for viewing/linking transactions (SP-027).
- Transactions appearing in Statistics (SP-028).

## Implementation Notes
_Completed 2026-08-23._

- `app/models.py` — new `Transaction` class (`date`, `description`, `amount`, `currency`, `direction`, `category`, `source`, `transaction_id`, `saved_at`, `user_email`, `linked_receipt_id`, `is_deleted`), `to_dict()`/`from_dict()` mirroring `Receipt`'s shape.
- `app/database/transaction_db.py` (new) — `JSONTransactionDatabase` (`save_transaction`, `get_all_transactions`, `get_transaction_by_id`, `update_transaction`), mirroring `JSONDatabase`'s method shapes and ownership/preserve-on-update conventions; exported from `app/database/__init__.py`.
- `app/services/transaction_service.py` (new) — `TransactionService`, a thin wrapper matching `ReceiptService`'s data-access shape; exported from `app/services/__init__.py`.
- `app/services/llm_service.py` — `extract_statement_transactions()` (new method, own prompt, no retry loop) extracts PDF text locally via `pypdf.PdfReader` (`_extract_pdf_text`) rather than sending the PDF itself to Claude - the pinned `anthropic==0.34.2` predates document-content-block support, and text-only extraction is a better fit for near-universally-text-based statement PDFs anyway. `_parse_response()` generalized to accept a `required_fields` parameter (defaults preserve the exact existing receipt behavior). Prompt asks for `direction`/`category` alongside `date`/`description`/`amount`/`currency`, with `valid_categories` threaded in the same way receipt extraction already does.
- `app/services/statement_service.py` (new) — `StatementService.process_statement()`, mirroring `ReceiptService`'s upload orchestration; validates `direction` against `{'debit', 'credit'}` (default `'debit'`) and `category` against `valid_categories` (default `'Other'`), same fallback shape `Receipt.from_llm_response` already uses.
- `app/routes.py` — new `GET/POST /upload-statement`, same validation/error-handling structure as `/upload`.
- `templates/upload_statement.html` (new), `templates/base.html` (nav tab), `templates/upload.html` (updated file-size text).
- `app/main.py` — wires `JSONTransactionDatabase`/`TransactionService`/`StatementService` (with `valid_categories`) alongside the existing services; `MAX_UPLOAD_SIZE` default raised from 5MB to 15MB (covers statement PDFs; harmless for receipts).
- `requirements.txt` — added `pypdf==6.16.1`. `.env.example` updated to match the new upload-size default.
- `static/css/style.css` — `.container` widened from 800px to 1100px and `.nav-tabs a` given `white-space: nowrap`, fixing a real bug the new nav tab exposed (7 tabs wrapped onto two lines in the old 800px-wide navbar).
- **Direction and category added after initial manual testing** (not in the original scope, folded in while still In Testing): reviewing a real statement upload showed an incoming "CREDIT ..." line was indistinguishable from an outgoing payment, and transactions had no category. Both fields added end-to-end (model → prompt → service → tests) and re-verified against the real API.
- No data migration - this is a new file/model with no prior shape to migrate from.
- Tests: 20 added across `test_database.py` (`TestJSONTransactionDatabase`), `test_llm_service.py` (`TestStatementExtraction`), `test_statement_service.py` (new file), and `test_routes.py` (`TestUploadStatementRoute`). 349 passed (full suite).
- Verified twice against the real Claude API (not just mocks): once with a 3-line synthetic statement (all debits), once with a debit+credit statement confirming `direction`/`category` extraction. Also manually reviewed against a real bank statement and a real credit-card statement the account holder uploaded - 11 bank + 47 card transactions extracted correctly, including catching and removing an accidental duplicate upload from `data/transactions.json` (backed up first).
