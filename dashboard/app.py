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
from strategies.momentum import SimpleMomentumStrategy
from portfolio.risk import RiskManager
from engine.filter import TradeViabilityFilter
from engine.decision import DecisionEngine

st.set_page_config(page_title="Panel de AlgoTrading en Vivo", layout="wide", page_icon="📈")
st.title("📈 Panel de AlgoTrading (Datos Reales)")

SYMBOL = "BTC-USD"

# --- INICIALIZACIÓN DEL ESTADO ---
if "engine_initialized" not in st.session_state:
    # 1. Configurar Proveedor de Datos Reales (YFinance)
    st.session_state.data_provider = YFinanceDataProvider()
    
    # Descargar datos históricos reales una sola vez para no saturar la API
    end_time = datetime.now()
    start_time = end_time - pd.Timedelta(days=100)
    try:
        df_real = st.session_state.data_provider.get_historical_data(SYMBOL, start_time, end_time, "1d")
    except Exception as e:
        st.error(f"Error cargando datos de YFinance: {e}")
        st.stop()
        
    st.session_state.real_history = df_real
    
    # Parchear get_historical_data para usar nuestro caché y no bloquearnos
    def cached_historical(symbol, start, end, timeframe):
        return st.session_state.real_history
    st.session_state.data_provider.get_historical_data = cached_historical
    
    # 2. Configurar Broker, Riesgo, Filtros
    st.session_state.broker = PaperBroker(settings.initial_capital, st.session_state.data_provider)
    
    # Usaremos ventanas cortas para que sea más sensible
    st.session_state.strategy = SimpleMomentumStrategy(short_window=3, long_window=10)
    st.session_state.risk = RiskManager(st.session_state.broker)
    
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
    st.session_state.is_running = False
    st.session_state.engine_initialized = True

# --- INTERFAZ LATERAL ---
st.sidebar.header("Control de Simulación")
if st.sidebar.button("▶️ Iniciar / Pausar"):
    st.session_state.is_running = not st.session_state.is_running

st.sidebar.write(f"**Estado:** {'Corriendo 🟢' if st.session_state.is_running else 'Pausado 🔴'}")
st.sidebar.write(f"**Activo:** {SYMBOL} (Datos Reales)")
st.sidebar.write(f"**Capital Inicial:** {settings.initial_capital} {settings.base_currency}")

# --- LÓGICA DE SIMULACIÓN (TICK) ---
if st.session_state.is_running:
    try:
        # 1. Obtener precio real actual
        current_price = st.session_state.data_provider.get_current_price(SYMBOL)
        
        # Actualizar histórico en memoria
        df_hist = st.session_state.real_history
        new_date = datetime.now()
        new_row = pd.DataFrame({'close': [current_price]}, index=[new_date])
        st.session_state.real_history = pd.concat([df_hist, new_row])
        
        # 2. Evaluar y Ejecutar
        # Como los datos son reales, el algoritmo solo operará si genuinamente
        # la estrategia matemática dicta que hay que hacerlo.
        # Quitamos el parche temporal, por lo que puede que tarde en operar.
        st.session_state.engine.evaluate_and_execute(SYMBOL)
        
        # 3. Registrar valor del portafolio
        cash = st.session_state.broker.get_balance()
        positions = st.session_state.broker.get_positions()
        portfolio_value = cash
        for sym, qty in positions.items():
            portfolio_value += qty * current_price
            
        st.session_state.portfolio_history.append({
            "Fecha": datetime.now(),
            "Valor": portfolio_value
        })
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
    portfolio_value += qty * current_price

net_profit = portfolio_value - settings.initial_capital
total_trades = len(broker.orders)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Valor del Portafolio", f"{portfolio_value:.2f} {settings.base_currency}", f"{net_profit:.2f} {settings.base_currency}")
col2.metric(f"Precio Actual {SYMBOL}", f"${current_price:.2f}")
col3.metric("Operaciones Realizadas", str(total_trades))

if positions:
    pos_str = ", ".join([f"{qty:.4f} {sym}" for sym, qty in positions.items()])
else:
    pos_str = "Ninguna"
col4.metric("Posiciones Abiertas", pos_str)

st.subheader("Curva de Capital del Portafolio")
if len(st.session_state.portfolio_history) > 0:
    df_chart = pd.DataFrame(st.session_state.portfolio_history).set_index("Fecha")
    st.line_chart(df_chart)

st.subheader("Órdenes y Operaciones")
if broker.orders:
    LADO_ES = {"buy": "COMPRA", "sell": "VENTA"}
    ESTADO_ES = {"pending": "PENDIENTE", "submitted": "ENVIADA", "filled": "EJECUTADA", "rejected": "RECHAZADA", "cancelled": "CANCELADA"}
    orders_list = []
    for oid, details in broker.orders.items():
        lado_raw = details["side"].value.lower()
        estado_raw = details["status"].value.lower()
        orders_list.append({
            "ID": oid[:8],
            "Símbolo": details["symbol"],
            "Lado": LADO_ES.get(lado_raw, lado_raw.upper()),
            "Estado": ESTADO_ES.get(estado_raw, estado_raw.upper()),
            "Cantidad": details["quantity"],
            "Precio Ejec.": details.get("execution_price", "-"),
            "Comisión": details.get("commission", "-")
        })
    st.dataframe(pd.DataFrame(orders_list).iloc[::-1], use_container_width=True)
else:
    st.info("Aún no hay operaciones. El algoritmo está analizando el mercado en tiempo real y operará cuando se cumplan las condiciones.")

if settings.trading_mode.value == "paper":
    st.info("🟡 Modo activo: SIMULACIÓN (Paper Trading). Ninguna operación usa dinero real.")
else:
    st.warning("🔴 Modo activo: TRADING EN VIVO. Las operaciones usan dinero real.")

# --- BUCLE DE REFRESCO ---
if st.session_state.is_running:
    # Retardo de 5 segundos para no ser bloqueados por Yahoo Finance
    time.sleep(5)
    st.rerun()
