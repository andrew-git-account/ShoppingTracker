"""
Database package initialization.

This package contains the database abstraction layer that allows
easy switching between different database implementations (JSON, SQL, etc.)
"""

# Import the base class and implementations for easy access
from .base import Database
from .json_db import JSONDatabase
from .usage_log_db import UsageLogDatabase

# Export the main classes
__all__ = ['Database', 'JSONDatabase', 'UsageLogDatabase']
