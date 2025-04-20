import logging
from flask import Flask
from flask_cors import CORS
from config import Config # Import the Config class
from extensions import db, init_market_data, migrate # Import db and migrate instances
from extensions import init_plaid, init_robinhood, init_coinbase
from routes import register_routes # Import the route registration function
# Import models to ensure they are registered with SQLAlchemy before migrations
from models import Account, MarketPrice, PlaidItem
from services.market_data_service import MarketDataService
from services.plaid_service import PlaidService
import atexit
import time
from apscheduler.schedulers.background import BackgroundScheduler # Import scheduler
from sqlalchemy.exc import SQLAlchemyError

# --- Background Job Function ---
def background_sync_job(app):
    """Background job to fetch prices for assets and update the MarketPrice table."""
    with app.app_context(): # IMPORTANT: Need app context to use extensions, config, db
        app.logger.info("Background job: Starting price fetch...")
        start_time = time.time()
        md_service = app.extensions.get('market_data_client')
        if not md_service:
            app.logger.warning("Background job: Market data service not available. Skipping price fetch.")
            return

        symbols_to_fetch = set()
        try:
            # Get unique symbols from investment/crypto accounts
            accounts = Account.query.filter(
                Account.account_type.in_(['investment', 'crypto'])
            ).all()
            for acc in accounts:
                if acc.account_subtype: # Assuming subtype holds the symbol
                     # Basic normalization (adapt if needed)
                     normalized_symbol = acc.account_subtype.upper().replace('-USD', '')
                     if normalized_symbol:
                        symbols_to_fetch.add((normalized_symbol, acc.account_type)) # Store type too

        except Exception as e:
            app.logger.error(f"Background job: Error fetching symbols from DB: {e}", exc_info=True)
            return # Exit job if symbols can't be fetched

        if not symbols_to_fetch:
             app.logger.info("Background job: No investment/crypto symbols found in accounts to update.")
             return

        app.logger.info(f"Background job: Found {len(symbols_to_fetch)} unique symbols to fetch prices for.")
        updated_count = 0
        created_count = 0
        failed_count = 0

        # Fetch prices one by one with delay to respect rate limits
        for symbol, acc_type in symbols_to_fetch:
            price_usd = None
            try:
                if acc_type == 'investment':
                    price_usd = md_service.get_stock_price(symbol)
                elif acc_type == 'crypto':
                    price_usd = md_service.get_crypto_price(symbol, target_currency='USD')

                if price_usd is not None:
                    # Update or Create in MarketPrice table
                    try:
                        mp = MarketPrice.query.filter_by(symbol=symbol).first()
                        if mp:
                            mp.price_usd = price_usd
                            mp.last_updated = db.func.now() # Update timestamp using server time
                            app.logger.debug(f"Background job: Updating price for {symbol}: {price_usd}")
                            updated_count +=1
                        else:
                            mp = MarketPrice(symbol=symbol, price_usd=price_usd)
                            db.session.add(mp)
                            app.logger.info(f"Background job: Creating price for {symbol}: {price_usd}")
                            created_count += 1
                        db.session.commit() # Commit after each successful update/create
                    except SQLAlchemyError as db_err:
                         db.session.rollback()
                         app.logger.error(f"Background job: DB error saving price for {symbol}: {db_err}", exc_info=True)
                         failed_count += 1
                    except Exception as inner_e: # Catch other unexpected errors during DB operation
                         db.session.rollback()
                         app.logger.error(f"Background job: Unexpected error saving price for {symbol}: {inner_e}", exc_info=True)
                         failed_count += 1
                else:
                    app.logger.warning(f"Background job: Failed to fetch price for {symbol}")
                    failed_count += 1

            except Exception as fetch_err:
                 app.logger.error(f"Background job: Error fetching price for {symbol}: {fetch_err}", exc_info=True)
                 failed_count += 1

            # --- IMPORTANT: Add Delay ---
            app.logger.debug("Background job: Pausing before next fetch...")
            # time.sleep(13) # Wait >12 seconds for 5 calls/min limit (adjust if needed)
            # --------------------------

        # --- Transaction Fetching (Use PlaidService) ---
        app.logger.info("Background job: Starting transaction sync...")
        try:
            plaid_service = app.extensions.get('plaid_service')
            if not plaid_service:
                app.logger.warning("Background job: Plaid service not available. Skipping transaction sync.")
            else:
                # Fetch all items for the user
                items_to_sync = PlaidItem.query.filter_by(user_id='finsmar-local-user-01').all()
                app.logger.info(f"Background job: Found {len(items_to_sync)} Plaid items for transaction sync.")
                success_count = 0
                fail_count = 0
                for item in items_to_sync:
                    # Call the service method for each item
                    success = plaid_service.sync_transactions_for_item(item)
                    if success:
                         success_count += 1
                    else:
                         fail_count += 1
                    # Optional small delay between syncing different bank items?
                    # time.sleep(1)
                app.logger.info(f"Background job: Transaction sync portion complete. Succeeded Items: {success_count}, Failed Items: {fail_count}")

        except Exception as e:
             app.logger.error(f"Background job: Error during transaction syncing: {e}", exc_info=True)
        # --------------------------------------------------

        end_time = time.time()
        app.logger.info(f"Background job: Sync cycle finished in {end_time - start_time:.2f} seconds.")
        app.logger.info(f"Background job: Price fetch complete. Updated: {updated_count}, Created: {created_count}, Failed: {failed_count}")

def create_app(config_class=Config):
    """Application factory function."""
    app = Flask(__name__)
    # Load configuration from config object
    app.config.from_object(config_class)
    app.logger.setLevel(logging.INFO)
    app.logger.info(f"DB URI Configured: {app.config.get('SQLALCHEMY_DATABASE_URI')}")

    # Initialize CORS
    CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

    # Initialize Flask extensions
    db.init_app(app)
    migrate.init_app(app, db)
    init_plaid(app)

    if 'plaid_client' in app.extensions:
        ps = PlaidService(app.extensions['plaid_client'], app.logger)
        app.extensions['plaid_service'] = ps # Store the service instance
        app.logger.info("Plaid Service initialized.")
    else:
        app.logger.error("Plaid client not initialized, cannot create PlaidService.")

    init_robinhood(app)
    init_coinbase(app)
    init_market_data(app)

    # Register routes
    register_routes(app)

    # --- Initialize and Start Scheduler ---
    scheduler = BackgroundScheduler(daemon=True, timezone='UTC')
    # Schedule job to run immediately and then every 30 minutes (adjust interval as needed)
    # Pass the app instance to the job function to establish context correctly
    scheduler.add_job(background_sync_job, trigger='interval', args=[app], minutes=30, id='', replace_existing=True, misfire_grace_time=600)
    # Consider running once immediately on startup as well?
    # scheduler.add_job(fetch_and_update_prices, args=[app], id='price_fetch_job_startup', replace_existing=True)
    scheduler.start()
    app.logger.info("Background price fetch scheduler started (running every 30 mins).")

    if not hasattr(app, 'extensions'):
        app.extensions = {}
    app.extensions['scheduler'] = scheduler

    # Ensure scheduler shuts down cleanly when app exits
    atexit.register(lambda: scheduler.shutdown())

    app.logger.info("Flask app created successfully with CORS and Scheduler enabled.")

    return app
