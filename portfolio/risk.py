from core.config import settings
from broker.base import BrokerInterface
from core.exceptions import RiskLimitExceededError

class RiskManager:
    """
    Manages portfolio risk, position sizing, and drawdown limits.
    """
    def __init__(self, broker: BrokerInterface):
        self.broker = broker
        
    def check_trade_allowed(self) -> bool:
        """Check high-level risk limits like Max Drawdown."""
        # TODO: Implement actual drawdown calculation from historical peaks
        return True

    def calculate_position_size(self, symbol: str, price: float, confidence: float) -> float:
        """
        Calculates how many shares to buy based on risk limits.
        With 50€, we probably buy fractional shares or small amounts.
        """
        balance = self.broker.get_balance()
        max_investment = balance * settings.max_position_size_percent
        
        # Scale investment by confidence
        target_investment = max_investment * confidence
        
        quantity = target_investment / price
        return quantity
