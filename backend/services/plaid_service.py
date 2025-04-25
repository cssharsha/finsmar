import datetime
from dateutil.relativedelta import relativedelta
from plaid.exceptions import ApiException
from plaid.model.transactions_sync_request import TransactionsSyncRequest
# Import necessary db objects and models carefully based on your structure
# Assuming db is accessible via an imported 'app' or directly if configured
from extensions import db # Adjusted based on previous successful imports in shell
from models import Account, Transaction, PlaidItem
from sqlalchemy.exc import SQLAlchemyError

# Placeholder - Category Mapping (Refine later)
PLAID_CATEGORY_TO_BUDGET_BUCKET = {
    "Food and Drink": "Food & Drink", "Travel": "Travel", "Transfer": "Transfers",
    "Payment": "Bills & Utilities", "Shops": "Shopping", "Recreation": "Entertainment",
    "Service": "Services", "Utilities": "Bills & Utilities", "Rent": "Housing",
    "Mortgage": "Housing", "Payroll": "Income", "Deposit": "Income",
    "Interest Earned": "Income", "_DEFAULT_": "Miscellaneous"
}

class PlaidService:
    def __init__(self, plaid_client, logger):
         if not plaid_client: raise ValueError("Plaid client is required for PlaidService")
         self.client = plaid_client
         self.logger = logger
         self.logger.info("PlaidService initialized.")

    def _map_category(self, plaid_categories):
         if not plaid_categories: return PLAID_CATEGORY_TO_BUDGET_BUCKET["_DEFAULT_"]
         primary = plaid_categories[0]
         return PLAID_CATEGORY_TO_BUDGET_BUCKET.get(primary, PLAID_CATEGORY_TO_BUDGET_BUCKET["_DEFAULT_"])
    
    def sync_transactions_for_item(self, item: PlaidItem):
        self.logger.info(f"Starting transaction sync for Item ID: {item.item_id}, {item.sync_cursor}")
        access_token = item.access_token
        cursor = item.sync_cursor # Load cursor from the DB item
        added_count, modified_count, removed_count = 0, 0, 0
        item_failed = False
        print(f"Cursor val: ", cursor)

        if cursor == None: cursor = ""

        try:
            has_more = True
            while has_more:
                request = TransactionsSyncRequest(
                    access_token=access_token,
                    cursor=cursor,
                    count=100 # Fetch 100 transactions per page (adjust as needed)
                )
                response = self.client.transactions_sync(request).to_dict() # Use .to_dict()

                added = response.get('added', [])
                modified = response.get('modified', [])
                removed = response.get('removed', [])
                has_more = response.get('has_more', False)
                next_cursor = response.get('next_cursor') # Get the new cursor

                self.logger.info(f"Sync page fetched: Added({len(added)}), Mod({len(modified)}), Rem({len(removed)}), More({has_more})")

                # --- Process Added/Modified/Removed (within a DB transaction) ---
                try:
                    # Added
                    for txn_data in added:
                        acc = Account.query.filter_by(external_id=txn_data['account_id']).first() # Match any Plaid account
                        if not acc:
                             self.logger.warning(f"Account not found for Plaid acc ID {txn_data['account_id']}. Skipping txn {txn_data['transaction_id']}.")
                             continue
                        if Transaction.query.filter_by(plaid_transaction_id=txn_data['transaction_id']).first():
                             self.logger.warning(f"Duplicate add: Transaction {txn_data['transaction_id']} already exists. Treating as modified.")
                             modified.append(txn_data) # Add to modified list to handle below
                             continue

                        budget_cat = self._map_category(txn_data.get('category'))
                        new_txn = Transaction(
                            account_db_id=acc.id, plaid_transaction_id=txn_data['transaction_id'],
                            plaid_account_id=txn_data['account_id'], name=txn_data.get('name', txn_data.get('merchant_name', 'N/A')),
                            merchant_name=txn_data.get('merchant_name'), amount=txn_data['amount'], currency_code=txn_data['iso_currency_code'],
                            date=txn_data['date'], pending=txn_data['pending'], plaid_primary_category=txn_data.get('category', [None])[0],
                            plaid_detailed_category=txn_data.get('category', [])[-1], plaid_category_id=txn_data.get('category_id'),
                            budget_category=budget_cat )
                        db.session.add(new_txn)
                        added_count += 1

                    # Modified
                    for txn_data in modified:
                        txn = Transaction.query.filter_by(plaid_transaction_id=txn_data['transaction_id']).first()
                        if txn:
                            txn.amount = txn_data['amount']; txn.pending = txn_data['pending']
                            txn.name = txn_data.get('name', txn_data.get('merchant_name', txn.name))
                            txn.merchant_name=txn_data.get('merchant_name'); txn.date = txn_data['date'] # Date can change too
                            txn.budget_category = self._map_category(txn_data.get('category'))
                            txn.plaid_primary_category=txn_data.get('category', [txn.plaid_primary_category])[0]
                            txn.plaid_detailed_category=txn_data.get('category', [txn.plaid_detailed_category])[-1]
                            txn.plaid_category_id=txn_data.get('category_id', txn.plaid_category_id)
                            modified_count += 1
                        else: self.logger.warning(f"Modified txn {txn_data['transaction_id']} not found locally.")

                    # Removed
                    removed_ids = [rt['transaction_id'] for rt in removed]
                    if removed_ids:
                         delete_q = Transaction.__table__.delete().where(Transaction.plaid_transaction_id.in_(removed_ids))
                         result = db.session.execute(delete_q)
                         removed_count += result.rowcount
                         if result.rowcount != len(removed_ids):
                             self.logger.warning(f"Attempted to delete {len(removed_ids)} txns, but only {result.rowcount} were found/deleted.")

                    # --- Commit changes for this page ---
                    db.session.commit()
                    self.logger.info("Committed transaction sync page changes.")
                    # Update cursor for next loop iteration *after* successful commit
                    cursor = next_cursor

                except SQLAlchemyError as db_err:
                    db.session.rollback()
                    self.logger.error(f"Database error processing sync page for Item {item.item_id}: {db_err}", exc_info=True)
                    item_failed = True # Mark item as failed for this run
                    break # Stop processing this item    
                # End of while has_more loop

            # --- Update Item's Cursor ---
            if not item_failed and next_cursor: # Only update cursor if sync didn't fail mid-way
                try:
                     item.sync_cursor = next_cursor
                     db.session.commit()
                     self.logger.info(f"Updated sync cursor for Item {item.item_id}")
                except SQLAlchemyError as db_err:
                     db.session.rollback()
                     self.logger.error(f"Database error updating cursor for Item {item.item_id}: {db_err}", exc_info=True)
                     item_failed = True # Mark as failed if cursor save fails

            # --- History Cleanup (Optional: run after successful sync) ---
            if not item_failed:

                self.cleanup_old_transactions()
            self.logger.info(f"Transaction sync finished for Item {item.item_id}. Added: {added_count}, Mod: {modified_count}, Rem: {removed_count}. Failed: {item_failed}")
            return not item_failed # Return True on success, False on failure
        except ApiException as e:
            self.logger.error(f"Plaid API error syncing transactions for Item {item.item_id}: {getattr(e, 'body', e)}", exc_info=True)
            return False # Indicate failure
        except Exception as e:
            self.logger.error(f"Unexpected error syncing transactions for Item {item.item_id}: {e}", exc_info=True)
            return False # Indicate failure

    def cleanup_old_transactions(self):

        """Deletes transactions older than 5 months."""
        # ... (Implementation from response #41) ...
        try:

            five_months_ago = datetime.date.today() - relativedelta(months=5)
            five_months_ago = five_months_ago.replace(day=1)
            self.logger.info(f"Cleaning up transactions before {five_months_ago}...")
            delete_q = Transaction.__table__.delete().where(Transaction.date < five_months_ago)
            result = db.session.execute(delete_q)
            db.session.commit()
            self.logger.info(f"Deleted {result.rowcount} old transactions.")
        except Exception as e: # Catch broader exceptions here too
            db.session.rollback()
            self.logger.error(f"Error cleaning old transactions: {e}", exc_info=True)
