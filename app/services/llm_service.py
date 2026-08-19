"""
LLM Service - Integration with Anthropic Claude API.

This service handles all communication with Claude AI for receipt processing.
It's responsible for:
1. Sending receipt images to Claude
2. Crafting effective prompts for data extraction
3. Parsing Claude's response into structured data

Key concept: Prompt Engineering
The quality of data extraction depends heavily on how we ask Claude.
We need to be specific about:
- What data to extract
- What format to return it in
- How to handle unclear cases
"""

import anthropic
import base64
import io
import json
from typing import Dict, List, Optional
from pathlib import Path
from PIL import Image


class LLMService:
    """
    Service for interacting with Anthropic's Claude API.

    This class handles:
    - API authentication
    - Image encoding
    - Prompt construction
    - Response parsing
    """

    # Tolerance for reconciling extracted item totals against the receipt's
    # own total_amount. Small enough to catch real misreads, large enough to
    # absorb per-line rounding noise.
    _RECONCILIATION_TOLERANCE = 0.02

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022", valid_categories: List[str] = None):
        """
        Initialize the LLM service.

        Args:
            api_key (str): Anthropic API key
            model (str): Claude model to use (default: Claude 3.5 Sonnet)

        Why Claude 3.5 Sonnet:
        - Excellent vision capabilities for reading receipts
        - Good balance of speed and accuracy
        - Supports structured output
        """
        self.api_key = api_key
        self.model = model
        self.valid_categories = valid_categories or []
        self.client = anthropic.Anthropic(api_key=api_key)

    def extract_receipt_data(self, image_path: str) -> Dict:
        """
        Extract structured data from a receipt image using Claude.

        This is the main method that:
        1. Reads the receipt image
        2. Encodes it for API transmission
        3. Sends it to Claude with a detailed prompt
        4. Parses the response into structured data

        Args:
            image_path (str): Path to the receipt image file

        Returns:
            Dict: Extracted receipt data with structure:
                {
                    'store_name': str,
                    'purchase_date': str,
                    'items': List[{'name': str, 'price': float, 'quantity': int, 'amount': float, 'unit': str}],
                    'tax_amount': float,
                    'discount_amount': float,
                    'total_amount': float
                }

        Raises:
            Exception: If API call fails or image cannot be read
        """
        print(f"Extracting data from receipt: {image_path}")

        # Step 1: Read and encode the image (compresses if over 4 MB) — reused
        # for both the initial attempt and the retry, if one is needed.
        image_data = self._encode_image(image_path)
        # After compression, output is always JPEG; otherwise honour original format
        original_size = Path(image_path).stat().st_size
        media_type = 'image/jpeg' if original_size > 4 * 1024 * 1024 else self._get_media_type(image_path)

        # Step 2: First attempt
        receipt_data = self._attempt_extraction(image_data, media_type)

        # Step 3: If the extracted items don't reconcile with the receipt's own
        # total, give the LLM one more chance with the specific discrepancy —
        # this catches misattributed price/quantity rows (see SP-018).
        reconciled, mismatch = self._check_reconciliation(receipt_data)
        if not reconciled:
            print(
                f"Reconciliation failed ({mismatch['formula']}): "
                f"computed {mismatch['computed']:.2f} vs total {mismatch['expected']:.2f} "
                f"(gap {mismatch['gap']:.2f}). Retrying once with the discrepancy..."
            )
            try:
                receipt_data = self._attempt_extraction(image_data, media_type, retry_mismatch=mismatch)
            except Exception as e:
                # Retry is a best-effort improvement — if it fails outright,
                # keep the first (unreconciled) result rather than losing the upload.
                print(f"Retry attempt failed, keeping original extraction: {e}")

        return receipt_data

    def _attempt_extraction(self, image_data: str, media_type: str, retry_mismatch: Optional[Dict] = None) -> Dict:
        """
        Send one extraction request to Claude and parse the response.

        Args:
            image_data (str): Base64-encoded receipt image
            media_type (str): Image MIME type
            retry_mismatch (Optional[Dict]): If set, this is a retry — the
                prompt includes the specific reconciliation gap from the
                previous attempt (see `_check_reconciliation`) so Claude can
                re-examine its transcription for the likely cause.

        Returns:
            Dict: Parsed receipt data

        Raises:
            Exception: If the API call fails or the response can't be parsed
        """
        prompt = self._create_extraction_prompt(self.valid_categories, retry_mismatch=retry_mismatch)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0.0,  # Use 0 for consistent, deterministic output
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )

            # Claude returns response in response.content[0].text
            response_text = response.content[0].text

            print("Received response from Claude")
            print(f"Response preview: {response_text[:200]}...")

            return self._parse_response(response_text)

        except anthropic.APIError as e:
            print(f"Anthropic API error: {e}")
            raise Exception(f"Failed to call Claude API: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise

    @staticmethod
    def _safe_float(value, default: float = 0.0) -> float:
        """Best-effort float conversion for LLM-extracted values that may be missing or malformed."""
        try:
            return float(value) if value is not None else default
        except (TypeError, ValueError):
            return default

    def _check_reconciliation(self, receipt_data: Dict) -> tuple:
        """
        Check whether the extracted item totals reconcile with the receipt's
        own total_amount.

        Two conventions exist depending on the receipt's country/store:
        - VAT-inclusive (e.g. Swiss/EU retail): item prices already include
          tax, so sum(items) alone should equal total_amount.
        - VAT-exclusive (e.g. US retail): tax is added on top, so
          sum(items) + tax - discount should equal total_amount.

        A receipt reconciles if either convention matches within tolerance,
        so this never false-positives just because a receipt uses the other
        country's pricing convention.

        Args:
            receipt_data (Dict): Parsed receipt data (items, tax_amount,
                discount_amount, total_amount)

        Returns:
            tuple: (reconciled: bool, mismatch: Optional[Dict]). mismatch is
                None when reconciled, otherwise a dict with the closer
                formula's 'formula', 'expected', 'computed', and 'gap'.
        """
        items = receipt_data.get('items', [])
        item_sum = sum(
            self._safe_float(item.get('price')) * self._safe_float(item.get('quantity'), 1.0)
            for item in items
        )
        tax = self._safe_float(receipt_data.get('tax_amount'))
        discount = self._safe_float(receipt_data.get('discount_amount'))
        total = self._safe_float(receipt_data.get('total_amount'))

        gross_diff = abs(item_sum - total)
        net_diff = abs(item_sum + tax - discount - total)

        if min(gross_diff, net_diff) <= self._RECONCILIATION_TOLERANCE:
            return True, None

        if gross_diff <= net_diff:
            return False, {
                'formula': 'sum(items) ≈ total (VAT-inclusive)',
                'expected': total,
                'computed': item_sum,
                'gap': gross_diff,
            }
        return False, {
            'formula': 'sum(items) + tax - discount ≈ total (VAT-exclusive)',
            'expected': total,
            'computed': item_sum + tax - discount,
            'gap': net_diff,
        }

    def _encode_image(self, image_path: str) -> str:
        """
        Read, compress if needed, and encode image file to base64 string.

        Claude API requires images to be sent as base64-encoded strings and
        enforces a 5 MB limit on the raw image data. Large receipt photos
        (from modern phone cameras) often exceed this, so we compress them
        down before encoding.

        Args:
            image_path (str): Path to image file

        Returns:
            str: Base64-encoded image data (guaranteed under 5 MB raw)
        """
        MAX_BYTES = 3_500_000  # raw limit: 5 MB base64 cap * 3/4, with margin

        image_bytes = Path(image_path).read_bytes()

        if len(image_bytes) <= MAX_BYTES:
            return base64.standard_b64encode(image_bytes).decode('utf-8')

        # Image is too large — re-encode at progressively lower JPEG quality
        # until it fits. We always output JPEG here because it compresses well
        # for photos and the Claude API accepts it regardless of the original format.
        print(f"Image too large ({len(image_bytes):,} bytes), compressing...")
        img = Image.open(image_path).convert('RGB')

        for quality in (85, 70, 55, 40):
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=quality, optimize=True)
            compressed = buf.getvalue()
            print(f"  quality={quality} -> {len(compressed):,} bytes")
            if len(compressed) <= MAX_BYTES:
                return base64.standard_b64encode(compressed).decode('utf-8')

        # Still too large — halve the resolution and try once more
        w, h = img.size
        img = img.resize((w // 2, h // 2), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=40, optimize=True)
        compressed = buf.getvalue()
        print(f"  resized to {w // 2}x{h // 2} -> {len(compressed):,} bytes")
        return base64.standard_b64encode(compressed).decode('utf-8')

    def _get_media_type(self, image_path: str) -> str:
        """
        Determine the media type (MIME type) of an image file.

        Args:
            image_path (str): Path to image file

        Returns:
            str: MIME type (e.g., 'image/jpeg', 'image/png')

        Raises:
            ValueError: If file extension is not supported
        """
        suffix = Path(image_path).suffix.lower()
        media_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }

        if suffix not in media_types:
            raise ValueError(f"Unsupported image format: {suffix}")

        return media_types[suffix]

    def _create_extraction_prompt(self, valid_categories: List[str] = None, retry_mismatch: Optional[Dict] = None) -> str:
        """
        Create the prompt for Claude to extract receipt data.

        This is CRITICAL for good results. The prompt needs to:
        - Clearly specify what data to extract
        - Define the exact output format (JSON)
        - Handle edge cases (missing data, unclear text)
        - Be specific about data types

        Args:
            valid_categories (List[str]): Categories to offer for item classification
            retry_mismatch (Optional[Dict]): When set (see `_check_reconciliation`),
                this is a retry — prepends a note telling Claude exactly what
                didn't reconcile in its previous attempt

        Returns:
            str: The prompt text

        Note: This is called "prompt engineering" - crafting effective
              instructions for AI models. It's both an art and a science!
        """
        categories_str = ", ".join(f'"{c}"' for c in (valid_categories or ["Other"]))

        retry_notice = ""
        if retry_mismatch:
            retry_notice = f"""
**This is a retry - your previous attempt did not reconcile.** Using
{retry_mismatch['formula']}, your extracted items came to
{retry_mismatch['computed']:.2f} but the receipt's own total is
{retry_mismatch['expected']:.2f} - a difference of {retry_mismatch['gap']:.2f}.
Before transcribing again, look specifically for a price or quantity that was
misread, or a quantity/unit-price sub-line (e.g. "2 St 1.60 CHF/St") that got
attributed to the wrong item row instead of the row it actually belongs to -
these are the most common causes of this kind of mismatch. Re-transcribe
carefully and make sure your final numbers reconcile this time.
"""

        return f"""You are a receipt data extraction assistant. Analyze the receipt image in two steps.
{retry_notice}
**Step 1: Transcribe the items table row by row.**

Before producing any JSON, write out a plain-text transcription of the items
table, exactly one line per row, in the order printed. For each row, copy down
every column you see left to right (e.g. name, quantity/"Menge" column, price
column, a discount/"Gespart" column if present, the line total, and any
trailing code column) - even if a row looks like a duplicate of another, or a
column looks irrelevant, transcribe it exactly as printed. Do not merge,
summarize, or reinterpret anything yet - this is a literal row-by-row copy of
what's on the receipt, done carefully one row at a time. This step matters
most on receipts with extra columns (discounts, tax codes) - reading each row
in isolation, left to right, prevents values from one row bleeding into the
row above or below it.

**Step 2: Using ONLY that transcription, produce the extracted JSON.**

**Extract these fields:**

1. **store_name**: Name of the store/merchant
2. **purchase_date**: Date of purchase in YYYY-MM-DD format
3. **items**: List of purchased items, each with:
   - name: Item description
   - price: Price per unit (as a number, not string)
   - quantity: Number of items (default to 1 if not specified)
   - category: One category from this exact list: {categories_str}
     Assign the category that best fits the item. Use "Other" if unsure.
   - amount: The purchased amount as printed on the receipt (e.g. a weight like
     0.743, or a count). Do NOT infer this from the item's name (e.g. ignore a
     package size like "500G" printed in the name itself) - only use an amount
     that is printed as the actual purchased quantity/weight for that line.
     Use null if no such amount is printed.
   - unit: The unit for `amount`, if shown (e.g. "kg", "g", "piece"). Use null
     if not shown.

   **Watch out for these two common misreads:**
   - Some receipts show a per-item discount/savings column in addition to
     price and total (e.g. a "Gespart"/"Savings" column), on top of the
     regular price/quantity/total columns. When a row has multiple price-like
     numbers (an original/unit price AND a line total), `price` must always
     come from the row's final "Total" column - the actual amount charged for
     that line - never from an earlier "unit price" column that a discount
     was then subtracted from. Keep every item's name, price, and quantity
     together as one row, using your Step 1 transcription. Never let an extra
     column on one row cause the price or quantity to shift onto a different
     item on the row above or below it.
   - Some receipts have a small numeric code in the rightmost column that is
     unrelated to quantity (e.g. a tax/VAT-rate category code, often just
     "1" or "2"). `quantity` must come only from an explicit quantity/count
     column (e.g. "Menge" or "Qty") - never from a trailing code column, and
     never just because a small integer happens to appear near the price.
4. **tax_amount**: Total tax amount (as a number)
5. **discount_amount**: Total discount/savings (as a number, use 0 if none)
6. **total_amount**: Final total amount paid (as a number)
7. **currency**: ISO 4217 currency code of the receipt (e.g. "USD", "EUR", "CHF", "GBP"). If the currency is not visible or cannot be determined, use "USD".

**Important guidelines:**
- Show your Step 1 transcription as plain text first, then give the Step 2
  JSON inside a ```json code block. Nothing you extract in Step 2 should be
  information that isn't in your Step 1 transcription.
- If a field is not visible or unclear, use null for strings or 0 for numbers
- For prices, use decimal numbers (e.g., 3.99, not "3.99" or "$3.99")
- For dates, use YYYY-MM-DD format (e.g., "2026-05-07")
- For item quantities, default to 1 if not specified
- For item amount/unit: if no amount is printed, use null for both. If an amount
  is printed but no unit, and the amount is not a whole number, assume "kg". If
  an amount is printed but no unit, and it is a whole number, assume "piece".
  Never derive amount/unit from the item name - only from an amount actually
  printed as the purchased quantity/weight.
- Ensure all number fields are actual numbers, not strings
- Double-check that total_amount matches the sum of items + tax - discounts.
  If it doesn't reconcile, re-examine your Step 1 transcription for a
  misread price or quantity rather than forcing the numbers to match
- For currency, always return an uppercase ISO 4217 code, never a symbol

**Return format (JSON), inside a ```json code block after your Step 1 transcription:**
```json
{{
  "store_name": "Store Name",
  "purchase_date": "2026-05-07",
  "items": [
    {{
      "name": "Item name",
      "price": 0.00,
      "quantity": 1,
      "category": "Food & Groceries",
      "amount": null,
      "unit": null
    }}
  ],
  "tax_amount": 0.00,
  "discount_amount": 0.00,
  "total_amount": 0.00,
  "currency": "USD"
}}
```

Analyze the receipt now: first transcribe the items table row by row, then return the extracted data as JSON:"""

    def _parse_response(self, response_text: str) -> Dict:
        """
        Parse Claude's response into structured data.

        Claude should return JSON, but we need to:
        1. Extract JSON from the response (might have markdown formatting)
        2. Validate the structure
        3. Handle errors gracefully

        Args:
            response_text (str): Raw response from Claude

        Returns:
            Dict: Parsed receipt data

        Raises:
            Exception: If response cannot be parsed or is invalid
        """
        try:
            # Claude sometimes wraps JSON in markdown code blocks
            # Look for ```json and ``` markers
            if '```json' in response_text:
                # Extract content between ```json and ```
                start = response_text.find('```json') + 7
                end = response_text.find('```', start)
                json_text = response_text[start:end].strip()
            elif '```' in response_text:
                # Sometimes just ``` without json
                start = response_text.find('```') + 3
                end = response_text.find('```', start)
                json_text = response_text[start:end].strip()
            else:
                # No markdown, assume entire response is JSON
                json_text = response_text.strip()

            # Parse JSON
            data = json.loads(json_text)

            # Validate required fields exist
            required_fields = ['items', 'total_amount']
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")

            # Ensure items is a list
            if not isinstance(data['items'], list):
                raise ValueError("'items' must be a list")

            print(f"Successfully parsed receipt with {len(data['items'])} items")
            return data

        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response: {e}")
            print(f"Response text: {response_text}")
            raise Exception(f"Invalid JSON response from Claude: {e}")
        except Exception as e:
            print(f"Error parsing response: {e}")
            raise Exception(f"Failed to parse Claude response: {e}")
