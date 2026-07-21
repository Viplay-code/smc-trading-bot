"""
research/layers.py — Contrato de señal y registro de capas 1/2/3 (Fase C3).

Fija la interfaz que deben cumplir los candidatos de FRAMEWORK.md (Tarea 1 del
plan de unificación del motor de señales, 2026-07-21). Tarea 2 porta el primer
candidato (Capa 1 — bias); Capa 2 y Capa 3 siguen sin candidatos hasta las
Tareas 3/4.

Cada capa es una función VECTORIZADA sobre un DataFrame histórico completo, nunca
"dame el valor actual": el bot en vivo toma el último valor/evento del mismo
cómputo que usa el backtest, en vez de tener una segunda implementación paralela
para "ahora mismo". Es la garantía estructural de que `bot.py` y `backtest.py`
dejan de divergir (hallazgo #1 de la revisión arquitectónica, 2026-07-17).

Composición de capas — quién filtra qué:
  - `BiasFn` (Capa 1) es un FILTRO de dirección (FRAMEWORK.md) — no forma parte
    del patrón de Capa 2.
  - `TriggerFn` (Capa 2) detecta el patrón de velas SIN mirar bias ni sesión.
    Alinear la dirección del trigger con el bias, y filtrar por sesión, es
    responsabilidad de quien orqueste las capas (`bot.py`/`backtest.py` hoy;
    `research.runner` a futuro) — no de cada candidato. Así ningún candidato
    nuevo reimplementa ese filtro.
  - `EntryFn` (Capa 3) calcula solo el PRECIO de entrada a partir de un
    `TriggerEvent`. El Stop Loss (estructura vs ATR×1.5) es "Gestión" fija por
    FRAMEWORK.md, no una variante de Capa 3 — no vive en este registro.

EMA/ATR: los candidatos que se porten en las Tareas 2-4 siguen calculando estos
indicadores con `pandas.ewm` tal cual hoy (`bot.py`/`backtest.py`) — migrar a
`dc_v1` como fuente única es el ítem #2 del backlog post-Fase-B, deliberadamente
posterior y separado de esta fase (decisión tomada 2026-07-21).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Mapping

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TriggerEvent:
    """Evento de patrón de Capa 2, sin filtrar por bias ni sesión.

    entry_idx: posición entera (iloc) en el DataFrame 1H donde se detectó el
    patrón. direction: "long" o "short". meta: campos libres específicos del
    candidato (ej. sweep_level/bos_level para Sweep+BOS) — cada EntryFn que
    consuma un TriggerEvent de un candidato en particular sabe qué buscar ahí;
    no forma parte del contrato compartido entre candidatos.
    """
    entry_idx: int
    direction: Literal["long", "short"]
    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EntrySignal:
    """Resultado de Capa 3: precio de entrada derivado de un TriggerEvent.

    Por ahora solo `price`. Es un dataclass (no un float suelto) para poder
    agregar campos (tipo de orden, expiración, etc.) más adelante sin romper
    el contrato de EntryFn.
    """
    price: float


# --------------------------------------------------------------------------- #
# Contrato de cada capa. Ningún candidato está registrado todavía (Tareas 2-4). #
# --------------------------------------------------------------------------- #
BiasFn = Callable[[pd.DataFrame], pd.Series]
"""4H OHLCV -> Series[int8] alineada al índice, dominio {-1,0,1} (coherente con
`dc_v1.htf_bias` — ver `DC-v1_Precisiones_Implementacion.md` P-6), no las
strings "long"/"short"/"neutral" que usan `bot.py`/`backtest.py` hoy."""

TriggerFn = Callable[[pd.DataFrame], list[TriggerEvent]]
"""1H OHLCV -> lista de TriggerEvent detectados, sin filtrar por bias/sesión."""

EntryFn = Callable[[pd.DataFrame, TriggerEvent], EntrySignal]
"""1H OHLCV + TriggerEvent -> EntrySignal con el precio de entrada."""


# --------------------------------------------------------------------------- #
# Capa 1 — candidato A: EMA200 4H con zona neutral ±1% (FRAMEWORK.md, baseline  #
# actual). Portado de bot.py::compute_ema + bot.py::htf_bias, vectorizado.     #
# --------------------------------------------------------------------------- #
def bias_A_ema200_neutral(
    df4h: pd.DataFrame, ema_period: int = 200, neutral_pct: float = 0.01,
) -> pd.Series:
    """Bias HTF: signo de `(close - EMA200) / EMA200` contra una zona neutral
    ±1%. Réplica EXACTA de la clasificación de `backtest.py::build_features`
    (`np.where` anidado), incluido su manejo de warmup: una comparación con
    NaN no cumple ninguna rama y cae en 0 (mismo comportamiento que hoy mapea
    a "neutral"). Deliberado: esta tarea porta el comportamiento tal cual
    existe, no lo corrige — ver hallazgo #2 del backlog post-Fase-B para la
    variante NaN-segura (`np.sign`, como en `dc_v1.derive_htf_bias`), que
    queda para una tarea de mejora futura, no para este port.

    Equivalencia validada durante la migración (Tarea 2, 2026-07-21): 0
    diferencias contra `backtest.py::build_features` sobre una serie 4H
    sintética de 260 filas, y último valor idéntico a `bot.py::htf_bias`.
    """
    ema = df4h["close"].ewm(span=ema_period, adjust=False).mean()
    dist = (df4h["close"] - ema) / ema
    bias = np.where(dist > neutral_pct, 1, np.where(dist < -neutral_pct, -1, 0))
    return pd.Series(bias, index=df4h.index, name="bias").astype("int8")


# --------------------------------------------------------------------------- #
# Capa 2 — candidato A: Liquidity Sweep + BOS 3 velas (FRAMEWORK.md, baseline  #
# actual). Portado de bot.py::detect_liquidity_sweep + bot.py::detect_bos.    #
# --------------------------------------------------------------------------- #
def _detect_sweep_at(
    df1h: pd.DataFrame, i: int, swing_lookback: int, sweep_min_pct: float,
) -> dict | None:
    """Réplica de `bot.py::detect_liquidity_sweep`, generalizada de `iloc[-1]`
    a un índice `i` arbitrario — única adaptación necesaria para vectorizar
    sobre toda la historia (el contrato de la Tarea 1 exige recorrer la serie
    completa, no solo "la última vela"). La fórmula relativa (swing_lookback
    velas hacia atrás desde `i`) no cambia."""
    if i < swing_lookback:
        return None

    candle = df1h.iloc[i]
    prev = df1h.iloc[i - swing_lookback:i]

    swing_low = prev["low"].min()
    swing_high = prev["high"].max()

    pen_long = (swing_low - candle["low"]) / swing_low
    if (candle["low"] < swing_low
            and candle["close"] > candle["open"]
            and pen_long >= sweep_min_pct):
        return {"type": "long", "sweep_level": candle["low"], "swing_low": swing_low}

    pen_short = (candle["high"] - swing_high) / swing_high
    if (candle["high"] > swing_high
            and candle["close"] < candle["open"]
            and pen_short >= sweep_min_pct):
        return {"type": "short", "sweep_level": candle["high"], "swing_high": swing_high}

    return None


def _detect_bos(
    df1h: pd.DataFrame, sweep_idx: int, direction: str,
    bos_lookback: int, bos_max_candles: int,
) -> dict | None:
    """Réplica EXACTA de `bot.py::detect_bos` — ya era genérica en `sweep_idx`
    (no estaba anclada a `iloc[-1]`), se porta sin ningún cambio de fórmula."""
    start = sweep_idx + 1
    end = min(sweep_idx + bos_max_candles + 1, len(df1h))
    window = df1h.iloc[start:end]

    ref = df1h.iloc[max(0, sweep_idx - bos_lookback + 1): sweep_idx + 1]

    if direction == "long":
        level = ref["high"].max()
        for idx, row in window.iterrows():
            if row["close"] > level:
                return {"bos_level": level, "bos_idx": df1h.index.get_loc(idx)}
    else:
        level = ref["low"].min()
        for idx, row in window.iterrows():
            if row["close"] < level:
                return {"bos_level": level, "bos_idx": df1h.index.get_loc(idx)}

    return None


def trigger_A_sweep_bos(
    df1h: pd.DataFrame,
    swing_lookback: int = 20,
    sweep_min_pct: float = 0.001,
    bos_lookback: int = 5,
    bos_max_candles: int = 3,
) -> list[TriggerEvent]:
    """Capa 2 — candidato A: Liquidity Sweep + BOS (3 velas), FRAMEWORK.md
    baseline actual. Recorre cada índice de la historia jugando el rol de
    "última vela cerrada" del loop en vivo de `bot.py` — misma fórmula en
    cada paso, la única adaptación es iterar en vez de mirar solo `iloc[-1]`.

    `meta` conserva EXACTAMENTE los nombres de campo que produce `bot.py` hoy
    (`sweep_level`, `swing_low` o `swing_high` según dirección, `bos_level`)
    sin unificar todavía — esa normalización (ej. un único `swing_level`)
    queda para una tarea posterior dedicada a estabilizar el contrato, no
    para este port. Único campo nuevo: `sweep_idx`, que en `bot.py` vivía
    implícito en el contexto del loop en vivo (no era un campo de ningún
    dict) y acá debe hacerse explícito porque ya no hay "índice actual" —
    sin él, Capa 3 no podría ubicar la vela de sweep para calcular el
    pullback.
    """
    events: list[TriggerEvent] = []
    for i in range(swing_lookback, len(df1h)):
        sweep = _detect_sweep_at(df1h, i, swing_lookback, sweep_min_pct)
        if sweep is None:
            continue
        bos = _detect_bos(df1h, i, sweep["type"], bos_lookback, bos_max_candles)
        if bos is None:
            continue
        meta = {"sweep_idx": i, "sweep_level": sweep["sweep_level"], "bos_level": bos["bos_level"]}
        if sweep["type"] == "long":
            meta["swing_low"] = sweep["swing_low"]
        else:
            meta["swing_high"] = sweep["swing_high"]
        events.append(TriggerEvent(entry_idx=bos["bos_idx"], direction=sweep["type"], meta=meta))
    return events


# --------------------------------------------------------------------------- #
# Capa 3 — candidato A: 50% del rango Sweep→BOS (FRAMEWORK.md, baseline       #
# actual). Portado de la sección "Calcular niveles" de bot.py::run_bot        #
# ([bot.py:335-355]) — ahí vive inline, mezclada con SL/TP/sizing.            #
# --------------------------------------------------------------------------- #
def entry_A_pullback_50(
    df1h: pd.DataFrame, event: TriggerEvent, pullback_pct: float = 0.50,
) -> EntrySignal:
    """Precio de entrada al `pullback_pct` (50%) del rango Sweep→BOS. Extrae
    SOLO la parte de `entry` de bot.py::run_bot — el Stop Loss (estructura vs
    ATR×1.5) y el Take Profit son "Gestión" fija por FRAMEWORK.md, no una
    variante de Capa 3, y quedan fuera de este registro (decisión de la
    Tarea 1). Riesgo/sizing tampoco se tocan en esta tarea.

    `df1h` no se usa (la fórmula depende solo de `event.meta`) — se mantiene
    en la firma por el contrato de `EntryFn`: otros candidatos futuros (ej.
    la entrada a mercado de T1) sí necesitan leer el DataFrame.
    """
    bos_lvl = event.meta["bos_level"]
    if event.direction == "long":
        sweep_lvl = event.meta["swing_low"]
        rng = bos_lvl - sweep_lvl
        entry = bos_lvl - rng * pullback_pct
    else:
        sweep_lvl = event.meta["swing_high"]
        rng = sweep_lvl - bos_lvl
        entry = bos_lvl + rng * pullback_pct
    return EntrySignal(price=entry)


# --------------------------------------------------------------------------- #
# Capa 2 — candidato T1: cruce EMA9/EMA21 con filtro de bias 4H (FRAMEWORK.md, #
# nuevo candidato explícito). Portado de backtest.py::find_entries            #
# ([backtest.py:87-115]).                                                     #
#                                                                              #
# El filtro de bias/sesión de find_entries (`bias == "neutral"`,              #
# `not in_session`, y "solo cross_up si bias es long / solo cross_down si     #
# bias es short") NO se replica acá — es exactamente el mismo principio de    #
# composición ya aplicado a `trigger_A_sweep_bos`: Capa 2 detecta el patrón   #
# de velas (el cruce, cuya dirección surge solo de la acción del precio,      #
# igual que el tipo de sweep) sin mirar bias ni sesión; alinear esa           #
# dirección contra el bias y filtrar sesión es responsabilidad de quien       #
# orqueste. El chequeo `pd.isna(row["ema200_4h"])` de find_entries tampoco se #
# replica: es redundante con `bias == "neutral"` (con NaN, `bias_A_ema200_    #
# neutral` ya devuelve 0 — ver su docstring — así que cualquier orquestador   #
# que filtre bias neutral cubre ese warmup sin que Capa 2 necesite conocer    #
# el 4H en absoluto).                                                         #
#                                                                              #
# El filtro de riesgo degenerado (`risk_pts < 1e-9: continue`) SÍ se replica  #
# exacto (decisión tomada explícitamente, no asumida): calcula SL/ATR solo    #
# para decidir si el evento existe, sin exponerlos en `meta` ni en el         #
# contrato público — el SL sigue siendo "Gestión" fija por FRAMEWORK.md, no   #
# una variante de Capa 2/3, igual que ya declara `entry_A_pullback_50`.       #
# Preservar este gate exacto es lo que garantiza que el universo de eventos   #
# generado acá, tras aplicarle el mismo filtro de bias/sesión que aplicaría   #
# un orquestador, coincide 1:1 con lo que `find_entries` produce hoy — no es  #
# opcional para la paridad.                                                   #
# --------------------------------------------------------------------------- #
def trigger_T1_ema_cross(
    df1h: pd.DataFrame,
    ema_fast: int = 9,
    ema_slow: int = 21,
    atr_period: int = 14,
    atr_mult: float = 1.5,
    warmup: int = 25,
) -> list[TriggerEvent]:
    """Capa 2 — candidato T1: cruce de EMA9 sobre/bajo EMA21. `direction` es
    "long" en cruce alcista, "short" en cruce bajista — determinado solo por
    el cruce, no por bias (ver nota de composición arriba). `meta` queda
    vacío: a diferencia de Sweep+BOS, Capa 3 de T1 (`entry_C_market_close`)
    no necesita ningún dato del evento más allá de `entry_idx`.

    Rango de iteración (`range(warmup, n-2)`, `warmup=25`) y fórmulas de
    EMA/ATR replicadas literalmente de `backtest.py::build_features`
    (`ewm(span=..., adjust=False)` para EMA, `ewm(alpha=1/atr_period,
    adjust=False)` sobre True Range para ATR) — no se reutiliza el ATR de
    `bot.py` porque su fórmula no está confirmada idéntica (ver hallazgo #3
    del backlog post-Fase-B); usar la de `bot.py` acá sería una fuente
    silenciosamente distinta a la que `find_entries` usa hoy.
    """
    close, high, low = df1h["close"], df1h["high"], df1h["low"]
    ema_f = close.ewm(span=ema_fast, adjust=False).mean()
    ema_s = close.ewm(span=ema_slow, adjust=False).mean()

    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / atr_period, adjust=False).mean()

    events: list[TriggerEvent] = []
    n = len(df1h)
    for i in range(warmup, n - 2):
        if pd.isna(ema_f.iloc[i]):
            continue

        cross_up = ema_f.iloc[i - 1] <= ema_s.iloc[i - 1] and ema_f.iloc[i] > ema_s.iloc[i]
        cross_down = ema_f.iloc[i - 1] >= ema_s.iloc[i - 1] and ema_f.iloc[i] < ema_s.iloc[i]
        if not cross_up and not cross_down:
            continue
        direction: Literal["long", "short"] = "long" if cross_up else "short"

        entry = close.iloc[i]
        atr_val = atr.iloc[i]
        if direction == "long":
            sl = min(low.iloc[i], entry - atr_mult * atr_val)
        else:
            sl = max(high.iloc[i], entry + atr_mult * atr_val)
        if abs(entry - sl) < 1e-9:
            continue

        events.append(TriggerEvent(entry_idx=i, direction=direction, meta={}))
    return events


# --------------------------------------------------------------------------- #
# Capa 3 — candidato C: cierre de la vela de señal, entrada a mercado         #
# (FRAMEWORK.md, candidato declarado pero no implementado hasta ahora).       #
# Generalizado de "cierre de vela BOS" a "cierre de la vela de señal" porque  #
# el mecanismo (usar `event.entry_idx` como la vela de entrada a mercado) no  #
# depende de qué candidato de Capa 2 produjo el evento — hoy lo usa T1        #
# (`backtest.py::find_entries`, `entry = row["close"]`), pero no es          #
# exclusivo de T1 (decisión tomada explícitamente al portar T1, no asumida). #
# --------------------------------------------------------------------------- #
def entry_C_market_close(df1h: pd.DataFrame, event: TriggerEvent) -> EntrySignal:
    """Precio de entrada = cierre de la vela en `event.entry_idx` (orden a
    mercado). No usa `event.meta` — a diferencia de `entry_A_pullback_50`,
    el precio no depende de niveles de sweep/BOS, solo de la posición del
    evento en la serie."""
    return EntrySignal(price=float(df1h["close"].iloc[event.entry_idx]))


# --------------------------------------------------------------------------- #
# Registros: nombre de candidato (FRAMEWORK.md) -> función.                  #
# --------------------------------------------------------------------------- #
BIAS_LAYERS: dict[str, BiasFn] = {
    "A_ema200_neutral": bias_A_ema200_neutral,
}
TRIGGER_LAYERS: dict[str, TriggerFn] = {
    "A_sweep_bos": trigger_A_sweep_bos,
    "T1_ema_cross": trigger_T1_ema_cross,
}
ENTRY_LAYERS: dict[str, EntryFn] = {
    "A_pullback_50": entry_A_pullback_50,
    "C_market_close": entry_C_market_close,
}
