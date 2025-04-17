# backend/services/market_data_service.py
import requests
import time

class MarketDataService:
    """
    Handles fetching market data (stock/crypto prices) from Alpha Vantage.
    """
    BASE_URL = "https://www.alphavantage.co/query"
    # Simple cache to avoid hitting rate limits too quickly during a single request
    # For more robust caching, consider Flask-Caching or Redis later.
    CACHE = {}
    CACHE_TTL = 300 # Cache prices for 5 minutes (300 seconds)

    def __init__(self, api_key, logger):
        if not api_key:
            raise ValueError("Alpha Vantage API Key must be provided.")
        self.api_key = api_key
        self.logger = logger
        self.session = requests.Session()
        self.logger.info("MarketDataService initialized.")

    def _clear_expired_cache(self):
        """Removes expired entries from the simple cache."""
        now = time.time()
        expired_keys = [k for k, (timestamp, _) in self.CACHE.items() if now - timestamp > self.CACHE_TTL]
        for key in expired_keys:
            del self.CACHE[key]

    def _make_request(self, params: dict) -> dict | None:
        """Makes a request to the Alpha Vantage API."""
        params['apikey'] = self.api_key
        self.logger.debug(f"Alpha Vantage Request Params: {params}")
        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=10) # Added timeout
            response.raise_for_status() # Check for HTTP errors
            data = response.json()

            # --- Alpha Vantage Specific Error/Limit Handling ---
            if not data:
                 self.logger.warning("Alpha Vantage returned empty response.")
                 return None
            if "Error Message" in data:
                self.logger.error(f"Alpha Vantage API Error: {data['Error Message']}")
                return None
            if "Note" in data: # Often indicates rate limiting on free tier
                self.logger.warning(f"Alpha Vantage API Note: {data['Note']}")
                # Treat rate limit note as an error for price fetching
                return None
            # ----------------------------------------------------

            return data

        except requests.exceptions.Timeout:
             self.logger.error("Alpha Vantage request timed out.")
             return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Alpha Vantage request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                self.logger.error(f"Response Status: {e.response.status_code}")
                self.logger.error(f"Response Body: {e.response.text}")
            return None
        except ValueError as e: # Handles JSON decoding errors
            self.logger.error(f"Failed to decode Alpha Vantage JSON response: {e}")
            return None

    def get_stock_price(self, symbol: str) -> float | None:
        """Fetches the current price for a stock symbol using GLOBAL_QUOTE."""
        self._clear_expired_cache()
        cache_key = f"stock_{symbol}"
        if cache_key in self.CACHE:
            _, price = self.CACHE[cache_key]
            self.logger.debug(f"Cache hit for stock: {symbol}")
            return price

        self.logger.info(f"Fetching stock price for: {symbol}")
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol
        }
        data = self._make_request(params)

        if data and 'Global Quote' in data and data['Global Quote']:
            try:
                price_str = data['Global Quote'].get('05. price')
                if price_str is not None:
                    price = float(price_str)
                    self.CACHE[cache_key] = (time.time(), price) # Update cache
                    return price
                else:
                     self.logger.warning(f"Price field ('05. price') not found in Global Quote for {symbol}")
            except (ValueError, TypeError) as e:
                self.logger.error(f"Could not convert price to float for {symbol}: {price_str}, Error: {e}")
        else:
             self.logger.warning(f"Could not find 'Global Quote' or valid price data for stock: {symbol}")

        return None # Return None if price not found or error

    def get_crypto_price(self, symbol: str, target_currency: str = 'USD') -> float | None:
        """Fetches the current exchange rate for a crypto symbol to a target currency."""
        self._clear_expired_cache()
        # Normalize crypto symbol if needed (e.g., BTC vs BTC-USD) - AV usually just wants 'BTC'
        normalized_symbol = symbol.upper().replace('-USD', '')
        cache_key = f"crypto_{normalized_symbol}_{target_currency}"
        if cache_key in self.CACHE:
             _, price = self.CACHE[cache_key]
             self.logger.debug(f"Cache hit for crypto: {symbol} -> {target_currency}")
             return price

        self.logger.info(f"Fetching crypto price for: {normalized_symbol} -> {target_currency}")
        params = {
            'function': 'CURRENCY_EXCHANGE_RATE',
            'from_currency': normalized_symbol,
            'to_currency': target_currency
        }
        data = self._make_request(params)

        if data and 'Realtime Currency Exchange Rate' in data:
            try:
                rate_str = data['Realtime Currency Exchange Rate'].get('5. Exchange Rate')
                if rate_str is not None:
                    price = float(rate_str)
                    self.CACHE[cache_key] = (time.time(), price) # Update cache
                    return price
                else:
                     self.logger.warning(f"Exchange rate field ('5. Exchange Rate') not found for {normalized_symbol}/{target_currency}")
            except (ValueError, TypeError) as e:
                 self.logger.error(f"Could not convert exchange rate to float for {normalized_symbol}: {rate_str}, Error: {e}")
        else:
            self.logger.warning(f"Could not find 'Realtime Currency Exchange Rate' data for crypto: {normalized_symbol}/{target_currency}")

        return None # Return None if price not found or error
