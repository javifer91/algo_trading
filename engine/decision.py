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
        price = self.data_provider.get_current_price(symbol)
        positions = self.broker.get_positions()
        
        # 1. Chequeo de Emergencia: Stop-Loss
        if symbol in positions and positions[symbol] > 0:
            if self.risk_manager.should_stop_loss(symbol, price):
                logger.info(f"{symbol}: Stop-Loss Triggered! Selling position.")
                self.broker.submit_order(symbol, OrderSide.SELL, OrderType.MARKET, positions[symbol])
                self.risk_manager.clear_entry(symbol)
                return  # Si vendemos por stop-loss, no evaluamos nuevas entradas

        # 2. Evaluación de estrategia normal
        signal: SignalType = self.signal_engine.evaluate(symbol, self.data_provider)
        
        if signal.signal == 0:
            logger.debug(f"{symbol}: HOLD. Reason: {signal.reason}")
            return
            
        if signal.signal == 1:
            quantity = self.risk_manager.calculate_position_size(symbol, price, signal.confidence)
            target_investment = quantity * price
            
            # Pasamos un dict temporal con el precio actual para que RiskManager evalúe el drawdown real
            if not self.risk_manager.check_trade_allowed({symbol: price}):
                logger.warning(f"{symbol}: Risk limits exceeded. Trade blocked.")
                return
                
            if not self.viability_filter.is_viable(symbol, signal.expected_return, target_investment):
                logger.warning(f"{symbol}: Trade is not viable due to costs/low expected return.")
                return
                
            logger.info(f"{symbol}: Decision BUY. Reason: {signal.reason}. Executing...")
            self.broker.submit_order(symbol, OrderSide.BUY, OrderType.MARKET, quantity)
            self.risk_manager.register_entry(symbol, price)
            
        elif signal.signal == -1:
            if symbol in positions and positions[symbol] > 0:
                quantity = positions[symbol]
                logger.info(f"{symbol}: Decision SELL (Close Position). Reason: {signal.reason}. Executing...")
                self.broker.submit_order(symbol, OrderSide.SELL, OrderType.MARKET, quantity)
                self.risk_manager.clear_entry(symbol)
            else:
                logger.debug(f"{symbol}: SELL signal ignored (no open position).")

