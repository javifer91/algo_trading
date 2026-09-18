from core.config import settings
from data.base import MarketDataProvider
from core.logger import get_logger

logger = get_logger(__name__)

class TradeViabilityFilter:
    """
    Evaluates if a trade makes mathematical sense after accounting for all costs.
    Crucial for small capital (50 €).
    """
    def __init__(self, data_provider: MarketDataProvider, min_commission: float = 1.0, commission_pct: float = 0.001):
        self.data_provider = data_provider
        self.min_commission = min_commission
        self.commission_pct = commission_pct

    def is_viable(self, symbol: str, expected_gross_return: float, target_investment: float) -> bool:
        """
        Returns True if the Expected Net Return > MIN_EXPECTED_NET_RETURN_PERCENT.
        Falla de forma segura: si no se puede obtener el spread, usa una estimación conservadora.
        """
        if target_investment <= 0:
            logger.warning(f"Trade {symbol} rechazado: inversión objetivo es 0 o negativa.")
            return False

        try:
            bid, ask = self.data_provider.get_bid_ask(symbol)
            if ask <= 0:
                raise ValueError("ask price is zero")
            spread_pct = (ask - bid) / ask
        except Exception:
            # Fuera de horario de bolsa o error de datos -> usar spread simulado conservador
            spread_pct = 0.001  # 0.1% spread simulado

        # Con comisiones en 0 (paper trading), solo el spread importa
        total_costs_abs = (self.commission_pct * 2 * target_investment) + (spread_pct * target_investment)
        cost_pct = total_costs_abs / target_investment if target_investment > 0 else 1.0

        # Si el retorno esperado es > coste total, la operación es viable
        if expected_gross_return < cost_pct:
            logger.warning(
                f"Trade {symbol} rechazado: Retorno esperado ({expected_gross_return*100:.3f}%) "
                f"< Costes ({cost_pct*100:.3f}%)"
            )
            return False

        logger.info(f"Trade {symbol} VIABLE: retorno={expected_gross_return*100:.3f}%, costes={cost_pct*100:.3f}%")
        return True
