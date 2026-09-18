# AlgoTrading

Sistema de inversión algorítmica optimizado para micro-capital (desde 50 €), centrado en preservar el capital, controlar el riesgo y maximizar la rentabilidad neta ajustada al riesgo descontando todos los costes operativos (comisiones, spread, slippage).

## Instalación

1. Clona el repositorio.
2. Instala las dependencias:
   ```bash
   pip install -e .[dev]
   ```
3. Copia el archivo de entorno y configúralo:
   ```bash
   cp .env.example .env
   ```

## Configuración

Toda la configuración se realiza a través de variables de entorno (fichero `.env`). No modifiques el código para ajustar parámetros.
Revisa `.env.example` para ver los valores disponibles.

## Modos de Operación

- **Paper Trading**: El sistema arranca SIEMPRE en este modo por defecto (`TRADING_MODE=paper`). Es obligatorio validar cualquier estrategia aquí.
- **Live Trading**: Para operar con dinero real, no basta con cambiar el código. Se deben cumplir estos requisitos:
  1. Realizar validación exitosa en backtest (incluyendo Walk-Forward testing).
  2. Ejecutar un periodo mínimo en Paper Trading comprobando que las métricas (spread, slippage) son realistas.
  3. Modificar el `.env` con:
     ```env
     TRADING_MODE=live
     LIVE_TRADING_ENABLED=true
     ```
  4. Configurar las API keys del broker (ej. Interactive Brokers, Alpaca). **NUNCA GUARDES LAS CLAVES EN EL CÓDIGO**. Úsalas únicamente en el `.env` (que está en el `.gitignore`).

## Backtesting

El motor de backtesting permite realizar simulaciones precisas con 50 €, incluyendo costes fraccionales. Ejecuta:
```bash
pytest tests/
```

## Seguridad

El sistema cuenta con dos mecanismos críticos:
- **Safe Mode**: Se activa automáticamente si detecta anomalías (errores repetidos de broker, datos desactualizados). Evita nuevas operaciones pero mantiene el monitoreo.
- **Emergency Stop**: Detiene inmediatamente cualquier nueva compra/venta especulativa. Configurable vía `.env` (`EMERGENCY_STOP=true`).
