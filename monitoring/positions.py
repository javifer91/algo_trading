from broker.base import BrokerInterface, OrderSide, OrderType
from data.base import MarketDataProvider
from core.logger import get_logger
from typing import Dict, Any

logger = get_logger(__name__)

class PositionManager:
    """
    Monitors active positions to manage dynamic exits (Take Profit, Trailing Stop, Time Stops).
    """
    def __init__(self, broker: BrokerInterface, data_provider: MarketDataProvider):
        self.broker = broker
        self.data_provider = data_provider
        # Mock storage for position metadata (e.g. highest price reached for trailing stop)
        self.position_metadata: Dict[str, Dict[str, Any]] = {}

    def monitor_positions(self):
        """Called periodically to check if any open position should be closed."""
        positions = self.broker.get_positions()
        
        for symbol, quantity in positions.items():
            if quantity <= 0:
                continue
                
            current_price = self.data_provider.get_current_price(symbol)
            meta = self.position_metadata.setdefault(symbol, {"highest_price": current_price, "entry_price": current_price})
            
            # Update trailing high
            if current_price > meta["highest_price"]:
                meta["highest_price"] = current_price
                
            # Trailing stop logic (e.g., 5% from highest)
            trailing_stop_price = meta["highest_price"] * 0.95
            if current_price < trailing_stop_price:
                logger.info(f"{symbol}: Trailing stop triggered. Current: {current_price:.2f}, High: {meta['highest_price']:.2f}. Selling.")
                self.broker.submit_order(symbol, OrderSide.SELL, OrderType.MARKET, quantity)
                # Cleanup metadata will happen once position is 0
