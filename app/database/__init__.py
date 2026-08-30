"""
Database package initialization.

This package contains the database abstraction layer that allows
easy switching between different database implementations (JSON, SQL, etc.)
"""

# Import the base class and implementations for easy access
from .base import Database
from .json_db import JSONDatabase
from .sqlite_db import SqliteDatabase
from .usage_log_db import UsageLogDatabase
from .sqlite_usage_log_db import SqliteUsageLogDatabase
from .transaction_db import JSONTransactionDatabase
from .sqlite_transaction_db import SqliteTransactionDatabase
from .sqlite_category_db import SqliteCategoryDatabase
from .sqlite_allowed_users_db import SqliteAllowedUsersDatabase
from .sqlite_feedback_db import SqliteFeedbackDatabase

# Export the main classes
__all__ = [
    'Database', 'JSONDatabase', 'SqliteDatabase', 'UsageLogDatabase', 'SqliteUsageLogDatabase',
    'JSONTransactionDatabase', 'SqliteTransactionDatabase', 'SqliteCategoryDatabase',
    'SqliteAllowedUsersDatabase', 'SqliteFeedbackDatabase'
]
