from core.config import settings
from broker.base import BrokerInterface
from core.logger import get_logger
from datetime import date
from typing import Dict, Optional

logger = get_logger(__name__)


class RiskManager:
    """
    Gestión de riesgo real: drawdown máximo, stop-loss por posición y límite de pérdida diaria.
    """
    def __init__(self, broker: BrokerInterface):
        self.broker = broker
        self.peak_portfolio_value: float = settings.initial_capital
        self.daily_start_value: float = settings.initial_capital
        self.last_check_date: date = date.today()

        # Registro de precios de entrada para stop-loss
        self.entry_prices: Dict[str, float] = {}

        # Parámetros de riesgo (desde settings)
        self.stop_loss_pct: float = 0.015          # Stop-loss por posición: -1.5% (Evita ser liquidado por ruido)
        self.take_profit_pct: float = 0.005        # Take-profit por posición: +0.5% (Ganancias ultra rápidas/micro)
        self.max_drawdown_pct: float = settings.max_drawdown_percent       # -25% desde el pico
        self.max_daily_loss_pct: float = settings.max_daily_loss_percent   # -5% en el día

    # ------------------------------------------------------------------ helpers

    def get_portfolio_value(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        """Calcula el valor total del portafolio: efectivo + posiciones valoradas."""
        cash = self.broker.get_balance()
        positions = self.broker.get_positions()
        value = cash
        if current_prices:
            for sym, qty in positions.items():
                price = current_prices.get(sym, 0.0)
                value += qty * price
        return value

    def _update_peak_and_daily(self, portfolio_value: float):
        """Actualiza el valor pico y el valor de inicio del día."""
        if portfolio_value > self.peak_portfolio_value:
            self.peak_portfolio_value = portfolio_value

        today = date.today()
        if today != self.last_check_date:
            self.daily_start_value = portfolio_value
            self.last_check_date = today

    # ------------------------------------------------------------------ public metrics

    def get_drawdown(self, portfolio_value: float) -> float:
        """Drawdown actual como fracción negativa (ej. -0.05 = -5%)."""
        if self.peak_portfolio_value <= 0:
            return 0.0
        return (portfolio_value - self.peak_portfolio_value) / self.peak_portfolio_value

    def get_daily_pnl(self, portfolio_value: float) -> float:
        """P&L del día como fracción (ej. -0.03 = -3%)."""
        if self.daily_start_value <= 0:
            return 0.0
        return (portfolio_value - self.daily_start_value) / self.daily_start_value

    # ------------------------------------------------------------------ risk checks

    def check_trade_allowed(self, current_prices: Optional[Dict[str, float]] = None) -> bool:
        """
        Comprueba los límites de riesgo globales antes de permitir cualquier operación.
        Returns False si se supera el drawdown máximo o la pérdida diaria máxima.
        """
        portfolio_value = self.get_portfolio_value(current_prices)
        self._update_peak_and_daily(portfolio_value)

        # Límite de drawdown máximo
        drawdown = self.get_drawdown(portfolio_value)
        if drawdown < -self.max_drawdown_pct:
            logger.warning(
                f"Operación bloqueada: Drawdown máximo superado "
                f"({drawdown*100:.1f}% < -{self.max_drawdown_pct*100:.0f}%)"
            )
            return False

        # Límite de pérdida diaria
        daily_pnl = self.get_daily_pnl(portfolio_value)
        if daily_pnl < -self.max_daily_loss_pct:
            logger.warning(
                f"Operación bloqueada: Pérdida diaria máxima superada "
                f"({daily_pnl*100:.1f}% < -{self.max_daily_loss_pct*100:.0f}%)"
            )
            return False

        return True

    def should_stop_loss(self, symbol: str, current_price: float) -> bool:
        """
        Comprueba si una posición ha superado el nivel de stop-loss.
        Returns True si la pérdida supera self.stop_loss_pct (3%).
        """
        if symbol not in self.entry_prices:
            return False
        entry = self.entry_prices[symbol]
        loss_pct = (current_price - entry) / entry
        if loss_pct < -self.stop_loss_pct:
            logger.warning(
                f"Stop-loss activado en {symbol}: entrada={entry:.4f}, "
                f"actual={current_price:.4f}, pérdida={loss_pct*100:.1f}%"
            )
            return True
        return False

    def should_take_profit(self, symbol: str, current_price: float) -> bool:
        """
        Comprueba si una posición ha alcanzado el nivel de take-profit.
        Returns True si la ganancia supera self.take_profit_pct (2%).
        """
        if symbol not in self.entry_prices:
            return False
        entry = self.entry_prices[symbol]
        gain_pct = (current_price - entry) / entry
        if gain_pct >= self.take_profit_pct:
            logger.info(
                f"Take-profit activado en {symbol}: entrada={entry:.4f}, "
                f"actual={current_price:.4f}, ganancia={gain_pct*100:.1f}% ✅"
            )
            return True
        return False

    def register_entry(self, symbol: str, price: float):
        """Registra el precio de entrada para control de stop-loss."""
        self.entry_prices[symbol] = price
        logger.debug(f"Precio de entrada registrado: {symbol} @ {price:.4f}")

    def clear_entry(self, symbol: str):
        """Elimina el registro de entrada al cerrar una posición."""
        self.entry_prices.pop(symbol, None)

    # ------------------------------------------------------------------ sizing

    def calculate_position_size(self, symbol: str, price: float, confidence: float) -> float:
        """
        Kelly Criterion simplificado:
        tamaño = confianza × max_position_pct × saldo / precio
        """
        if price <= 0:
            return 0.0
        balance = self.broker.get_balance()
        max_investment = balance * settings.max_position_size_percent
        target_investment = max_investment * confidence  # confidence: 0.33 – 1.0
        return target_investment / price
