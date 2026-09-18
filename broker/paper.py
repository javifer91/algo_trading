from typing import Dict, Any, Optional
import uuid
from broker.base import BrokerInterface, OrderSide, OrderType, OrderStatus
from data.base import MarketDataProvider
from core.exceptions import OrderExecutionError
from core.logger import get_logger

logger = get_logger(__name__)

class PaperBroker(BrokerInterface):
    """
    Paper Trading broker that calculates explicit costs such as commissions, 
    spread, and slippage to ensure realistic micro-capital behavior.
    """
    def __init__(
        self, 
        initial_capital: float, 
        data_provider: MarketDataProvider,
        commission_pct: float = 0.001,  # 0.1% commission
        min_commission: float = 1.0,    # 1.0 EUR min commission (critical for micro capital)
        slippage_pct: float = 0.0005    # 0.05% slippage
    ):
        self.cash = initial_capital
        self.data_provider = data_provider
        self.commission_pct = commission_pct
        self.min_commission = min_commission
        self.slippage_pct = slippage_pct
        
        # symbol -> quantity
        self.positions: Dict[str, float] = {}
        # order_id -> details
        self.orders: Dict[str, Dict[str, Any]] = {}
        
    def get_balance(self) -> float:
        return self.cash

    def get_positions(self) -> Dict[str, float]:
        return {k: v for k, v in self.positions.items() if v != 0}

    def _calculate_commission(self, trade_value: float) -> float:
        return max(self.min_commission, trade_value * self.commission_pct)

    def submit_order(self, symbol: str, side: OrderSide, type: OrderType, quantity: float, price: Optional[float] = None) -> str:
        order_id = str(uuid.uuid4())
        
        # In this simple version, Market orders execute immediately.
        # Limit orders would just sit in pending (not fully implemented in this base version).
        
        self.orders[order_id] = {
            "symbol": symbol,
            "side": side,
            "type": type,
            "quantity": quantity,
            "price": price,
            "status": OrderStatus.PENDING
        }
        
        logger.info(f"Submitted order {order_id}: {side.value.upper()} {quantity} {symbol} @ {type.value.upper()}")
        
        if type == OrderType.MARKET:
            self._execute_market_order(order_id)
            
        return order_id

    def _execute_market_order(self, order_id: str):
        order = self.orders[order_id]
        symbol = order["symbol"]
        side = order["side"]
        quantity = order["quantity"]
        
        try:
            bid, ask = self.data_provider.get_bid_ask(symbol)
        except Exception as e:
            self.orders[order_id]["status"] = OrderStatus.REJECTED
            logger.error(f"Order {order_id} rejected due to data error: {e}")
            return

        if side == OrderSide.BUY:
            # You buy at the ask price + slippage
            execution_price = ask * (1 + self.slippage_pct)
            trade_value = execution_price * quantity
            commission = self._calculate_commission(trade_value)
            
            total_cost = trade_value + commission
            if self.cash < total_cost:
                self.orders[order_id]["status"] = OrderStatus.REJECTED
                logger.error(f"Order {order_id} rejected: Insufficient funds. Need {total_cost:.2f}, have {self.cash:.2f}")
                return
                
            self.cash -= total_cost
            self.positions[symbol] = self.positions.get(symbol, 0.0) + quantity
            
        else: # SELL
            # You sell at the bid price - slippage
            execution_price = bid * (1 - self.slippage_pct)
            trade_value = execution_price * quantity
            commission = self._calculate_commission(trade_value)
            
            current_pos = self.positions.get(symbol, 0.0)
            if current_pos < quantity:
                self.orders[order_id]["status"] = OrderStatus.REJECTED
                logger.error(f"Order {order_id} rejected: Insufficient position. Need {quantity}, have {current_pos}")
                return
                
            self.cash += (trade_value - commission)
            self.positions[symbol] -= quantity
            
        self.orders[order_id]["status"] = OrderStatus.FILLED
        self.orders[order_id]["execution_price"] = execution_price
        self.orders[order_id]["commission"] = commission
        
        logger.info(f"Order {order_id} FILLED: {side.value.upper()} {quantity} {symbol} @ {execution_price:.2f}. Comm: {commission:.2f}")

    def get_order_status(self, order_id: str) -> OrderStatus:
        if order_id not in self.orders:
            raise OrderExecutionError(f"Order {order_id} not found")
        return self.orders[order_id]["status"]
        
    def cancel_order(self, order_id: str) -> bool:
        if order_id not in self.orders:
            return False
        if self.orders[order_id]["status"] in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
            self.orders[order_id]["status"] = OrderStatus.CANCELLED
            return True
        return False
