"""
Flask routes - HTTP request handlers.

Routes are the "entry points" to our application. They:
1. Receive HTTP requests from the browser
2. Extract data from the request (form data, files, etc.)
3. Call business logic (services)
4. Return HTML responses (render templates)

Routes should be "thin" - they handle HTTP stuff and delegate
the actual work to services.
"""

from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.exceptions import RequestEntityTooLarge


def register_routes(app: Flask):
    """
    Register all routes with the Flask app.

    Args:
        app (Flask): Flask application instance

    Note: We define routes inside this function so they have access
          to the app instance and its attached services.
    """

    # ===================================
    # Home / Upload Page
    # ===================================

    @app.route('/')
    def index():
        """
        Home page - shows upload form.

        GET / → Returns upload.html template

        This is the default page users see when they visit the app.
        """
        return render_template('upload.html')

    @app.route('/upload', methods=['GET', 'POST'])
    def upload():
        """
        Upload receipt page.

        GET /upload → Shows upload form
        POST /upload → Processes uploaded receipt

        Flow for POST:
        1. Validate file was uploaded
        2. Process receipt with ReceiptService
        3. Show success message
        4. Redirect to history page
        """
        if request.method == 'GET':
            # Show the upload form
            return render_template('upload.html')

        # POST request - process uploaded file
        try:
            # Check if file was uploaded
            if 'receipt' not in request.files:
                flash('No file uploaded. Please select a file.', 'error')
                return redirect(url_for('upload'))

            file = request.files['receipt']

            # Check if user actually selected a file
            # (file.filename is empty string if no file selected)
            if file.filename == '':
                flash('No file selected. Please choose a file.', 'error')
                return redirect(url_for('upload'))

            # Process the receipt
            # This does all the work: validate, extract data, save to DB
            receipt = app.receipt_service.process_receipt(file)

            # Show success message
            flash(
                f'Receipt processed successfully! '
                f'Found {len(receipt.items)} items totaling ${receipt.total_amount:.2f}',
                'success'
            )

            # Redirect to history page to see the result
            return redirect(url_for('history'))

        except ValueError as e:
            # Validation errors (invalid file type, invalid data, etc.)
            flash(f'Error: {str(e)}', 'error')
            return redirect(url_for('upload'))

        except RequestEntityTooLarge:
            # File too large (exceeds MAX_CONTENT_LENGTH)
            flash('Error: File is too large. Maximum size is 5MB.', 'error')
            return redirect(url_for('upload'))

        except Exception as e:
            # Unexpected errors
            print(f"Error processing receipt: {e}")
            flash(
                'An error occurred while processing the receipt. Please try again.',
                'error'
            )
            return redirect(url_for('upload'))

    # ===================================
    # History Page
    # ===================================

    @app.route('/history')
    def history():
        """
        Receipt history page.

        GET /history → Shows all receipts

        Displays all receipts in expandable cards.
        Most recent receipts shown first.
        """
        try:
            # Get all receipts from database
            receipts = app.receipt_service.get_all_receipts()

            # Get total count
            total_count = app.receipt_service.get_receipts_count()

            # Render history page with receipts
            return render_template(
                'history.html',
                receipts=receipts,
                total_count=total_count
            )

        except Exception as e:
            print(f"Error loading history: {e}")
            flash('Error loading receipt history.', 'error')
            return render_template('history.html', receipts=[], total_count=0)

    # ===================================
    # Receipt Detail Page (Optional)
    # ===================================

    @app.route('/receipt/<receipt_id>')
    def receipt_detail(receipt_id: str):
        """
        Individual receipt detail page.

        GET /receipt/<id> → Shows single receipt

        This is optional - mainly useful if you want a dedicated
        page for each receipt (e.g., for sharing links).
        """
        try:
            receipt = app.receipt_service.get_receipt_by_id(receipt_id)

            if not receipt:
                flash('Receipt not found.', 'error')
                return redirect(url_for('history'))

            return render_template('receipt_detail.html', receipt=receipt)

        except Exception as e:
            print(f"Error loading receipt: {e}")
            flash('Error loading receipt.', 'error')
            return redirect(url_for('history'))

    # ===================================
    # Error Handlers
    # ===================================

    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 Not Found errors."""
        return render_template('error.html',
                               error_code=404,
                               error_message='Page not found'), 404

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 Internal Server errors."""
        return render_template('error.html',
                               error_code=500,
                               error_message='Internal server error'), 500

    @app.errorhandler(RequestEntityTooLarge)
    def handle_file_too_large(error):
        """Handle file upload too large errors."""
        flash('Error: File is too large. Maximum size is 5MB.', 'error')
        return redirect(url_for('upload'))


# Note about Flask's flash() function:
# flash() stores messages in the session to display on the next request
# Messages are categorized: 'success', 'error', 'info', 'warning'
# Templates can display these with: {% with messages = get_flashed_messages(with_categories=true) %}

# Note about url_for():
# url_for('function_name') generates the URL for that route
# This is better than hardcoding URLs because:
# - If you change the route path, url_for() updates automatically
# - It handles URL encoding
# - It works with URL prefixes/blueprints
