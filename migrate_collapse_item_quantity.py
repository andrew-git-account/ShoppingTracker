"""
One-time migration (SP-053): folds every receipt item's quantity into its line
total, so an item is just an amount of a unit with a price that is the whole
line total, and quantity is always 1.

For each row in receipt_items with quantity > 1 it applies the same rule the
app uses when loading old data (app.models.fold_quantity_into_total):
    price  = price * quantity
    amount = quantity   (only for a 'piece' item whose amount is the default 1.0)
    quantity = 1

Safe by default: without --apply it only reports what it WOULD change. With
--apply it first copies the database to a backup file, then updates the rows in
one transaction and checks that each receipt's sum of item prices is unchanged.
Running it again afterwards changes nothing.

Run from the project root:
    python migrate_collapse_item_quantity.py            # dry run
    python migrate_collapse_item_quantity.py --apply    # really do it
"""

import argparse
import os
import shutil
import sqlite3

from app.models import fold_quantity_into_total

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'shopping_tracker.db')
BACKUP_SUFFIX = '.bak-sp053'


def _receipt_sums(conn):
    """Sum of price * quantity per receipt - what the old model counted as the items' value."""
    rows = conn.execute(
        'SELECT receipt_id, SUM(price * quantity) FROM receipt_items GROUP BY receipt_id'
    ).fetchall()
    return {receipt_id: total for receipt_id, total in rows}


def migrate(db_path=DEFAULT_DB_PATH, apply=False, out=print):
    """
    Fold quantity into price/amount for every receipt item with quantity > 1.

    Returns:
        int: how many item rows were (or, in a dry run, would be) changed.
    """
    if not os.path.exists(db_path):
        out(f"No database found at {db_path} - nothing to migrate.")
        return 0

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            'SELECT id, name, price, quantity, amount, unit FROM receipt_items WHERE quantity > 1'
        ).fetchall()
        if not rows:
            out("No items with quantity > 1 - nothing to migrate.")
            return 0

        changes = []
        for item_id, name, price, quantity, amount, unit in rows:
            new_price, new_amount = fold_quantity_into_total(price, quantity, amount, unit)
            changes.append((item_id, name, price, quantity, amount, new_price, new_amount, unit))
            # ASCII-only so the Windows console (cp1252) never chokes on item names.
            safe_name = name.encode('ascii', 'replace').decode()
            out(f"  {safe_name}: {quantity} x {price:.2f} ({amount:g} {unit}) -> "
                f"{new_price:.2f} ({new_amount:g} {unit})")

        if not apply:
            out(f"Dry run: {len(changes)} item(s) would change. Re-run with --apply to do it.")
            return len(changes)

        backup_path = db_path + BACKUP_SUFFIX
        shutil.copyfile(db_path, backup_path)
        out(f"Backup written to {backup_path}")

        sums_before = _receipt_sums(conn)
        with conn:  # one transaction: all rows change, or none do
            for item_id, _name, _price, _quantity, _amount, new_price, new_amount, _unit in changes:
                conn.execute(
                    'UPDATE receipt_items SET price = ?, amount = ?, quantity = 1 WHERE id = ?',
                    (new_price, new_amount, item_id)
                )
        sums_after = _receipt_sums(conn)

        mismatched = [
            rid for rid, total in sums_before.items()
            if abs(total - sums_after.get(rid, 0.0)) > 0.005
        ]
        if mismatched:
            out(f"WARNING: item totals changed for {len(mismatched)} receipt(s): {mismatched}. "
                f"Restore the backup {backup_path} and investigate.")
        else:
            out(f"Migration complete: {len(changes)} item(s) updated; every receipt's item total is unchanged.")
        return len(changes)
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Fold item quantity into the line total (SP-053).")
    parser.add_argument('--apply', action='store_true', help="really change the database (default: dry run)")
    parser.add_argument('--db', default=DEFAULT_DB_PATH, help="path to the SQLite database")
    args = parser.parse_args()
    migrate(args.db, apply=args.apply)
