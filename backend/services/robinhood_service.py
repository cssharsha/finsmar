# backend/services/robinhood_service.py
import requests
import time
import json
import base64
from urllib.parse import urlparse, urlunparse # For cleaning URLs
import nacl.signing
import nacl.encoding

class RobinhoodService:
    """
    Handles interactions with the Robinhood API (primarily Crypto API structure).
    """
    # Using API base documented for Crypto Trading API
    BASE_URL = "https://api.robinhood.com"

    def __init__(self, pri_key, pub_key, api_key, logger):
        if not pri_key or not pub_key or not api_key:
             raise ValueError("Robinhood API Key and Secret must be provided.")
        self.api_key = api_key
        self.logger = logger
        self.session = requests.Session() # Use a session for potential connection reuse
        # --- Temporary Debug Print ---
        # Safely print only the start/end and length to avoid exposing full key in logs
        safe_key_repr = f"'{pri_key[:5]}...{pri_key[-5:]}' (Length: {len(pri_key)})" if pri_key and len(pri_key) > 10 else "'Invalid or too short'"
        self.logger.info(f"Attempting to decode RH Private Key B64: {safe_key_repr}")
        if not pri_key: # Add explicit check here
            raise ValueError("Private key string is empty.")
        # ---------------------------
        try:
            private_key_seed = base64.b64decode(pri_key)
            self.signing_key = nacl.signing.SigningKey(private_key_seed)
            self.logger.info("Robinhood SigningKey initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to decode/initialize Robinhood private key: {e}", exc_info=True)
            raise ValueError("Invalid Robinhood private key provided.") from e

    def _generate_ed25519_auth_headers(self, method: str, path: str, body_str: str = "") -> dict:
        """Generates Ed25519 authentication headers."""
        # Ensure path starts with '/' and includes API version if needed (e.g., /api/v1/)
        if not path.startswith('/'):
            path = '/' + path
        # --- Check if path needs '/api/v1' prefix ---
        # This might depend on the specific endpoint. Assuming yes based on example.
        # if not path.startswith('/api/v1/'):
        #    path = '/api/v1' + path # Adjust as needed per endpoint docs

        timestamp = str(int(time.time())) # Timestamp in SECONDS as string

        # Message: API_Key + Timestamp + Path + Method + Body
        message = f"{self.api_key}{timestamp}{path}{method}{body_str}"
        self.logger.debug(f"Robinhood signing message: {message}")

        # Sign the message using the private key
        signed = self.signing_key.sign(message.encode("utf-8"))

        # Base64 encode the raw signature
        b64_signature = base64.b64encode(signed.signature).decode("utf-8")

        headers = {
            'Accept': 'application/json',
            'X-Api-Key': self.api_key,
            'X-Timestamp': timestamp,
            'X-Signature': b64_signature, # The Base64 encoded Ed25519 signature
        }
        if body_str:
            headers['Content-Type'] = 'application/json; charset=utf-8'

        return headers
    
    def _make_request(self, method: str, endpoint: str, params: dict = None, data: dict = None) -> dict:
        """Makes an authenticated request using Ed25519 signature."""
        # --- Crucial: Verify if endpoint path needs '/api/v1' prefix ---
        # Assuming it does based on the example snippet. Adjust if needed.
        if not endpoint.startswith('/api/v1/'):
             endpoint = '/api/v1' + '/' + endpoint.lstrip('/')
             self.logger.warning(f"Prepending /api/v1 to endpoint: {endpoint}")

        full_url = self.BASE_URL.rstrip('/') + '/' + endpoint.lstrip('/')
        body_str = json.dumps(data) if data else ""

        # Path for signature should likely match the endpoint used in the URL
        path_for_sig = urlparse(full_url).path

        headers = self._generate_ed25519_auth_headers(method.upper(), path_for_sig, body_str)
        self.logger.debug(f"Robinhood Request: {method} {full_url} Headers: {headers} Params: {params} Body: {body_str}")

        try:
            response = self.session.request(
                method.upper(),
                full_url,
                headers=headers,
                params=params,
                data=body_str.encode('utf-8') if body_str else None # Send body as bytes
            )
            self.logger.debug(f"Robinhood Response Status: {response.status_code}")
            self.logger.debug(f"Robinhood Response Body: {response.text[:500]}...") # Log truncated body
            response.raise_for_status()
            if response.text:
                 # Check content type before assuming JSON
                 content_type = response.headers.get('Content-Type', '')
                 if 'application/json' in content_type:
                      return response.json()
                 else:
                      self.logger.warning(f"Unexpected Content-Type: {content_type}")
                      return {"raw_content": response.text}
            return {}
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Robinhood API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                 self.logger.error(f"Response Status: {e.response.status_code}")
                 self.logger.error(f"Response Body: {e.response.text}")
            raise

    # --- Public Methods ---
    def get_crypto_accounts(self) -> list:
         """Fetches crypto accounts using the /api/v1/crypto/accounts/ endpoint."""
         try:
              # Use the correct endpoint path based on v1 assumption
              endpoint = "/crypto/accounts/" # Path relative to /api/v1/
              data = self._make_request('GET', endpoint)
              return data.get('results', []) if data else []
         except Exception as e:
              self.logger.error(f"Failed to get Robinhood crypto accounts: {e}", exc_info=True)
              return []

    # Method to combine fetching and processing (adapt as needed)
    def get_positions(self) -> list:
        """Fetches positions, prioritizing crypto via Ed25519."""
        positions = []
        crypto_accounts = self.get_crypto_accounts() # Use the new method

        for account in crypto_accounts:
            currency_info = account.get('currency', {})
            symbol = currency_info.get('code')
            account_id = account.get('id')
            # Adjust key access based on actual response structure
            quantity = account.get('balance', {}).get('amount')

            if symbol and quantity and account_id and float(quantity) > 0:
                positions.append({
                    'symbol': symbol, 'quantity': quantity, 'average_cost': None,
                    'id': account_id, 'type': 'crypto'
                })
            else:
                self.logger.warning(f"Skipping crypto account due to missing data: {account_id}")

        # Speculative stock fetching (might fail if keys/auth don't apply)
        # Consider removing or making conditional if Ed25519 keys *only* work for /api/v1/crypto
        try:
             # This likely requires different auth or won't work with these keys/prefix
             # stock_positions_data = self._make_request('GET', '/positions/') # REMOVE /api/v1 prefix if testing this old endpoint
             # ... processing ...
             pass # Commenting out for now as it's unlikely to work with Ed25519
             self.logger.info("Skipping speculative stock position fetch (/positions/).")

        except Exception as stock_err:
             self.logger.warning(f"Expected failure or skipping fetching stock positions via /positions/: {stock_err}")

        return positions

    # --- Older version ---
    # def _generate_auth_headers(self, method: str, path: str, body: str = "") -> dict:
    #     """Generates authentication headers required by Robinhood API."""
    #     # Ensure path starts with '/'
    #     if not path.startswith('/'):
    #         path = '/' + path
    #
    #     timestamp = str(int(time.time() * 1000)) # Millisecond timestamp as string
    #
    #     # Body is empty string for GET, URL-encoded query string for some GETs, or JSON string for POST/PUT
    #     # Per RH docs example: message = f"{api_key}{timestamp}{path}{method}{body}"
    #     message = f"{self.api_key}{timestamp}{path}{method}{body}"
    #
    #     signature = hmac.new(
    #         self.api_secret.encode('utf-8'),
    #         message.encode('utf-8'),
    #         hashlib.sha256
    #     ).hexdigest()
    #
    #     headers = {
    #         'Accept': 'application/json',
    #         'X-Api-Key': self.api_key,
    #         'X-Timestamp': timestamp,
    #         'X-Signature': signature,
    #     }
    #     # Add Content-Type if there's a body for POST/PUT etc.
    #     if body:
    #         headers['Content-Type'] = 'application/json'
    #
    #     return headers
    # ------


    # Add other methods like get_portfolio_value() if needed, calling relevant endpoints
