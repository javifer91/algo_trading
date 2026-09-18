import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict
from data.base import MarketDataProvider
from core.exceptions import DataError

class MockMarketDataProvider(MarketDataProvider):
    """Provides generated or static mocked data for testing and paper trading."""
    def __init__(self):
        self.prices: Dict[str, float] = {}
        self.historical_data: Dict[str, pd.DataFrame] = {}
        self.spreads: Dict[str, float] = {} # Constant spread for simplicity

    def set_mock_data(self, symbol: str, price: float, spread: float = 0.01):
        self.prices[symbol] = price
        self.spreads[symbol] = spread

    def load_historical_dataframe(self, symbol: str, df: pd.DataFrame):
        """Loads a pre-generated DataFrame containing at least OHLCV columns."""
        self.historical_data[symbol] = df

    def get_current_price(self, symbol: str) -> float:
        if symbol not in self.prices:
            raise DataError(f"No mock price available for {symbol}")
        return self.prices[symbol]

    def get_bid_ask(self, symbol: str) -> tuple[float, float]:
        price = self.get_current_price(symbol)
        half_spread = self.spreads.get(symbol, 0.01) / 2
        return price - half_spread, price + half_spread

    def get_historical_data(self, symbol: str, start: datetime, end: datetime, timeframe: str) -> pd.DataFrame:
        if symbol not in self.historical_data:
            raise DataError(f"No historical data loaded for {symbol}")
        
        df = self.historical_data[symbol]
        # In a real scenario, this would filter by index
        if not isinstance(df.index, pd.DatetimeIndex):
            raise DataError(f"Historical data for {symbol} must have a DatetimeIndex")
            
        mask = (df.index >= start) & (df.index <= end)
        return df.loc[mask]

    def advance_time(self, symbol: str, current_time: datetime):
        """Advances the internal state by reading from the historical dataframe. Used by backtesting."""
        if symbol in self.historical_data:
            df = self.historical_data[symbol]
            past_data = df[df.index <= current_time]
            if not past_data.empty:
                last_row = past_data.iloc[-1]
                self.prices[symbol] = last_row['close']
