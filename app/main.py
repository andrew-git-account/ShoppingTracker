"""
Main application entry point.

This file:
1. Loads environment variables
2. Creates and configures the Flask app
3. Initializes services (database, LLM)
4. Registers routes
5. Starts the server

To run the application:
    python app/main.py

Or:
    flask --app app.main run
"""

import os
from dotenv import load_dotenv
from flask import Flask

from .database import JSONDatabase
from .services import LLMService, ReceiptService

# Load environment variables from .env file
# This must be done BEFORE accessing os.getenv()
load_dotenv()


def create_app() -> Flask:
    """
    Create and configure the Flask application.

    This is the application factory pattern. It:
    1. Creates Flask app
    2. Loads configuration from environment
    3. Initializes services
    4. Registers routes

    Returns:
        Flask: Configured application instance
    """
    # Create Flask app
    # When running as a module, we need to specify template and static folders
    # relative to the project root (parent of app folder)
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    app = Flask(
        __name__,
        template_folder=os.path.join(project_root, 'templates'),
        static_folder=os.path.join(project_root, 'static')
    )

    # ===================================
    # Configuration from environment
    # ===================================

    # Flask configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_UPLOAD_SIZE', 5242880))  # 5MB default

    # Application settings
    upload_folder = os.getenv('UPLOAD_FOLDER', './uploads')
    data_folder = os.getenv('DATA_FOLDER', './data')
    allowed_extensions = set(os.getenv('ALLOWED_EXTENSIONS', 'jpg,jpeg,png').split(','))

    # LLM settings
    anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
    llm_model = os.getenv('LLM_MODEL', 'claude-3-5-sonnet-20241022')

    # Validate required configuration
    if not anthropic_api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not found in environment variables. "
            "Please copy .env.example to .env and add your API key."
        )

    # ===================================
    # Initialize Services
    # ===================================

    # Database
    database_path = os.path.join(data_folder, 'receipts.json')
    database = JSONDatabase(database_path)
    print(f"[OK] Database initialized: {database_path}")

    # LLM Service
    llm_service = LLMService(
        api_key=anthropic_api_key,
        model=llm_model
    )
    print(f"[OK] LLM service initialized: {llm_model}")

    # Receipt Service
    receipt_service = ReceiptService(
        database=database,
        llm_service=llm_service,
        upload_folder=upload_folder,
        allowed_extensions=allowed_extensions
    )
    print(f"[OK] Receipt service initialized")

    # ===================================
    # Make services available to routes
    # ===================================
    # We attach services to the app object so routes can access them
    app.receipt_service = receipt_service
    app.database = database

    # ===================================
    # Register routes
    # ===================================
    from . import routes
    routes.register_routes(app)
    print(f"[OK] Routes registered")

    return app


def main():
    """
    Main function to run the development server.

    This is called when running: python app/main.py
    """
    print("=" * 50)
    print("Shopping Tracker - Starting Application")
    print("=" * 50)

    # Create app
    app = create_app()

    # Get host and port from environment
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'development') == 'development'

    print(f"\n[OK] Application ready!")
    print(f"[OK] Running on: http://{host}:{port}")
    print(f"[OK] Debug mode: {debug}")
    print("\nPress Ctrl+C to stop the server\n")
    print("=" * 50)

    # Run the development server
    app.run(host=host, port=port, debug=debug)


# This allows running the app with: python app/main.py
if __name__ == '__main__':
    main()
