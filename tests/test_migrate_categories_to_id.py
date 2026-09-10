"""
Tests for migrate_categories_to_id.py (SP-044).

Builds an old-schema SQLite file by hand (matching the pre-migration DDL:
categories(name TEXT PRIMARY KEY), receipt_items/transactions with a plain
category TEXT column) rather than going through the app's SqliteDatabase/
SqliteTransactionDatabase/SqliteCategoryDatabase classes, since those now
create the *new* schema directly - the whole point here is to exercise the
migration path a real pre-existing production database would take.
"""

import sqlite3

from migrate_categories_to_id import migrate


def _build_old_schema_db(db_path):
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute('CREATE TABLE categories (name TEXT PRIMARY KEY)')
            conn.executemany(
                'INSERT INTO categories (name) VALUES (?)',
                [('Other',), ('Food & Groceries',)]
            )
            conn.execute('''
                CREATE TABLE receipt_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    receipt_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    category TEXT NOT NULL DEFAULT 'Other',
                    amount REAL NOT NULL DEFAULT 1.0,
                    unit TEXT NOT NULL DEFAULT 'piece',
                    position INTEGER NOT NULL
                )
            ''')
            conn.execute('''
                CREATE TABLE transactions (
                    id TEXT PRIMARY KEY,
                    date TEXT,
                    description TEXT NOT NULL DEFAULT '',
                    amount REAL NOT NULL DEFAULT 0,
                    currency TEXT NOT NULL DEFAULT 'USD',
                    direction TEXT NOT NULL DEFAULT 'debit',
                    category TEXT NOT NULL DEFAULT 'Other',
                    source TEXT NOT NULL DEFAULT 'card',
                    statement_id TEXT,
                    saved_at TEXT,
                    user_email TEXT NOT NULL,
                    is_deleted INTEGER NOT NULL DEFAULT 0
                )
            ''')
            conn.execute(
                "INSERT INTO receipt_items (receipt_id, name, price, quantity, category, position) "
                "VALUES ('r1', 'Milk', 2.99, 1, 'Food & Groceries', 0)"
            )
            # A legacy/typo'd category with no matching row in `categories` -
            # the orphaned case the migration must still resolve.
            conn.execute(
                "INSERT INTO receipt_items (receipt_id, name, price, quantity, category, position) "
                "VALUES ('r1', 'Widget', 1.50, 1, 'Legacy Category', 1)"
            )
            conn.execute(
                "INSERT INTO transactions (id, description, amount, category, user_email) "
                "VALUES ('t1', 'Corner Store', 12.50, 'Other', 'owner@example.com')"
            )
    finally:
        conn.close()


def _connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _has_column(conn, table, column):
    return any(row['name'] == column for row in conn.execute(f'PRAGMA table_info({table})'))


def test_categories_gains_id_column_preserving_existing_names(tmp_path):
    db_path = str(tmp_path / 'shopping_tracker.db')
    _build_old_schema_db(db_path)

    migrate(db_path)

    conn = _connect(db_path)
    try:
        assert _has_column(conn, 'categories', 'id')
        names = {row['name'] for row in conn.execute('SELECT name FROM categories')}
        assert {'Other', 'Food & Groceries'} <= names
    finally:
        conn.close()


def test_orphaned_category_text_gets_its_own_row(tmp_path):
    db_path = str(tmp_path / 'shopping_tracker.db')
    _build_old_schema_db(db_path)

    migrate(db_path)

    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT r.category_id, c.name FROM receipt_items r "
            "JOIN categories c ON r.category_id = c.id WHERE r.name = 'Widget'"
        ).fetchone()
        assert row['name'] == 'Legacy Category'
    finally:
        conn.close()


def test_every_row_gets_a_non_null_category_id(tmp_path):
    db_path = str(tmp_path / 'shopping_tracker.db')
    _build_old_schema_db(db_path)

    migrate(db_path)

    conn = _connect(db_path)
    try:
        for table in ('receipt_items', 'transactions'):
            remaining_null = conn.execute(
                f'SELECT COUNT(*) AS cnt FROM {table} WHERE category_id IS NULL'
            ).fetchone()['cnt']
            assert remaining_null == 0
    finally:
        conn.close()


def test_category_id_resolves_to_correct_name(tmp_path):
    db_path = str(tmp_path / 'shopping_tracker.db')
    _build_old_schema_db(db_path)

    migrate(db_path)

    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT c.name FROM transactions t JOIN categories c ON t.category_id = c.id "
            "WHERE t.id = 't1'"
        ).fetchone()
        assert row['name'] == 'Other'
    finally:
        conn.close()


def test_old_category_column_dropped(tmp_path):
    db_path = str(tmp_path / 'shopping_tracker.db')
    _build_old_schema_db(db_path)

    migrate(db_path)

    conn = _connect(db_path)
    try:
        assert not _has_column(conn, 'receipt_items', 'category')
        assert not _has_column(conn, 'transactions', 'category')
    finally:
        conn.close()


def test_running_twice_is_a_safe_no_op(tmp_path):
    db_path = str(tmp_path / 'shopping_tracker.db')
    _build_old_schema_db(db_path)

    migrate(db_path)
    conn = _connect(db_path)
    try:
        before_categories = {row['id']: row['name'] for row in conn.execute('SELECT id, name FROM categories')}
        before_item_category_ids = [
            row['category_id'] for row in conn.execute('SELECT category_id FROM receipt_items ORDER BY id')
        ]
    finally:
        conn.close()

    migrate(db_path)  # second run should no-op every step

    conn = _connect(db_path)
    try:
        after_categories = {row['id']: row['name'] for row in conn.execute('SELECT id, name FROM categories')}
        after_item_category_ids = [
            row['category_id'] for row in conn.execute('SELECT category_id FROM receipt_items ORDER BY id')
        ]
        assert after_categories == before_categories
        assert after_item_category_ids == before_item_category_ids
    finally:
        conn.close()


def test_missing_database_file_does_not_raise(tmp_path):
    missing_path = str(tmp_path / 'does_not_exist.db')
    migrate(missing_path)  # should just print a message and return
