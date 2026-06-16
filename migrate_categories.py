"""
One-time migration: assigns "Other" category to all existing receipt line items
that are missing a 'category' field.

Run once from the project root:
    python migrate_categories.py
"""

import json
import os

RECEIPTS_PATH = os.path.join(os.path.dirname(__file__), 'data', 'receipts.json')
DEFAULT_CATEGORY = "Other"


def migrate():
    if not os.path.exists(RECEIPTS_PATH):
        print(f"No receipts file found at {RECEIPTS_PATH} — nothing to migrate.")
        return

    with open(RECEIPTS_PATH, 'r', encoding='utf-8') as f:
        receipts = json.load(f)

    updated_items = 0
    for receipt in receipts:
        for item in receipt.get('items', []):
            if 'category' not in item:
                item['category'] = DEFAULT_CATEGORY
                updated_items += 1

    with open(RECEIPTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(receipts, f, indent=2, ensure_ascii=False)

    print(f"Migration complete: {updated_items} item(s) assigned category '{DEFAULT_CATEGORY}'.")


if __name__ == '__main__':
    migrate()
