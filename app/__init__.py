"""
Flask application initialization.

This module sets up the Flask application and configures it.
"""

from flask import Flask


def create_app():
    """
    Application factory function.

    This pattern (factory function) is recommended for Flask apps because:
    - Can create multiple app instances (useful for testing)
    - Configuration is centralized
    - Extension initialization is cleaner
    - Follows Flask best practices

    Returns:
        Flask: Configured Flask application instance
    """
    # Create Flask app instance
    app = Flask(__name__)

    # Load configuration
    # Configuration will be set in main.py based on .env file

    return app
