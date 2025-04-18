import logging
from flask import Flask
from flask_cors import CORS
from .config import Config # Import the Config class
from .extensions import db, init_market_data, migrate # Import db and migrate instances
from .extensions import init_plaid, init_robinhood, init_coinbase
from .routes import register_routes # Import the route registration function
# Import models to ensure they are registered with SQLAlchemy before migrations
from . import models # noqa F401 - prevents unused import error but needed for discovery

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
    init_robinhood(app)
    init_coinbase(app)
    init_market_data(app)

    # Register routes
    register_routes(app)

    return app
