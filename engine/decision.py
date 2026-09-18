from strategies.base import SignalEngine, SignalType
from portfolio.risk import RiskManager
from engine.filter import TradeViabilityFilter
from broker.base import BrokerInterface, OrderSide, OrderType
from data.base import MarketDataProvider
from core.logger import get_logger

logger = get_logger(__name__)

class DecisionEngine:
    """
    Coordinates Signal generation, Risk Management, and Viability Filtering
    to make the final trading decision.
    """
    def __init__(
        self, 
        signal_engine: SignalEngine, 
        risk_manager: RiskManager, 
        viability_filter: TradeViabilityFilter,
        broker: BrokerInterface,
        data_provider: MarketDataProvider
    ):
        self.signal_engine = signal_engine
        self.risk_manager = risk_manager
        self.viability_filter = viability_filter
        self.broker = broker
        self.data_provider = data_provider

    def evaluate_and_execute(self, symbol: str):
        signal: SignalType = self.signal_engine.evaluate(symbol, self.data_provider)
        
        if signal.signal == 0:
            logger.debug(f"{symbol}: HOLD. Reason: {signal.reason}")
            return
            
        price = self.data_provider.get_current_price(symbol)
        
        if signal.signal == 1:
            quantity = self.risk_manager.calculate_position_size(symbol, price, signal.confidence)
            target_investment = quantity * price
            
            if not self.risk_manager.check_trade_allowed():
                logger.warning(f"{symbol}: Risk limits exceeded. Trade blocked.")
                return
                
            if not self.viability_filter.is_viable(symbol, signal.expected_return, target_investment):
                logger.warning(f"{symbol}: Trade is not viable due to costs/low expected return.")
                return
                
            logger.info(f"{symbol}: Decision BUY. Reason: {signal.reason}. Executing...")
            self.broker.submit_order(symbol, OrderSide.BUY, OrderType.MARKET, quantity)
            
        elif signal.signal == -1:
            # We are not allowing short selling by default (ENABLE_SHORT=false)
            # So a SELL signal is only for closing existing positions
            positions = self.broker.get_positions()
            if symbol in positions and positions[symbol] > 0:
                quantity = positions[symbol]
                logger.info(f"{symbol}: Decision SELL (Close Position). Reason: {signal.reason}. Executing...")
                self.broker.submit_order(symbol, OrderSide.SELL, OrderType.MARKET, quantity)
            else:
                logger.debug(f"{symbol}: SELL signal ignored (no open position).")
