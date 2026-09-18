import pandas as pd
from strategies.base import Strategy, SignalType
from datetime import datetime
from data.base import MarketDataProvider

class SimpleMomentumStrategy(Strategy):
    """
    A basic momentum strategy looking at short vs long term moving averages.
    Note: Real production strategy would be more robust.
    """
    def __init__(self, short_window: int = 10, long_window: int = 50):
        super().__init__("SimpleMomentum")
        self.short_window = short_window
        self.long_window = long_window

    def generate_signal(self, symbol: str, data_provider: MarketDataProvider) -> SignalType:
        # For simplicity, we just request the last 100 periods of data 
        # (assume daily timeframe for this mock)
        end_time = datetime.now()
        start_time = end_time - pd.Timedelta(days=100)
        
        try:
            df = data_provider.get_historical_data(symbol, start_time, end_time, "1d")
        except Exception:
            return SignalType(symbol=symbol, signal=0, confidence=0.0, expected_return=0.0, expected_risk=0.0, reason="Data error")

        if len(df) < self.long_window:
            return SignalType(symbol=symbol, signal=0, confidence=0.0, expected_return=0.0, expected_risk=0.0, reason="Not enough data")

        short_ma = df['close'].rolling(window=self.short_window).mean().iloc[-1]
        long_ma = df['close'].rolling(window=self.long_window).mean().iloc[-1]
        
        current_price = df['close'].iloc[-1]
        
        # Calculate roughly expected return and risk based on historical volatility
        daily_returns = df['close'].pct_change().dropna()
        volatility = daily_returns.std() * 16 # roughly annualized assuming 252 days
        expected_return = 0.02 # mock expected return for momentum 2%
        
        if short_ma > long_ma:
            return SignalType(symbol=symbol, signal=1, confidence=0.6, expected_return=expected_return, expected_risk=volatility, reason=f"Short MA ({short_ma:.2f}) > Long MA ({long_ma:.2f})")
        elif short_ma < long_ma:
            return SignalType(symbol=symbol, signal=-1, confidence=0.6, expected_return=-expected_return, expected_risk=volatility, reason=f"Short MA ({short_ma:.2f}) < Long MA ({long_ma:.2f})")
            
        return SignalType(symbol=symbol, signal=0, confidence=0.0, expected_return=0.0, expected_risk=0.0, reason="No trend")
