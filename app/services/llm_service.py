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
import json
from typing import Dict, Optional
from pathlib import Path


class LLMService:
    """
    Service for interacting with Anthropic's Claude API.

    This class handles:
    - API authentication
    - Image encoding
    - Prompt construction
    - Response parsing
    """

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
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
        # Create Anthropic client
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
                    'items': List[{'name': str, 'price': float, 'quantity': int}],
                    'tax_amount': float,
                    'discount_amount': float,
                    'total_amount': float
                }

        Raises:
            Exception: If API call fails or image cannot be read
        """
        print(f"Extracting data from receipt: {image_path}")

        # Step 1: Read and encode the image
        image_data = self._encode_image(image_path)
        media_type = self._get_media_type(image_path)

        # Step 2: Create the prompt for Claude
        prompt = self._create_extraction_prompt()

        # Step 3: Call Claude API
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

            # Step 4: Extract and parse the response
            # Claude returns response in response.content[0].text
            response_text = response.content[0].text

            print("Received response from Claude")
            print(f"Response preview: {response_text[:200]}...")

            # Parse the JSON response
            receipt_data = self._parse_response(response_text)

            return receipt_data

        except anthropic.APIError as e:
            print(f"Anthropic API error: {e}")
            raise Exception(f"Failed to call Claude API: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise

    def _encode_image(self, image_path: str) -> str:
        """
        Read and encode image file to base64 string.

        Claude API requires images to be sent as base64-encoded strings.

        Args:
            image_path (str): Path to image file

        Returns:
            str: Base64-encoded image data

        Why base64:
        Base64 encoding converts binary image data to ASCII text,
        which can be safely transmitted in JSON over HTTP.
        """
        with open(image_path, 'rb') as image_file:
            image_bytes = image_file.read()
            # Encode to base64 and convert to string
            return base64.standard_b64encode(image_bytes).decode('utf-8')

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

    def _create_extraction_prompt(self) -> str:
        """
        Create the prompt for Claude to extract receipt data.

        This is CRITICAL for good results. The prompt needs to:
        - Clearly specify what data to extract
        - Define the exact output format (JSON)
        - Handle edge cases (missing data, unclear text)
        - Be specific about data types

        Returns:
            str: The prompt text

        Note: This is called "prompt engineering" - crafting effective
              instructions for AI models. It's both an art and a science!
        """
        return """You are a receipt data extraction assistant. Analyze the receipt image and extract the following information.

**Extract these fields:**

1. **store_name**: Name of the store/merchant
2. **purchase_date**: Date of purchase in YYYY-MM-DD format
3. **items**: List of purchased items, each with:
   - name: Item description
   - price: Price per unit (as a number, not string)
   - quantity: Number of items (default to 1 if not specified)
4. **tax_amount**: Total tax amount (as a number)
5. **discount_amount**: Total discount/savings (as a number, use 0 if none)
6. **total_amount**: Final total amount paid (as a number)

**Important guidelines:**
- Return ONLY valid JSON, no additional text or explanation
- If a field is not visible or unclear, use null for strings or 0 for numbers
- For prices, use decimal numbers (e.g., 3.99, not "3.99" or "$3.99")
- For dates, use YYYY-MM-DD format (e.g., "2026-05-07")
- For item quantities, default to 1 if not specified
- Ensure all number fields are actual numbers, not strings
- Double-check that total_amount matches the sum of items + tax - discounts

**Return format (JSON):**
```json
{
  "store_name": "Store Name",
  "purchase_date": "2026-05-07",
  "items": [
    {
      "name": "Item name",
      "price": 0.00,
      "quantity": 1
    }
  ],
  "tax_amount": 0.00,
  "discount_amount": 0.00,
  "total_amount": 0.00
}
```

Analyze the receipt now and return the extracted data as JSON:"""

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
