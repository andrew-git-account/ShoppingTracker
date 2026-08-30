"""
One-time migration: moves the LLM usage log from data/llm_usage.json (JSON
file, UsageLogDatabase) to data/shopping_tracker.db (SQLite,
SqliteUsageLogDatabase) - see SP-036. Shares the same .db file SP-034/035
already write to.

Preserves every record's original timestamp exactly (append-only log, no
id/ownership fields to preserve beyond that) - deliberately does NOT go
through SqliteUsageLogDatabase.log_call(), which stamps datetime.now().

Run once from the project root:
    python migrate_usage_log_to_sqlite.py
"""

import json
import os
import sqlite3

from app.database.sqlite_usage_log_db import SqliteUsageLogDatabase

USAGE_LOG_JSON_PATH = os.path.join(os.path.dirname(__file__), 'data', 'llm_usage.json')
SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'shopping_tracker.db')


def migrate():
    if not os.path.exists(USAGE_LOG_JSON_PATH):
        print(f"No usage log file found at {USAGE_LOG_JSON_PATH} — nothing to migrate.")
        return

    with open(USAGE_LOG_JSON_PATH, 'r', encoding='utf-8') as f:
        records = json.load(f)

    # Reuse SqliteUsageLogDatabase.initialize() for schema creation rather
    # than duplicating the CREATE TABLE statement here.
    SqliteUsageLogDatabase(SQLITE_DB_PATH)

    conn = sqlite3.connect(SQLITE_DB_PATH)
    try:
        written = 0
        with conn:
            for record in records:
                conn.execute(
                    '''INSERT INTO usage_log
                       (timestamp, user_email, model, input_tokens, output_tokens,
                        cost_usd, success, is_retry)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        record.get('timestamp'),
                        record.get('user_email'),
                        record.get('model'),
                        record.get('input_tokens', 0),
                        record.get('output_tokens', 0),
                        record.get('cost_usd', 0.0),
                        int(bool(record.get('success', False))),
                        int(bool(record.get('is_retry', False))),
                    )
                )
                written += 1
    finally:
        conn.close()

    print(f"Migration complete: {len(records)} record(s) read, {written} record(s) written to {SQLITE_DB_PATH}.")


if __name__ == '__main__':
    migrate()
