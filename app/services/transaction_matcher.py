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

        The link is written on the *receipt* (see SP-037) via
        receipt_service.update_receipt - not a recursion risk even though that
        method re-invokes match_receipt on success: the receipt object is
        mutated with its new linked_transaction_id *before* this call, so the
        re-entrant match_receipt sees that already-set field and returns
        immediately via its own guard.
        """
        receipts = self.receipt_service.get_all_receipts(transaction.user_email)

        # Skip if this transaction already has one or more receipts linked to
        # it - automatic matching never adds a receipt on top of an existing
        # link, whether that link is automatic or manual (SP-038).
        if any(r.linked_transaction_id == transaction.transaction_id for r in receipts):
            return

        candidates = [
            r for r in receipts
            if not r.linked_transaction_id and _core_match(transaction, r)
        ]

        match = _narrow(candidates, lambda r: _substring_match(transaction.description, r.store_name))
        if match is not None:
            match.linked_transaction_id = transaction.transaction_id
            self.receipt_service.update_receipt(match.receipt_id, match.user_email, match)

    def match_receipt(self, receipt: Receipt) -> None:
        """
        Try to link an existing unlinked transaction to a newly-saved or
        newly-edited receipt. Called after a receipt is saved (direct upload,
        draft promotion) or edited.
        """
        # A receipt belongs to at most one transaction (see SP-037) - skip if
        # already linked. This also stops the re-entrant call
        # receipt_service.update_receipt makes back into match_receipt after
        # this method's own write below (see match_transaction's docstring).
        if receipt.linked_transaction_id:
            return

        other_receipts = self.receipt_service.get_all_receipts(receipt.user_email)
        claimed_transaction_ids = {
            r.linked_transaction_id for r in other_receipts if r.linked_transaction_id
        }

        candidates = [
            t for t in self.transaction_service.get_all_transactions(receipt.user_email)
            if t.transaction_id not in claimed_transaction_ids and _core_match(t, receipt)
        ]

        match = _narrow(candidates, lambda t: _substring_match(t.description, receipt.store_name))
        if match is not None:
            receipt.linked_transaction_id = match.transaction_id
            self.receipt_service.update_receipt(receipt.receipt_id, receipt.user_email, receipt)
