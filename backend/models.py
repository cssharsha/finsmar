from extensions import db # Import db instance from extensions.py
from sqlalchemy import func, ForeignKey
from sqlalchemy.orm import relationship

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
    # --- Add Relationship to Transactions ---
    # 'transactions' will be a list of Transaction objects associated with this Account
    # back_populates connects this relationship to the 'account' relationship in Transaction
    # lazy='dynamic' allows querying transactions efficiently, e.g., acc.transactions.filter_by(...)
    transactions = relationship('Transaction', back_populates='account', lazy='dynamic', cascade="all, delete-orphan")

    loan_monthly_payment = db.Column(db.Numeric(10, 2), nullable=True)
    loan_original_amount = db.Column(db.Numeric(12, 2), nullable=True)
    loan_interest_rate = db.Column(db.Numeric(5, 4), nullable=True) # Store as decimal, e.g., 0.05 for 5%

    plaid_item_id = db.Column(db.Integer, ForeignKey('plaid_item.id'), nullable=True, index=True)
    plaid_item = relationship('PlaidItem', back_populates='accounts')

    def to_dict(self):
        """Returns a dictionary representation of the account."""
        return {
            'id': self.id,
            'name': self.name,
            'source': self.source,
            'account_type': self.account_type,
            'account_subtype': self.account_subtype,
            'external_id': self.external_id,
            'balance': float(self.balance) if self.balance is not None else None,
            # --- Add loan fields ---
            'loan_monthly_payment': float(self.loan_monthly_payment) if self.loan_monthly_payment is not None else None,
            'loan_original_amount': float(self.loan_original_amount) if self.loan_original_amount is not None else None,
            'loan_interest_rate': float(self.loan_interest_rate) if self.loan_interest_rate is not None else None,
            # -----------------------
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'loan_interest_rate': float(self.loan_interest_rate) if self.loan_interest_rate is not None else None,
            'plaid_item_id': self.plaid_item_id # Add if useful for frontend
        }

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
    sync_cursor = db.Column(db.String(255), nullable=True)
    accounts = relationship('Account', back_populates='plaid_item', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<PlaidItem {self.item_id} (User: {self.user_id})>'

class MarketPrice(db.Model):
    __tablename__ = 'market_price'

    id = db.Column(db.Integer, primary_key=True)
    # Symbol (e.g., 'AAPL', 'BTC', 'ETH') - should be unique
    symbol = db.Column(db.String(20), unique=True, nullable=False, index=True)
    # Store price with sufficient precision
    price_usd = db.Column(db.Numeric(18, 8), nullable=False)
    # Track when the price was last successfully updated
    last_updated = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f'<MarketPrice {self.symbol}: {self.price_usd} @ {self.last_updated}>'

# --- Transaction Model ---
class Transaction(db.Model):
    __tablename__ = 'transaction'

    id = db.Column(db.Integer, primary_key=True)
    # Foreign Key to link transaction to an account in our Account table
    account_db_id = db.Column(db.Integer, ForeignKey('account.id'), nullable=False, index=True)
    # Plaid's unique ID for the transaction
    plaid_transaction_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    # Plaid's unique ID for the account associated with this transaction
    plaid_account_id = db.Column(db.String(100), nullable=False, index=True)

    name = db.Column(db.String(255), nullable=False) # Transaction name/description from Plaid
    merchant_name = db.Column(db.String(255), nullable=True) # Merchant name, if available
    amount = db.Column(db.Numeric(18, 4), nullable=False) # Transaction amount (+ for income/credit, - for debit)
    currency_code = db.Column(db.String(3), nullable=True)
    date = db.Column(db.Date, nullable=False, index=True) # Date transaction occurred
    pending = db.Column(db.Boolean, default=False, nullable=False)
    # Store Plaid's primary category (first element of hierarchy)
    plaid_primary_category = db.Column(db.String(100), nullable=True)
    # Store Plaid's detailed category (last element of hierarchy)
    plaid_detailed_category = db.Column(db.String(100), nullable=True)
    # Plaid's stable category ID
    plaid_category_id = db.Column(db.String(50), nullable=True)

    # Our assigned budget category bucket (e.g., 'Food & Drink', 'Travel')
    # We'll populate this based on Plaid categories later
    budget_category = db.Column(db.String(50), nullable=True, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # --- Add Relationship back to Account ---
    account = relationship('Account', back_populates='transactions')
    # --------------------------------------

    def to_dict(self):
        """Returns a dictionary representation of the transaction."""
        return {
            'id': self.id,
            'account_db_id': self.account_db_id,
            'plaid_transaction_id': self.plaid_transaction_id,
            'plaid_account_id': self.plaid_account_id,
            'name': self.name,
            'merchant_name': self.merchant_name,
            # Convert Decimal amount to float for JSON compatibility
            'amount': float(self.amount) if self.amount is not None else None,
            'currency_code': self.currency_code,
            # Format date as ISO standard string YYYY-MM-DD
            'date': self.date.isoformat() if self.date else None,
            'pending': self.pending,
            'plaid_primary_category': self.plaid_primary_category,
            'plaid_detailed_category': self.plaid_detailed_category,
            'plaid_category_id': self.plaid_category_id,
            'budget_category': self.budget_category,
            # Format datetimes as ISO standard strings
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
            # Optional: Include related account name if needed often, but be mindful of performance
            # 'account_name': self.account.name if self.account else None
        }

    def __repr__(self):
        return f'<Transaction {self.date} {self.name} {self.amount}>'

class UserProfile(db.Model):
    __tablename__ = 'user_profile'
    # Simple ID, could just always be 1 for single user
    id = db.Column(db.Integer, primary_key=True)
    # Store user's estimated GROSS or NET monthly income (clarify which one later)
    monthly_salary_estimate = db.Column(db.Numeric(12, 2), nullable=True)
    # We can add other user settings here later

    # Ensure only one profile exists (for single-user app)
    # You might enforce this in application logic rather than DB constraint

    def to_dict(self):
        return {
            'id': self.id,
            'monthly_salary_estimate': float(self.monthly_salary_estimate) if self.monthly_salary_estimate is not None else None
            # Add other fields later if needed
        }

    def __repr__(self):
        return f'<UserProfile {self.id}>'

class RecurringExpense(db.Model):
    __tablename__ = 'recurring_expense'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # Use the same categories as transactions for consistency
    budget_category = db.Column(db.String(50), nullable=False, index=True)
    # Amount per occurrence
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    # How often it occurs (e.g., 'monthly', 'yearly', 'quarterly', 'weekly')
    frequency = db.Column(db.String(20), nullable=False, default='monthly')
    # Optional: next due date for reminders/projections
    next_due_date = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'budget_category': self.budget_category,
            'amount': float(self.amount) if self.amount is not None else None,
            'frequency': self.frequency,
            'next_due_date': self.next_due_date.isoformat() if self.next_due_date else None,
            'is_active': self.is_active,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<RecurringExpense {self.name} ({self.amount}/{self.frequency})>'
