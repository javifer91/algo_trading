from enum import Enum
from pydantic_settings import BaseSettings, SettingsConfigDict

class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"

class TimeHorizon(str, Enum):
    INTRADAY = "intraday"
    SHORT_TERM = "short_term"
    SWING = "swing"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"

class Settings(BaseSettings):
    # General
    initial_capital: float = 50.0
    base_currency: str = "EUR"

    # Trading Mode
    trading_mode: TradingMode = TradingMode.PAPER
    live_trading_enabled: bool = False
    safe_mode_enabled: bool = False
    emergency_stop: bool = False

    # Broker & Data
    broker_name: str = "mock_broker"
    data_provider: str = "yfinance" # mock | yfinance | kraken

    # Time Horizon
    time_horizon: TimeHorizon = TimeHorizon.SWING
    market_refresh_seconds: int = 5

    # Risk Management
    max_position_size_percent: float = 0.20
    max_daily_loss_percent: float = 0.05
    max_monthly_loss_percent: float = 0.15
    max_drawdown_percent: float = 0.25

    # Profitability Filter
    min_expected_net_return_percent: float = 0.005
    max_transaction_cost_percent: float = 0.05

    # Advanced Features
    enable_ml: bool = False
    enable_short: bool = False
    enable_leverage: bool = False

    # Database
    database_url: str = "sqlite:///algotrading.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
