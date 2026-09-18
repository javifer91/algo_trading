class AlgoTradingError(Exception):
    """Base class for all AlgoTrading exceptions."""
    pass

class DataError(AlgoTradingError):
    """Raised when there's an issue with market data (stale, missing, incorrect)."""
    pass

class BrokerError(AlgoTradingError):
    """Raised when the broker API fails or returns unexpected results."""
    pass

class OrderExecutionError(BrokerError):
    """Raised when an order fails to execute properly."""
    pass

class RiskLimitExceededError(AlgoTradingError):
    """Raised when a proposed trade violates risk management limits."""
    pass

class ConfigurationError(AlgoTradingError):
    """Raised when there's a configuration mismatch or missing setting."""
    pass

class SafeModeActiveError(AlgoTradingError):
    """Raised when an action is blocked because Safe Mode is active."""
    pass

class EmergencyStopActiveError(AlgoTradingError):
    """Raised when an action is blocked because Emergency Stop is active."""
    pass
