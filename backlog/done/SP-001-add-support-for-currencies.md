# SP-001: Add Support for Currencies

**Priority**: High
**Status**: Done

## Description
Add currency recognition to the receipt OCR pipeline. During processing, the LLM should identify the currency used on the receipt (e.g. USD, EUR, GBP, PLN) and store it alongside the receipt data. If the currency cannot be determined from the receipt, it defaults to US dollars (USD).

## Acceptance Criteria
- [x] LLM extracts a `currency` field (ISO 4217 code, e.g. "USD", "EUR") when scanning a receipt
- [x] If no currency is found or recognized, the system defaults to "USD"
- [x] The `Receipt` model stores the `currency` field
- [x] The receipt history page displays the currency code next to prices
- [x] Receipts with non-USD currencies show the correct iso code 

## Notes / Context
- ISO 4217 codes are the standard (USD, EUR, GBP,  etc.)
- The LLM prompt in `llm_service.py` needs to be updated to ask for currency
- The `Receipt` and/or `ReceiptItem` model in `models.py` needs a `currency` field
- Existing receipts in `data/receipts.json` have no currency field — default them to "USD" on load
- Display: show the ISO code ("USD") 

## Implementation Notes
Four files changed:

- **`app/models.py`** — Added `currency: str = "USD"` parameter to `Receipt.__init__`. Stored as `self.currency`. Included in `to_dict()` for persistence, and read back in `from_dict()` and `from_llm_response()` both with `"USD"` as default (backward-compatible with existing JSON records that have no currency key).

- **`app/services/llm_service.py`** — Added field 7 (`currency`) to `_create_extraction_prompt()` with instruction to return an uppercase ISO 4217 code and fall back to `"USD"` if not visible. Added matching key to the JSON example in the prompt.

- **`templates/history.html`** — Replaced all 6 hardcoded `$` signs with `{{ receipt.currency }}` — covers the summary card total, each item price, subtotal, tax, discount, and the expanded total row.

- **`app/routes.py`** — Fixed the success flash message which also had a hardcoded `$`; now uses `{receipt.currency}`.
