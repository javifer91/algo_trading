import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os
import time

# Add parent path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import settings
from broker.paper import PaperBroker
from data.yfinance_provider import YFinanceDataProvider
from strategies.base import SignalEngine
from strategies.momentum import MultiIndicatorStrategy
from portfolio.risk import RiskManager
from engine.filter import TradeViabilityFilter
from engine.decision import DecisionEngine

st.set_page_config(page_title="Panel de AlgoTrading en Vivo", layout="wide", page_icon="📈")
st.title("📈 Panel de AlgoTrading (Datos Reales)")

# Versión de la app: actualizar cuando cambia la lógica del motor para forzar reinicio
APP_VERSION = "v16"

# --- SELECCIÓN DE ACTIVO ---
st.sidebar.header("Configuración de Activo")
selected_option = st.sidebar.radio(
    "Selecciona en qué invertir:",
    [
        "SPY (S&P 500 - Horario Bolsa EE.UU.)",
        "ETH-USD (Ethereum - 24/7)",
        "DOGE-USD (Dogecoin Meme - 24/7)",
        "GC=F (Oro - Futuros 23h/día)",
        "BZ=F (Petróleo Brent - Futuros 23h/día)",
    ]
)

SYMBOL_MAP = {
    "SPY (S&P 500 - Horario Bolsa EE.UU.)": "SPY",
    "ETH-USD (Ethereum - 24/7)": "ETH-USD",
    "DOGE-USD (Dogecoin Meme - 24/7)": "DOGE-USD",
    "GC=F (Oro - Futuros 23h/día)": "GC=F",
    "BZ=F (Petróleo Brent - Futuros 23h/día)": "BZ=F",
}
SYMBOL = SYMBOL_MAP[selected_option]

st.sidebar.markdown("---")
st.sidebar.header("Estilo de Trading")
intense_mode = st.sidebar.toggle("🔥 Scalping Intenso (x10 Margen)", value=False, help="Aplica apalancamiento financiero x10 y relaja los indicadores para operar de forma continua y muy agresiva.")

# Reiniciar estado si se cambia de activo, de modo O si la versión de la app ha cambiado
if (
    "current_symbol" not in st.session_state
    or st.session_state.current_symbol != SYMBOL
    or st.session_state.get("app_version") != APP_VERSION
    or st.session_state.get("intense_mode") != intense_mode
):
    st.session_state.current_symbol = SYMBOL
    st.session_state.app_version = APP_VERSION
    st.session_state.intense_mode = intense_mode
    st.session_state.engine_initialized = False
    st.session_state.is_running = False

# --- INICIALIZACIÓN DEL ESTADO ---
if not st.session_state.get("engine_initialized", False):
    # 1. Configurar Proveedor de Datos Reales (YFinance)
    st.session_state.data_provider = YFinanceDataProvider()
    
    # Descargar datos históricos reales en temporalidad de 1 minuto para mayor agilidad
    end_time = datetime.now()
    start_time = end_time - pd.Timedelta(days=5)
    try:
        df_real = st.session_state.data_provider.get_historical_data(SYMBOL, start_time, end_time, "1m")
    except Exception as e:
        st.error(f"Error cargando datos de YFinance: {e}")
        st.stop()
        
    st.session_state.real_history = df_real
    
    # Parchear get_historical_data para usar nuestro caché y no bloquearnos
    def cached_historical(symbol, start, end, timeframe):
        return st.session_state.real_history
    st.session_state.data_provider.get_historical_data = cached_historical
    
    # 2. Configurar Broker (sin comisiones para paper trading micro-capital)
    intense = st.session_state.get("intense_mode", False)
    leverage_val = 10.0 if intense else 1.0
    
    st.session_state.broker = PaperBroker(
        settings.initial_capital,
        st.session_state.data_provider,
        commission_pct=0.001,  # 0.1% por operación (realista para cripto)
        min_commission=0.0,    # Sin mínimo para micro-capital
        slippage_pct=0.0005,
        leverage=leverage_val
    )
    
    # Estrategia Multi-Indicador (RSI, MACD, Vol)
    multi_strategy = MultiIndicatorStrategy(is_intense_mode=intense)
    st.session_state.strategy = SignalEngine([multi_strategy])
    st.session_state.risk = RiskManager(st.session_state.broker, leverage=leverage_val)
    
    # Comisiones en 0 para que cualquier mínima ganancia esperada pase el filtro y veamos acción
    st.session_state.filter = TradeViabilityFilter(st.session_state.data_provider, min_commission=0.0, commission_pct=0.0)
    
    # 3. Motor
    st.session_state.engine = DecisionEngine(
        st.session_state.strategy,
        st.session_state.risk,
        st.session_state.filter,
        st.session_state.broker,
        st.session_state.data_provider
    )
    
    st.session_state.portfolio_history = [{"Fecha": datetime.now(), "Valor": settings.initial_capital}]
    st.session_state.confidence_history = []  # historial de confianza por tick
    st.session_state.is_running = False
    st.session_state.engine_initialized = True

# --- INTERFAZ LATERAL ---
st.sidebar.markdown("---")
st.sidebar.header("Control de Simulación")
if st.sidebar.button("▶️ Iniciar / ⏸️ Pausar"):
    st.session_state.is_running = not st.session_state.is_running

st.sidebar.write(f"**Estado:** {'Corriendo 🟢' if st.session_state.is_running else 'Pausado 🔴'}")
st.sidebar.write(f"**Activo:** {SYMBOL} (Datos Reales)")
st.sidebar.write(f"**Capital Inicial:** {settings.initial_capital} {settings.base_currency}")

# --- LÓGICA DE SIMULACIÓN (TICK) ---
if st.session_state.is_running:
    try:
        # 1. Obtener precio real actual
        current_price = st.session_state.data_provider.get_current_price(SYMBOL)
        
        # Actualizar histórico en memoria: añadir nueva vela con el precio actual
        # y recortar para no crecer indefinidamente
        df_hist = st.session_state.real_history
        new_date = pd.Timestamp.now()
        new_row = pd.DataFrame(
            {'open': [current_price], 'high': [current_price], 'low': [current_price],
             'close': [current_price], 'volume': [0]},
            index=[new_date]
        )
        st.session_state.real_history = pd.concat([df_hist, new_row]).tail(3000)
        
        # 2. Evaluar señal directamente para mostrar diagnóstico
        raw_signal = st.session_state.strategy.evaluate(SYMBOL, st.session_state.data_provider)
        st.session_state.last_signal = raw_signal
        
        # Verificar riesgo
        risk_ok = st.session_state.risk.check_trade_allowed({SYMBOL: current_price})
        st.session_state.last_risk_ok = risk_ok
        
        # Calcular cantidad y viabilidad si hay señal de compra
        if raw_signal.signal == 1:
            qty = st.session_state.risk.calculate_position_size(SYMBOL, current_price, raw_signal.confidence)
            target_inv = qty * current_price
            viable = st.session_state.filter.is_viable(SYMBOL, raw_signal.expected_return, target_inv)
            st.session_state.last_viable = viable
            st.session_state.last_target_inv = target_inv
        else:
            st.session_state.last_viable = None
            st.session_state.last_target_inv = 0
        
        # 3. Ejecutar el motor
        st.session_state.engine.evaluate_and_execute(SYMBOL)
        
        # 4. Registrar valor REAL del portafolio (margen + PnL no realizado)
        cash_now = st.session_state.broker.get_balance()
        positions_now = st.session_state.broker.get_positions()
        portfolio_value_tick = cash_now
        for sym, qty in positions_now.items():
            if qty > 0:
                avg_e = st.session_state.broker.avg_entry.get(sym, current_price)
                unrealized = (current_price - avg_e) * qty
                margin_held = st.session_state.broker.margins.get(sym, 0.0)
                portfolio_value_tick += margin_held + unrealized
            
        st.session_state.portfolio_history.append({
            "Fecha": datetime.now(),
            "Valor": portfolio_value_tick
        })
        # Guardar historial de confianza (últimos 200 ticks)
        extra_dict = getattr(raw_signal, "extra", {})
        st.session_state.confidence_history.append({
            "Fecha": datetime.now(),
            "Confianza %": round(raw_signal.confidence * 100, 1),
            "Señal": {1: "COMPRA", -1: "VENTA", 0: "HOLD"}.get(raw_signal.signal, "?"),
            "RSI Score %": round(extra_dict.get("rsi_score", 0), 1),
            "MACD Score %": round(extra_dict.get("macd_score", 0), 1),
            "Vol Score %": round(extra_dict.get("vol_score", 0), 1),
        })
        if len(st.session_state.confidence_history) > 200:
            st.session_state.confidence_history = st.session_state.confidence_history[-200:]
    except Exception as e:
        st.error(f"Error en tick de simulación: {e}")
        st.session_state.is_running = False
    
# --- RENDERIZADO DE DATOS ---
broker = st.session_state.broker
cash = broker.get_balance()
positions = broker.get_positions()
portfolio_value = cash
current_price = 0
try:
    current_price = st.session_state.data_provider.get_current_price(SYMBOL)
except:
    pass

for sym, qty in positions.items():
    if qty > 0:
        # PnL no realizado
        avg_entry = broker.avg_entry.get(sym, current_price)
        unrealized_pnl = (current_price - avg_entry) * qty
        # Margen retenido
        margin = broker.margins.get(sym, 0.0)
        # Sumar margen devuelto + beneficios
        portfolio_value += margin + unrealized_pnl

net_profit = portfolio_value - settings.initial_capital
total_trades = len(broker.orders)

# Calcular Win Rate y Comisiones Totales
total_commissions = sum(details.get("commission", 0.0) for details in broker.orders.values())
sell_orders = [details for details in broker.orders.values() if details["side"].value.lower() == "sell" and details["status"].value.lower() == "filled"]
winning_trades = sum(1 for details in sell_orders if details.get("net_pnl", 0) > 0)
win_rate = (winning_trades / len(sell_orders)) if sell_orders else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Valor del Portafolio", f"{portfolio_value:.2f} {settings.base_currency}", f"{net_profit:.2f} {settings.base_currency}")
col2.metric(f"Precio Actual {SYMBOL}", f"${current_price:.2f}")

# Calcular métricas de riesgo
current_prices_dict = {SYMBOL: current_price} if current_price else {}
drawdown = st.session_state.risk.get_drawdown(portfolio_value)
daily_pnl = st.session_state.risk.get_daily_pnl(portfolio_value)

col3.metric("Drawdown Máximo", f"{drawdown*100:.2f}%", delta_color="inverse")
col4.metric("P&L Diario", f"{daily_pnl*100:.2f}%")

st.markdown("---")
col_pos, col_trades, col_winrate, col_comm = st.columns(4)
if positions:
    pos_str = ", ".join([f"{qty:.4f} {sym}" for sym, qty in positions.items()])
else:
    pos_str = "Ninguna"
col_pos.metric("Posiciones Abiertas", pos_str)
col_trades.metric("Órdenes Registradas", str(total_trades))
col_winrate.metric("Tasa de Acierto (Win Rate)", f"{win_rate*100:.1f}%")
col_comm.metric("Comisiones Pagadas", f"{total_commissions:.2f} {settings.base_currency}")

st.subheader("Curva de Capital del Portafolio")
if len(st.session_state.portfolio_history) > 0:
    df_chart = pd.DataFrame(st.session_state.portfolio_history).set_index("Fecha")
    st.line_chart(df_chart)

st.subheader("Órdenes y Operaciones")
if broker.orders:
    LADO_ES = {"buy": "COMPRA", "sell": "VENTA"}
    ESTADO_ES = {"pending": "PENDIENTE", "submitted": "ENVIADA", "filled": "EJECUTADA", "rejected": "RECHAZADA", "cancelled": "CANCELADA"}
    
    # Reconstruir historial de saldo acumulado operación a operación
    running_balance = settings.initial_capital
    orders_list = []
    for oid, details in broker.orders.items():
        lado_raw = details["side"].value.lower()
        estado_raw = details["status"].value.lower()
        net_pnl = details.get("net_pnl", None)
        
        # Actualizar saldo acumulado
        if lado_raw == "sell" and estado_raw == "filled" and net_pnl is not None:
            running_balance += net_pnl
        
        orders_list.append({
            "id": oid[:8],
            "symbol": details["symbol"],
            "lado": LADO_ES.get(lado_raw, lado_raw.upper()),
            "motivo": details.get("reason", "-"),
            "estado": ESTADO_ES.get(estado_raw, estado_raw.upper()),
            "cantidad": f"{details['quantity']:.6f}",
            "precio": f"${details.get('execution_price', 0):.4f}" if details.get('execution_price') else "-",
            "comision": f"{details.get('commission', 0):.4f}€" if details.get('commission') is not None else "-",
            "net_pnl": net_pnl,
            "balance": running_balance if lado_raw == "sell" else None
        })
    
    # Renderizar tabla HTML con colores
    table_rows = ""
    for row in reversed(orders_list):
        net_pnl = row["net_pnl"]
        balance = row["balance"]
        
        if net_pnl is not None:
            if net_pnl > 0:
                pnl_html = f'<td style="color:#00c853;font-weight:bold">+{net_pnl:.4f}€ ✅</td>'
            else:
                pnl_html = f'<td style="color:#ff1744;font-weight:bold">{net_pnl:.4f}€ 🛑</td>'
        else:
            pnl_html = '<td style="color:#888">-</td>'
        
        if balance is not None:
            if balance >= settings.initial_capital:
                bal_html = f'<td style="color:#00c853;font-weight:bold">{balance:.2f}€</td>'
            else:
                bal_html = f'<td style="color:#ff1744;font-weight:bold">{balance:.2f}€</td>'
        else:
            bal_html = '<td style="color:#888">-</td>'
        
        if row["lado"] == "COMPRA":
            lado_html = f'<td style="color:#42a5f5;font-weight:bold">📈 {row["lado"]}</td>'
        else:
            lado_html = f'<td style="color:#ef5350;font-weight:bold">📉 {row["lado"]}</td>'
        
        table_rows += f"""
        <tr>
            <td style="font-family:monospace;font-size:0.85em;color:#aaa">{row['id']}</td>
            <td style="font-weight:bold">{row['symbol']}</td>
            {lado_html}
            <td>{row['motivo']}</td>
            <td style="color:#aaa">{row['estado']}</td>
            <td style="font-family:monospace">{row['cantidad']}</td>
            <td style="font-family:monospace">{row['precio']}</td>
            <td style="color:#ff9800">{row['comision']}</td>
            {pnl_html}
            {bal_html}
        </tr>"""
    
    st.markdown(f"""
    <div style="overflow-x:auto">
    <table style="width:100%;border-collapse:collapse;font-size:0.9em">
        <thead>
            <tr style="border-bottom:2px solid #444;text-align:left">
                <th>ID</th><th>S&iacute;mbolo</th><th>Lado</th><th>Motivo</th>
                <th>Estado</th><th>Cantidad</th><th>Precio Ejec.</th>
                <th>Comisi&oacute;n</th><th>Beneficio Neto</th><th>Balance Acum.</th>
            </tr>
        </thead>
        <tbody>
        {table_rows}
        </tbody>
    </table>
    </div>
    """, unsafe_allow_html=True)
else:
    st.info("Aún no hay operaciones. Revisa el diagnóstico de abajo para ver qué está evaluando el bot.")

# --- EXPLICACIÓN DE CÁLCULO DE CONFIANZA ---
st.markdown("---")
st.subheader("📐 ¿Cómo se calcula la Confianza del Algoritmo?")

with st.container(border=True):
    st.markdown("""
    La **Confianza (0% a 100%)** del algoritmo no es un número arbitrario. Se calcula combinando la **unanimidad** de las señales con la **intensidad** del movimiento del mercado mediante esta fórmula:

    $$\\text{Confianza Total} = (50\\% \\times \\text{Consenso}) + (50\\% \\times \\text{Intensidad Ponderada})$$
    """)

    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        st.markdown("""
        #### 1️⃣ Consenso de Indicadores (50% de la Confianza)
        Mide cuántos de los 3 indicadores (RSI, MACD y Volumen) concuerdan en la misma dirección:
        * **3 de 3 coinciden:** Consenso = **100%**
        * **2 de 3 coinciden:** Consenso = **66.7%**
        * **1 de 3 coinciden:** Consenso = **33.3%**
        * **0 coinciden:** Consenso = **0%**

        > **🛡️ Regla de Seguridad:** Se exige un **consenso mínimo de 66.7% (2/3)** para permitir cualquier operación. Si es menor, la señal se fuerza a **HOLD / ESPERA**.
        """)

    with col_exp2:
        st.markdown("""
        #### 2️⃣ Intensidad Ponderada (50% de la Confianza)
        Mide la convicción individual de cada indicador favorable:
        * 📈 **RSI (Peso 40%):** Mide la distancia respecto a la zona neutra. Cuanto más cerca del extremo (sobrecompra/sobreventa), mayor es la puntuación (hasta 100%).
        * 📊 **MACD (Peso 35%):** Mide el tamaño del *gap* entre la línea MACD y su línea de Señal respecto a la volatilidad reciente.
        * 📉 **Volumen (Peso 25%):** Ratio entre el volumen del tick actual y la media móvil de 20 periodos ($Vol_{actual} / Vol_{media20}$).
        """)

# --- PANEL DE DIAGNÓSTICO EN TIEMPO REAL ---
st.subheader("🔎 Diagnóstico del Motor (Tiempo Real)")

if st.session_state.get("last_signal"):
    sig = st.session_state.last_signal
    SIGNAL_ICONS = {1: "🟢 COMPRA", -1: "🔴 VENTA", 0: "⏸️ ESPERA (HOLD)"}
    sig_icon = SIGNAL_ICONS.get(sig.signal, "?")

    # --- Métricas actuales ---
    dcol1, dcol2, dcol3 = st.columns(3)
    dcol1.metric("Señal Actual", sig_icon)
    dcol1.caption(f"**Razón:** {sig.reason}")

    dcol2.metric("Confianza Total", f"{sig.confidence*100:.1f}%")
    dcol2.metric("Retorno Esp.", f"{sig.expected_return*100:.3f}%")

    risk_ok = st.session_state.get("last_risk_ok", None)
    viable = st.session_state.get("last_viable", None)
    target_inv = st.session_state.get("last_target_inv", 0)

    with dcol3:
        if risk_ok is not None:
            st.write(f"**Riesgo OK:** {'✅ Sí' if risk_ok else '❌ Bloqueado'}")
        if viable is not None:
            st.write(f"**Viable:** {'✅ Sí' if viable else '❌ Bloqueado'}")
        if target_inv > 0:
            st.write(f"**Inversión objetivo:** {target_inv:.4f} {settings.base_currency}")

        # Mostrar niveles de Stop-Loss / Take-Profit para la posición abierta
        risk_mgr = st.session_state.risk
        positions_now = st.session_state.broker.get_positions()
        if SYMBOL in positions_now and SYMBOL in risk_mgr.entry_prices:
            entry_p = risk_mgr.entry_prices[SYMBOL]
            sl_level = entry_p * (1 - risk_mgr.stop_loss_pct)
            tp_level = entry_p * (1 + risk_mgr.take_profit_pct)
            st.markdown("---")
            st.write(f"**Precio entrada:** ${entry_p:.4f}")
            st.write(f"**🛑 Stop-Loss:** ${sl_level:.4f} (-{risk_mgr.stop_loss_pct*100:.0f}%)")
            st.write(f"**✅ Take-Profit:** ${tp_level:.4f} (+{risk_mgr.take_profit_pct*100:.0f}%)")


    # --- Barras de intensidad por indicador ---
    st.markdown("#### Intensidad de cada indicador (ciclo actual)")
    icol1, icol2, icol3 = st.columns(3)
    sig_extra = getattr(sig, "extra", {})
    rsi_score = sig_extra.get("rsi_score", None)
    macd_score = sig_extra.get("macd_score", None)
    vol_score = sig_extra.get("vol_score", None)
    rsi_val = sig_extra.get("rsi_val", None)
    vol_ratio = sig_extra.get("vol_ratio", None)

    with icol1:
        st.markdown("**RSI (peso 40%)**")
        if rsi_val is not None:
            st.caption(f"Valor RSI: {rsi_val:.2f} | Umbral compra: <{sig.__class__.__mro__[0].__init__.__defaults__ and 60}")
        if rsi_score is not None:
            st.progress(min(1.0, rsi_score / 100), text=f"{rsi_score:.1f}%")

    with icol2:
        st.markdown("**MACD (peso 35%)**")
        macd_v = sig_extra.get("macd_val", None)
        sig_v = sig_extra.get("signal_val", None)
        if macd_v is not None and sig_v is not None:
            st.caption(f"MACD: {macd_v:.4f} | Señal: {sig_v:.4f}")
        if macd_score is not None:
            st.progress(min(1.0, macd_score / 100), text=f"{macd_score:.1f}%")

    with icol3:
        st.markdown("**Volumen (peso 25%)**")
        if vol_ratio is not None:
            st.caption(f"Vol actual / media 20: ×{vol_ratio:.2f}")
        if vol_score is not None:
            st.progress(min(1.0, vol_score / 100), text=f"{vol_score:.1f}%")

else:
    st.info("Inicia el bot para ver el diagnóstico en tiempo real.")

# --- HISTORIAL DE CONFIANZA ---
st.markdown("#### 📈 Historial de Confianza")
conf_hist = st.session_state.get("confidence_history", [])
if len(conf_hist) > 1:
    df_conf = pd.DataFrame(conf_hist).set_index("Fecha")
    st.line_chart(df_conf[["Confianza %"]], height=180)
    # Tabla compacta con últimos 10 ticks
    with st.expander("Ver últimos ticks", expanded=False):
        st.dataframe(
            pd.DataFrame(conf_hist[-20:]).iloc[::-1].reset_index(drop=True),
            use_container_width=True
        )
else:
    st.caption("El historial aparecerá aquí una vez que el bot lleve al menos 2 ciclos corriendo.")

if settings.trading_mode.value == "paper":
    st.info("🟡 Modo activo: SIMULACIÓN (Paper Trading). Ninguna operación usa dinero real.")
else:
    st.warning("🔴 Modo activo: TRADING EN VIVO. Las operaciones usan dinero real.")

# --- BUCLE DE REFRESCO ---
if st.session_state.is_running:
    # Retardo de 5 segundos para no ser bloqueados por Yahoo Finance
    time.sleep(5)
    st.rerun()
