import os
from dotenv import load_dotenv

# Load environment variables from .env file, useful for local development outside Docker
load_dotenv()

class Config:
    """Base configuration class."""
    # Get database URL from environment variable
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    if not SQLALCHEMY_DATABASE_URI:
        raise RuntimeError("DATABASE_URL environment variable not set.")

    # Disable modification tracking for SQLAlchemy, saves resources
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # It's good practice to set a secret key for session management, etc.
    # Load from env var or use a default (change default for production)
    SECRET_KEY = os.getenv('SECRET_KEY', 'your_default_secret_key_change_me')

    PLAID_CLIENT_ID = os.getenv('PLAID_CLIENT_ID')
    PLAID_SECRET = os.getenv('PLAID_SECRET')
    # Map string env name ('sandbox', 'development', 'production') to Plaid environments
    PLAID_ENV = os.getenv('PLAID_ENV', 'sandbox')
    # Basic validation
    if not PLAID_CLIENT_ID or not PLAID_SECRET:
         raise RuntimeError("PLAID_CLIENT_ID or PLAID_SECRET environment variables not set.")

# You could add subclasses for different environments later, e.g.:
# class DevelopmentConfig(Config):
#     DEBUG = True
# class ProductionConfig(Config):
#     DEBUG = False
