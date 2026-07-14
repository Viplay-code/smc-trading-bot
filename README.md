# SMC Trading Bot — BTCUSDT Binance Futures

Estrategia: Liquidity Sweep + BOS + Pullback 50%  
Filtro HTF: EMA200 4H  
Gestión: ATR(14) Stop + 2.5R TP fijo

---

## Instalación

```bash
pip install -r requirements.txt
```

---

## Orden de ejecución recomendado

### 1. Backtest primero (sin API key)
```bash
python backtest.py
```
Descarga datos históricos de Binance públicos (no requiere cuenta).  
Genera `backtest_trades.csv` con cada operación simulada.

### 2. Paper trading en Testnet
1. Crea cuenta en https://testnet.binancefuture.com
2. Obtén API key del testnet
3. Configura variables de entorno:
```bash
export BINANCE_API_KEY="tu_key_testnet"
export BINANCE_API_SECRET="tu_secret_testnet"
```
4. Ejecuta:
```bash
python bot.py
```
El bot corre en modo `paper_trade=True` por defecto — no ejecuta órdenes reales.

### 3. Capital real (cuando tengas 4+ semanas de paper trading positivo)
En `bot.py`, cambia:
```python
cfg = Config(testnet=False, paper_trade=False)
```
Y usa API keys de cuenta real con permiso solo de Futures.

---

## Archivos

| Archivo | Descripción |
|---------|-------------|
| `bot.py` | Bot en tiempo real con loop principal |
| `backtest.py` | Backtester vectorizado 2022-2024 |
| `requirements.txt` | Dependencias |

---

## Parámetros clave (Config)

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `swing_lookback` | 20 | Velas para detectar swing high/low |
| `sweep_min_pct` | 0.001 | Penetración mínima del sweep (0.10%) |
| `bos_max_candles` | 3 | Máx velas post-sweep esperando BOS |
| `pullback_timeout` | 5 | Máx velas esperando pullback al 50% |
| `atr_mult` | 1.5 | Multiplicador ATR para SL |
| `risk_per_trade` | 0.005 | Riesgo por trade (0.5% del equity) |
| `rr` | 2.5 | Risk/Reward objetivo |
| `ema_neutral_pct` | 0.01 | Zona neutral ±1% alrededor de EMA200 |

---

## Métricas a monitorear

- **Winrate mínimo viable**: >30% con RR 1:2.5 (expectancy positiva)
- **Max drawdown aceptable**: <15%
- **Mínimo de trades para validación estadística**: 50+

---

## Seguridad

- **Nunca** pongas API keys en el código directamente
- Usa siempre variables de entorno
- Activa IP whitelist en Binance para las API keys
- Usa permisos mínimos: solo Futures Trading (sin retiros)

---

## Advertencia

Este bot es un sistema experimental. El trading de futuros implica riesgo de pérdida total del capital.  
Valida siempre con backtesting + paper trading antes de usar capital real.
