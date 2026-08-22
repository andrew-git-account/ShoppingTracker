# SP-023: "Edit Before Saving" Checkbox

**Priority**: High
**Status**: Done
**Fulfils**: BehaviorSpec.md#BS-035
**Deployed**: 6f2a14b (2026-08-22)

## Description
Add an "Edit before saving" checkbox to the upload form. When checked, the extracted receipt is *not* saved to `receipts.json` immediately — instead the user is taken to an edit page (reusing SP-022's editing mechanism) to review/correct it first; the receipt is only actually created once they save from there. Depends on SP-022 — this reuses its form/validation/template, applied to not-yet-saved data instead of an existing receipt.

## Acceptance Criteria
- [x] The upload form has an "Edit before saving" checkbox, unchecked by default (today's save-immediately behavior is the default, unchanged).
- [x] With the checkbox unchecked, upload behaves exactly as it does today — no change to that path.
- [x] With the checkbox checked, after extraction succeeds, the user lands on an edit page pre-filled with the extracted data (same editable fields as SP-022: item name/category/price, receipt currency/total, item removal) — the receipt is not yet in `receipts.json` at this point.
- [x] Saving from that page creates the receipt for the first time (assigns a new ID, appears in History from then on) — reusing SP-022's validation (non-negative price/total, at least one item).
- [x] The user can discard the draft instead of saving (e.g. navigating away or an explicit "Discard" action) without it ever being saved.

## Notes / Context

### Draft storage
Per discussion: a small per-draft temp JSON file (mirroring how `app/services/receipt_service.py` already handles temp uploaded images via `_save_temp_file`/`_delete_temp_file`), not the Flask session directly — a receipt with several items as raw JSON risks bumping into typical browser cookie-size limits (~4KB) if stored in the session itself. Only a generated draft ID needs to live in the session (or just be part of the URL — see Route design below, which avoids needing session state for this at all).

Add a small helper (e.g. a new `_save_draft`/`_load_draft`/`_delete_draft` set of functions, or a tiny class if that reads cleaner) that writes/reads a single receipt dict as JSON to a temp file keyed by a generated UUID, living alongside the existing temp upload files (same folder/cleanup spirit as `ReceiptService._save_temp_file`). Suggested shape: `{upload_folder}/draft_{uuid}.json`.

### `ReceiptService.process_receipt()` changes (`app/services/receipt_service.py`)
Add an `edit_before_save: bool = False` parameter. After extraction + building the `Receipt` object (Steps 3-4, unchanged), branch:
- `edit_before_save` is `True` → skip validation/save entirely, write the receipt's dict to a new draft file, and return a reference to the draft (e.g. a small result value distinguishable from a saved `Receipt` — a `(receipt: Optional[Receipt], draft_id: Optional[str])` tuple works cleanly: exactly one is populated, and the caller/route decides what to do with each case).
- `edit_before_save` is `False` → today's existing behavior, unchanged (validate, save, return the saved `Receipt`).

This SP does **not** touch the validation-failure or reconciliation-failure paths — those still behave exactly as they do today (raise / silently accept) when the checkbox isn't checked. That's SP-024's job, building on the same draft mechanism this SP introduces.

### Routes (`app/routes.py`)
- `/upload`'s POST handler reads the checkbox (`request.form.get('edit_before_save') == 'on'` or similar) and passes it through to `process_receipt(file, user_email, edit_before_save=...)`. On the draft-returned case, redirect to the new draft-edit route instead of flashing "success" and going to `/history`.
- New `GET/POST /receipt/draft/<draft_id>/edit` — a sibling to SP-022's `/receipt/<receipt_id>/edit`, **not** the same route (a draft has no `receipt_id` yet, and GET/POST semantics differ: load from the draft file instead of the database, and POST calls `save_receipt` fresh instead of `update_receipt`). Reuses SP-022's `templates/edit_receipt.html` template and the same field-editing/removal/validation mechanics — pass enough context (e.g. an `is_draft` flag and the right form action URL) for the template to post to the right place. On successful save: create the receipt via the normal save path, delete the draft file, flash success, redirect to `/history`.
- New `POST /receipt/draft/<draft_id>/discard` — deletes the draft file, redirects to `/history` (or `/`) with a neutral flash.
- Ownership: a draft isn't in `allowed_users.json`-style storage, but should still only be completable by the user who created it — include `user_email` in the draft file's contents and check it matches `session['user_email']` before allowing edit/save/discard, same spirit as every other per-user check in this app.

### Out of scope
- Automatic cleanup of long-abandoned draft files (e.g. a scheduled sweep) — acceptable to leave unbounded for now, same call made for the LLM usage log's growth in SP-020. A draft is cleaned up on save or explicit discard; one abandoned by just closing the tab stays on disk.

## Implementation Notes
_Completed 2026-08-23._

- `app/services/receipt_service.py` — `process_receipt()` gained `edit_before_save: bool = False` and its return type became `Tuple[Optional[Receipt], Optional[str]]` (`(receipt, draft_id)`, exactly one populated) in **both** branches, a real breaking signature change absorbed the same way comparable ones (SP-005/SP-020) have been. New draft mechanism, mirroring `_save_temp_file`/`_delete_temp_file`'s shape: private `_draft_path`/`_save_draft`/`_load_draft`/`_delete_draft` (one JSON file per draft at `{upload_folder}/draft_{uuid}.json`; `_load_draft` validates `draft_id` is a well-formed UUID via `uuid.UUID(...)` before it's ever used to build a filesystem path, so a malformed/malicious ID from the URL can't escape `upload_folder`), plus public `get_draft`/`save_draft`/`discard_draft`, all ownership-checked ("not found" and "not owned" are indistinguishable, same pattern as `get_receipt_by_id`).
- `app/routes.py` — `/upload`'s POST handler reads the `edit_before_save` checkbox and, on a draft result, redirects to the new draft-edit route instead of History. New `GET/POST /receipt/draft/<draft_id>/edit` and `POST /receipt/draft/<draft_id>/discard`. SP-022's `receipt_edit` route was refactored (behavior-preserving — the full existing SP-022 test suite stayed green throughout) to share its form-parsing/validation and template-rendering logic with the new draft route via three extracted module-level helpers: `_rows_from_receipt`, `_parse_edit_form` (generalized to work against any "original" receipt-shaped object, saved or draft), and `_render_edit_form` (now also threading through `is_draft`/`draft_id`).
- `templates/upload.html` — "Edit before saving" checkbox, unchecked by default, between the file input and the submit button.
- `templates/edit_receipt.html` — now branches on `is_draft`: heading becomes "Review Receipt", the "Cancel" link is replaced by an explicit "Discard" action (its own small `<form>`, since a `<form>` can't nest inside the main one — the Save button instead uses the `form="edit-receipt-form"` attribute so both sit in the same `.form-actions` row without nesting), and the Save button reads "Save Receipt" instead of "Save Changes".
- `static/css/style.css` — `.checkbox-label` (upload page's checkbox); `.form-actions` reworked to sit outside `.upload-form` (needed once Save no longer lives inside the same `<form>` tag as its wrapping div) with `.form-actions > form`/`.form-actions .btn` keeping both action buttons equal-width regardless of which one is form-wrapped.
- No data migration — drafts are a new, self-contained file type; nothing about existing `receipts.json`/`allowed_users.json` shapes changed.
- Mechanical test migration: the 6 pre-existing `process_receipt()` call sites in `tests/test_receipt_service.py` were updated to unpack the new `(receipt, draft_id)` tuple; no behavior assertions changed.
- Tests: 27 added (`test_receipt_service.py`'s `TestReceiptServiceDraft` — draft creation/get/save/discard, ownership checks, and a path-traversal guard test; `test_routes.py`'s `TestEditBeforeSavingDraftFlow` — checkbox presence, unchanged default path, draft creation/review/save/discard end-to-end, validation-failure re-rendering, and cross-user ownership checks on the draft routes). 301 passed (full suite).
- Verified manually: rendered the real `/upload` page (checkbox present, unchecked) and a real draft-review page (via the actual Flask app + a stubbed LLM response) in the browser — "Review Receipt" heading, pre-filled items, live subtotal (USD 3.50 for two stubbed items), and both "Discard"/"Save Receipt" controls confirmed present with valid, non-nested HTML.
