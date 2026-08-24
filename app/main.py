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

from .database import JSONDatabase, UsageLogDatabase, JSONTransactionDatabase
from .database.json_db import CategoryDatabase
from .services import (
    LLMService, ReceiptService, AuthService, TransactionService, StatementService, TransactionMatcher
)

# Load environment variables from .env file - this must happen before any
# os.getenv() calls below. We don't use load_dotenv(override=True) blindly:
# the OS can pre-set some vars to an empty string (e.g. ANTHROPIC_API_KEY=""
# on this Windows machine) which would otherwise block .env from filling
# them in - but a blanket override also clobbers deliberately-set values,
# like a test's monkeypatched DATA_FOLDER (see SP-019). Instead, clear out
# any pre-existing *empty-string* env vars first, then load normally, so a
# real non-empty value (from the OS or a test) always wins over .env, and
# only a blank one gets filled in.
for _env_key, _env_value in list(os.environ.items()):
    if _env_value == '':
        del os.environ[_env_key]
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
    # 15MB default - was 5MB, sized for receipt images; widened for statement
    # PDF uploads too (see SP-025), harmless for receipts either way.
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_UPLOAD_SIZE', 15728640))

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

    # Categories
    categories_path = os.path.join(data_folder, 'categories.json')
    category_db = CategoryDatabase(categories_path)
    category_db.initialize()
    valid_categories = [c['name'] for c in category_db.get_all_categories()]
    print(f"[OK] Categories loaded: {valid_categories}")

    # LLM Usage Log (see SP-020)
    usage_log_path = os.path.join(data_folder, 'llm_usage.json')
    usage_log_db = UsageLogDatabase(usage_log_path)
    print(f"[OK] Usage log initialized: {usage_log_path}")

    # LLM Service
    llm_service = LLMService(
        api_key=anthropic_api_key,
        model=llm_model,
        valid_categories=valid_categories,
        usage_logger=usage_log_db
    )
    print(f"[OK] LLM service initialized: {llm_model}")

    # Receipt Service
    receipt_service = ReceiptService(
        database=database,
        llm_service=llm_service,
        upload_folder=upload_folder,
        allowed_extensions=allowed_extensions,
        valid_categories=valid_categories
    )
    print(f"[OK] Receipt service initialized")

    # Transaction storage + Statement Service (see SP-025)
    transactions_path = os.path.join(data_folder, 'transactions.json')
    transaction_db = JSONTransactionDatabase(transactions_path)
    transaction_service = TransactionService(database=transaction_db)
    print(f"[OK] Transaction service initialized: {transactions_path}")

    statement_service = StatementService(
        transaction_service=transaction_service,
        llm_service=llm_service,
        upload_folder=upload_folder,
        allowed_extensions={'pdf'},
        valid_categories=valid_categories
    )
    print(f"[OK] Statement service initialized")

    # Transaction Matcher (see SP-026) - built after receipt_service and
    # transaction_service exist, since it depends on both, then assigned onto
    # the services that trigger it (which were built without one, since the
    # matcher didn't exist yet).
    matcher = TransactionMatcher(receipt_service=receipt_service, transaction_service=transaction_service)
    receipt_service.matcher = matcher
    statement_service.matcher = matcher
    print(f"[OK] Transaction matcher initialized")

    # Auth Service
    allowed_users_path = os.path.join(data_folder, 'allowed_users.json')
    auth_service = AuthService(
        allowed_users_path=allowed_users_path,
        smtp_host=os.getenv('SMTP_HOST', 'smtp.gmail.com'),
        smtp_port=int(os.getenv('SMTP_PORT', '587')),
        smtp_user=os.getenv('SMTP_USER', ''),
        smtp_password=os.getenv('SMTP_PASSWORD', ''),
        smtp_from=os.getenv('SMTP_FROM', ''),
    )
    print(f"[OK] Auth service initialized: {allowed_users_path}")

    # ===================================
    # Make services available to routes
    # ===================================
    # We attach services to the app object so routes can access them
    app.receipt_service = receipt_service
    app.database = database
    app.auth_service = auth_service
    app.usage_log_db = usage_log_db
    app.transaction_service = transaction_service
    app.statement_service = statement_service
    app.transaction_matcher = matcher

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
