"""SP-053: the one-time script that folds item quantity into the line total."""

import os
import shutil
import sqlite3

import pytest

from migrate_collapse_item_quantity import BACKUP_SUFFIX, migrate


@pytest.fixture
def db_path(tmp_path):
    """A temporary database with just the receipt_items table the script touches."""
    path = str(tmp_path / "test.db")
    conn = sqlite3.connect(path)
    conn.execute('''
        CREATE TABLE receipt_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_id TEXT NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            amount REAL NOT NULL DEFAULT 1.0,
            unit TEXT NOT NULL DEFAULT 'piece'
        )
    ''')
    rows = [
        # (receipt_id, name, price, quantity, amount, unit)
        ("r1", "Yoghurt", 1.50, 3, 1.0, "piece"),   # piece, default amount -> 4.50, 3 piece
        ("r1", "Rice", 3.00, 2, 1.5, "kg"),         # kg -> 6.00, amount unchanged
        ("r2", "Couscous", 3.80, 2, 2.0, "piece"),  # piece, amount already 2 -> 7.60, 2 piece
        ("r2", "Milk", 2.99, 1, 1.0, "piece"),      # quantity 1 -> untouched
    ]
    conn.executemany(
        'INSERT INTO receipt_items (receipt_id, name, price, quantity, amount, unit) VALUES (?, ?, ?, ?, ?, ?)',
        rows
    )
    conn.commit()
    conn.close()
    return path


def _items(path):
    conn = sqlite3.connect(path)
    try:
        return {
            name: (price, quantity, amount, unit)
            for name, price, quantity, amount, unit in conn.execute(
                'SELECT name, price, quantity, amount, unit FROM receipt_items'
            )
        }
    finally:
        conn.close()


def _sums(path):
    conn = sqlite3.connect(path)
    try:
        return dict(conn.execute('SELECT receipt_id, SUM(price * quantity) FROM receipt_items GROUP BY receipt_id'))
    finally:
        conn.close()


class TestMigrateCollapseItemQuantity:

    def test_dry_run_changes_nothing_and_makes_no_backup(self, db_path):
        before = _items(db_path)
        messages = []
        changed = migrate(db_path, apply=False, out=messages.append)
        assert changed == 3
        assert _items(db_path) == before
        assert not os.path.exists(db_path + BACKUP_SUFFIX)
        assert any("Dry run" in m for m in messages)

    def test_apply_folds_quantity_into_price_and_amount(self, db_path):
        migrate(db_path, apply=True, out=lambda m: None)
        items = _items(db_path)
        assert items["Yoghurt"] == (pytest.approx(4.50), 1, 3.0, "piece")
        assert items["Rice"] == (pytest.approx(6.00), 1, 1.5, "kg")
        assert items["Couscous"] == (pytest.approx(7.60), 1, 2.0, "piece")
        assert items["Milk"] == (2.99, 1, 1.0, "piece")

    def test_apply_keeps_every_receipts_item_total(self, db_path):
        before = _sums(db_path)
        migrate(db_path, apply=True, out=lambda m: None)
        after = _sums(db_path)
        assert after == {rid: pytest.approx(total) for rid, total in before.items()}

    def test_apply_writes_backup_of_the_original_data(self, db_path):
        original = _items(db_path)
        migrate(db_path, apply=True, out=lambda m: None)
        assert _items(db_path + BACKUP_SUFFIX) == original

    def test_second_run_changes_nothing(self, db_path):
        migrate(db_path, apply=True, out=lambda m: None)
        after_first = _items(db_path)
        assert migrate(db_path, apply=True, out=lambda m: None) == 0
        assert _items(db_path) == after_first

    def test_missing_database_is_reported_not_created(self, tmp_path):
        missing = str(tmp_path / "nope.db")
        messages = []
        assert migrate(missing, apply=True, out=messages.append) == 0
        assert not os.path.exists(missing)
        assert any("No database" in m for m in messages)
