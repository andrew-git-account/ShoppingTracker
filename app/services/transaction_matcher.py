"""
Transaction Matcher - links statement transactions to receipts (see SP-026).

Conservative, one-to-one auto-matching so a receipt and the statement line it
corresponds to aren't both counted in Statistics (SP-028). Runs both
directions - triggered after a receipt is saved/edited and after a statement
upload creates new transactions - since either can arrive first. Deliberately
strict (exact date/amount only, no tolerance window): under-matching just
leaves a transaction unlinked (safe - SP-028 still counts it), while
over-matching would silently drop real spend from Statistics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Optional, TypeVar

from ..models import Receipt, Transaction

if TYPE_CHECKING:
    from .receipt_service import ReceiptService
    from .transaction_service import TransactionService

_T = TypeVar('_T')


def _date_for_receipt(receipt: Receipt) -> str:
    """Same purchase-date fallback as _month_key() in routes.py."""
    return receipt.purchase_date or receipt.saved_at[:10]


def _core_match(transaction: Transaction, receipt: Receipt) -> bool:
    """
    Debit only (see SP-032 - a credit is reconciled by hand via SP-027's
    manual link, not silently by automatic matching), same currency, exact
    amount (rounded to avoid float-representation noise), exact date.
    """
    return (
        transaction.direction == 'debit'
        and transaction.currency == receipt.currency
        and round(transaction.amount, 2) == round(receipt.total_amount, 2)
        and transaction.date == _date_for_receipt(receipt)
    )


def _substring_match(description: str, store_name: Optional[str]) -> bool:
    """Case-insensitive, either string containing the other."""
    if not description or not store_name:
        return False
    d, s = description.lower(), store_name.lower()
    return d in s or s in d


def _narrow(candidates: List[_T], matches_fn: Callable[[_T], bool]) -> Optional[_T]:
    """
    Exactly one candidate -> that one. More than one -> narrow by matches_fn,
    but only if that narrows it to exactly one. Otherwise (zero, or still
    ambiguous), don't guess.
    """
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        narrowed = [c for c in candidates if matches_fn(c)]
        if len(narrowed) == 1:
            return narrowed[0]
    return None


class TransactionMatcher:
    """Finds and links the receipt/transaction pair that represent the same purchase."""

    def __init__(self, receipt_service: 'ReceiptService', transaction_service: 'TransactionService'):
        self.receipt_service = receipt_service
        self.transaction_service = transaction_service

    def match_transaction(self, transaction: Transaction) -> None:
        """
        Try to link a newly-created transaction to an existing unlinked receipt.
        Called after a statement upload saves new transactions.
        """
        if transaction.linked_receipt_id:
            return

        linked_receipt_ids = {
            t.linked_receipt_id
            for t in self.transaction_service.get_all_transactions(transaction.user_email)
            if t.linked_receipt_id
        }
        candidates = [
            r for r in self.receipt_service.get_all_receipts(transaction.user_email)
            if r.receipt_id not in linked_receipt_ids and _core_match(transaction, r)
        ]

        match = _narrow(candidates, lambda r: _substring_match(transaction.description, r.store_name))
        if match is not None:
            transaction.linked_receipt_id = match.receipt_id
            self.transaction_service.update_transaction(
                transaction.transaction_id, transaction.user_email, transaction
            )

    def match_receipt(self, receipt: Receipt) -> None:
        """
        Try to link an existing unlinked transaction to a newly-saved or
        newly-edited receipt. Called after a receipt is saved (direct upload,
        draft promotion) or edited.
        """
        candidates = [
            t for t in self.transaction_service.get_all_transactions(receipt.user_email)
            if not t.linked_receipt_id and _core_match(t, receipt)
        ]

        match = _narrow(candidates, lambda t: _substring_match(t.description, receipt.store_name))
        if match is not None:
            match.linked_receipt_id = receipt.receipt_id
            self.transaction_service.update_transaction(
                match.transaction_id, match.user_email, match
            )
