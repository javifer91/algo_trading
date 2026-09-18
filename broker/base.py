from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, List, Optional

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"

class OrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"

class BrokerInterface(ABC):
    @abstractmethod
    def get_balance(self) -> float:
        """Returns available cash balance."""
        pass

    @abstractmethod
    def get_positions(self) -> Dict[str, Any]:
        """Returns current open positions."""
        pass

    @abstractmethod
    def submit_order(self, symbol: str, side: OrderSide, type: OrderType, quantity: float, price: Optional[float] = None) -> str:
        """Submits an order and returns an order ID."""
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderStatus:
        """Returns the status of an order."""
        pass
        
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancels a pending order."""
        pass
