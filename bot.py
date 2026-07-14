"""
SMC Trading Bot — BTCUSDT Binance Futures
Estrategia: Liquidity Sweep + BOS + Pullback 50%
Filtro: EMA200 4H
Sesiones: Londres (07-11 UTC) + Nueva York (13-17 UTC)
Gestión: ATR(14) Stop + 2.5R TP
"""

import os
import time
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import numpy as np
from binance.client import Client
from binance.exceptions import BinanceAPIException

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("smc_bot.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ─── Configuración ──────────────────────────────────────────────────────────
@dataclass
class Config:
    symbol: str = "BTCUSDT"
    htf: str = "4h"
    ltf: str = "1h"

    # EMA HTF
    ema_period: int = 200
    ema_neutral_pct: float = 0.01          # ±1%

    # Swing
    swing_lookback: int = 20               # velas para swing high/low
    sweep_min_pct: float = 0.001           # 0.10% mínimo de penetración

    # BOS
    bos_lookback: int = 5                  # velas para BOS
    bos_max_candles: int = 3               # máx velas post-sweep para BOS

    # Pullback
    pullback_pct: float = 0.50             # 50% del rango Sweep→BOS
    pullback_timeout: int = 5              # máx velas esperando pullback

    # ATR
    atr_period: int = 14
    atr_mult: float = 1.5

    # Riesgo
    risk_per_trade: float = 0.005          # 0.5%
    rr: float = 2.5                        # RR mínimo

    # Sesiones (UTC)
    sessions: list = field(default_factory=lambda: [
        (7, 11),   # Londres
        (13, 17),  # Nueva York
    ])

    # Modo
    testnet: bool = True
    paper_trade: bool = True               # True = no ejecuta órdenes reales


# ─── Utilidades de datos ────────────────────────────────────────────────────
def fetch_ohlcv(client: Client, symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
    raw = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(raw, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","qav","trades","tbbav","tbqav","ignore"
    ])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    for col in ["open","high","low","close","volume"]:
        df[col] = df[col].astype(float)
    df.set_index("open_time", inplace=True)
    # Excluir vela activa (no cerrada)
    df = df.iloc[:-1]
    return df


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def compute_atr(df: pd.DataFrame, period: int) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([h - l, (h - c).abs(), (l - c).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()


# ─── Lógica de señales ──────────────────────────────────────────────────────
def htf_bias(df4h: pd.DataFrame, cfg: Config) -> str:
    """Devuelve 'long', 'short' o 'neutral' según EMA200 4H."""
    ema = compute_ema(df4h["close"], cfg.ema_period)
    price = df4h["close"].iloc[-1]
    ema_val = ema.iloc[-1]
    dist = (price - ema_val) / ema_val
    if dist > cfg.ema_neutral_pct:
        return "long"
    elif dist < -cfg.ema_neutral_pct:
        return "short"
    return "neutral"


def detect_liquidity_sweep(df1h: pd.DataFrame, cfg: Config) -> Optional[dict]:
    """
    Detecta sweep en la última vela cerrada (iloc[-1]).
    Retorna dict con tipo, sweep_low/high o None.
    """
    if len(df1h) < cfg.swing_lookback + 1:
        return None

    candle = df1h.iloc[-1]
    prev = df1h.iloc[-(cfg.swing_lookback + 1):-1]

    swing_low  = prev["low"].min()
    swing_high = prev["high"].max()

    # LONG sweep: wick abajo + cierre alcista
    pen_long = (swing_low - candle["low"]) / swing_low
    if (candle["low"] < swing_low
            and candle["close"] > candle["open"]
            and pen_long >= cfg.sweep_min_pct):
        return {"type": "long", "sweep_level": candle["low"], "swing_low": swing_low}

    # SHORT sweep: wick arriba + cierre bajista
    pen_short = (candle["high"] - swing_high) / swing_high
    if (candle["high"] > swing_high
            and candle["close"] < candle["open"]
            and pen_short >= cfg.sweep_min_pct):
        return {"type": "short", "sweep_level": candle["high"], "swing_high": swing_high}

    return None


def detect_bos(df1h: pd.DataFrame, sweep_idx: int, direction: str, cfg: Config) -> Optional[dict]:
    """
    Busca BOS en las 3 velas después del sweep.
    sweep_idx: índice entero de la vela del sweep.
    Retorna dict con bos_level y bos_idx o None.
    """
    start = sweep_idx + 1
    end   = min(sweep_idx + cfg.bos_max_candles + 1, len(df1h))
    window = df1h.iloc[start:end]

    ref = df1h.iloc[max(0, sweep_idx - cfg.bos_lookback + 1): sweep_idx + 1]

    if direction == "long":
        level = ref["high"].max()
        for i, row in window.iterrows():
            if row["close"] > level:
                return {"bos_level": level, "bos_idx": df1h.index.get_loc(i)}
    else:
        level = ref["low"].min()
        for i, row in window.iterrows():
            if row["close"] < level:
                return {"bos_level": level, "bos_idx": df1h.index.get_loc(i)}

    return None


def in_session(dt: datetime, cfg: Config) -> bool:
    """Verifica si la hora UTC está dentro de sesión operativa."""
    h = dt.hour
    return any(start <= h < end for start, end in cfg.sessions)


# ─── Estado del bot ─────────────────────────────────────────────────────────
@dataclass
class BotState:
    position: Optional[dict] = None        # posición abierta
    pending_order: Optional[dict] = None   # orden límite pendiente
    setup: Optional[dict] = None           # setup activo esperando pullback
    equity: float = 500.0                  # capital en USD (ajustar)


# ─── Gestión de órdenes ─────────────────────────────────────────────────────
def calculate_position(entry: float, sl: float, equity: float, cfg: Config) -> float:
    """Tamaño de posición en USD basado en riesgo fijo."""
    risk_usd = equity * cfg.risk_per_trade
    sl_pct = abs(entry - sl) / entry
    if sl_pct == 0:
        return 0
    size_usd = risk_usd / sl_pct
    return round(size_usd, 2)


def place_order(client: Client, symbol: str, side: str, size_usd: float,
                entry: float, sl: float, tp: float, cfg: Config, state: BotState):
    if cfg.paper_trade:
        log.info(f"[PAPER] {side} entry={entry:.2f} sl={sl:.2f} tp={tp:.2f} size=${size_usd:.2f}")
        state.pending_order = {
            "side": side, "entry": entry, "sl": sl, "tp": tp,
            "size_usd": size_usd, "opened_at": datetime.now(timezone.utc)
        }
        return

    try:
        qty = round(size_usd / entry, 3)
        order_side = "BUY" if side == "long" else "SELL"

        # Orden límite de entrada
        client.futures_create_order(
            symbol=symbol, side=order_side, type="LIMIT",
            quantity=qty, price=str(round(entry, 2)),
            timeInForce="GTC"
        )
        log.info(f"Orden límite colocada: {side} {qty} @ {entry:.2f}")
        state.pending_order = {
            "side": side, "entry": entry, "sl": sl, "tp": tp,
            "size_usd": size_usd, "qty": qty,
            "opened_at": datetime.now(timezone.utc)
        }
    except BinanceAPIException as e:
        log.error(f"Error colocando orden: {e}")


def cancel_pending(client: Client, symbol: str, cfg: Config, state: BotState, reason: str):
    log.info(f"Setup cancelado: {reason}")
    if not cfg.paper_trade:
        try:
            client.futures_cancel_all_open_orders(symbol=symbol)
        except BinanceAPIException as e:
            log.error(f"Error cancelando órdenes: {e}")
    state.pending_order = None
    state.setup = None


# ─── Loop principal ──────────────────────────────────────────────────────────
def run_bot(client: Client, cfg: Config):
    state = BotState()
    log.info("Bot iniciado. Modo: " + ("PAPER" if cfg.paper_trade else "REAL"))

    while True:
        try:
            now = datetime.now(timezone.utc)

            # ── 1. Datos ────────────────────────────────────────────────────
            df4h = fetch_ohlcv(client, cfg.symbol, cfg.htf, limit=250)
            df1h = fetch_ohlcv(client, cfg.symbol, cfg.ltf, limit=300)
            atr  = compute_atr(df1h, cfg.atr_period)

            # ── 2. Filtro HTF ───────────────────────────────────────────────
            bias = htf_bias(df4h, cfg)
            if bias == "neutral":
                log.info(f"HTF neutral — sin operación. EMA zona ±1%")
                time.sleep(60)
                continue

            # ── 3. Verificar posición abierta ───────────────────────────────
            if state.position:
                price = float(client.futures_symbol_ticker(symbol=cfg.symbol)["price"])
                pos = state.position
                hit_sl = (pos["side"] == "long"  and price <= pos["sl"]) or \
                         (pos["side"] == "short" and price >= pos["sl"])
                hit_tp = (pos["side"] == "long"  and price >= pos["tp"]) or \
                         (pos["side"] == "short" and price <= pos["tp"])

                if hit_sl:
                    log.info(f"SL tocado @ {price:.2f}")
                    state.equity -= state.equity * cfg.risk_per_trade
                    state.position = None
                elif hit_tp:
                    log.info(f"TP tocado @ {price:.2f}")
                    state.equity += state.equity * cfg.risk_per_trade * cfg.rr
                    state.position = None

                time.sleep(60)
                continue

            # ── 4. Setup pendiente (esperando pullback) ──────────────────────
            if state.setup:
                setup = state.setup
                price = float(client.futures_symbol_ticker(symbol=cfg.symbol)["price"])
                candles_waited = len(df1h) - setup["bos_candle_count"]

                # Timeout
                if candles_waited >= cfg.pullback_timeout:
                    cancel_pending(client, cfg.symbol, cfg, state, "timeout pullback")
                    time.sleep(60)
                    continue

                # Sweep contrario invalida
                new_sweep = detect_liquidity_sweep(df1h, cfg)
                if new_sweep and new_sweep["type"] != setup["direction"]:
                    cancel_pending(client, cfg.symbol, cfg, state, "sweep contrario antes de entrada")
                    time.sleep(60)
                    continue

                # Verificar si orden límite fue tocada (paper trade)
                if cfg.paper_trade and state.pending_order:
                    po = state.pending_order
                    if (po["side"] == "long"  and price <= po["entry"]) or \
                       (po["side"] == "short" and price >= po["entry"]):
                        log.info(f"[PAPER] Orden ejecutada @ {po['entry']:.2f}")
                        state.position = po
                        state.pending_order = None
                        state.setup = None

                time.sleep(60)
                continue

            # ── 5. Buscar nuevo setup ────────────────────────────────────────
            if not in_session(now, cfg):
                log.info(f"Fuera de sesión ({now.strftime('%H:%M')} UTC)")
                time.sleep(60)
                continue

            sweep = detect_liquidity_sweep(df1h, cfg)
            if not sweep:
                time.sleep(60)
                continue

            if sweep["type"] != bias:
                log.info(f"Sweep {sweep['type']} pero bias es {bias} — ignorado")
                time.sleep(60)
                continue

            sweep_idx = len(df1h) - 1
            bos = detect_bos(df1h, sweep_idx, sweep["type"], cfg)
            if not bos:
                log.info("Sweep detectado pero sin BOS en 3 velas — setup inválido")
                time.sleep(60)
                continue

            # ── 6. Calcular niveles ──────────────────────────────────────────
            bos_idx  = bos["bos_idx"]
            bos_lvl  = bos["bos_level"]
            atr_val  = atr.iloc[-1]

            if sweep["type"] == "long":
                sweep_lvl = sweep["swing_low"]
                rng       = bos_lvl - sweep_lvl
                entry     = bos_lvl - rng * cfg.pullback_pct   # 50%
                sl_struct = sweep_lvl
                sl_atr    = entry - cfg.atr_mult * atr_val
                sl        = min(sl_struct, sl_atr)             # el más conservador
                tp        = entry + (entry - sl) * cfg.rr
            else:
                sweep_lvl = sweep["swing_high"]
                rng       = sweep_lvl - bos_lvl
                entry     = bos_lvl + rng * cfg.pullback_pct
                sl_struct = sweep_lvl
                sl_atr    = entry + cfg.atr_mult * atr_val
                sl        = max(sl_struct, sl_atr)
                tp        = entry - (sl - entry) * cfg.rr

            size_usd = calculate_position(entry, sl, state.equity, cfg)

            log.info(
                f"Setup {sweep['type'].upper()} | entry={entry:.2f} "
                f"sl={sl:.2f} tp={tp:.2f} size=${size_usd:.2f} | "
                f"RR real: {abs(tp-entry)/abs(entry-sl):.2f}"
            )

            state.setup = {
                "direction": sweep["type"],
                "entry": entry, "sl": sl, "tp": tp,
                "bos_candle_count": len(df1h)
            }

            place_order(client, cfg.symbol, sweep["type"], size_usd,
                        entry, sl, tp, cfg, state)

        except Exception as e:
            log.error(f"Error en loop: {e}", exc_info=True)

        time.sleep(60)


# ─── Entrypoint ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    API_KEY    = os.getenv("BINANCE_API_KEY", "")
    API_SECRET = os.getenv("BINANCE_API_SECRET", "")

    cfg = Config(testnet=True, paper_trade=True)

    client = Client(API_KEY, API_SECRET, testnet=cfg.testnet)
    run_bot(client, cfg)
