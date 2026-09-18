buy_signals = 1
sell_signals = 0
rsi_w = 0.0
macd_w = 0.0
vol_w = 0.0
consensus_ratio = max(buy_signals, sell_signals) / 3.0
intensity_score = rsi_w + macd_w + vol_w
confidence = min(1.0, (consensus_ratio * 0.5) + (intensity_score * 0.5))
print(f"consensus_ratio: {consensus_ratio}")
print(f"confidence: {confidence}")
print(f"Confianza %: {round(confidence * 100, 1)}")
