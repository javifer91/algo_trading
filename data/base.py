from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd

class AssetUniverse(ABC):
    @abstractmethod
    def get_eligible_assets(self) -> List[str]:
        """Returns a list of symbols eligible for trading."""
        pass

class MarketDataProvider(ABC):
    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        pass
        
    @abstractmethod
    def get_bid_ask(self, symbol: str) -> tuple[float, float]:
        """Returns (bid, ask)"""
        pass
        
    @abstractmethod
    def get_historical_data(self, symbol: str, start: datetime, end: datetime, timeframe: str) -> pd.DataFrame:
        """Returns OHLCV DataFrame."""
        pass
