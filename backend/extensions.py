from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import plaid
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode
from plaid.model.products import Products

# Create extension instances
db = SQLAlchemy()
migrate = Migrate()

# Global variable to hold the Plaid client instance
plaid_products = [Products("auth"), Products("transactions")] # Default products
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
