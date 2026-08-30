"""
One-time migration: moves the category vocabulary from data/categories.json
(JSON file, CategoryDatabase) to data/shopping_tracker.db (SQLite,
SqliteCategoryDatabase) - see SP-036. Shares the same .db file SP-034/035
already write to.

This is a *different* script from the existing migrate_categories.py, which
solved a different, already-completed problem (backfilling a missing
'category' field on receipt line items).

Category names only - the id column in categories.json is dropped (nothing
downstream ever reads it; see SP-036's verification notes).

Run once from the project root:
    python migrate_categories_to_sqlite.py
"""

import json
import os
import sqlite3

from app.database.sqlite_category_db import SqliteCategoryDatabase

CATEGORIES_JSON_PATH = os.path.join(os.path.dirname(__file__), 'data', 'categories.json')
SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'shopping_tracker.db')


def migrate():
    if not os.path.exists(CATEGORIES_JSON_PATH):
        print(f"No categories file found at {CATEGORIES_JSON_PATH} — nothing to migrate.")
        return

    with open(CATEGORIES_JSON_PATH, 'r', encoding='utf-8') as f:
        categories = json.load(f)

    # Reuse SqliteCategoryDatabase.initialize() for schema creation - it
    # also auto-seeds the default list if the table is empty, so clear that
    # seed data first and replace it with whatever categories.json actually
    # has (preserves any custom categories an admin added by hand).
    SqliteCategoryDatabase(SQLITE_DB_PATH)

    conn = sqlite3.connect(SQLITE_DB_PATH)
    try:
        written = 0
        with conn:
            conn.execute('DELETE FROM categories')
            for category in categories:
                name = category.get('name') if isinstance(category, dict) else category
                if not name:
                    continue
                conn.execute('INSERT OR IGNORE INTO categories (name) VALUES (?)', (name,))
                written += 1
    finally:
        conn.close()

    print(f"Migration complete: {len(categories)} categor(y/ies) read, {written} written to {SQLITE_DB_PATH}.")


if __name__ == '__main__':
    migrate()
