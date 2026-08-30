"""
One-time migration: moves the allowed-users list from data/allowed_users.json
(hand-rolled JSON read/write in AuthService) to data/shopping_tracker.db
(SQLite, SqliteAllowedUsersDatabase) - see SP-036. Shares the same .db file
SP-034/035 already write to.

Tolerant of the same two entry shapes AuthService's old _load_allowed_users
handled (a bare email string, or an {"email","is_admin","is_blocked"} object
with either key optionally missing) - this is the one place that tolerance
still matters, since it's reading the legacy JSON file one last time.
Preserves email case exactly as stored (see the COLLATE NOCASE note in
SqliteAllowedUsersDatabase - case is never normalized, only compared
case-insensitively at lookup time).

Run once from the project root:
    python migrate_allowed_users_to_sqlite.py
"""

import json
import os

from app.database.sqlite_allowed_users_db import SqliteAllowedUsersDatabase

ALLOWED_USERS_JSON_PATH = os.path.join(os.path.dirname(__file__), 'data', 'allowed_users.json')
SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'shopping_tracker.db')


def migrate():
    if not os.path.exists(ALLOWED_USERS_JSON_PATH):
        print(f"No allowed users file found at {ALLOWED_USERS_JSON_PATH} — nothing to migrate.")
        return

    with open(ALLOWED_USERS_JSON_PATH, 'r', encoding='utf-8') as f:
        raw_entries = json.load(f)

    users = []
    for entry in raw_entries:
        if isinstance(entry, str):
            users.append({'email': entry, 'is_admin': False, 'is_blocked': False})
        else:
            users.append({
                'email': entry.get('email', ''),
                'is_admin': bool(entry.get('is_admin', False)),
                'is_blocked': bool(entry.get('is_blocked', False)),
            })

    SqliteAllowedUsersDatabase(SQLITE_DB_PATH).save_all_users(users)

    print(f"Migration complete: {len(raw_entries)} user(s) read, {len(users)} user(s) written to {SQLITE_DB_PATH}.")


if __name__ == '__main__':
    migrate()
