"""
SQLite Feedback Database Implementation.

Stores user-submitted feedback to admins (see SP-039), in the shared
shopping_tracker.db file. Plain dicts in/out, no model class - nothing in
this SP loads a record back into a route or template, the same reasoning
that leaves usage_log with no corresponding class in app/models.py either.
"""

import os
import sqlite3
import uuid
from datetime import datetime
from typing import Dict, List


class SqliteFeedbackDatabase:
    """SQLite-backed storage for user feedback submissions."""

    def __init__(self, file_path: str):
        """
        Initialize the feedback database.

        Args:
            file_path (str): Path to the SQLite database file (shared with
                receipts/transactions/etc. in production)
        """
        self.file_path = file_path
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        conn = sqlite3.connect(self.file_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        """Create the feedback table if it doesn't exist."""
        conn = self._connect()
        try:
            with conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS feedback (
                        id TEXT PRIMARY KEY,
                        user_email TEXT NOT NULL,
                        message_type TEXT NOT NULL,
                        functionality TEXT NOT NULL,
                        message TEXT NOT NULL,
                        image_filename TEXT,
                        created_at TEXT NOT NULL
                    )
                ''')
        finally:
            conn.close()

    def save_feedback(self, feedback_data: Dict) -> str:
        """
        Save a feedback submission.

        Args:
            feedback_data (Dict): Feedback information to save (user_email,
                message_type, functionality, message, image_filename)

        Returns:
            str: The unique ID assigned to this feedback record
        """
        feedback_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()

        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    '''INSERT INTO feedback
                       (id, user_email, message_type, functionality, message,
                        image_filename, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (
                        feedback_id,
                        feedback_data.get('user_email'),
                        feedback_data.get('message_type'),
                        feedback_data.get('functionality'),
                        feedback_data.get('message'),
                        feedback_data.get('image_filename'),
                        created_at,
                    )
                )
        finally:
            conn.close()

        print(f"Saved feedback with ID: {feedback_id}")
        return feedback_id

    def get_all_feedback(self) -> List[Dict]:
        """
        Return every feedback record, oldest first.

        Not used by any route in this SP (no admin inbox UI yet) - exists so
        tests can verify persistence through the public interface instead of
        reaching around the class with a raw sqlite3 connection.
        """
        conn = self._connect()
        try:
            rows = conn.execute('SELECT * FROM feedback ORDER BY rowid ASC').fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
