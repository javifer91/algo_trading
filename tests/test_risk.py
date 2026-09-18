import pytest
from portfolio.risk import RiskManager
from broker.paper import PaperBroker
from data.mock import MockMarketDataProvider
from core.config import settings

def test_risk_manager_position_sizing():
    # Setup
    data_provider = MockMarketDataProvider()
    broker = PaperBroker(initial_capital=50.0, data_provider=data_provider)
    risk_manager = RiskManager(broker)
    
    # 50 capital, 20% max pos size = 10 max investment
    # at 100% confidence, price=5
    # quantity should be 10 / 5 = 2
    
    quantity = risk_manager.calculate_position_size(symbol="TEST", price=5.0, confidence=1.0)
    assert quantity == 2.0
    
    # 50% confidence = 5 max investment
    # at price=5 -> quantity = 1
    quantity2 = risk_manager.calculate_position_size(symbol="TEST", price=5.0, confidence=0.5)
    assert quantity2 == 1.0
