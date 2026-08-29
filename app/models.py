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
        user_email: Optional[str] = None,
        linked_transaction_id: Optional[str] = None
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
            linked_transaction_id (str, optional): ID of the statement transaction
                that settled this receipt, if any (see SP-026/SP-037). A receipt
                belongs to at most one transaction, but several receipts can
                share the same transaction id - a few receipts paid off in one
                card charge (SP-038) - so the "many" side of the relationship
                holds the reference, not the transaction.
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
        self.linked_transaction_id = linked_transaction_id

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
            'user_email': self.user_email,
            'linked_transaction_id': self.linked_transaction_id
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
            user_email=data.get('user_email'),
            linked_transaction_id=data.get('linked_transaction_id')
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


class Transaction:
    """
    Represents a single line from a bank or credit-card statement (see SP-025).

    Deliberately thinner than Receipt - a statement line is never itemized.
    - date: Transaction date as printed on the statement
    - description: Merchant/payee string as printed, not normalized
    - amount: Transaction amount (always positive - "how much", not a signed
      balance change)
    - currency: ISO 4217 currency code
    - direction: "debit" (money out) or "credit" (money in) - independent of
      amount's sign, which always stays positive
    - category: Best-effort guess from the same category vocabulary receipt
      items use, since a statement line has no itemization to categorize from
    - source: Which kind of statement this came from - "bank" or "card"
    - statement_id: Shared by every transaction extracted from the same
      statement upload (SP-029) - groups them into one card in History,
      the way items are grouped under one receipt

    Whether this transaction is matched to a receipt (SP-026/SP-027) lives on
    the *receipt* side (`Receipt.linked_transaction_id`, see SP-037) - a
    transaction can have several receipts linked to it (SP-038), so the field
    belongs on the "many" side of the relationship, not here.
    """

    def __init__(
        self,
        date: Optional[str] = None,
        description: str = "",
        amount: float = 0.0,
        currency: str = "USD",
        direction: str = "debit",
        category: str = "Other",
        source: str = "card",
        statement_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
        saved_at: Optional[str] = None,
        user_email: Optional[str] = None,
        is_deleted: bool = False
    ):
        """
        Create a new transaction.

        Args:
            date (str, optional): Transaction date (YYYY-MM-DD)
            description (str): Merchant/payee description as printed
            amount (float): Transaction amount (positive)
            currency (str): ISO 4217 currency code (default "USD")
            direction (str): "debit" (money out) or "credit" (money in)
            category (str): Item category (default "Other")
            source (str): "bank" or "card"
            statement_id (str, optional): Shared ID for every transaction from
                the same statement upload
            transaction_id (str, optional): Unique ID (assigned by database)
            saved_at (str, optional): Save timestamp (assigned by database)
            user_email (str, optional): Email of the user who owns this transaction
            is_deleted (bool): Soft-delete flag, same spirit as Receipt (SP-002)
        """
        self.date = date
        self.description = description
        self.amount = amount
        self.currency = currency
        self.direction = direction
        self.category = category
        self.source = source
        self.statement_id = statement_id
        self.transaction_id = transaction_id
        self.saved_at = saved_at
        self.user_email = user_email
        self.is_deleted = is_deleted

    def to_dict(self) -> Dict:
        """
        Convert transaction to dictionary format for database storage.

        Returns:
            Dict: Transaction data as dictionary
        """
        return {
            'id': self.transaction_id,
            'date': self.date,
            'description': self.description,
            'amount': self.amount,
            'currency': self.currency,
            'direction': self.direction,
            'category': self.category,
            'source': self.source,
            'statement_id': self.statement_id,
            'saved_at': self.saved_at,
            'user_email': self.user_email,
            'is_deleted': self.is_deleted
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Transaction':
        """
        Create a Transaction from a dictionary.

        Args:
            data (Dict): Dictionary with transaction data

        Returns:
            Transaction: New transaction instance
        """
        return cls(
            date=data.get('date'),
            description=data.get('description', ''),
            amount=data.get('amount', 0.0),
            currency=data.get('currency', 'USD'),
            direction=data.get('direction', 'debit'),
            category=data.get('category', 'Other'),
            source=data.get('source', 'card'),
            statement_id=data.get('statement_id') or data.get('id'),
            transaction_id=data.get('id'),
            saved_at=data.get('saved_at'),
            user_email=data.get('user_email'),
            is_deleted=data.get('is_deleted', False)
        )

    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate transaction data (see SP-030).

        Returns:
            tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        if self.amount < 0:
            return False, "Amount cannot be negative"
        return True, None

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (f"Transaction(date='{self.date}', "
                f"description='{self.description}', "
                f"amount={self.amount}, "
                f"source='{self.source}')")
