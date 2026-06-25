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

from flask import Flask, render_template, request, redirect, url_for, flash, session
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
    # Authentication guard
    # ===================================

    # Routes that don't require a login — everything else is protected
    _PUBLIC_ENDPOINTS = {'login', 'verify', 'static'}

    @app.before_request
    def require_login():
        """
        Runs before every request. Redirects to /login if the user is not
        authenticated, unless they're already on a public page.
        """
        if request.endpoint in _PUBLIC_ENDPOINTS:
            return  # Allow through without checking

        if not session.get('logged_in'):
            return redirect(url_for('login'))

    # ===================================
    # Login — step 1: enter email
    # ===================================

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """
        GET  /login -> Show the email entry form.
        POST /login -> Check email against allowed list; if allowed, generate
                       OTP, log it, and redirect to /verify.
        """
        # Already logged in? Go straight to the app
        if session.get('logged_in'):
            return redirect(url_for('index'))

        if request.method == 'GET':
            return render_template('login.html')

        email = request.form.get('email', '').strip()

        if not email:
            flash('Please enter your email address.', 'error')
            return render_template('login.html')

        if not app.auth_service.is_email_allowed(email):
            flash('Email address not authorised', 'error')
            return render_template('login.html')

        # Generate OTP and store in session
        otp = app.auth_service.generate_otp()
        app.auth_service.store_otp_in_session(session, email, otp)

        # Deliver OTP (mocked: logged to server.log; real email is SP-009)
        app.auth_service.log_otp(email, otp)

        flash(f'A login code has been sent to {email}.', 'info')
        return redirect(url_for('verify'))

    # ===================================
    # Verify — step 2: enter OTP code
    # ===================================

    @app.route('/verify', methods=['GET', 'POST'])
    def verify():
        """
        GET  /verify -> Show the code entry form.
        POST /verify -> Validate submitted code; on success mark session as
                        logged in and redirect to the upload page.
        """
        # Must have started the login flow (email stored in session)
        if not session.get('otp_email'):
            return redirect(url_for('login'))

        if request.method == 'GET':
            return render_template('verify.html', email=session.get('otp_email'))

        code = request.form.get('code', '').strip()

        if not code:
            flash('Please enter the code.', 'error')
            return render_template('verify.html', email=session.get('otp_email'))

        if not app.auth_service.verify_otp(session, code):
            flash('Invalid code, please try again', 'error')
            return render_template('verify.html', email=session.get('otp_email'))

        # Code is correct — mark the session as authenticated and tidy up OTP data
        session['logged_in'] = True
        app.auth_service.clear_otp_from_session(session)

        return redirect(url_for('index'))

    # ===================================
    # Logout
    # ===================================

    @app.route('/logout')
    def logout():
        """Clear the session and return to the login page."""
        session.clear()
        flash('You have been logged out.', 'info')
        return redirect(url_for('login'))

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
                f'Found {len(receipt.items)} items totaling {receipt.currency} {receipt.total_amount:.2f}',
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
    # Delete Receipt
    # ===================================

    @app.route('/delete-receipt/<receipt_id>', methods=['POST'])
    def delete_receipt(receipt_id):
        success = app.receipt_service.soft_delete_receipt(receipt_id)
        if success:
            flash('Receipt removed.', 'success')
        else:
            flash('Receipt not found.', 'error')
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
