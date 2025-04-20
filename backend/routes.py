from flask import jsonify, request, current_app # Added request and current_app

# Import plaid client and constants from extensions
from extensions import db, plaid_products, plaid_country_codes

# Import Plaid models needed for link token creation
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest
from plaid.exceptions import ApiException

from models import PlaidItem, Account, MarketPrice, Transaction
import datetime
from sqlalchemy import func

# Import SQLAlchemyError for DB error handling
from sqlalchemy.exc import SQLAlchemyError

import decimal

# Helper function for safe float conversion (optional)
def to_decimal(value, default=decimal.Decimal(0.0)):
    if value is None:
        return default
    try:
        return decimal.Decimal(value)
    except (TypeError, ValueError, decimal.InvalidOperation):
        current_app.logger.warning(f"Could not convert value '{value}' to Decimal, using default.")
        return default

def register_routes(app):
    """Registers routes with the Flask app."""

    @app.route('/')
    def hello_world():
        """Root endpoint."""
        return jsonify({"message": "Welcome to finsmar API (Modular)!"})

    @app.route('/api/create_link_token', methods=['POST'])
    def create_link_token():
        """Creates a Plaid Link token."""
        try:
            client = current_app.extensions['plaid_client']
            # Define a unique and STABLE identifier for your user.
            # For a single-user local app, a hardcoded string is okay,
            # but it MUST remain the same across sessions for Plaid
            # to recognize the user and manage items correctly.
            client_user_id = 'finsmar-local-user-01' # Example ID

            # Create the user object for the request
            request_user = LinkTokenCreateRequestUser(client_user_id=client_user_id)

            # Create the main Link Token request object
            link_request = LinkTokenCreateRequest(
                user=request_user,
                client_name="finsmar", # Your app's name displayed in Plaid Link
                products=plaid_products, # From extensions.py (e.g., ['auth', 'transactions'])
                country_codes=plaid_country_codes, # From extensions.py (e.g., ['US'])
                language='en'
                # Optional: Add a webhook URL for real-time updates (more complex setup)
                # webhook='https://your-publicly-accessible-webhook-url/api/plaid/webhook'
            )

            # Make the API call to Plaid
            current_app.logger.info("Getting here")
            response = client.link_token_create(link_request)

            # Return the link_token to the frontend
            return jsonify(response.to_dict()) # Convert Plaid response object to dict

        except ApiException as e:
            # Log the detailed error from Plaid
            current_app.logger.error(f"Plaid API error creating link token: {e.body}")
            # Return a generic error message to the client
            # Include e.body (JSON string) for detailed debugging if needed,
            # but be cautious about exposing too much detail in a real frontend.
            error_details = e.body if hasattr(e, 'body') else str(e)
            return jsonify({'error': 'Plaid API error', 'details': error_details}), 500
        except Exception as e:
             # Catch any other unexpected errors
             current_app.logger.error(f"Unexpected error creating link token: {e}")
             return jsonify({'error': 'Internal server error'}), 500

    # --- Add New Route for Exchanging Public Token ---
    @app.route('/api/exchange_public_token', methods=['POST'])
    def exchange_public_token():
        """Exchanges a Plaid public_token for an access_token and item_id."""
        public_token = request.json.get('public_token')
        if not public_token:
            return jsonify({'error': 'Missing public_token in request body'}), 400

        try:
            # Get Plaid client from app context
            client = current_app.extensions['plaid_client']

            # Create request object for token exchange
            exchange_request = ItemPublicTokenExchangeRequest(public_token=public_token)

            # Make the API call to Plaid
            exchange_response = client.item_public_token_exchange(exchange_request)

            # Extract the needed tokens/IDs
            access_token = exchange_response['access_token']
            item_id = exchange_response['item_id']
            # Note: exchange_response may contain other useful info like webhook details

            current_app.logger.info(f"Successfully exchanged public token for Item ID: {item_id}")

            # --- Store the Item ID and Access Token in the database ---
            try:
                # Check if item already exists (e.g., re-linking) - optional
                existing_item = PlaidItem.query.filter_by(item_id=item_id).first()
                if existing_item:
                    # Option 1: Update existing item's access token (if needed)
                    existing_item.access_token = access_token
                    current_app.logger.info(f"Updating existing PlaidItem: {item_id}")
                    # Option 2: Return error/message indicating item already linked
                    # return jsonify({'message': 'Item already linked.'}), 200
                else:
                     # Create a new PlaidItem record
                    new_item = PlaidItem(
                        item_id=item_id,
                        access_token=access_token,
                        user_id='finsmar-local-user-01' # Make sure this matches create_link_token
                        # You could optionally fetch institution details here too
                    )
                    db.session.add(new_item)
                    current_app.logger.info(f"Adding new PlaidItem: {item_id}")

                current_app.logger.info("Attempting to flush session...")
                db.session.flush() # Send pending SQL to DB immediately
                current_app.logger.info("Session flush successful.")

                # Commit the session to save changes/new item
                current_app.logger.info("Attempting to commit PlaidItem to database...")
                db.session.commit()
                current_app.logger.info("Database commit successfull for Plaid item.")

                 # --- Verification Query ---
                try:
                    # Immediately try to query the item we just committed
                    verify_item = PlaidItem.query.filter_by(item_id=item_id).first()
                    if verify_item:
                        current_app.logger.info(f"VERIFIED item {item_id} exists in DB immediately after commit. ID: {verify_item.id}")
                    else:
                        # This should NOT happen if commit was truly successful
                        current_app.logger.error(f"VERIFICATION FAILED: item {item_id} NOT FOUND in DB immediately after commit!")
                except Exception as verify_e:
                    current_app.logger.error(f"Error during post-commit verification query: {verify_e}", exc_info=True)
                # --- End Verification Query ---

            except SQLAlchemyError as e:
                db.session.rollback() # Rollback DB changes on error
                current_app.logger.error(f"Database error saving Plaid item: {e}", exc_info=True)
                return jsonify({'error': 'Database error processing Plaid item'}), 500
            # ----------------------------------------------------------

            # Return success message to frontend
            # Avoid sending access_token back to the frontend!
            return jsonify({'message': 'Public token exchanged successfully.'}), 200

        except ApiException as e:
            current_app.logger.error(f"Plaid API error exchanging token: {e.body}", exc_info=True)
            error_details = e.body if hasattr(e, 'body') else str(e)
            return jsonify({'error': 'Plaid API error', 'details': error_details}), 500
        except Exception as e:
             current_app.logger.error(f"Unexpected error exchanging token: {e}", exc_info=True)
             return jsonify({'error': 'Internal server error'}), 500

    # --- Route for Syncing Plaid Accounts ---
    @app.route('/api/plaid/sync_accounts', methods=['POST'])
    def sync_plaid_accounts():
        """
        Fetches account AND investment holdings data from Plaid for all stored items
        and syncs with local DB.
        """
        user_id = 'finsmar-local-user-01'
        accounts_synced_count = 0
        accounts_created_count = 0
        holdings_synced_count = 0
        holdings_created_count = 0
        items_processed_count = 0
        items_failed_count = 0
        items_requiring_relink = []

        # Overall try block for the sync process
        try:
            items = PlaidItem.query.filter_by(user_id=user_id).all()
            if not items:
                return jsonify({'message': 'No Plaid items found to sync.'}), 200

            client = current_app.extensions['plaid_client']

            for item in items:
                current_app.logger.info(f"--- Processing Plaid Item ID: {item.item_id} ---")
                item_fetch_successful = True # Flag for this item

                # === 1. Fetch Basic Account Data ===
                try:
                    get_request = AccountsGetRequest(access_token=item.access_token)
                    accounts_response = client.accounts_get(get_request)
                    plaid_accounts = accounts_response['accounts']

                    for plaid_account in plaid_accounts:
                        plaid_account_id = plaid_account['account_id']
                        account = Account.query.filter_by(external_id=plaid_account_id, source='Plaid').first() # Filter by source too
                        current_app.logger.info(f"Processing current acount: {plaid_account_id}")

                        plaid_type_obj = plaid_account['type']
                        plaid_subtype_obj = plaid_account['subtype']

                        account_type_str = plaid_type_obj.value if hasattr(plaid_type_obj, 'value') else str(plaid_type_obj)
                        account_subtype_str = plaid_subtype_obj.value if hasattr(plaid_subtype_obj, 'value') else str(plaid_subtype_obj)
                        if plaid_subtype_obj == 'None': account_subtype_str = None

                        balance = plaid_account['balances']['current']
                        if balance is None: balance = plaid_account['balances']['available']
                        balance = balance if balance is not None else 0.0

                        if account: # Update depository/loan/credit accounts
                            if account.account_type != 'investment': # Avoid overwriting investment accounts managed below
                                account.name = plaid_account['name']
                                account.balance = balance
                                # Don't sync type/subtype typically unless necessary
                                # account.account_type = plaid_account['type']
                                # account.account_subtype = plaid_account['subtype']
                                accounts_synced_count += 1
                                current_app.logger.debug(f"Updating Plaid account: {account.name} (ID: {account.id}), Bal: {balance}")
                        else: # Create depository/loan/credit accounts
                             if plaid_account['type'] != 'investment': # Only create non-investment here
                                new_account = Account(
                                    external_id=plaid_account_id,
                                    name=plaid_account['name'],
                                    source='Plaid',
                                    account_type=account_type_str,
                                    account_subtype=account_subtype_str,
                                    balance=balance )
                                db.session.add(new_account)
                                accounts_created_count += 1
                                current_app.logger.info(f"Creating Plaid account: {new_account.name} (Plaid ID: {plaid_account_id}), Bal: {balance}")

                except ApiException as e:
                    item_fetch_successful = False
                    items_failed_count += 1
                    current_app.logger.error(f"Plaid API error fetching accounts for Item {item.item_id}: {getattr(e, 'body', e)}", exc_info=True)
                    if getattr(e, 'body', None): # Check if error body exists
                         error_data = {}
                         try: # Try parsing error body
                             if isinstance(e.body, str): error_data = json.loads(e.body)
                             elif isinstance(e.body, dict): error_data = e.body
                         except: pass
                         if error_data.get('error_code') == 'ITEM_LOGIN_REQUIRED':
                             current_app.logger.warning(f"Item {item.item_id} requires re-link.")
                             items_requiring_relink.append(item.item_id)
                             continue # Skip to next item if relink needed

                # === 2. Fetch Investment Holdings (if basic account fetch succeeded) ===
                if item_fetch_successful: # Only try if accounts_get didn't fail badly
                    try:
                        holdings_request = InvestmentsHoldingsGetRequest(access_token=item.access_token)
                        holdings_response = client.investments_holdings_get(holdings_request)
                        holdings = holdings_response.get('holdings', [])
                        securities = holdings_response.get('securities', [])
                        # Create a lookup map for security details
                        security_map = {s['security_id']: s for s in securities}

                        current_app.logger.info(f"Fetched {len(holdings)} holdings for Item {item.item_id}.")

                        processed_holding_ids = set() # Track holdings processed in this run for this item

                        for holding in holdings:
                            security_id = holding['security_id']
                            security_info = security_map.get(security_id)
                            processed_holding_ids.add(security_id)

                            if not security_info:
                                current_app.logger.warning(f"Security info not found for security_id: {security_id}")
                                continue

                            ticker = security_info.get('ticker_symbol', f"SEC_ID_{security_id}")
                            if ticker is None: ticker = 'rando'
                            name = security_info.get('name', 'Unknown Security')
                            quantity = holding['quantity']

                            # Treat each security holding as an "Account" in our model
                            account = Account.query.filter_by(external_id=security_id, source='PlaidInvestment').first()

                            if account:
                                # Update holding quantity
                                account.balance = quantity # Store quantity in balance
                                account.name = ticker # Ensure name is up-to-date
                                holdings_synced_count += 1
                                current_app.logger.debug(f"Updating Plaid holding: {ticker} (ID: {account.id}), Qty: {quantity}")
                            else:
                                # Create new holding account
                                new_account = Account(
                                    external_id=security_id, # Use Plaid security_id
                                    name=ticker,
                                    source='PlaidInvestment', # Differentiate source
                                    account_type='investment',
                                    account_subtype=name, # Use security name as subtype
                                    balance=quantity # Store quantity
                                )
                                db.session.add(new_account)
                                holdings_created_count += 1
                                current_app.logger.info(f"Creating Plaid holding: {ticker} (Sec ID: {security_id}), Qty: {quantity}")

                        # Optional: Zero out holdings previously synced but no longer present
                        # stale_holdings = Account.query.filter(
                        #    Account.source == 'PlaidInvestment',
                        #    Account.plaid_item_id == item.id, # Requires linking Account to PlaidItem
                        #    ~Account.external_id.in_(processed_holding_ids)
                        # ).all()
                        # for stale in stale_holdings: stale.balance = 0.0

                    except ApiException as e:
                         # Holdings might not be available for this item type or access token scope
                         if e.body and 'error_code' in e.body:
                             error_data = {}
                             try:
                                 if isinstance(e.body, str): error_data = json.loads(e.body)
                                 elif isinstance(e.body, dict): error_data = e.body
                             except: pass
                             # Common error if 'investments' product not consented or not supported
                             if error_data.get('error_code') in ['PRODUCT_NOT_READY', 'PRODUCTS_NOT_SUPPORTED', 'ITEM_NOT_SUPPORTED']:
                                 current_app.logger.info(f"Investments product not available for Item {item.item_id}. Skipping holdings.")
                             else:
                                 # Log other Plaid API errors for holdings
                                 current_app.logger.error(f"Plaid API error fetching holdings for Item {item.item_id}: {error_data}", exc_info=True)
                         else:
                             current_app.logger.error(f"Plaid API error fetching holdings for Item {item.item_id}: {e}", exc_info=True)
                         # Decide if this constitutes a full item failure
                         # item_fetch_successful = False # Optional: Mark item as failed if holdings are critical
                         # items_failed_count += 1

                if item_fetch_successful:
                     items_processed_count += 1

            # --- End of Item Loop ---

            # Commit all DB changes after processing all items
            try:
                db.session.commit()
                current_app.logger.info("Database changes committed successfully after sync.")
            except SQLAlchemyError as e:
                db.session.rollback()
                current_app.logger.error(f"Database error committing sync changes: {e}", exc_info=True)
                # Return error even if some items succeeded before commit failed
                return jsonify({'error': 'Database error saving sync updates'}), 500

            # Return final summary
            summary = {
                'message': 'Plaid sync process complete.',
                'items_processed': items_processed_count,
                'items_failed_or_relink': items_failed_count + len(items_requiring_relink),
                'accounts_created': accounts_created_count,
                'accounts_updated': accounts_synced_count,
                'holdings_created': holdings_created_count,
                'holdings_updated': holdings_synced_count,
                'items_requiring_relink': items_requiring_relink
            }
            return jsonify(summary), 200

        except Exception as e:
             # Catch unexpected errors in the overall process
             db.session.rollback()
             current_app.logger.error(f"Unexpected error during Plaid sync: {e}", exc_info=True)
             return jsonify({'error': 'Internal server error during sync'}), 500

    # --- Budget Summary Route ---
    @app.route('/api/budget/summary/<int:year>/<int:month>', methods=['GET'])
    def get_budget_summary(year, month):
        """Returns total spending per budget category for a given month."""
        if not (1 <= month <= 12):
            return jsonify({"error": "Invalid month provided"}), 400

        current_app.logger.info(f"Querying summary for {year}, {month}")

        try:
            # Calculate start and end date for the requested month
            start_date = datetime.date(year, month, 1)
            # Go to the first day of the *next* month, then subtract one day? No, just filter < first day of next month
            if month == 12:
                end_date_exclusive = datetime.date(year + 1, 1, 1)
            else:
                end_date_exclusive = datetime.date(year, month + 1, 1)

            # Query transactions: filter by date, exclude positive amounts/income categories
            # Note: Plaid amounts are signed (+ income, - expense)
            summary_query = db.session.query(
                Transaction.budget_category,
                func.sum(Transaction.amount).label('total_amount')
            ).filter(
                Transaction.date >= start_date,
                Transaction.date < end_date_exclusive,
                # Transaction.amount < 0, # Only include expenses (negative amounts)
                # Optionally filter out specific categories like 'Transfers' if needed
                Transaction.budget_category != 'Income',
                Transaction.budget_category != 'Transfers'
            ).group_by(
                Transaction.budget_category
            ).order_by(
                func.sum(Transaction.amount) # Order by lowest amount (most negative) first
            ).all()

            # Format the results
            summary_data = [
                {"category": category if category else "Uncategorized", "total": float(total)}
                for category, total in summary_query
            ]

            return jsonify(summary_data)

        except ValueError:
             return jsonify({"error": "Invalid year or month provided"}), 400
        except Exception as e:
            current_app.logger.error(f"Error generating budget summary for {year}-{month}: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    # --- Transactions List Route ---
    @app.route('/api/transactions', methods=['GET'])
    def get_transactions():
        """Returns a paginated list of transactions with filtering/sorting."""
        try:
            # --- Pagination ---
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 50, type=int)
            # Limit per_page to a reasonable max
            per_page = min(per_page, 200)

            # --- Base Query ---
            query = Transaction.query

            # --- Filtering ---
            start_date_str = request.args.get('start_date')
            end_date_str = request.args.get('end_date')
            category = request.args.get('category')
            account_db_id = request.args.get('account_id', type=int) # Filter by our internal Account ID

            if start_date_str:
                try:
                    start_date = datetime.date.fromisoformat(start_date_str)
                    query = query.filter(Transaction.date >= start_date)
                except ValueError:
                    return jsonify({"error": "Invalid start_date format (YYYY-MM-DD)"}), 400
            if end_date_str:
                try:
                    end_date = datetime.date.fromisoformat(end_date_str)
                    query = query.filter(Transaction.date <= end_date)
                except ValueError:
                    return jsonify({"error": "Invalid end_date format (YYYY-MM-DD)"}), 400
            if category:
                 query = query.filter(Transaction.budget_category == category)
            if account_db_id:
                 query = query.filter(Transaction.account_db_id == account_db_id)

            # --- Sorting ---
            sort_by = request.args.get('sort_by', 'date') # Default sort by date
            sort_dir = request.args.get('sort_dir', 'desc') # Default sort descending

            sort_column = getattr(Transaction, sort_by, None)
            if sort_column is None: # Default to date if invalid column provided
                sort_column = Transaction.date
                sort_by = 'date' # Reset for logging

            if sort_dir.lower() == 'asc':
                query = query.order_by(sort_column.asc())
            else:
                query = query.order_by(sort_column.desc()) # Default desc

            # --- Execute Query ---
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            transactions = pagination.items
            total_items = pagination.total
            total_pages = pagination.pages

            return jsonify({
                'transactions': [t.to_dict() for t in transactions],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_items': total_items,
                    'total_pages': total_pages
                },
                'filters': { # Echo back applied filters
                    'start_date': start_date_str, 'end_date': end_date_str,
                    'category': category, 'account_id': account_db_id
                },
                'sorting': {
                    'sort_by': sort_by, 'sort_dir': sort_dir.lower()
                }
            })

        except Exception as e:
            current_app.logger.error(f"Error fetching transactions: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    # --- Add Robinhood Sync Route ---
    @app.route('/api/robinhood/sync', methods=['POST'])
    def sync_robinhood_portfolio():
        """Fetches positions from Robinhood and syncs with local DB."""
        if 'robinhood_client' not in current_app.extensions:
             return jsonify({'error': 'Robinhood service not initialized. Check API keys.'}), 503 # Service Unavailable

        client = current_app.extensions['robinhood_client']
        accounts_created = 0
        accounts_updated = 0

        try:
            positions = client.get_positions() # Call service method
            if not positions:
                return jsonify({'message': 'No positions found or failed to fetch from Robinhood.'}), 200

            processed_ids = set() # Keep track of processed external IDs in this run

            for pos in positions:
                # Use position ID or instrument URL as external ID
                external_id = pos.get('id')
                if not external_id:
                     current_app.logger.warning(f"Skipping position due to missing ID: {pos.get('symbol')}")
                     continue

                processed_ids.add(external_id)
                quantity = pos.get('quantity')
                symbol = pos.get('symbol')
                pos_type = pos.get('type', 'investment') # 'stock' or 'crypto'

                # Convert quantity to numeric, handle potential errors
                try:
                    balance_quantity = float(quantity) if quantity is not None else 0.0
                except (ValueError, TypeError):
                     current_app.logger.warning(f"Invalid quantity for {symbol}: {quantity}. Setting to 0.")
                     balance_quantity = 0.0

                # Find/Create Account in local DB
                account = Account.query.filter_by(external_id=external_id, source='Robinhood').first()

                if account:
                    # Update existing
                    account.balance = balance_quantity # Store quantity in balance field for now
                    account.name = symbol or account.name # Update symbol if available
                    accounts_updated += 1
                    current_app.logger.debug(f"Updating Robinhood account: {symbol} ({external_id}) Qty: {balance_quantity}")
                else:
                    # Create new
                    new_account = Account(
                        external_id=external_id,
                        name=symbol or f"RH_{pos_type}_{external_id}", # Fallback name
                        source='Robinhood',
                        # Map position type ('stock', 'crypto') to our types
                        account_type='crypto' if pos_type == 'crypto' else 'investment',
                        account_subtype=symbol, # Store symbol as subtype
                        balance=balance_quantity # Store quantity
                    )
                    db.session.add(new_account)
                    accounts_created += 1
                    current_app.logger.info(f"Creating Robinhood account: {symbol} ({external_id}) Qty: {balance_quantity}")

            # Optional: Deactivate/Zero out accounts previously linked to Robinhood but not in the current positions
            # old_accounts = Account.query.filter(Account.source == 'Robinhood', ~Account.external_id.in_(processed_ids)).all()
            # for old_acc in old_accounts:
            #     old_acc.balance = 0.0 # Or mark as inactive
            #     accounts_updated +=1
            #     current_app.logger.info(f"Zeroing out stale Robinhood account: {old_acc.name} ({old_acc.external_id})")


            # Commit DB changes
            try:
                db.session.commit()
            except SQLAlchemyError as db_err:
                db.session.rollback()
                current_app.logger.error(f"Database error during Robinhood sync commit: {db_err}", exc_info=True)
                return jsonify({'error': 'Database commit error'}), 500

            return jsonify({
                'message': 'Robinhood sync complete.',
                'accounts_created': accounts_created,
                'accounts_updated': accounts_updated
            }), 200

        except Exception as e:
            # Catch errors from client.get_positions() or other unexpected issues
            current_app.logger.error(f"Error during Robinhood sync: {e}", exc_info=True)
            return jsonify({'error': 'Failed to sync Robinhood portfolio'}), 500

    # --- Coinbase Sync Route ---
    @app.route('/api/coinbase/sync', methods=['POST'])
    def sync_coinbase_portfolio():
        """Fetches accounts/wallets from Coinbase and syncs with local DB."""
        if 'coinbase_client' not in current_app.extensions:
             return jsonify({'error': 'Coinbase service not initialized. Check API keys.'}), 503

        client = current_app.extensions['coinbase_client']
        accounts_created = 0
        accounts_updated = 0

        try:
            coinbase_accounts = client.get_accounts() # Call service method
            if not coinbase_accounts:
                return jsonify({'message': 'No accounts found or failed to fetch from Coinbase.'}), 200

            processed_ids = set() # Keep track of processed external IDs in this run

            for cb_account in coinbase_accounts:
                uuid = cb_account.uuid
                currency = cb_account.currency
                # Balance is nested, get the value (amount as string)
                balance_str = cb_account.available_balance.get('value', '0')

                if not uuid or not currency:
                    current_app.logger.warning(f"Skipping Coinbase account due to missing uuid or currency: {cb_account}")
                    continue

                processed_ids.add(uuid)

                # Convert balance string to numeric (float or Decimal)
                try:
                    balance_amount = float(balance_str) # Or use Decimal for precision
                except (ValueError, TypeError):
                    current_app.logger.warning(f"Invalid balance for {currency} ({uuid}): {balance_str}. Setting to 0.")
                    balance_amount = 0.0

                # Skip accounts with zero balance? Optional.
                # if balance_amount <= 0:
                #     continue

                # Find/Create Account in local DB
                account = Account.query.filter_by(external_id=uuid, source='Coinbase').first()

                if account:
                    # Update existing
                    account.balance = balance_amount # Store native currency amount
                    # Maybe update name if needed, but currency code is likely stable
                    # account.name = currency
                    accounts_updated += 1
                    current_app.logger.debug(f"Updating Coinbase account: {currency} ({uuid}) Amt: {balance_amount}")
                else:
                    # Create new
                    new_account = Account(
                        external_id=uuid,
                        name=f"{currency} Wallet", # e.g., "BTC Wallet"
                        source='Coinbase',
                        account_type='crypto',
                        account_subtype=currency, # Store currency code as subtype
                        balance=balance_amount # Store native quantity
                    )
                    db.session.add(new_account)
                    accounts_created += 1
                    current_app.logger.info(f"Creating Coinbase account: {currency} ({uuid}) Amt: {balance_amount}")

            # Optional: Deactivate/Zero out accounts previously linked but not in current response
            # ... (similar logic as Robinhood/Plaid sync) ...

            # Commit DB changes
            try:
                db.session.commit()
            except SQLAlchemyError as db_err:
                db.session.rollback()
                current_app.logger.error(f"Database error during Coinbase sync commit: {db_err}", exc_info=True)
                return jsonify({'error': 'Database commit error'}), 500

            return jsonify({
                'message': 'Coinbase sync complete.',
                'accounts_created': accounts_created,
                'accounts_updated': accounts_updated
            }), 200

        except Exception as e:
            # Catch errors from client.get_accounts() or other unexpected issues
            current_app.logger.error(f"Error during Coinbase sync: {e}", exc_info=True)
            return jsonify({'error': 'Failed to sync Coinbase portfolio'}), 500

     # --- Manual Transaction Sync Trigger Route ---
    # This reuses the same mechanism as the market sync trigger,
    # running the *entire* background job immediately.
    @app.route('/api/plaid/sync_transactions', methods=['POST'])
    def trigger_transaction_sync():
        """Manually triggers the background sync job (prices & transactions)."""
        scheduler = current_app.extensions.get('scheduler')
        if not scheduler or not scheduler.running:
            return jsonify({'error': 'Scheduler not running'}), 503

        job_id = 'background_sync_job' # ID of the combined job
        try:
            scheduler.modify_job(job_id, next_run_time=datetime.datetime.now(datetime.timezone.utc))
            current_app.logger.info(f"Manually triggered background sync job '{job_id}' to run now.")
            return jsonify({'message': f"Background sync job '{job_id}' triggered."}), 202
        except Exception as e:
            current_app.logger.error(f"Error triggering background sync job '{job_id}': {e}", exc_info=True)
            return jsonify({'error': f"Failed to trigger background sync job '{job_id}'"}), 500

    # --- Add Portfolio Overview Route ---
    @app.route('/api/portfolio/overview', methods=['GET'])
    def get_portfolio_overview():
        """Calculates and returns a consolidated overview of all accounts."""
        portfolio = {
            'total_value_usd': decimal.Decimal(0.0),
            'cash_total_usd': decimal.Decimal(0.0),
            'investment_total_usd': decimal.Decimal(0.0), # Stocks, ETFs etc.
            'crypto_total_usd': decimal.Decimal(0.0),
            'other_assets_total_usd': decimal.Decimal(0.0), # e.g., from unsupported sources
            'loan_total_usd': decimal.Decimal(0.0),
            'account_details': [] # List to hold details of each account
        }
        # Map our account types/sources to portfolio categories
        type_mapping = {
             'depository': 'cash',
             'investment': 'investment',
             'crypto': 'crypto',
             'loan': 'loan'
        }
        source_mapping = { # To categorize holdings by where they came from
             'Plaid': 'Bank/Broker (via Plaid)',
             'PlaidInvestment': 'Investment (via Plaid)',
             'Coinbase': 'Crypto (via Coinbase)',
             'Robinhood': 'Investment/Crypto (via Robinhood)', # Combined for now
             'Manual': 'Manual Entry'
        }

        try:
            # 1. Fetch all accounts from our local database
            accounts = Account.query.all()
            if not accounts:
                return jsonify({'message': 'No accounts found in the database.'}), 200

            # 2. Get cached prices (or relevant ones) into a dictionary
            cached_prices_query = MarketPrice.query.all()
            price_cache = {mp.symbol: {'price': mp.price_usd, 'time': mp.last_updated} for mp in cached_prices_query}

            # Find the oldest timestamp from the prices used
            oldest_price_time = None
            if price_cache:
                # Query min time directly or find from dict
                # oldest_price_time = db.session.query(func.min(MarketPrice.last_updated)).scalar()
                valid_times = [p['time'] for p in price_cache.values() if p.get('time')]
                if valid_times:
                     oldest_price_time = min(valid_times)
                     # Format timestamp for display (ISO 8601 is good)
                     portfolio['prices_as_of'] = oldest_price_time.isoformat()

            # 3. Process each account
            for acc in accounts:
                account_info = {
                    'id': acc.id,
                    'name': acc.name,
                    'balance': float(acc.balance), # Native balance (quantity or cash amount)
                    'type': acc.account_type,
                    'subtype': acc.account_subtype,
                    'source': source_mapping.get(acc.source, acc.source),
                    'external_id': acc.external_id,
                    'market_value_usd': None, # Will calculate if possible
                    'price_usd': None,
                    'category': 'other' # Default category
                }
                if account_info['balance'] <= 0: continue
                category = type_mapping.get(acc.account_type, 'other')
                account_info['category'] = category

                native_balance = to_decimal(acc.balance)
                market_value_usd = decimal.Decimal(0.0)
                price_usd = None

                if category == 'cash':
                    market_value_usd = native_balance # Assuming cash balance is in USD
                    portfolio['cash_total_usd'] += market_value_usd
                elif category == 'loan':
                     market_value_usd = native_balance # Outstanding loan amount
                     portfolio['loan_total_usd'] += market_value_usd
                     # Loans typically reduce net worth, but we sum positive value here
                elif category in ['investment', 'crypto']:
                     symbol = acc.account_subtype # Assume subtype holds the ticker/crypto symbol
                     if symbol and symbol in price_cache:
                         cached = price_cache[symbol]
                         price_usd = to_decimal(cached['price'])
                         market_value_usd = native_balance * price_usd
                         account_info['price_usd'] = float(price_usd)
                     elif symbol:
                         current_app.logger.warning(f"Price not found in cache for symbol: {symbol}")
                         # Market value remains 0
                     
                     # Add to category total
                     if category == 'investment': portfolio['investment_total_usd'] += market_value_usd
                     elif category == 'crypto': portfolio['crypto_total_usd'] += market_value_usd
                else:
                     portfolio['other_assets_total_usd'] += native_balance

                account_info['market_value_usd'] = float(market_value_usd)
                portfolio['account_details'].append(account_info)



            # Calculate overall total value
            portfolio['total_value_usd'] = (portfolio['cash_total_usd'] +
                                          portfolio['investment_total_usd'] +
                                          portfolio['crypto_total_usd'] +
                                          portfolio['other_assets_total_usd'])
            # Convert Decimal totals back to float for JSON serialization
            for key in portfolio:
                 if isinstance(portfolio[key], decimal.Decimal):
                      portfolio[key] = float(portfolio[key])

            return jsonify(portfolio)

        except SQLAlchemyError as db_err:
            current_app.logger.error(f"Database error fetching accounts for portfolio overview: {db_err}", exc_info=True)
            return jsonify({'error': 'Database error fetching accounts'}), 500
        except Exception as e:
             current_app.logger.error(f"Unexpected error generating portfolio overview: {e}", exc_info=True)
             return jsonify({'error': 'Internal server error'}), 500

    # --- Add Manual Market Sync Trigger Route ---
    @app.route('/api/market/sync', methods=['POST'])
    def trigger_market_sync():
        """Manually triggers the background market price fetch job."""
        scheduler = current_app.extensions.get('scheduler')
        if not scheduler or not scheduler.running:
            return jsonify({'error': 'Scheduler not running or not available'}), 503 # Service Unavailable

        job_id = 'price_fetch_job' # The ID we gave the job in app.py
        try:
            # Option 1: Modify next_run_time to run ASAP (preferred for background execution)
            scheduler.modify_job(job_id, next_run_time=datetime.datetime.now(datetime.timezone.utc))
            current_app.logger.info(f"Manually triggered market sync job '{job_id}' to run now.")
            return jsonify({'message': f"Market data sync job '{job_id}' triggered."}), 202 # Accepted

            # Option 2: Run job directly (can block request if job is long) - Less ideal
            # scheduler.run_job(job_id, blocking=False) # run_job might not exist or work this way easily with context
            # return jsonify({'message': f"Market data sync job '{job_id}' run attempt initiated."}), 200

        except Exception as e:
            current_app.logger.error(f"Error triggering market sync job '{job_id}': {e}", exc_info=True)
            return jsonify({'error': f"Failed to trigger market sync job '{job_id}'"}), 500
