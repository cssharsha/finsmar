# backend/models.py
from .extensions import db # Import db instance from extensions.py

# Define the Account model
class Account(db.Model):
    __tablename__ = 'account' # Optional: explicitly set table name

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    # Example: 'Plaid', 'Robinhood', 'Coinbase', 'Manual'
    source = db.Column(db.String(50), nullable=False, default='Manual')
    # Example: 'depository', 'investment', 'loan', 'crypto' (matches Plaid types where possible)
    account_type = db.Column(db.String(50), nullable=False)
    # Example: 'checking', 'savings', '401k', 'BTC'
    account_subtype = db.Column(db.String(255), nullable=True)
    # Unique identifier from the source (e.g., Plaid account_id)
    external_id = db.Column(db.String(100), unique=True, nullable=True, index=True)
    balance = db.Column(db.Numeric(18, 8), nullable=False, default=0.0) # Increased precision for crypto/stocks
    # Could add currency code if handling multiple currencies
    # currency_code = db.Column(db.String(3), nullable=False, default='USD')
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())


    def __repr__(self):
        return f'<Account {self.name} ({self.account_type} - {self.source})>'

# PlaidItem for storing Item returned for plaid access_token
class PlaidItem(db.Model):
    __tablename__ = 'plaid_item'

    id = db.Column(db.Integer, primary_key=True)
    # Plaid's unique identifier for the Item/connection
    item_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    # The long-lived token for accessing Item data - STORE SECURELY
    access_token = db.Column(db.String(255), nullable=False)
    # Link back to our user (hardcoded for now)
    user_id = db.Column(db.String(80), nullable=False, default='finsmar-local-user-01')
    # Optional: Store institution details linked to this item
    institution_id = db.Column(db.String(50), nullable=True)
    institution_name = db.Column(db.String(100), nullable=True)
    # Timestamps
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return f'<PlaidItem {self.item_id} (User: {self.user_id})>'

# --- Add more models later ---
# class Transaction(db.Model): ...
# class Budget(db.Model): ...
# class Loan(db.Model): ...
# class Income(db.Model): ...
