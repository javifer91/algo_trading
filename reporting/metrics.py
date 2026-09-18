from typing import List, Dict, Any
import pandas as pd
import numpy as np

def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    if len(returns) < 2 or returns.std() == 0:
        return 0.0
    excess_returns = returns - risk_free_rate
    # assuming daily returns
    return np.sqrt(252) * excess_returns.mean() / excess_returns.std()

def calculate_max_drawdown(portfolio_values: pd.Series) -> float:
    if len(portfolio_values) == 0:
        return 0.0
    rolling_max = portfolio_values.cummax()
    drawdown = (portfolio_values - rolling_max) / rolling_max
    return drawdown.min()

class MetricsGenerator:
    def __init__(self, trades: List[Dict[str, Any]], daily_portfolio_values: pd.Series):
        self.trades = trades
        self.daily_portfolio_values = daily_portfolio_values

    def get_summary(self) -> Dict[str, Any]:
        num_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t.get('net_pnl', 0) > 0]
        win_rate = len(winning_trades) / num_trades if num_trades > 0 else 0.0
        
        gross_pnl = sum(t.get('gross_pnl', 0) for t in self.trades)
        total_costs = sum(t.get('commission_paid', 0) + t.get('spread_cost', 0) + t.get('slippage_cost', 0) for t in self.trades)
        net_pnl = sum(t.get('net_pnl', 0) for t in self.trades)
        
        returns = self.daily_portfolio_values.pct_change().dropna()
        sharpe = calculate_sharpe_ratio(returns)
        max_dd = calculate_max_drawdown(self.daily_portfolio_values)
        
        return {
            "num_trades": num_trades,
            "win_rate": win_rate,
            "gross_pnl": gross_pnl,
            "total_costs": total_costs,
            "net_pnl": net_pnl,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd
        }
