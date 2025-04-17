from flask import jsonify, request, current_app # Added request and current_app
# Import plaid client and constants from extensions
from .extensions import plaid_products, plaid_country_codes
from .extensions import db
# Import Plaid models needed for link token creation
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.accounts_get_request import AccountsGetRequest
# Import Plaid ApiException for error handling
from plaid.exceptions import ApiException
from .models import PlaidItem, Account
# Import SQLAlchemyError for DB error handling
from sqlalchemy.exc import SQLAlchemyError

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

                # Commit the session to save changes/new item
                db.session.commit()

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
        """Fetches account data from Plaid for all stored items and syncs local DB."""
        # Define our user ID (must match the one used for token exchange)
        user_id = 'finsmar-local-user-01'
        accounts_synced_count = 0
        accounts_created_count = 0
        items_processed_count = 0
        items_requiring_relink = []

        try:
            # 1. Get all Plaid items (and their access tokens) for our user
            items = PlaidItem.query.filter_by(user_id=user_id).all()
            if not items:
                return jsonify({'message': 'No Plaid items found to sync.'}), 200

            client = current_app.extensions['plaid_client']

            # 2. Loop through each item and fetch accounts
            for item in items:
                items_processed_count += 1
                current_app.logger.info(f"Syncing accounts for Item ID: {item.item_id}")
                try:
                    # Create request for /accounts/get
                    get_request = AccountsGetRequest(access_token=item.access_token)
                    # Fetch accounts from Plaid
                    accounts_response = client.accounts_get(get_request)
                    plaid_accounts = accounts_response['accounts']

                    # 3. Process each account returned by Plaid
                    for plaid_account in plaid_accounts:
                        plaid_account_id = plaid_account['account_id']
                        # Try to find this account in our local DB using Plaid's ID
                        account = Account.query.filter_by(external_id=plaid_account_id).first()

                        # Determine balance (prefer 'current', fallback to 'available')
                        balance = plaid_account['balances']['current']
                        if balance is None:
                            balance = plaid_account['balances']['available']
                        balance = balance if balance is not None else 0.0 # Ensure balance is not None

                        if account:
                            # Account exists - Update it
                            account.name = plaid_account['name']
                            account.balance = balance
                            # Optional: update type/subtype if they can change
                            # account.account_type = plaid_account['type']
                            # account.account_subtype = plaid_account['subtype']
                            current_app.logger.debug(f"Updating account: {account.name} (ID: {account.id}), New Balance: {balance}")
                            accounts_synced_count += 1
                        else:
                            # Account doesn't exist - Create it
                            new_account = Account(
                                external_id=plaid_account_id,
                                name=plaid_account['name'],
                                source='Plaid', # Mark source as Plaid
                                account_type=plaid_account['type'],
                                account_subtype=plaid_account['subtype'],
                                balance=balance,
                                # Link to PlaidItem (optional, could add relationship later)
                                # plaid_item_id=item.id,
                                # Add other relevant fields if needed
                            )
                            db.session.add(new_account)
                            current_app.logger.info(f"Creating new account: {new_account.name} (Plaid ID: {plaid_account_id}), Balance: {balance}")
                            accounts_created_count += 1

                except ApiException as e:
                    current_app.logger.error(f"Plaid API error fetching accounts for Item {item.item_id}: {e.body}", exc_info=True)
                    # Check if item needs re-authentication
                    if e.body and 'error_code' in e.body:
                         error_data = e.body # If body is already parsed JSON/dict
                         try: # If body is a JSON string, parse it
                             if isinstance(e.body, str):
                                 import json
                                 error_data = json.loads(e.body)
                         except:
                             pass # Keep error_data as string if parsing fails

                         if isinstance(error_data, dict) and error_data.get('error_code') == 'ITEM_LOGIN_REQUIRED':
                             current_app.logger.warning(f"Item {item.item_id} requires login. User needs to re-link via Plaid Link update mode.")
                             items_requiring_relink.append(item.item_id)
                             # Continue to next item, don't stop the whole sync
                             continue
                    # Handle other Plaid errors as needed, maybe continue or break

            # 4. Commit all DB changes after processing all items/accounts
            try:
                db.session.commit()
                current_app.logger.info("Database changes committed successfully.")
            except SQLAlchemyError as e:
                db.session.rollback()
                current_app.logger.error(f"Database error committing account sync: {e}", exc_info=True)
                return jsonify({'error': 'Database error saving account updates'}), 500

            # 5. Return summary (or fetch/return synced accounts from DB)
            # For now, just return a success summary
            summary = {
                'message': 'Plaid accounts sync complete.',
                'items_processed': items_processed_count,
                'accounts_created': accounts_created_count,
                'accounts_updated': accounts_synced_count,
                'items_requiring_relink': items_requiring_relink
            }
            return jsonify(summary), 200

        except Exception as e:
             # Catch any other unexpected errors during the process
             db.session.rollback() # Rollback any potential uncommitted changes
             current_app.logger.error(f"Unexpected error during account sync: {e}", exc_info=True)
             return jsonify({'error': 'Internal server error during sync'}), 500
    # --- Add more routes later ---
    # @app.route('/accounts', methods=['GET'])
    # def get_accounts(): ...
    #
    # @app.route('/accounts', methods=['POST'])
    # def create_account(): ...
