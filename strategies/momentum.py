import pandas as pd
import numpy as np
from strategies.base import Strategy, SignalType
from datetime import datetime
from data.base import MarketDataProvider


class MultiIndicatorStrategy(Strategy):
    """
    Estrategia multi-indicador: RSI + MACD + Volumen.
    - RSI (período 21) sobre velas de 1m para menor ruido.
    - MACD calculado sobre velas de 5m (resample) para mayor estabilidad.
    - Volumen: suma de los últimos 20 candles con volumen > 0 vs media histórica.
    - Requiere consenso ≥ 2/3 indicadores para generar señal.
    """
    def __init__(
        self,
        rsi_period: int = 21,
        rsi_buy_threshold: float = 45.0,   # RSI < 45 = sobreventa = COMPRA
        rsi_sell_threshold: float = 55.0,  # RSI > 55 = sobrecompra = VENTA
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal_period: int = 9,
        volume_window: int = 20,           # velas con vol>0 a comparar
        is_intense_mode: bool = False
    ):
        super().__init__("MultiIndicator_RSI_MACD_Vol")
        self.is_intense_mode = is_intense_mode
        self.rsi_period = rsi_period
        
        # En modo intenso relajamos el umbral para operar muchísimo más
        self.rsi_buy_threshold = 50.0 if is_intense_mode else rsi_buy_threshold
        self.rsi_sell_threshold = 50.0 if is_intense_mode else rsi_sell_threshold
        
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal_period = macd_signal_period
        self.volume_window = volume_window

    def _calculate_rsi(self, prices: pd.Series) -> float:
        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])

    def _calculate_macd(self, prices: pd.Series):
        """Calcula MACD sobre precios de 5m (resampleados de 1m) para evitar ruido."""
        # Resamplear a 5 minutos si el índice es DatetimeTzAware
        try:
            prices_5m = prices.resample("5min").last().dropna()
            if len(prices_5m) < self.macd_slow + self.macd_signal_period:
                prices_5m = prices  # fallback a 1m si hay pocas velas
        except Exception:
            prices_5m = prices

        ema_fast = prices_5m.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = prices_5m.ewm(span=self.macd_slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.macd_signal_period, adjust=False).mean()
        macd_cross_up = macd_line.iloc[-1] > signal_line.iloc[-1]
        macd_cross_down = macd_line.iloc[-1] < signal_line.iloc[-1]
        return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), macd_cross_up, macd_cross_down

    def _calculate_volume_ratio(self, volumes: pd.Series) -> float:
        """
        Yahoo Finance devuelve volumen 0 en la mayoría de velas de 1m para criptos.
        Solución: comparar la suma de los últimos N ticks con vol>0 vs la media histórica.
        Devuelve ratio: >1 significa volumen por encima de la media.
        """
        non_zero = volumes[volumes > 0]
        if len(non_zero) < self.volume_window * 2:
            return 1.0  # Sin datos suficientes → neutral

        # Media histórica: todos los no-cero salvo los últimos 'window'
        historical_mean = non_zero.iloc[:-self.volume_window].mean()
        recent_mean = non_zero.iloc[-self.volume_window:].mean()

        if historical_mean <= 0:
            return 1.0
        return float(recent_mean / historical_mean)

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

        min_rows = self.macd_slow + self.macd_signal_period + self.rsi_period + 5
        if len(df) < min_rows:
            return SignalType(
                symbol=symbol, signal=0, confidence=0.0,
                expected_return=0.0, expected_risk=0.0,
                reason="Datos insuficientes"
            )

        prices = df['close']
        volumes = df.get('volume', pd.Series(dtype=float))

        # --- RSI (período 21 para menor ruido en 1m) ---
        rsi = self._calculate_rsi(prices)
        rsi_buy  = rsi < self.rsi_buy_threshold
        rsi_sell = rsi > self.rsi_sell_threshold

        # --- MACD (sobre velas de 5m resampladas) ---
        macd_val, signal_val, macd_cross_up, macd_cross_down = self._calculate_macd(prices)

        # --- Volumen (robusto ante velas con 0) ---
        vol_ratio = self._calculate_volume_ratio(volumes)
        vol_confirmed = vol_ratio > 1.1  # umbral ligeramente por encima del 100% de media

        # --- Retorno esperado ---
        # Usamos la volatilidad media de los últimos 60 minutos como retorno potencial.
        # Esto asegura que el filtro de viabilidad siempre recibe un valor positivo y realista.
        minute_returns = prices.pct_change().dropna()
        volatility_60m = float(minute_returns.tail(60).abs().mean())  # media de movimientos absolutos
        # El retorno esperado es conservador: la mitad de la volatilidad reciente (esperamos capturar el 50%)
        expected_return = max(volatility_60m * 30, 0.002)  # mínimo 0.2% para superar el spread
        volatility = float(minute_returns.std())

        # --- Scores continuos por indicador ---
        # RSI: (distancia al umbral) / umbral → 0% en el límite, 100% en el extremo
        rsi_buy_score  = max(0.0, (self.rsi_buy_threshold - rsi) / self.rsi_buy_threshold) if rsi_buy else 0.0
        rsi_sell_score = max(0.0, (rsi - self.rsi_sell_threshold) / (100.0 - self.rsi_sell_threshold)) if rsi_sell else 0.0

        # MACD: distancia MACD-señal normalizada por el ATR (average true range proxy)
        macd_gap = abs(macd_val - signal_val)
        atr_proxy = float(prices.tail(60).diff().abs().mean()) if len(prices) >= 60 else float(prices.std())
        macd_norm = atr_proxy if atr_proxy > 0 else 1.0
        macd_score = min(1.0, macd_gap / macd_norm)

        # Volumen: cuánto por encima de la media histórica (cap ×3)
        vol_score = min(1.0, max(0.0, (vol_ratio - 1.0) / 2.0)) if vol_confirmed else 0.0

        # Pesos: RSI 40%, MACD 35%, Volumen 25%
        W_RSI, W_MACD, W_VOL = 0.40, 0.35, 0.25

        # --- Conteo de señales de dirección ---
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

        # --- Confianza: 50% Consenso + 50% Intensidad ---
        if buy_signals >= sell_signals:
            rsi_w = rsi_buy_score * W_RSI if rsi_buy else 0.0
            macd_w = macd_score * W_MACD if macd_cross_up else 0.0
            vol_w = vol_score * W_VOL if (vol_confirmed and buy_signals > sell_signals) else 0.0
        else:
            rsi_w = rsi_sell_score * W_RSI if rsi_sell else 0.0
            macd_w = macd_score * W_MACD if macd_cross_down else 0.0
            vol_w = vol_score * W_VOL if (vol_confirmed and sell_signals > buy_signals) else 0.0

        consensus_ratio = max(buy_signals, sell_signals) / 3.0
        intensity_score = rsi_w + macd_w + vol_w
        confidence = min(1.0, (consensus_ratio * 0.5) + (intensity_score * 0.5))

        # Guardar métricas extra para el dashboard
        extra = {
            "rsi_score": round((rsi_buy_score if rsi_buy else rsi_sell_score) * 100, 1),
            "macd_score": round(macd_score * 100, 1),
            "vol_score": round(vol_score * 100, 1),
            "rsi_val": round(rsi, 2),
            "macd_val": round(macd_val, 4),
            "signal_val": round(signal_val, 4),
            "vol_ratio": round(vol_ratio, 2),
        }

        # En modo intenso requerimos menos confirmación (1/3 o 2/3) para disparar rápido
        required_signals = 1 if self.is_intense_mode else 2

        if buy_signals >= required_signals and buy_signals > sell_signals:
            result = SignalType(
                symbol=symbol, signal=1, confidence=confidence,
                expected_return=expected_return, expected_risk=volatility,
                reason=f"COMPRA ({buy_signals}/3): {reason_str}"
            )
        elif sell_signals >= required_signals and sell_signals > buy_signals:
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

        result.extra = extra
        return result
