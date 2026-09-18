from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Dict, Any, List

class SignalType(BaseModel):
    symbol: str
    signal: int  # 1 for BUY, -1 for SELL, 0 for HOLD
    confidence: float  # 0.0 to 1.0
    expected_return: float # e.g., 0.02 for 2%
    expected_risk: float   # e.g., 0.01 for 1%
    reason: str

class Strategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def generate_signal(self, symbol: str, data_provider: Any) -> SignalType:
        """Evaluates the market data and returns a signal."""
        pass

class SignalEngine:
    """
    Combines signals from multiple strategies.
    For now, uses a simple weighted average or majority vote.
    """
    def __init__(self, strategies: List[Strategy]):
        self.strategies = strategies

    def evaluate(self, symbol: str, data_provider: Any) -> SignalType:
        signals = [s.generate_signal(symbol, data_provider) for s in self.strategies]
        
        # Very simple combination logic: Average the signals
        avg_signal_val = sum(s.signal for s in signals) / len(signals) if signals else 0
        avg_conf = sum(s.confidence for s in signals) / len(signals) if signals else 0.0
        avg_ret = sum(s.expected_return for s in signals) / len(signals) if signals else 0.0
        avg_risk = sum(s.expected_risk for s in signals) / len(signals) if signals else 0.0
        
        final_signal = 0
        if avg_signal_val > 0.3:
            final_signal = 1
        elif avg_signal_val < -0.3:
            final_signal = -1
            
        reasons = " | ".join([f"{s.reason}" for s in signals if s.signal != 0])
        
        return SignalType(
            symbol=symbol,
            signal=final_signal,
            confidence=avg_conf,
            expected_return=avg_ret,
            expected_risk=avg_risk,
            reason=reasons if reasons else "No clear consensus"
        )
