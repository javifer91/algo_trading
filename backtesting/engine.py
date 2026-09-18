from datetime import datetime
from typing import List, Callable
from data.mock import MockMarketDataProvider
from broker.paper import PaperBroker
from core.logger import get_logger
import pandas as pd

logger = get_logger(__name__)

class BacktestEngine:
    """
    Core engine for simulating time passing and evaluating trading strategies.
    It feeds historical data step-by-step to the broker and the strategy.
    """
    def __init__(
        self,
        data_provider: MockMarketDataProvider,
        broker: PaperBroker,
        universe: List[str]
    ):
        self.data_provider = data_provider
        self.broker = broker
        self.universe = universe
        self.strategies: List[Callable] = []

    def add_strategy(self, strategy_func: Callable):
        """Adds a strategy callback that gets evaluated each step."""
        self.strategies.append(strategy_func)

    def run(self, start_time: datetime, end_time: datetime, step_delta: pd.Timedelta):
        """
        Runs the simulation loop from start_time to end_time, advancing by step_delta.
        """
        logger.info(f"Starting backtest from {start_time} to {end_time}")
        current_time = start_time
        
        while current_time <= end_time:
            # 1. Update Market Data State
            for symbol in self.universe:
                self.data_provider.advance_time(symbol, current_time)
                
            # 2. Evaluate Strategies
            for strategy in self.strategies:
                strategy(current_time)
                
            current_time += step_delta
            
        logger.info("Backtest completed.")
        logger.info(f"Final Balance: {self.broker.get_balance():.2f}")
        logger.info(f"Final Positions: {self.broker.get_positions()}")
