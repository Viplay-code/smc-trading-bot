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
# Registros: nombre de candidato (FRAMEWORK.md) -> función. Capa 2 y Capa 3   #
# siguen vacíos hasta las Tareas 3/4.                                         #
# --------------------------------------------------------------------------- #
BIAS_LAYERS: dict[str, BiasFn] = {
    "A_ema200_neutral": bias_A_ema200_neutral,
}
TRIGGER_LAYERS: dict[str, TriggerFn] = {}
ENTRY_LAYERS: dict[str, EntryFn] = {}
