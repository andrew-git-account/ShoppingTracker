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

from collections import defaultdict

from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.exceptions import RequestEntityTooLarge
from .models import Receipt, ReceiptItem, Transaction
from .services import EmailDeliveryError


# Curated set of common ISO 4217 currency codes offered on the receipt edit
# form (see SP-022). Not exhaustive - the receipt's own currency is always
# added to the dropdown too, so an unusual existing value is never dropped.
_CURRENCY_CODES = [
    'USD', 'EUR', 'GBP', 'CHF', 'JPY', 'CAD', 'AUD', 'CNY', 'INR',
    'SEK', 'NOK', 'DKK', 'PLN', 'CZK', 'HUF', 'RON', 'BGN',
    'TRY', 'BRL', 'MXN', 'ZAR', 'SGD', 'HKD', 'NZD', 'KRW'
]


def _rows_subtotal(rows, original_items) -> float:
    """
    Best-effort sum of price * quantity across non-removed edit-form rows,
    shown as a reference next to Total Price so the user can sanity-check
    their edits. Quantity is carried over from the original item at the same
    index (quantity itself isn't editable - see SP-022). Rows with an
    unparseable price are skipped rather than raising, since this is purely
    informational and must never block rendering the form.
    """
    total = 0.0
    for i, row in enumerate(rows):
        if row['removed']:
            continue
        try:
            price = float(row['price'])
        except ValueError:
            continue
        quantity = original_items[i].quantity if i < len(original_items) else 1
        total += price * quantity
    return total


def _rows_from_receipt(receipt) -> list:
    """Build edit-form rows (name/category/price/quantity/removed) from a receipt's items."""
    return [
        {
            'name': item.name,
            'category': item.category,
            'price': str(item.price),
            'quantity': item.quantity,
            'removed': False
        }
        for item in receipt.items
    ]


def _parse_edit_form(original, categories, user_email):
    """
    Parse a submitted edit form (SP-022's per-row item_name/item_category/
    item_price/item_remove inputs, plus currency/total_amount) against an
    "original" receipt-shaped object, and build an updated Receipt.

    `original` supplies everything the form doesn't submit and that isn't
    editable - store_name/purchase_date/tax_amount/discount_amount, plus
    per-item quantity/amount/unit, and its own receipt_id/saved_at (which may
    be None for a not-yet-saved draft - see SP-023). Works identically for
    editing an existing saved receipt or a draft, since both are represented
    the same way once loaded into a Receipt.

    Returns:
        (rows, currency_value, total_value, updated_receipt_or_None, error_message_or_None)
        rows/currency_value/total_value are always the *submitted* values (for
        re-rendering on error without losing the user's edits).
    """
    item_names = request.form.getlist('item_name')
    item_categories = request.form.getlist('item_category')
    item_prices = request.form.getlist('item_price')
    removed_indices = {int(i) for i in request.form.getlist('item_remove')}
    currency_value = request.form.get('currency', original.currency).strip()
    total_value = request.form.get('total_amount', '')

    rows = [
        {
            'name': item_names[i] if i < len(item_names) else '',
            'category': item_categories[i] if i < len(item_categories) else 'Other',
            'price': item_prices[i] if i < len(item_prices) else '',
            'quantity': original.items[i].quantity if i < len(original.items) else 1,
            'removed': i in removed_indices
        }
        for i in range(len(item_names))
    ]

    error_message = None
    new_items = []
    for i, row in enumerate(rows):
        if row['removed']:
            continue
        try:
            price = float(row['price'])
        except ValueError:
            error_message = f"Invalid price for '{row['name'] or 'item'}'."
            break
        original_item = original.items[i] if i < len(original.items) else None
        new_items.append(ReceiptItem(
            name=row['name'].strip(),
            price=price,
            quantity=original_item.quantity if original_item else 1,
            category=row['category'] if row['category'] in categories else 'Other',
            amount=original_item.amount if original_item else 1.0,
            unit=original_item.unit if original_item else 'piece'
        ))

    total_amount = None
    if error_message is None:
        try:
            total_amount = float(total_value)
        except ValueError:
            error_message = 'Please enter a valid total amount.'

    updated_receipt = None
    if error_message is None:
        updated_receipt = Receipt(
            items=new_items,
            store_name=original.store_name,
            purchase_date=original.purchase_date,
            tax_amount=original.tax_amount,
            discount_amount=original.discount_amount,
            total_amount=total_amount,
            receipt_id=original.receipt_id,
            saved_at=original.saved_at,
            currency=currency_value or original.currency,
            user_email=user_email
        )
        is_valid, validate_error = updated_receipt.validate()
        if not is_valid:
            error_message = validate_error

    return rows, currency_value, total_value, updated_receipt, error_message


def _render_edit_form(
    rows, currency_value, total_value, categories, form_action, original_items,
    is_draft=False, draft_id=None
):
    """Render templates/edit_receipt.html with the context it needs (see SP-022/SP-023)."""
    return render_template(
        'edit_receipt.html',
        rows=rows,
        currency_value=currency_value,
        total_value=total_value,
        categories=categories,
        currencies=sorted(set(_CURRENCY_CODES) | {currency_value}),
        items_subtotal=_rows_subtotal(rows, original_items),
        form_action=form_action,
        is_draft=is_draft,
        draft_id=draft_id
    )


def _parse_statement_edit_form(originals_by_id, categories):
    """
    Parse a submitted statement edit form (SP-030's per-row transaction_id/
    description/date/category/is_credit/currency/amount inputs) against the
    statement's own transactions, and build the list of updated Transactions.
    Mirrors _parse_edit_form's parallel-list shape for receipt items, but each
    row is its own independently-addressable Transaction record (identified by
    a hidden transaction_id) rather than a sub-item of one parent record.

    originals_by_id: {transaction_id: Transaction} - already ownership-scoped
    by the caller (only this statement's transactions, owned by this user), so
    a transaction_id not found here (tampered or foreign) is simply an invalid
    row, never a database lookup.

    Returns:
        (rows, updated_transactions_or_None, error_message_or_None)
        rows is always the *submitted* values (for re-rendering on error).
        All-or-nothing: if any row fails, updated_transactions is None and
        nothing is saved - same atomic-save behavior as receipt item editing.
    """
    transaction_ids = request.form.getlist('transaction_id')
    descriptions = request.form.getlist('description')
    dates = request.form.getlist('date')
    categories_submitted = request.form.getlist('category')
    # is_credit is a checkbox per row (value=row index, same convention as
    # edit_receipt.html's item_remove) - only checked rows are submitted at
    # all, so direction is unconditionally 'debit' or 'credit' with no
    # invalid-value case to fall back from.
    credit_row_indices = {int(i) for i in request.form.getlist('is_credit')}
    currencies = request.form.getlist('currency')
    amounts = request.form.getlist('amount')

    rows = []
    updated_transactions = []
    error_message = None

    for i, tid in enumerate(transaction_ids):
        direction = 'credit' if i in credit_row_indices else 'debit'
        row = {
            'transaction_id': tid,
            'description': descriptions[i] if i < len(descriptions) else '',
            'date': dates[i] if i < len(dates) else '',
            'category': categories_submitted[i] if i < len(categories_submitted) else 'Other',
            'direction': direction,
            'currency': currencies[i] if i < len(currencies) else 'USD',
            'amount': amounts[i] if i < len(amounts) else '',
        }
        rows.append(row)

        original = originals_by_id.get(tid)
        if not original:
            error_message = error_message or f"Row {i + 1}: transaction not found."
            continue

        # Category is a <select> in the form, so an out-of-list value here
        # means a hand-crafted request - fall back the same way
        # StatementService.process_statement() already does for extracted
        # values, rather than rejecting the whole form over it.
        category = row['category'] if row['category'] in categories else 'Other'

        try:
            amount = float(row['amount'])
        except ValueError:
            error_message = error_message or f"Row {i + 1}: please enter a valid amount."
            continue

        updated = Transaction(
            date=row['date'] or None,
            description=row['description'],
            amount=amount,
            currency=row['currency'] or original.currency,
            direction=direction,
            category=category,
            source=original.source,
            statement_id=original.statement_id,
            transaction_id=original.transaction_id,
            saved_at=original.saved_at,
            user_email=original.user_email,
            linked_receipt_id=original.linked_receipt_id,
            is_deleted=original.is_deleted
        )
        is_valid, validate_error = updated.validate()
        if not is_valid:
            error_message = error_message or f"Row {i + 1}: {validate_error}"
            continue

        updated_transactions.append(updated)

    if error_message:
        return rows, None, error_message
    return rows, updated_transactions, None


def _render_statement_edit_form(rows, categories, form_action):
    """Render templates/edit_statement.html with the context it needs (see SP-030)."""
    row_currencies = {row['currency'] for row in rows}
    return render_template(
        'edit_statement.html',
        rows=rows,
        categories=categories,
        currencies=sorted(set(_CURRENCY_CODES) | row_currencies),
        form_action=form_action
    )


def _month_key(date_str: str) -> str:
    """
    YYYY-MM key used to group a receipt or transaction by month.

    Callers supply the date string themselves - a receipt's
    purchase_date-or-saved_at fallback, or a transaction's date-or-saved_at
    fallback (see SP-028) - since a Transaction has no purchase_date field.
    """
    return date_str[:7]


def _already_linked_receipt_ids(transaction_service, user_email: str, excluding_transaction_id: str) -> set:
    """
    Receipt IDs already claimed by some *other* transaction - the same
    one-to-one check TransactionMatcher.match_transaction (SP-026) uses,
    reused here so manual linking (SP-027) can't violate the rule automatic
    matching already enforces.
    """
    return {
        t.linked_receipt_id
        for t in transaction_service.get_all_transactions(user_email)
        if t.linked_receipt_id and t.transaction_id != excluding_transaction_id
    }


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

        Also requires session['user_email'] (see SP-005) - a session that
        predates per-user receipt scoping would have logged_in=True but no
        user_email, so this forces a clean re-login instead of silently
        showing an empty history.
        """
        if request.endpoint in _PUBLIC_ENDPOINTS:
            return  # Allow through without checking

        if not session.get('logged_in') or not session.get('user_email'):
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
        # Already logged in? Go straight to the app. Also require user_email
        # (see SP-005) - a stale session missing it would otherwise bounce
        # forever between here and the before_request guard in an infinite
        # redirect loop, since the guard treats that session as not fully
        # logged in but this check alone wouldn't.
        if session.get('logged_in') and session.get('user_email'):
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

        # Send OTP by email; show a friendly error if SMTP fails
        try:
            app.auth_service.send_otp_email(email, otp)
        except EmailDeliveryError:
            flash('Could not send code — please try again', 'error')
            return render_template('login.html')

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

        # Code is correct — mark the session as authenticated and tidy up OTP data.
        # user_email must be captured before clear_otp_from_session pops otp_email,
        # since it's how every route scopes receipts to their owner (see SP-005).
        session['logged_in'] = True
        session['user_email'] = session.get('otp_email')
        # is_admin is cached in session at login (see SP-020) - same trust model
        # as user_email/logged_in; a flag change takes effect on next login.
        session['is_admin'] = app.auth_service.is_admin(session['user_email'])
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
            # This does all the work: validate, extract data, save to DB (or,
            # if review is needed - checkbox checked, invalid data, or an
            # unreconciled total - write a draft for review instead: SP-023/024)
            edit_before_save = request.form.get('edit_before_save') == 'on'
            receipt, draft_id, review_reason = app.receipt_service.process_receipt(
                file, session['user_email'], edit_before_save=edit_before_save
            )

            if draft_id:
                if review_reason == 'invalid':
                    flash('This receipt has a problem — please review and fix it before saving.', 'error')
                elif review_reason == 'unreconciled':
                    flash(
                        "We couldn't fully verify this receipt's totals — "
                        "please double-check the items and total before saving.",
                        'error'
                    )
                else:
                    flash('Review the extracted receipt before saving.', 'info')
                return redirect(url_for('receipt_draft_edit', draft_id=draft_id))

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
            flash('Error: File is too large. Maximum size is 15MB.', 'error')
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
    # Upload Statement Page (SP-025)
    # ===================================

    @app.route('/upload-statement', methods=['GET', 'POST'])
    def upload_statement():
        """
        Upload a bank or credit-card statement page.

        GET /upload-statement  -> Shows upload form
        POST /upload-statement -> Extracts transactions from the uploaded PDF

        A separate page/route from receipt upload (SP-025) - statements are a
        different data source (PDF, multiple transactions per file, no
        itemization) with their own dedicated LLM extraction call.
        """
        if request.method == 'GET':
            return render_template('upload_statement.html')

        try:
            if 'statement' not in request.files:
                flash('No file uploaded. Please select a file.', 'error')
                return redirect(url_for('upload_statement'))

            file = request.files['statement']

            if file.filename == '':
                flash('No file selected. Please choose a file.', 'error')
                return redirect(url_for('upload_statement'))

            source = request.form.get('source')
            if source not in ('bank', 'card'):
                flash('Please select whether this is a bank or credit card statement.', 'error')
                return redirect(url_for('upload_statement'))

            transactions = app.statement_service.process_statement(file, session['user_email'], source)

            flash(f'Found {len(transactions)} transactions.', 'success')
            return redirect(url_for('history'))

        except ValueError as e:
            flash(f'Error: {str(e)}', 'error')
            return redirect(url_for('upload_statement'))

        except RequestEntityTooLarge:
            flash('Error: File is too large.', 'error')
            return redirect(url_for('upload_statement'))

        except Exception as e:
            print(f"Error processing statement: {e}")
            flash(
                'An error occurred while processing the statement. Please try again.',
                'error'
            )
            return redirect(url_for('upload_statement'))

    # ===================================
    # History Page
    # ===================================

    @app.route('/history')
    def history():
        """
        Receipt history page.

        GET /history           → Shows all receipts grouped by month
        GET /history?q=<term>  → Shows every item (across all receipts) whose
                                  name matches <term> (min 3 characters)

        In the normal view, receipts are shown in expandable cards, grouped
        by YYYY-MM, newest-first. In search mode, results are a flat list of
        matching items (not receipt cards) with no subtotal/total, since the
        goal is comparing prices for the same item across different
        purchases rather than reviewing whole receipts.
        """
        # Raw value always goes back into the search box, even if too short
        search_input_value = request.args.get('q', '')
        search_term = search_input_value.strip()

        try:
            receipts = app.receipt_service.get_all_receipts(session['user_email'])

            if search_term and len(search_term) < 3:
                flash('Search term must be at least 3 characters.', 'error')
                search_term = ''

            if search_term:
                term_lower = search_term.lower()
                results = []
                for receipt in receipts:
                    for item in receipt.items:
                        if term_lower in item.name.lower():
                            results.append({
                                'name': item.name,
                                'price': item.price,
                                'quantity': item.quantity,
                                'price_per_unit': item.price_per_unit,
                                'unit': item.unit,
                                'currency': receipt.currency,
                                'store_name': receipt.store_name or 'Unknown Store',
                                'date': receipt.purchase_date or receipt.saved_at[:10],
                            })

                # Sort by item name then price-per-unit so identical items land
                # next to each other with the cheapest first - that's the whole
                # point of search, comparing prices for the same kind of item
                results.sort(key=lambda r: (r['name'].lower(), r['price_per_unit']))

                return render_template(
                    'history.html',
                    search_mode=True,
                    search_term=search_term,
                    search_input_value=search_input_value,
                    search_results=results
                )

            # Normal view: get total count
            total_count = app.receipt_service.get_receipts_count(session['user_email'])

            # Transactions (SP-029) are shown as one card per statement
            # upload - grouped by statement_id, the same relationship a
            # receipt has to its items - interleaved with receipts by date.
            # Not deduplicated against a linked receipt, since History is a
            # complete record.
            transactions = app.transaction_service.get_all_transactions(session['user_email'])

            statements_by_id = defaultdict(list)
            for transaction in transactions:
                statements_by_id[transaction.statement_id].append(transaction)

            statement_entries = []
            for statement_id, txns in statements_by_id.items():
                txns_sorted = sorted(txns, key=lambda t: t.date, reverse=True)
                statement_entries.append({
                    'kind': 'statement',
                    'statement_id': statement_id,
                    'source': txns_sorted[0].source,
                    'transactions': txns_sorted,
                    'date_from': txns_sorted[-1].date,
                    'date_to': txns_sorted[0].date,
                    'date': txns_sorted[0].date
                })

            # Group receipts and statement cards together by month (YYYY-MM) -
            # a union of both, so a month with only statements still gets a group
            grouped = defaultdict(list)
            for receipt in receipts:
                grouped[_month_key(receipt.purchase_date or receipt.saved_at[:10])].append({'kind': 'receipt', 'receipt': receipt, 'date': receipt.purchase_date or receipt.saved_at[:10]})
            for entry in statement_entries:
                grouped[entry['date'][:7]].append(entry)

            # Sort groups newest-first (descending), and entries within each group by date descending
            sorted_groups = []
            for month_key in sorted(grouped.keys(), reverse=True):
                entries_in_month = grouped[month_key]
                entries_in_month.sort(key=lambda e: e['date'], reverse=True)
                sorted_groups.append({
                    'month': month_key,
                    'entries': entries_in_month
                })

            # Render history page with grouped receipts
            return render_template(
                'history.html',
                grouped_receipts=sorted_groups,
                total_count=total_count,
                search_mode=False,
                search_input_value=search_input_value
            )

        except Exception as e:
            print(f"Error loading history: {e}")
            flash('Error loading receipt history.', 'error')
            return render_template(
                'history.html',
                grouped_receipts=[],
                total_count=0,
                search_mode=False,
                search_input_value=search_input_value
            )

    # ===================================
    # Statistics Page
    # ===================================

    @app.route('/statistics')
    def statistics():
        """
        Shopping statistics page.

        GET /statistics                -> Category breakdown for the most recent month
        GET /statistics?month=YYYY-MM  -> Category breakdown for the selected month

        Shows, for a chosen month, how much was spent per category and what
        percentage of that currency's total spend each category represents.

        Receipts can be in different currencies, so amounts are grouped by
        currency first — summing across currencies would produce a meaningless
        total. Each currency gets its own subtotal and its categories'
        percentages are relative to that subtotal, not the whole month.
        """
        try:
            receipts = app.receipt_service.get_all_receipts(session['user_email'])

            # Unlinked debit transactions count as their own un-itemized spend,
            # merged into the same per-category breakdown by their own category
            # field (SP-025 already assigns one, same vocabulary receipt items
            # use) - see SP-028. A linked transaction contributes nothing here;
            # its receipt already accounts for that money at the item level.
            # A credit (refund, incoming transfer, salary) isn't spend either way.
            transactions = app.transaction_service.get_all_transactions(session['user_email'])
            unlinked_debit_transactions = [
                t for t in transactions if t.direction == 'debit' and not t.linked_receipt_id
            ]

            # Months that have receipts and/or unlinked debit transactions, newest first
            receipt_months = {_month_key(r.purchase_date or r.saved_at[:10]) for r in receipts}
            transaction_months = {_month_key(t.date or t.saved_at[:10]) for t in unlinked_debit_transactions}
            months = sorted(receipt_months | transaction_months, reverse=True)

            # Pick the requested month if it exists, otherwise the most recent one
            selected_month = request.args.get('month')
            if selected_month not in months:
                selected_month = months[0] if months else None

            # Sum item totals per category, grouped by currency: {currency: {category: amount}}
            totals_by_currency = defaultdict(lambda: defaultdict(float))
            if selected_month:
                for receipt in receipts:
                    if _month_key(receipt.purchase_date or receipt.saved_at[:10]) != selected_month:
                        continue
                    for item in receipt.items:
                        totals_by_currency[receipt.currency][item.category] += item.price * item.quantity

                for transaction in unlinked_debit_transactions:
                    if _month_key(transaction.date or transaction.saved_at[:10]) != selected_month:
                        continue
                    totals_by_currency[transaction.currency][transaction.category] += transaction.amount

            # Build one group per currency, each with its own total and category breakdown
            currency_groups = []
            for currency in sorted(totals_by_currency.keys()):
                category_totals = totals_by_currency[currency]
                currency_total = sum(category_totals.values())

                categories = []
                for name, amount in sorted(category_totals.items(), key=lambda kv: kv[1], reverse=True):
                    percentage = (amount / currency_total * 100) if currency_total else 0.0
                    categories.append({
                        'name': name,
                        'amount': amount,
                        'percentage': percentage
                    })

                currency_groups.append({
                    'currency': currency,
                    'total': currency_total,
                    'categories': categories
                })

            return render_template(
                'statistics.html',
                months=months,
                selected_month=selected_month,
                currency_groups=currency_groups
            )

        except Exception as e:
            print(f"Error loading statistics: {e}")
            flash('Error loading statistics.', 'error')
            return render_template(
                'statistics.html',
                months=[],
                selected_month=None,
                currency_groups=[]
            )

    # ===================================
    # LLM Usage Page (Admin only)
    # ===================================

    @app.route('/llm-usage')
    def llm_usage():
        """
        Admin-only page showing LLM (Claude API) usage and cost stats.

        GET /llm-usage                            -> All users, all time
        GET /llm-usage?user=<email>                -> One user's totals
        GET /llm-usage?month=YYYY-MM               -> One month's totals
        GET /llm-usage?user=<email>&month=YYYY-MM  -> Both filters combined

        Distinct from the shopping /statistics page — this tracks LLM API
        usage/cost, not purchase spending. See SP-020.
        """
        if not session.get('is_admin'):
            flash('You do not have access to that page.', 'error')
            return redirect(url_for('index'))

        try:
            records = app.usage_log_db.get_all_records()

            # Dropdown option lists always come from the full unfiltered set
            users = sorted({r['user_email'] for r in records})
            months = sorted({r['timestamp'][:7] for r in records}, reverse=True)

            selected_user = request.args.get('user', '')
            selected_month = request.args.get('month', '')

            filtered = records
            if selected_user:
                filtered = [r for r in filtered if r['user_email'] == selected_user]
            if selected_month:
                filtered = [r for r in filtered if r['timestamp'][:7] == selected_month]

            total_requests = len(filtered)
            total_cost = sum(r['cost_usd'] for r in filtered)
            retry_count = sum(1 for r in filtered if r['is_retry'])
            success_count = sum(1 for r in filtered if r['success'])
            retry_rate = (retry_count / total_requests * 100) if total_requests else 0.0
            success_rate = (success_count / total_requests * 100) if total_requests else 0.0

            return render_template(
                'llm_usage.html',
                users=users,
                months=months,
                selected_user=selected_user,
                selected_month=selected_month,
                total_requests=total_requests,
                total_cost=total_cost,
                retry_rate=retry_rate,
                success_rate=success_rate
            )

        except Exception as e:
            print(f"Error loading LLM usage stats: {e}")
            flash('Error loading LLM usage stats.', 'error')
            return render_template(
                'llm_usage.html',
                users=[],
                months=[],
                selected_user='',
                selected_month='',
                total_requests=0,
                total_cost=0.0,
                retry_rate=0.0,
                success_rate=0.0
            )

    # ===================================
    # User Management Page (Admin only)
    # ===================================

    @app.route('/users')
    def users():
        """
        Admin-only page listing every allowed user, with actions to add a
        user, and toggle their admin/blocked flags. See SP-021.
        """
        if not session.get('is_admin'):
            flash('You do not have access to that page.', 'error')
            return redirect(url_for('index'))

        try:
            return render_template('users.html', users=app.auth_service.get_all_users())
        except Exception as e:
            print(f"Error loading users page: {e}")
            flash('Error loading users page.', 'error')
            return render_template('users.html', users=[])

    @app.route('/users/add', methods=['POST'])
    def add_user():
        """Admin-only: add a new allowed user by email. See SP-021."""
        if not session.get('is_admin'):
            flash('You do not have access to that page.', 'error')
            return redirect(url_for('index'))

        email = request.form.get('email', '')
        success, error = app.auth_service.add_user(email)
        if success:
            flash(f'Added {email.strip()}.', 'success')
        else:
            flash(error, 'error')
        return redirect(url_for('users'))

    @app.route('/users/<email>/toggle-admin', methods=['POST'])
    def toggle_user_admin(email):
        """Admin-only: flip a user's admin flag. See SP-021."""
        if not session.get('is_admin'):
            flash('You do not have access to that page.', 'error')
            return redirect(url_for('index'))

        success, error = app.auth_service.toggle_admin(email)
        if not success:
            flash(error, 'error')
        return redirect(url_for('users'))

    @app.route('/users/<email>/toggle-blocked', methods=['POST'])
    def toggle_user_blocked(email):
        """Admin-only: flip a user's blocked flag. See SP-021."""
        if not session.get('is_admin'):
            flash('You do not have access to that page.', 'error')
            return redirect(url_for('index'))

        success, error = app.auth_service.toggle_blocked(email)
        if not success:
            flash(error, 'error')
        return redirect(url_for('users'))

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
            receipt = app.receipt_service.get_receipt_by_id(receipt_id, session['user_email'])

            if not receipt:
                flash('Receipt not found.', 'error')
                return redirect(url_for('history'))

            return render_template('receipt_detail.html', receipt=receipt)

        except Exception as e:
            print(f"Error loading receipt: {e}")
            flash('Error loading receipt.', 'error')
            return redirect(url_for('history'))

    # ===================================
    # Edit Receipt
    # ===================================

    @app.route('/receipt/<receipt_id>/edit', methods=['GET', 'POST'])
    def receipt_edit(receipt_id: str):
        """
        Edit an existing receipt's items (name/category/price), currency, and
        total - or remove individual items entirely. See SP-022.

        GET  /receipt/<id>/edit -> Shows the edit form pre-filled with current data.
        POST /receipt/<id>/edit -> Validates and saves changes in place, or
                                    re-renders the form with the user's submitted
                                    values preserved if validation fails.

        Editing is restricted to the receipt's owner, enforced the same way as
        receipt_detail/delete_receipt (SP-005) - not found and not-owned look
        identical to the caller.
        """
        receipt = app.receipt_service.get_receipt_by_id(receipt_id, session['user_email'])

        if not receipt:
            flash('Receipt not found.', 'error')
            return redirect(url_for('history'))

        categories = app.receipt_service.valid_categories
        form_action = url_for('receipt_edit', receipt_id=receipt_id)

        if request.method == 'GET':
            rows = _rows_from_receipt(receipt)
            return _render_edit_form(
                rows, receipt.currency, str(receipt.total_amount), categories,
                form_action, receipt.items
            )

        # POST
        rows, currency_value, total_value, updated_receipt, error_message = _parse_edit_form(
            receipt, categories, session['user_email']
        )

        if error_message:
            flash(error_message, 'error')
            return _render_edit_form(
                rows, currency_value, total_value, categories, form_action, receipt.items
            )

        app.receipt_service.update_receipt(receipt_id, session['user_email'], updated_receipt)
        flash('Receipt updated.', 'success')
        return redirect(url_for('history'))

    # ===================================
    # Edit Receipt Draft (SP-023)
    # ===================================

    @app.route('/receipt/draft/<draft_id>/edit', methods=['GET', 'POST'])
    def receipt_draft_edit(draft_id: str):
        """
        Review/correct a not-yet-saved draft receipt before it's saved for the
        first time. See SP-023 - a sibling to receipt_edit, not the same route,
        since a draft has no receipt_id yet and POST saves fresh instead of
        updating an existing record.

        GET  /receipt/draft/<id>/edit -> Shows the edit form pre-filled with the
                                          extracted (not yet saved) data.
        POST /receipt/draft/<id>/edit -> Validates and creates the receipt for
                                          the first time, or re-renders the form
                                          with the user's submitted values
                                          preserved if validation fails.

        Restricted to the draft's owner - not found and not-owned look
        identical to the caller, same as receipt_edit.
        """
        receipt = app.receipt_service.get_draft(draft_id, session['user_email'])

        if not receipt:
            flash('Draft not found.', 'error')
            return redirect(url_for('history'))

        categories = app.receipt_service.valid_categories
        form_action = url_for('receipt_draft_edit', draft_id=draft_id)

        if request.method == 'GET':
            rows = _rows_from_receipt(receipt)
            return _render_edit_form(
                rows, receipt.currency, str(receipt.total_amount), categories,
                form_action, receipt.items, is_draft=True, draft_id=draft_id
            )

        # POST
        rows, currency_value, total_value, updated_receipt, error_message = _parse_edit_form(
            receipt, categories, session['user_email']
        )

        if error_message:
            flash(error_message, 'error')
            return _render_edit_form(
                rows, currency_value, total_value, categories, form_action, receipt.items,
                is_draft=True, draft_id=draft_id
            )

        saved_receipt = app.receipt_service.save_draft(draft_id, session['user_email'], updated_receipt)
        if not saved_receipt:
            flash('Draft not found.', 'error')
            return redirect(url_for('history'))

        flash(
            f'Receipt saved! '
            f'Found {len(saved_receipt.items)} items totaling '
            f'{saved_receipt.currency} {saved_receipt.total_amount:.2f}',
            'success'
        )
        return redirect(url_for('history'))

    @app.route('/receipt/draft/<draft_id>/discard', methods=['POST'])
    def receipt_draft_discard(draft_id: str):
        """Discard a draft without ever saving it. See SP-023."""
        app.receipt_service.discard_draft(draft_id, session['user_email'])
        flash('Draft discarded.', 'info')
        return redirect(url_for('history'))

    # ===================================
    # Edit Statement (SP-030)
    # ===================================

    @app.route('/statement/<statement_id>/edit', methods=['GET', 'POST'])
    def statement_edit(statement_id: str):
        """
        Edit every transaction in a statement at once - each row's description/
        date/category/direction/currency/amount. See SP-030 - mirrors
        receipt_edit's shape, but each row is its own Transaction record
        (identified by a hidden transaction_id) rather than a receipt's
        sub-item, so rows are saved individually rather than as one whole-
        record overwrite.

        GET  /statement/<id>/edit -> Shows the edit form pre-filled with every
                                      transaction in this statement.
        POST /statement/<id>/edit -> Validates and saves every row in place, or
                                      re-renders the form with the user's
                                      submitted values preserved if any row
                                      fails validation (all-or-nothing, same as
                                      receipt item editing).

        Editing is restricted to the statement's owner - a statement_id with
        no transactions owned by the caller looks identical to a nonexistent
        one, same not-found/not-owned indistinguishability as receipt_edit (SP-005).
        """
        transactions = [
            t for t in app.transaction_service.get_all_transactions(session['user_email'])
            if t.statement_id == statement_id
        ]

        if not transactions:
            flash('Statement not found.', 'error')
            return redirect(url_for('history'))

        transactions.sort(key=lambda t: t.date, reverse=True)
        categories = app.receipt_service.valid_categories
        form_action = url_for('statement_edit', statement_id=statement_id)

        if request.method == 'GET':
            rows = [{
                'transaction_id': t.transaction_id,
                'description': t.description,
                'date': t.date or '',
                'category': t.category,
                'direction': t.direction,
                'currency': t.currency,
                'amount': str(t.amount),
            } for t in transactions]
            return _render_statement_edit_form(rows, categories, form_action)

        # POST
        originals_by_id = {t.transaction_id: t for t in transactions}
        rows, updated_transactions, error_message = _parse_statement_edit_form(originals_by_id, categories)

        if error_message:
            flash(error_message, 'error')
            return _render_statement_edit_form(rows, categories, form_action)

        for updated in updated_transactions:
            app.transaction_service.update_transaction(updated.transaction_id, session['user_email'], updated)
            # Re-run the matcher the same way receipt_edit already does (SP-026) -
            # e.g. correcting a row's amount can newly match an existing unlinked
            # receipt. No-ops for a row that's already linked.
            if app.transaction_matcher:
                app.transaction_matcher.match_transaction(updated)

        flash('Statement updated.', 'success')
        return redirect(url_for('history'))

    # ===================================
    # Delete Statement (SP-031)
    # ===================================

    @app.route('/statement/<statement_id>/delete', methods=['POST'])
    def statement_delete(statement_id: str):
        """
        Soft-delete every transaction in a statement at once. See SP-031 -
        mirrors delete_receipt's shape, but scoped to a group of records.

        Any transaction being deleted that's linked to a receipt (SP-026) has
        that link cleared first, so the receipt is genuinely available again
        for a future automatic match rather than left pointing at a now-hidden
        transaction.

        Restricted to the statement's owner - a statement_id with no
        transactions owned by the caller looks identical to a nonexistent one,
        same not-found/not-owned indistinguishability as delete_receipt (SP-005).
        """
        transactions = [
            t for t in app.transaction_service.get_all_transactions(session['user_email'])
            if t.statement_id == statement_id
        ]

        if not transactions:
            flash('Statement not found.', 'error')
            return redirect(url_for('history'))

        for transaction in transactions:
            if transaction.linked_receipt_id:
                transaction.linked_receipt_id = None
                app.transaction_service.update_transaction(
                    transaction.transaction_id, session['user_email'], transaction
                )
            app.transaction_service.soft_delete_transaction(transaction.transaction_id, session['user_email'])

        count = len(transactions)
        flash(f'Statement removed ({count} transaction{"s" if count != 1 else ""}).', 'success')
        return redirect(url_for('history'))

    # ===================================
    # Link / Unlink a Transaction (SP-027)
    # ===================================

    @app.route('/transactions/<transaction_id>/link', methods=['GET', 'POST'])
    def transaction_link(transaction_id: str):
        """
        Manually link a transaction to a receipt. See SP-027 - a separate
        filter-and-pick page (no JS), mirroring History's search pattern
        (SP-004), rather than folded into SP-030's statement-edit page.

        GET  /transactions/<id>/link -> Shows the filter form and matching
                                         unlinked receipts. With no query
                                         string at all (first visit), the
                                         filter defaults to the narrowest
                                         useful search: this transaction's
                                         own date and amount.
        POST /transactions/<id>/link -> Sets linked_receipt_id from the
                                         selected receipt, re-validating
                                         ownership and the one-to-one rule
                                         server-side rather than trusting the
                                         previously-rendered list.

        Restricted to the transaction's owner - not found and not-owned look
        identical, same pattern as every other action in the app (SP-005).
        """
        transaction = app.transaction_service.get_transaction_by_id(transaction_id, session['user_email'])

        if not transaction:
            flash('Transaction not found.', 'error')
            return redirect(url_for('history'))

        if request.method == 'POST':
            receipt_id = request.form.get('receipt_id', '')
            receipt = app.receipt_service.get_receipt_by_id(receipt_id, session['user_email'])
            already_linked = _already_linked_receipt_ids(app.transaction_service, session['user_email'], transaction_id)

            if not receipt or receipt_id in already_linked:
                flash('That receipt is not available to link.', 'error')
                return redirect(url_for('transaction_link', transaction_id=transaction_id))

            transaction.linked_receipt_id = receipt_id
            app.transaction_service.update_transaction(transaction_id, session['user_email'], transaction)
            flash('Transaction linked.', 'success')
            return redirect(url_for('history'))

        # GET - build filter values, defaulting to the narrowest useful
        # search only on a genuinely first visit (no query string at all) so
        # a field the user deliberately cleared stays cleared on re-filter.
        if request.args:
            name = request.args.get('name', '').strip()
            date_from = request.args.get('date_from', '').strip()
            date_to = request.args.get('date_to', '').strip()
            amount_from = request.args.get('amount_from', '').strip()
            amount_to = request.args.get('amount_to', '').strip()
        else:
            name = ''
            date_from = transaction.date or ''
            date_to = transaction.date or ''
            amount_from = str(transaction.amount)
            amount_to = str(transaction.amount)

        already_linked = _already_linked_receipt_ids(app.transaction_service, session['user_email'], transaction_id)

        def matches(receipt) -> bool:
            if receipt.receipt_id in already_linked:
                return False
            if name and name.lower() not in (receipt.store_name or '').lower():
                return False
            receipt_date = receipt.purchase_date or receipt.saved_at[:10]
            if date_from and receipt_date < date_from:
                return False
            if date_to and receipt_date > date_to:
                return False
            try:
                if amount_from and receipt.total_amount < float(amount_from):
                    return False
                if amount_to and receipt.total_amount > float(amount_to):
                    return False
            except ValueError:
                pass  # malformed amount filter - ignore rather than error
            return True

        receipts = app.receipt_service.get_all_receipts(session['user_email'])
        results = [r for r in receipts if matches(r)]

        return render_template(
            'transaction_link.html',
            transaction=transaction,
            results=results,
            name=name,
            date_from=date_from,
            date_to=date_to,
            amount_from=amount_from,
            amount_to=amount_to
        )

    @app.route('/transactions/<transaction_id>/unlink', methods=['POST'])
    def transaction_unlink(transaction_id: str):
        """
        Clear a transaction's linked_receipt_id, whether the link was made
        automatically (SP-026) or manually. See SP-027. No confirmation
        dialog - unlinking isn't destructive, same reasoning receipt editing
        needed none (only deleting does).

        Restricted to the transaction's owner, same pattern as transaction_link.
        """
        transaction = app.transaction_service.get_transaction_by_id(transaction_id, session['user_email'])

        if not transaction:
            flash('Transaction not found.', 'error')
            return redirect(url_for('history'))

        transaction.linked_receipt_id = None
        app.transaction_service.update_transaction(transaction_id, session['user_email'], transaction)
        flash('Transaction unlinked.', 'success')
        return redirect(url_for('history'))

    # ===================================
    # Delete Receipt
    # ===================================

    @app.route('/delete-receipt/<receipt_id>', methods=['POST'])
    def delete_receipt(receipt_id):
        # Clear the link on any transaction pointing at this receipt (SP-026/
        # SP-027) before it's soft-deleted, so it doesn't carry a stale
        # reference and the transaction is genuinely unlinked again - the
        # mirror of what statement_delete (SP-031) already does the other way.
        linked_transactions = [
            t for t in app.transaction_service.get_all_transactions(session['user_email'])
            if t.linked_receipt_id == receipt_id
        ]
        for transaction in linked_transactions:
            transaction.linked_receipt_id = None
            app.transaction_service.update_transaction(
                transaction.transaction_id, session['user_email'], transaction
            )

        success = app.receipt_service.soft_delete_receipt(receipt_id, session['user_email'])
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
        flash('Error: File is too large. Maximum size is 15MB.', 'error')
        if request.path == url_for('upload_statement'):
            return redirect(url_for('upload_statement'))
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
