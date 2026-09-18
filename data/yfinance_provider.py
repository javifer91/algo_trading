import yfinance as yf
import pandas as pd
from datetime import datetime
from data.base import MarketDataProvider
from core.exceptions import DataError
from core.logger import get_logger

logger = get_logger(__name__)

class YFinanceDataProvider(MarketDataProvider):
    """
    Provides real market data using the Yahoo Finance API (yfinance).
    Ideal for end-of-day data, swing trading, and basic intraday simulation.
    """
    def __init__(self):
        # We cache recent tickers to avoid repeatedly calling yfinance for the same static info
        self._ticker_cache = {}

    def _get_ticker(self, symbol: str) -> yf.Ticker:
        if symbol not in self._ticker_cache:
            self._ticker_cache[symbol] = yf.Ticker(symbol)
        return self._ticker_cache[symbol]

    def get_current_price(self, symbol: str) -> float:
        try:
            ticker = self._get_ticker(symbol)
            # Fetch very recent data
            df = ticker.history(period="1d", interval="1m")
            if df.empty:
                # Fallback to info (slower, sometimes None)
                info = ticker.info
                if "currentPrice" in info:
                    return info["currentPrice"]
                if "regularMarketPrice" in info:
                    return info["regularMarketPrice"]
                raise DataError(f"Cannot retrieve current price for {symbol}")
            return df['Close'].iloc[-1]
        except Exception as e:
            logger.error(f"Error fetching current price for {symbol}: {e}")
            raise DataError(f"Error fetching current price for {symbol}: {e}")

    def get_bid_ask(self, symbol: str) -> tuple[float, float]:
        """
        yfinance doesn't reliably provide real-time bid/ask for all symbols.
        We will simulate a realistic bid/ask spread based on the current price 
        and typical liquidity (e.g. 0.05% spread).
        """
        try:
            ticker = self._get_ticker(symbol)
            info = ticker.info
            bid = info.get("bid", 0.0)
            ask = info.get("ask", 0.0)
            
            # If bid/ask are missing or zero (common in yfinance during off-hours), estimate it
            if not bid or not ask or bid == 0 or ask == 0:
                price = self.get_current_price(symbol)
                spread = price * 0.0005 # 0.05% simulated spread
                bid = price - (spread / 2)
                ask = price + (spread / 2)
                
            return bid, ask
        except Exception as e:
            logger.error(f"Error fetching bid/ask for {symbol}: {e}")
            raise DataError(f"Error fetching bid/ask for {symbol}: {e}")

    def get_historical_data(self, symbol: str, start: datetime, end: datetime, timeframe: str) -> pd.DataFrame:
        """
        Timeframe mapping from our internal format to yfinance format.
        e.g., '1d' -> '1d', '1h' -> '60m', '1m' -> '1m'
        """
        yf_interval = timeframe
        if timeframe == '1h':
            yf_interval = '60m'
            
        try:
            ticker = self._get_ticker(symbol)
            df = ticker.history(start=start, end=end, interval=yf_interval)
            
            if df.empty:
                raise DataError(f"No historical data returned for {symbol} between {start} and {end}")
                
            # Standardize columns to lowercase to match our mock/expected format
            df.columns = [col.lower() for col in df.columns]
            return df
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            raise DataError(f"Error fetching historical data for {symbol}: {e}")
