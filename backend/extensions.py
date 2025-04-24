from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import plaid
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode
from plaid.model.products import Products
from services.robinhood_service import RobinhoodService
from services.coinbase_service import CoinbaseService
from services.market_data_service import MarketDataService

# Create extension instances
db = SQLAlchemy()
migrate = Migrate()

# Global variable to hold the Plaid client instance
plaid_products = [
    Products("auth"),
    Products("transactions"),
    Products("investments"),
    Products("liabilities")
] # Default products
plaid_country_codes = [CountryCode('US')] # Default country codes

def init_plaid(app):
    """Initializes the Plaid client using Flask app config."""

    # Get the environment string from config (e.g., 'sandbox', 'development', 'production')
    config_env = app.config.get('PLAID_ENV', 'sandbox').lower()

    # Map string env name to Plaid environments
    # Treat 'development' config setting as Plaid's Sandbox environment
    if config_env == 'development':
        plaid_env_target = plaid.Environment.Sandbox
    elif config_env == 'sandbox':
         plaid_env_target = plaid.Environment.Sandbox
    elif config_env == 'production':
        plaid_env_target = plaid.Environment.Production
    else:
         raise ValueError(f"Invalid PLAID_ENV: {config_env}")

    configuration = plaid.Configuration(
        host=plaid_env_target,
        api_key={
            'clientId': app.config['PLAID_CLIENT_ID'],
            'secret': app.config['PLAID_SECRET'],
        }
    )
    api_client = plaid.ApiClient(configuration)
    client = plaid_api.PlaidApi(api_client)

    # --- Store the client on the app object ---
    # Create app.extensions dictionary if it doesn't exist
    if not hasattr(app, 'extensions'):
        app.extensions = {}
    # Store the initialized client under a key (e.g., 'plaid_client')
    app.extensions['plaid_client'] = client
    app.logger.info(f"Plaid client initialized for environment: {app.config['PLAID_ENV']}")

def init_robinhood(app):
    """Initializes the Robinhood service client."""
    pri_key = app.config.get('ROBINHOOD_PRI_KEY')
    pub_key = app.config.get('ROBINHOOD_PUB_KEY')
    api_key = app.config.get('ROBINHOOD_API_KEY')

    if api_key and pri_key and pub_key:
        try:
            client = RobinhoodService(pri_key=pri_key, pub_key=pub_key, api_key=api_key, logger=app.logger)
            if not hasattr(app, 'extensions'):
                app.extensions = {}
            app.extensions['robinhood_client'] = client
            app.logger.info("Robinhood Service client initialized.")
        except ValueError as e:
             app.logger.error(f"Robinhood Service initialization failed: {e}")
    else:
         app.logger.warning("Robinhood API keys not configured. Robinhood Service not initialized.")

# --- Coinbase Client Setup ---
def init_coinbase(app):
    """Initializes the Coinbase service client."""
    api_key = app.config.get('COINBASE_API_KEY')
    api_secret = app.config.get('COINBASE_API_SECRET')

    if api_key and api_secret:
        try:
            client = CoinbaseService(api_key=api_key, api_secret=api_secret, logger=app.logger)
            if not hasattr(app, 'extensions'):
                app.extensions = {}
            app.extensions['coinbase_client'] = client
            app.logger.info("Coinbase Service client initialized.")
        except ValueError as e:
             app.logger.error(f"Coinbase Service initialization failed: {e}")
    else:
         app.logger.warning("Coinbase API keys not configured. Coinbase Service not initialized.")

# --- Market Data Client Setup ---
def init_market_data(app):
    """Initializes the MarketData service client."""
    api_key = app.config.get('FINANCIAL_DATA_API_KEY') # Uses the key set in config

    if api_key:
        try:
            client = MarketDataService(api_key=api_key, logger=app.logger)
            if not hasattr(app, 'extensions'):
                app.extensions = {}
            app.extensions['market_data_client'] = client
            app.logger.info("MarketData Service client initialized.")
        except ValueError as e:
             app.logger.error(f"MarketData Service initialization failed: {e}")
    else:
         app.logger.warning("FINANCIAL_DATA_API_KEY not configured. MarketData Service not initialized.")
