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
# Registros: nombre de candidato (FRAMEWORK.md) -> función. Capa 3 sigue     #
# vacía hasta la Tarea 4.                                                     #
# --------------------------------------------------------------------------- #
BIAS_LAYERS: dict[str, BiasFn] = {
    "A_ema200_neutral": bias_A_ema200_neutral,
}
TRIGGER_LAYERS: dict[str, TriggerFn] = {
    "A_sweep_bos": trigger_A_sweep_bos,
}
ENTRY_LAYERS: dict[str, EntryFn] = {}
