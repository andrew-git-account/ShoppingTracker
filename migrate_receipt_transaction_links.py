"""
One-time migration: moves the receipt/transaction link from
Transaction.linked_receipt_id (old, one-to-one) to Receipt.linked_transaction_id
(new, one-to-many — see SP-037). For every transaction with a linked_receipt_id,
sets that receipt's linked_transaction_id accordingly.

Leaves the old linked_receipt_id key sitting unused in transactions.json
afterward (harmless — nothing reads it anymore) rather than doing a separate
cleanup pass.

Run once from the project root:
    python migrate_receipt_transaction_links.py
"""

import json
import os

TRANSACTIONS_PATH = os.path.join(os.path.dirname(__file__), 'data', 'transactions.json')
RECEIPTS_PATH = os.path.join(os.path.dirname(__file__), 'data', 'receipts.json')


def migrate():
    if not os.path.exists(TRANSACTIONS_PATH):
        print(f"No transactions file found at {TRANSACTIONS_PATH} — nothing to migrate.")
        return
    if not os.path.exists(RECEIPTS_PATH):
        print(f"No receipts file found at {RECEIPTS_PATH} — nothing to migrate.")
        return

    with open(TRANSACTIONS_PATH, 'r', encoding='utf-8') as f:
        transactions = json.load(f)
    with open(RECEIPTS_PATH, 'r', encoding='utf-8') as f:
        receipts = json.load(f)

    receipts_by_id = {r['receipt_id']: r for r in receipts}

    links_migrated = 0
    links_skipped_missing_receipt = 0
    for transaction in transactions:
        receipt_id = transaction.get('linked_receipt_id')
        if not receipt_id:
            continue
        receipt = receipts_by_id.get(receipt_id)
        if receipt is None:
            links_skipped_missing_receipt += 1
            continue
        receipt['linked_transaction_id'] = transaction['transaction_id']
        links_migrated += 1

    with open(RECEIPTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(receipts, f, indent=2, ensure_ascii=False)

    print(f"Migration complete: {links_migrated} link(s) migrated to Receipt.linked_transaction_id.")
    if links_skipped_missing_receipt:
        print(f"Skipped {links_skipped_missing_receipt} link(s) whose receipt_id no longer exists.")


if __name__ == '__main__':
    migrate()
