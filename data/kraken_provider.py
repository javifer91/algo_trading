import ccxt
import pandas as pd
from datetime import datetime
from data.base import MarketDataProvider
from core.exceptions import DataError
from core.logger import get_logger

logger = get_logger(__name__)

class KrakenDataProvider(MarketDataProvider):
    """
    Provides real crypto market data using Kraken via the ccxt library.
    Ideal for real-time and historical cryptocurrency data.
    """
    def __init__(self):
        self.exchange = ccxt.kraken({
            'enableRateLimit': True,
        })

    def get_current_price(self, symbol: str) -> float:
        try:
            # ccxt expects symbols like 'BTC/EUR' or 'ETH/USD'
            ticker = self.exchange.fetch_ticker(symbol)
            if 'last' in ticker and ticker['last'] is not None:
                return ticker['last']
            raise DataError(f"Cannot retrieve current price for {symbol} on Kraken")
        except Exception as e:
            logger.error(f"Error fetching current price for {symbol} on Kraken: {e}")
            raise DataError(f"Error fetching current price for {symbol}: {e}")

    def get_bid_ask(self, symbol: str) -> tuple[float, float]:
        """
        Fetches the real-time order book top bid and ask from Kraken.
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            bid = ticker.get('bid', 0.0)
            ask = ticker.get('ask', 0.0)
            
            if not bid or not ask:
                # Fallback to estimating from price if orderbook data is missing in ticker
                price = self.get_current_price(symbol)
                spread = price * 0.001 # 0.1% simulated fallback spread for crypto
                return price - (spread/2), price + (spread/2)
                
            return bid, ask
        except Exception as e:
            logger.error(f"Error fetching bid/ask for {symbol} on Kraken: {e}")
            raise DataError(f"Error fetching bid/ask for {symbol}: {e}")

    def get_historical_data(self, symbol: str, start: datetime, end: datetime, timeframe: str) -> pd.DataFrame:
        """
        Timeframe mapping from our internal format to ccxt format.
        e.g., '1d' -> '1d', '1h' -> '1h', '1m' -> '1m'
        """
        try:
            since = int(start.timestamp() * 1000)
            # ccxt fetch_ohlcv returns: [timestamp, open, high, low, close, volume]
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since)
            
            if not ohlcv:
                raise DataError(f"No historical data returned for {symbol} from Kraken")
                
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Filter exactly to the requested 'end' date, as ccxt might return more
            df = df[df.index <= end]
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol} on Kraken: {e}")
            raise DataError(f"Error fetching historical data for {symbol}: {e}")
