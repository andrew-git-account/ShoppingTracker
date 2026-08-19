"""
Data Models.

This module defines the data structures (classes) used in the application.
Models represent the "shape" of our data and provide methods to convert
between different formats (dict, JSON, etc.).

Why we use classes:
- Type safety: Know what fields a Receipt has
- Validation: Check data is correct before saving
- Conversion: Easy to convert between formats
- Documentation: Clear what data we're working with
"""

from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Unit synonyms the LLM might return, normalized to our two representative
# units: "kg" (weight) and "piece" (count). Grams convert to kg since kg is
# the representative unit for weight.
_KG_SYNONYMS = {'kg', 'kilogram', 'kilograms'}
_GRAM_SYNONYMS = {'g', 'gram', 'grams'}
_PIECE_SYNONYMS = {'piece', 'pieces', 'stk', 'stück', 'stueck', 'pc', 'pcs', 'st'}


def _resolve_amount_unit(raw_amount, raw_unit) -> Tuple[float, str]:
    """
    Resolve an item's (amount, unit) from raw LLM-extracted values, applying
    fallback rules so every item ends up with a usable representative unit.

    Rules (see SP-013):
    - No amount found -> 1 piece.
    - A recognized unit is normalized (grams converted to kg).
    - Amount present but no usable unit, and not a whole number -> kg.
    - Amount present but no usable unit, and a whole number -> piece.

    Args:
        raw_amount: Amount as extracted by the LLM (may be None, a number, or a string).
        raw_unit: Unit as extracted by the LLM (may be None or a string).

    Returns:
        Tuple[float, str]: (amount, unit) with unit always "kg" or "piece".
    """
    if raw_amount is None:
        return 1.0, 'piece'

    try:
        amount = float(raw_amount)
        if amount <= 0:
            amount = 1.0
    except (ValueError, TypeError):
        return 1.0, 'piece'

    unit = str(raw_unit).strip().lower() if raw_unit else None

    if unit in _KG_SYNONYMS:
        return amount, 'kg'
    if unit in _GRAM_SYNONYMS:
        return amount / 1000.0, 'kg'
    if unit in _PIECE_SYNONYMS:
        return amount, 'piece'

    # No usable unit given - infer from whether the amount is a whole number
    return amount, ('piece' if amount.is_integer() else 'kg')


class ReceiptItem:
    """
    Represents a single item on a receipt.

    Each item has:
    - name: What was bought (e.g., "Milk")
    - price: How much it cost (e.g., 3.99)
    - quantity: How many were bought (optional, default 1)
    - amount: The purchased amount in its representative unit, e.g. 0.743 for
      a weighed item (optional, default 1.0)
    - unit: The representative unit for `amount` - "kg" or "piece" (optional,
      default "piece")
    """

    def __init__(
        self,
        name: str,
        price: float,
        quantity: int = 1,
        category: str = "Other",
        amount: float = 1.0,
        unit: str = "piece"
    ):
        """
        Create a new receipt item.

        Args:
            name (str): Item name
            price (float): Item price
            quantity (int): Number of items (default 1)
            category (str): Item category (default "Other")
            amount (float): Purchased amount in the representative unit (default 1.0)
            unit (str): Representative unit for amount - "kg" or "piece" (default "piece")
        """
        self.name = name
        self.price = price
        self.quantity = quantity
        self.category = category
        self.amount = amount
        self.unit = unit

    @property
    def price_per_unit(self) -> float:
        """
        Price per representative unit (CHF/kg for weighed items, CHF/piece
        otherwise), derived from the item's existing line total rather than
        trusted from any printed "unit price" - see SP-013 for why.
        """
        if self.amount <= 0:
            return 0.0
        return (self.price * self.quantity) / self.amount

    def to_dict(self) -> Dict:
        """
        Convert item to dictionary format.

        Returns:
            Dict: Item data as dictionary
        """
        return {
            'name': self.name,
            'price': self.price,
            'quantity': self.quantity,
            'category': self.category,
            'amount': self.amount,
            'unit': self.unit
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ReceiptItem':
        """
        Create a ReceiptItem from a dictionary.

        Args:
            data (Dict): Dictionary with item data

        Returns:
            ReceiptItem: New item instance

        Note: @classmethod means this is a factory method that creates instances.
              amount/unit default to 1.0/"piece" so receipts saved before SP-013
              (which have neither key) still load correctly.
        """
        return cls(
            name=data.get('name', ''),
            price=data.get('price', 0.0),
            quantity=data.get('quantity', 1),
            category=data.get('category', 'Other'),
            amount=data.get('amount', 1.0),
            unit=data.get('unit', 'piece')
        )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"ReceiptItem(name='{self.name}', price={self.price}, quantity={self.quantity})"


class Receipt:
    """
    Represents a complete receipt.

    A receipt contains:
    - items: List of items purchased
    - store_name: Where the purchase was made
    - purchase_date: When the purchase occurred
    - tax_amount: Tax paid
    - discount_amount: Discounts applied
    - total_amount: Final total
    - id: Unique identifier (assigned when saved)
    - saved_at: When this receipt was saved to database
    """

    def __init__(
        self,
        items: List[ReceiptItem],
        store_name: Optional[str] = None,
        purchase_date: Optional[str] = None,
        tax_amount: float = 0.0,
        discount_amount: float = 0.0,
        total_amount: Optional[float] = None,
        receipt_id: Optional[str] = None,
        saved_at: Optional[str] = None,
        currency: str = "USD",
        user_email: Optional[str] = None
    ):
        """
        Create a new receipt.

        Args:
            items (List[ReceiptItem]): List of purchased items
            store_name (str, optional): Store name
            purchase_date (str, optional): Purchase date (ISO format)
            tax_amount (float): Tax amount
            discount_amount (float): Discount amount
            total_amount (float, optional): Total amount (calculated if not provided)
            receipt_id (str, optional): Unique ID (assigned by database)
            saved_at (str, optional): Save timestamp (assigned by database)
            currency (str): ISO 4217 currency code (default "USD")
            user_email (str, optional): Email of the user who owns this receipt (see SP-005)
        """
        self.items = items
        self.store_name = store_name
        self.purchase_date = purchase_date
        self.tax_amount = tax_amount
        self.discount_amount = discount_amount
        self.receipt_id = receipt_id
        self.saved_at = saved_at
        self.currency = currency
        self.user_email = user_email

        # Calculate total if not provided
        if total_amount is None:
            self.total_amount = self._calculate_total()
        else:
            self.total_amount = total_amount

    def _calculate_total(self) -> float:
        """
        Internal method to calculate total from items, tax, and discounts.

        Formula: (sum of all items) + tax - discounts

        Returns:
            float: Calculated total
        """
        items_total = sum(item.price * item.quantity for item in self.items)
        return items_total + self.tax_amount - self.discount_amount

    def get_subtotal(self) -> float:
        """
        Get subtotal (items only, before tax and discounts).

        Returns:
            float: Subtotal amount
        """
        return sum(item.price * item.quantity for item in self.items)

    def to_dict(self) -> Dict:
        """
        Convert receipt to dictionary format for database storage.

        Returns:
            Dict: Receipt data as dictionary
        """
        return {
            'id': self.receipt_id,
            'store_name': self.store_name,
            'purchase_date': self.purchase_date,
            'items': [item.to_dict() for item in self.items],
            'subtotal': self.get_subtotal(),
            'tax_amount': self.tax_amount,
            'discount_amount': self.discount_amount,
            'total_amount': self.total_amount,
            'saved_at': self.saved_at,
            'currency': self.currency,
            'user_email': self.user_email
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Receipt':
        """
        Create a Receipt from a dictionary.

        This is useful when loading data from the database.

        Args:
            data (Dict): Dictionary with receipt data

        Returns:
            Receipt: New receipt instance
        """
        # Convert item dictionaries to ReceiptItem objects
        items = [ReceiptItem.from_dict(item_data) for item_data in data.get('items', [])]

        return cls(
            items=items,
            store_name=data.get('store_name'),
            purchase_date=data.get('purchase_date'),
            tax_amount=data.get('tax_amount', 0.0),
            discount_amount=data.get('discount_amount', 0.0),
            total_amount=data.get('total_amount'),
            receipt_id=data.get('id'),
            saved_at=data.get('saved_at'),
            currency=data.get('currency', 'USD'),
            user_email=data.get('user_email')
        )

    @classmethod
    def from_llm_response(cls, llm_data: Dict, valid_categories: Optional[List[str]] = None) -> 'Receipt':
        """
        Create a Receipt from LLM (Claude) response data.

        The LLM returns data in a specific format, this method
        converts it to our Receipt model.

        Args:
            llm_data (Dict): Data extracted by LLM from receipt image

        Returns:
            Receipt: New receipt instance

        Note: This method handles the conversion between LLM's format
              and our internal format
        """
        # Convert LLM items to ReceiptItem objects
        items = []
        for item_data in llm_data.get('items', []):
            # Quantity can be None, a float (weight-based items), or missing —
            # convert safely and treat anything <= 0 as 1.
            raw_qty = item_data.get('quantity')
            try:
                quantity = max(1, int(float(raw_qty))) if raw_qty is not None else 1
            except (ValueError, TypeError):
                quantity = 1

            raw_category = item_data.get('category', 'Other')
            category = raw_category if (valid_categories and raw_category in valid_categories) else 'Other'

            amount, unit = _resolve_amount_unit(item_data.get('amount'), item_data.get('unit'))

            item = ReceiptItem(
                name=item_data.get('name', 'Unknown Item'),
                price=float(item_data.get('price') or 0.0),
                quantity=quantity,
                category=category,
                amount=amount,
                unit=unit
            )
            items.append(item)

        return cls(
            items=items,
            store_name=llm_data.get('store_name'),
            purchase_date=llm_data.get('purchase_date'),
            tax_amount=float(llm_data.get('tax_amount', 0.0)),
            discount_amount=float(llm_data.get('discount_amount', 0.0)),
            total_amount=float(llm_data.get('total_amount', 0.0)),
            currency=llm_data.get('currency', 'USD')
        )

    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate receipt data.

        Checks:
        - Has at least one item
        - All prices are non-negative
        - Total amount is non-negative

        Returns:
            tuple[bool, Optional[str]]: (is_valid, error_message)
                - (True, None) if valid
                - (False, "error message") if invalid
        """
        # Check if there are any items
        if not self.items:
            return False, "Receipt must have at least one item"

        # Check if all prices are non-negative
        for item in self.items:
            if item.price < 0:
                return False, f"Item '{item.name}' has negative price"
            if item.quantity <= 0:
                return False, f"Item '{item.name}' has invalid quantity"

        # Check if amounts are valid
        if self.total_amount < 0:
            return False, "Total amount cannot be negative"
        if self.tax_amount < 0:
            return False, "Tax amount cannot be negative"
        if self.discount_amount < 0:
            return False, "Discount amount cannot be negative"

        # All checks passed
        return True, None

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (f"Receipt(store='{self.store_name}', "
                f"date='{self.purchase_date}', "
                f"items={len(self.items)}, "
                f"total={self.total_amount})")
