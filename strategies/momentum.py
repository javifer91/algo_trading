import pandas as pd
import numpy as np
from strategies.base import Strategy, SignalType
from datetime import datetime
from data.base import MarketDataProvider


class MultiIndicatorStrategy(Strategy):
    """
    Estrategia multi-indicador: RSI + MACD + Volumen.
    Requiere consenso de al menos 2/3 indicadores para generar una señal.
    El retorno esperado se calcula desde datos reales (no inventado).
    """
    def __init__(
        self,
        rsi_period: int = 14,
        rsi_buy_threshold: float = 45.0,   # RSI < 45 = sobreventa = COMPRA
        rsi_sell_threshold: float = 55.0,  # RSI > 55 = sobrecompra = VENTA
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal_period: int = 9,
        volume_period: int = 20
    ):
        super().__init__("MultiIndicator_RSI_MACD_Vol")
        self.rsi_period = rsi_period
        self.rsi_buy_threshold = rsi_buy_threshold
        self.rsi_sell_threshold = rsi_sell_threshold
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal_period = macd_signal_period
        self.volume_period = volume_period

    def _calculate_rsi(self, prices: pd.Series) -> float:
        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])

    def _calculate_macd(self, prices: pd.Series):
        ema_fast = prices.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = prices.ewm(span=self.macd_slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.macd_signal_period, adjust=False).mean()
        # Detectar tendencia en lugar de cruce exacto para más agilidad
        macd_cross_up = macd_line.iloc[-1] > signal_line.iloc[-1]
        macd_cross_down = macd_line.iloc[-1] < signal_line.iloc[-1]
        return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), macd_cross_up, macd_cross_down

    def generate_signal(self, symbol: str, data_provider: MarketDataProvider) -> SignalType:
        end_time = datetime.now()
        # Yahoo Finance: máximo 7 días para datos de 1 minuto
        start_time = end_time - pd.Timedelta(days=5)

        try:
            df = data_provider.get_historical_data(symbol, start_time, end_time, "1m")
        except Exception as e:
            return SignalType(
                symbol=symbol, signal=0, confidence=0.0,
                expected_return=0.0, expected_risk=0.0,
                reason=f"Error de datos: {e}"
            )

        min_rows = self.macd_slow + self.macd_signal_period + 5
        if len(df) < min_rows:
            return SignalType(
                symbol=symbol, signal=0, confidence=0.0,
                expected_return=0.0, expected_risk=0.0,
                reason="Datos insuficientes"
            )

        prices = df['close']
        volumes = df.get('volume', pd.Series(dtype=float))

        # --- RSI ---
        rsi = self._calculate_rsi(prices)
        rsi_buy  = rsi < self.rsi_buy_threshold
        rsi_sell = rsi > self.rsi_sell_threshold

        # --- MACD ---
        macd_val, signal_val, macd_cross_up, macd_cross_down = self._calculate_macd(prices)

        # --- Volúmen ---
        # Usamos el penúltimo tick porque Yahoo Finance devuelve el último minuto con vol=0
        vol_confirmed = False
        vol_ratio = 1.0
        if not volumes.empty and len(volumes) >= self.volume_period + 1:
            vol_avg = volumes.rolling(window=self.volume_period).mean().iloc[-2]
            current_vol = volumes.iloc[-2]  # penúltimo: ya consolidado
            vol_ratio = current_vol / vol_avg if vol_avg > 0 else 1.0
            vol_confirmed = vol_ratio > 1.0

        # --- Retorno esperado REAL escalado a horizonte de 60 minutos ---
        # Con velas de 1 minuto, el retorno por vela es muy pequeño.
        # Proyectamos a 60 minutos para que el filtro de viabilidad sea realista.
        minute_returns = prices.pct_change().dropna()
        positive_returns = minute_returns[minute_returns > 0].tail(60)
        expected_return_per_min = float(positive_returns.mean()) if len(positive_returns) > 0 else 0.0001
        expected_return = expected_return_per_min * 60  # proyección a ~1h de holding
        volatility = float(minute_returns.std())

        # --- Confianza CONTINUA por indicador (ponderada) ---
        # RSI: cuanto más alejado del centro (50), más convicción.
        # Compra: RSI < threshold (ej. 60) → score proporcional a (threshold - rsi) / threshold
        # Venta: RSI > threshold (ej. 40) → score proporcional a (rsi - threshold) / (100 - threshold)
        rsi_buy_score = max(0.0, (self.rsi_buy_threshold - rsi) / self.rsi_buy_threshold) if rsi_buy else 0.0
        rsi_sell_score = max(0.0, (rsi - self.rsi_sell_threshold) / (100.0 - self.rsi_sell_threshold)) if rsi_sell else 0.0

        # MACD: cuanto mayor la distancia entre la línea MACD y la señal, más convicción.
        macd_gap = abs(macd_val - signal_val)
        macd_norm = float(prices.std()) if float(prices.std()) > 0 else 1.0
        macd_score = min(1.0, macd_gap / macd_norm)  # normalizado por volatilidad

        # Volumen: cuanto más por encima de la media, más convicción (cap a ×3).
        vol_score = min(1.0, max(0.0, (vol_ratio - 1.0) / 2.0)) if vol_confirmed else 0.0

        # Pesos: RSI 40%, MACD 35%, Volumen 25%
        W_RSI, W_MACD, W_VOL = 0.40, 0.35, 0.25

        # Señal de dirección
        buy_signals = 0
        sell_signals = 0
        reasons = []

        if rsi_buy:
            buy_signals += 1
            reasons.append(f"RSI={rsi:.1f}↓({rsi_buy_score*100:.0f}%)")
        elif rsi_sell:
            sell_signals += 1
            reasons.append(f"RSI={rsi:.1f}↑({rsi_sell_score*100:.0f}%)")

        if macd_cross_up:
            buy_signals += 1
            reasons.append(f"MACD↑({macd_score*100:.0f}%)")
        elif macd_cross_down:
            sell_signals += 1
            reasons.append(f"MACD↓({macd_score*100:.0f}%)")

        if vol_confirmed:
            if buy_signals > sell_signals:
                buy_signals += 1
                reasons.append(f"Vol×{vol_ratio:.1f}({vol_score*100:.0f}%)")
            elif sell_signals > buy_signals:
                sell_signals += 1
                reasons.append(f"Vol×{vol_ratio:.1f}({vol_score*100:.0f}%)")

        reason_str = " | ".join(reasons) if reasons else "Sin señal clara"

        # Confianza continua: combina presencia (señales) con intensidad (scores)
        if buy_signals >= sell_signals:
            rsi_w = rsi_buy_score * W_RSI if rsi_buy else 0.0
            macd_w = macd_score * W_MACD if macd_cross_up else 0.0
            vol_w = vol_score * W_VOL if (vol_confirmed and buy_signals > sell_signals) else 0.0
            direction = 1
        else:
            rsi_w = rsi_sell_score * W_RSI if rsi_sell else 0.0
            macd_w = macd_score * W_MACD if macd_cross_down else 0.0
            vol_w = vol_score * W_VOL if (vol_confirmed and sell_signals > buy_signals) else 0.0
            direction = -1

        # Confianza base por consenso de indicadores + intensidad ponderada
        consensus_ratio = max(buy_signals, sell_signals) / 3.0
        intensity_score = rsi_w + macd_w + vol_w  # max ~1.0
        confidence = min(1.0, (consensus_ratio * 0.5) + (intensity_score * 0.5))

        # Guardar scores individuales en el objeto para el diagnóstico del dashboard
        extra = {
            "rsi_score": round((rsi_buy_score if rsi_buy else rsi_sell_score) * 100, 1),
            "macd_score": round(macd_score * 100, 1),
            "vol_score": round(vol_score * 100, 1),
            "rsi_val": round(rsi, 2),
            "macd_val": round(macd_val, 4),
            "signal_val": round(signal_val, 4),
            "vol_ratio": round(vol_ratio, 2),
        }

        if buy_signals >= 2:
            result = SignalType(
                symbol=symbol, signal=1, confidence=confidence,
                expected_return=expected_return, expected_risk=volatility,
                reason=f"COMPRA ({buy_signals}/3): {reason_str}"
            )
        elif sell_signals >= 2:
            result = SignalType(
                symbol=symbol, signal=-1, confidence=confidence,
                expected_return=expected_return, expected_risk=volatility,
                reason=f"VENTA ({sell_signals}/3): {reason_str}"
            )
        else:
            result = SignalType(
                symbol=symbol, signal=0, confidence=confidence,
                expected_return=0.0, expected_risk=volatility,
                reason=f"HOLD: {reason_str}"
            )

        # Adjuntar scores extra al objeto señal para el diagnóstico
        result.extra = extra
        return result
