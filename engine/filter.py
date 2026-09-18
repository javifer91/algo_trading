from core.config import settings
from data.base import MarketDataProvider
from core.logger import get_logger

logger = get_logger(__name__)

class TradeViabilityFilter:
    """
    Evaluates if a trade makes mathematical sense after accounting for all costs.
    Crucial for small capital (50 €).
    """
    def __init__(self, data_provider: MarketDataProvider, min_commission: float = 1.0, commission_pct: float = 0.001):
        self.data_provider = data_provider
        self.min_commission = min_commission
        self.commission_pct = commission_pct

    def is_viable(self, symbol: str, expected_gross_return: float, target_investment: float) -> bool:
        """
        Returns True if the Expected Net Return > MIN_EXPECTED_NET_RETURN_PERCENT.
        """
        if target_investment <= 0:
            return False

        try:
            bid, ask = self.data_provider.get_bid_ask(symbol)
        except Exception:
            return False
            
        spread_pct = (ask - bid) / ask
        
        # Calculate round-trip costs
        entry_commission = max(self.min_commission, target_investment * self.commission_pct)
        # Assume exit value is similar for commission calculation
        exit_commission = max(self.min_commission, target_investment * (1+expected_gross_return) * self.commission_pct) 
        
        total_costs_abs = entry_commission + exit_commission + (spread_pct * target_investment)
        cost_pct = total_costs_abs / target_investment
        
        expected_net_return_pct = expected_gross_return - cost_pct

        if cost_pct > settings.max_transaction_cost_percent:
            logger.warning(f"Trade {symbol} rejected: Costs ({cost_pct*100:.2f}%) exceed max allowed ({settings.max_transaction_cost_percent*100:.2f}%)")
            return False

        if expected_net_return_pct < settings.min_expected_net_return_percent:
            logger.warning(f"Trade {symbol} rejected: Expected Net Return ({expected_net_return_pct*100:.2f}%) < Min required ({settings.min_expected_net_return_percent*100:.2f}%)")
            return False
            
        return True
