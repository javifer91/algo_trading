from datetime import datetime
from broker.base import BrokerInterface
from reporting.metrics import MetricsGenerator
from core.config import settings

class DailyReportGenerator:
    def __init__(self, broker: BrokerInterface, metrics: MetricsGenerator):
        self.broker = broker
        self.metrics = metrics

    def generate_markdown(self) -> str:
        summary = self.metrics.get_summary()
        balance = self.broker.get_balance()
        positions = self.broker.get_positions()
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        md = f"""# DAILY INVESTMENT REPORT - {date_str}

## Capital & Portfolio
- **Initial Capital**: {settings.initial_capital:.2f} {settings.base_currency}
- **Current Cash**: {balance:.2f} {settings.base_currency}
- **Positions**: {positions}

## Performance
- **Gross P&L**: {summary['gross_pnl']:.2f}
- **Trading Costs**: {summary['total_costs']:.2f}
- **Net P&L**: {summary['net_pnl']:.2f}
- **Win Rate**: {summary['win_rate']*100:.1f}% ({summary['num_trades']} trades)

## Risk
- **Max Drawdown**: {summary['max_drawdown']*100:.2f}%
- **Sharpe Ratio**: {summary['sharpe_ratio']:.2f}

## System Status
- **Trading Mode**: {settings.trading_mode.value.upper()}
- **Safe Mode**: {"ON" if settings.safe_mode_enabled else "OFF"}
- **Emergency Stop**: {"ON" if settings.emergency_stop else "OFF"}
"""
        return md
