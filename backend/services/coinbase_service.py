from coinbase.rest import RESTClient
from requests.exceptions import RequestException # Import requests exception for broader catch if needed

class CoinbaseService:
    """
    Handles interactions with the Coinbase Advanced Trade API using the SDK (JWT Auth).
    """
    def __init__(self, api_key, api_secret, logger):
        # api_secret here is the EC Private Key PEM string
        if not api_key or not api_secret:
            raise ValueError("Coinbase API Key and EC Private Key (as API Secret) must be provided.")

        self.logger = logger
        try:
            # Initialize the SDK client
            # The SDK handles JWT generation and Authorization header internally
            self.client = RESTClient(api_key=api_key, api_secret=api_secret)
            self.logger.info("Coinbase SDK Client initialized successfully.")
        except Exception as e:
            # Catch potential errors during client init (e.g., invalid key format)
            self.logger.error(f"Failed to initialize Coinbase SDK Client: {e}", exc_info=True)
            raise ValueError("Failed to initialize Coinbase SDK Client.") from e

    def get_accounts(self) -> list:
        """Fetches all brokerage accounts (wallets) using the SDK."""
        all_accounts = []
        try:
            # The SDK's list_accounts method handles authentication and pagination
            # Check SDK documentation for exact method signature and parameters (like limit)
            # Example: Fetching up to 250 accounts per page (max allowed by API)
            self.logger.info("Fetching accounts")
            response = self.client.get_accounts() # Initial call
            self.logger.info(f"Print test out: {response.accounts[0].available_balance['value']}")

            if response:
                all_accounts.extend(response.accounts)
                self.logger.info(f"Fetched {len(response.accounts)} Coinbase accounts page.")

                # Handle pagination using the cursor from the response
                # The SDK might have helper methods or you handle cursor manually like below
                # next_cursor = response.get('pagination', {}).get('next_cursor')
                # while next_cursor:
                #     self.logger.info(f"Fetching next Coinbase accounts page (cursor: {next_cursor[:5]}...)")
                #     response = self.client.list_accounts(limit=250, cursor=next_cursor)
                #     if response and 'accounts' in response:
                #         all_accounts.extend(response['accounts'])
                #         next_cursor = response.get('pagination', {}).get('next_cursor')
                #     else:
                #          self.logger.warning("Pagination response missing 'accounts' or invalid.")
                #          break # Stop if pagination fails
                self.logger.info(f"Appened to all_accounts {len(all_accounts)}")
            else:
                self.logger.warning(f"Coinbase list_accounts initial response missing 'accounts' key: {response}")

            self.logger.info(f"Total Coinbase accounts fetched: {len(all_accounts)}")
            return all_accounts

        except RequestException as req_err: # Catch potential HTTP errors from underlying requests library
             self.logger.error(f"Coinbase API request failed via SDK: {req_err}")
             if hasattr(req_err, 'response') and req_err.response is not None:
                  self.logger.error(f"Response Status: {req_err.response.status_code}")
                  self.logger.error(f"Response Body: {req_err.response.text}")
             return [] # Return empty on specific request errors
        except Exception as e:
            # Catch other potential SDK errors
            self.logger.error(f"Failed to get Coinbase accounts via SDK: {e}", exc_info=True)
            return [] # Return empty list on failure
