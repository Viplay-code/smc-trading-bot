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

EMA/ATR: desde la Iniciativa B (backlog post-Fase-B, ítem #2), `bias_A_ema200_
neutral` y `trigger_T1_ema_cross` calculan EMA/ATR vía `dc_v1.ema()`/`dc_v1.
atr()` (TA-Lib, ADR-001) en vez de `pandas.ewm`. Es la primera dependencia de
`research` sobre `dc_v1` — permitida por la regla de dependencias
(`market_data → dc_v1 → research → bot`), pero implica que `import research`
requiere TA-Lib instalado. TA-Lib difiere numéricamente de `pandas.ewm`
(semilla SMA + NaN de warmup real vs recursión sin NaN desde el primer valor)
— no es un simple cambio de fuente transparente, ver validación de la
Iniciativa B para las diferencias medidas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Mapping

import numpy as np
import pandas as pd

import dc_v1


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
    ±1%. Clasificación (`np.where` anidado) sin cambios desde la Tarea 2:
    NaN no cumple ninguna rama y cae en 0 ("neutral") — deliberado, no se
    corrige a `np.sign` acá (ver hallazgo #2 del backlog post-Fase-B).

    EMA vía `dc_v1.ema()` desde la Iniciativa B (antes `pandas.ewm`) — a
    diferencia de `pandas.ewm`, TA-Lib devuelve NaN real en las primeras
    `ema_period-1` filas (warmup), lo que ahora SÍ activa la rama NaN->0 de
    forma genuina en vez de solo defensiva. Sobre series cortas (tests
    sintéticos) esto reduce el rango de filas con bias no-neutral; en
    producción es irrelevante porque `dc_v1`/`bot.py` siempre alimentan esta
    función con muchas más de 200 velas 4H de historia.

    Equivalencia contra `backtest.py::build_features`/`bot.py::htf_bias` ya
    NO es exacta desde esta migración (ambos siguen en `pandas.ewm` — ver
    Iniciativa B en el backlog post-Fase-B para las diferencias numéricas
    medidas, e Iniciativa G para la reconciliación funcional pendiente).
    """
    ema = dc_v1.ema(df4h["close"], ema_period)
    dist = (df4h["close"] - ema) / ema
    bias = np.where(dist > neutral_pct, 1, np.where(dist < -neutral_pct, -1, 0))
    return pd.Series(bias, index=df4h.index, name="bias").astype("int8")


# --------------------------------------------------------------------------- #
# Capa 1 — candidato A2: EMA200 4H con zona neutral ±1%, PERO reclasificado   #
# en cada vela 1H contra un nivel 4H sostenido. Port histórico de            #
# backtest.py::build_features (Iniciativa G, backlog post-Fase-B). Fuera de  #
# BIAS_LAYERS — ver docstring.                                               #
# --------------------------------------------------------------------------- #
def bias_A2_ema200_neutral_1h_held(
    df1h: pd.DataFrame, df4h: pd.DataFrame, ema_period: int = 200, neutral_pct: float = 0.01,
) -> pd.Series:
    """Bias HTF candidato "A2" (FRAMEWORK.md, Capa 1): mismo umbral ±1% que A,
    pero con una mecánica temporal distinta — reclasifica en CADA vela 1H,
    comparando el cierre 1H (que se mueve cada hora) contra el nivel de EMA200
    de la última vela 4H YA CERRADA (`shift(1)`, sostenido/`ffill` durante las
    4 horas siguientes), en vez de comparar el cierre 4H contra su propia
    EMA200 como hace A.

    PORT HISTÓRICO de una implementación ya existente, NO una fórmula nueva y
    NO una recomendación de convergencia: es una transcripción literal, campo
    a campo, de la lógica que hoy vive inline en `backtest.py::build_features`
    (bloque de Bias, sin modificar desde antes de la Tarea 7), incluyendo su
    fuente de indicador (`pandas.ewm`, NO `dc_v1.ema()` — a diferencia de
    `bias_A_ema200_neutral` desde la Iniciativa B, deliberadamente sin migrar
    acá). El propósito de este port es dar nombre y ubicación formal en el
    registro de candidatos a una fórmula que ya existe y ya se ejecuta de
    facto dentro de `backtest.py`; que quede documentada y testeada NO implica
    preferirla sobre A ni sugerir que `backtest.py` deba converger hacia A, o
    viceversa. `backtest.py` sigue calculando su Bias inline exactamente igual
    que antes de este port — esta función no la reemplaza ni la consume
    ningún consumidor todavía.

    Fuera de `BIAS_LAYERS`/`BiasFn` a propósito: `BiasFn` es
    `Callable[[pd.DataFrame], pd.Series]` (una sola vela 4H de entrada) — esta
    fórmula necesita AMBOS `df1h` y `df4h` (el precio que se mueve cada hora y
    el nivel 4H que se sostiene entre velas), incompatible con esa firma. No
    se fuerza el contrato de `BiasFn` para acomodarla.

    La decisión de mantener A y A2 como candidatos separados, converger hacia
    uno solo, o diseñar una tercera fórmula, queda condicionada a validación
    con datos reales 2022/2023 contra las métricas de `FRAMEWORK.md` (PF, DD,
    Expectancy, frecuencia) — Iniciativa G del backlog post-Fase-B, todavía
    abierta. Ver ese backlog para el análisis de la divergencia numérica entre
    A y A2 medida sobre datos sintéticos.
    """
    df4h_ema = df4h.copy()
    df4h_ema["ema200"] = df4h_ema["close"].ewm(span=ema_period, adjust=False).mean()
    df4h_s = df4h_ema[["ema200", "close"]].shift(1)
    df4h_s.columns = ["ema200_4h", "close_4h"]

    df1h_j = df1h.join(df4h_s, how="left")
    df1h_j[["ema200_4h", "close_4h"]] = df1h_j[["ema200_4h", "close_4h"]].ffill()

    dist = (df1h_j["close"] - df1h_j["ema200_4h"]) / df1h_j["ema200_4h"]
    bias = np.where(dist > neutral_pct, 1, np.where(dist < -neutral_pct, -1, 0))
    return pd.Series(bias, index=df1h.index, name="bias").astype("int8")


# --------------------------------------------------------------------------- #
# Capa 1 — candidato B: EMA50 + EMA200 4H, cruce de medias (FRAMEWORK.md).    #
# Diseño formal cerrado 2026-08-22 (Espacio 5 — desempate ex ante Bias B/C,   #
# elegido por reutilización de primitivas ya canónicas, NO por expectativa   #
# de resultado — ver docs/research/EXPERIMENTAL_ROADMAP.md).                 #
# --------------------------------------------------------------------------- #
def bias_B_ema50_ema200_cross(
    df4h: pd.DataFrame, ema_fast: int = 50, ema_slow: int = 200,
) -> pd.Series:
    """Capa 1 — candidato B: `sign(EMA50_4H - EMA200_4H)`. Diseño formal
    cerrado 2026-08-22 (checkpoint de priorización de Espacio 5, elección
    entre Bias B/Bias C — ninguno de los dos "mejor" ex ante, B elegido por
    reutilización de primitivas ya existentes, no por expectativa de PF).

    `EMA50_4H`/`EMA200_4H` se calculan vía `dc_v1.ema(df4h["close"],
    timeperiod)` — la MISMA función genérica que ya usa
    `bias_A_ema200_neutral` con `ema_period=200`, sin ninguna fórmula de EMA
    nueva (P-7/ADR-001: TA-Lib es la única fuente canónica).

    Clasificación:
        LONG  (+1) si EMA50_4H > EMA200_4H
        SHORT (-1) si EMA50_4H < EMA200_4H
        0          si son exactamente iguales (float, prácticamente
                   inalcanzable) o si cualquiera de las dos es NaN (warmup)

    SIN zona neutral por magnitud — a diferencia de `bias_A_ema200_neutral`
    (banda ±`neutral_pct`), acá no hay ninguna tolerancia: una diferencia
    arbitrariamente pequeña pero no nula entre EMA50 y EMA200 resuelve
    direccionalmente (+1/-1), nunca a 0. Decisión explícita (diseño formal
    2026-08-22): `FRAMEWORK.md` no menciona ninguna banda para B (a
    diferencia de A, que sí especifica "±1%" en su propia línea) — no se
    introduce una por analogía. El único 0 es el caso estructural de
    arriba, no una zona de indiferencia deliberada.

    Convención NaN->0 vía `np.where` (nunca `np.sign`): sigue la misma
    convención ya documentada y deliberada de `bias_A_ema200_neutral` —
    "NaN no cumple ninguna rama y cae en 0" — porque ambas son candidatos
    del mismo registro (`BIAS_LAYERS`) y deben comportarse igual ante
    warmup. Distinto, a propósito, de `dc_v1.derive_htf_bias` (que usa
    `np.sign` y LANZA ante NaN) — esa función resuelve un problema distinto
    (la columna interna fija del pipeline `dc_v1`, no un candidato de
    `BIAS_LAYERS`), no es la convención a imitar acá.

    Estado direccional por vela 4H, NUNCA un evento puntual de cruce:
    produce un valor para CADA fila de `df4h` (dominio continuo), como
    exige `BiasFn = Callable[[pd.DataFrame], pd.Series]` — la
    interpretación "evento de cruce" (bias definido solo en la vela donde
    ocurre el cruce) no encajaría en ese contrato en absoluto (eso es lo
    que existe Capa 2/`TriggerFn` para modelar), así que la arquitectura de
    3 capas resuelve esa ambigüedad, no una elección de conveniencia.

    Sin `shift` interno — igual que `bias_A_ema200_neutral`, el
    desplazamiento anti-lookahead (evitar mirar la vela 4H todavía en
    formación) lo aplica `apply_bias` externamente
    (`scripts/bias_campaign.py`), no esta función.
    """
    fast = dc_v1.ema(df4h["close"], ema_fast)
    slow = dc_v1.ema(df4h["close"], ema_slow)
    diff = fast - slow
    bias = np.where(diff > 0, 1, np.where(diff < 0, -1, 0))
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

    Rango de iteración (`range(warmup, n-2)`, `warmup=25`) preservado tal
    cual desde el port original. EMA/ATR vía `dc_v1.ema()`/`dc_v1.atr()`
    desde la Iniciativa B (antes replicaban `pandas.ewm` de
    `backtest.py::build_features` literalmente) — `warmup=25` sigue siendo
    mayor que el warmup NaN real de TA-Lib para cualquiera de los 3
    indicadores acá (8/20/13 velas para EMA9/EMA21/ATR14 respectivamente),
    así que el rango de iteración no necesita ajustarse.
    """
    close, high, low = df1h["close"], df1h["high"], df1h["low"]
    ema_f = dc_v1.ema(close, ema_fast)
    ema_s = dc_v1.ema(close, ema_slow)
    atr = dc_v1.atr(high, low, close, atr_period)

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
# Capa 2 — candidato D: ruptura y cierre fuera de rango de N velas            #
# (FRAMEWORK.md, candidato declarado pero nunca implementado hasta ahora —    #
# Rama B / revisión estratégica global, 2026-08-13). Familia de canal/        #
# breakout, conceptualmente distinta tanto de Sweep+BOS (A/B/C, estructura de #
# liquidez) como de T1 (cruce de EMAs) — no depende de ningún indicador ni de #
# niveles de sweep/BOS, solo del rango high/low de las `range_lookback`       #
# velas ANTERIORES a la vela evaluada (la vela de ruptura no se incluye en su #
# propio rango de referencia).                                                #
# --------------------------------------------------------------------------- #
def trigger_D_range_breakout(
    df1h: pd.DataFrame, range_lookback: int = 10,
) -> list[TriggerEvent]:
    """Capa 2 — candidato D: ruptura y cierre fuera del rango de las
    `range_lookback` (10, valor ya declarado en FRAMEWORK.md — no una
    elección nueva) velas 1H inmediatamente anteriores. `direction`="long" si
    el cierre de la vela actual supera el máximo de ese rango; "short" si cae
    por debajo del mínimo — determinado solo por la acción del precio, sin
    mirar bias ni sesión (mismo principio de composición que
    `trigger_A_sweep_bos`/`trigger_T1_ema_cross`). `meta` queda vacío: a
    diferencia de Sweep+BOS, este candidato no produce niveles de
    sweep/bos_level, por lo que es compatible con `entry_C_market_close`/
    `entry_D_next_candle_open` pero NO con `entry_A_pullback_50` (que
    requiere `event.meta["bos_level"]`, ausente acá — mismo tipo de
    incompatibilidad estructural ya documentado para T1 en el cierre de
    Espacio 4).

    Sin filtro de riesgo degenerado interno (a diferencia de
    `trigger_T1_ema_cross`, que lo replica para preservar paridad exacta con
    `backtest.py::find_entries`): este candidato no tiene contraparte legacy
    que igualar, así que ese chequeo queda enteramente a cargo de quien
    orqueste (`find_entries_for_trigger`/`find_entries_for_entry`), mismo
    patrón ya usado por `trigger_A_sweep_bos`.
    """
    events: list[TriggerEvent] = []
    for i in range(range_lookback, len(df1h)):
        window = df1h.iloc[i - range_lookback:i]
        candle = df1h.iloc[i]
        range_high = window["high"].max()
        range_low = window["low"].min()

        if candle["close"] > range_high:
            events.append(TriggerEvent(entry_idx=i, direction="long", meta={}))
        elif candle["close"] < range_low:
            events.append(TriggerEvent(entry_idx=i, direction="short", meta={}))
    return events


# --------------------------------------------------------------------------- #
# Capa 2 — candidato C: Solo BOS, sin sweep previo (FRAMEWORK.md, candidato    #
# declarado pero nunca implementado hasta ahora — diseño formal 2026-08-19,   #
# Trigger C / priorización de Espacio 5). Ablación de trigger_A_sweep_bos:     #
# conserva EXACTAMENTE la fórmula de nivel/confirmación de `_detect_bos`      #
# (arriba), elimina la precondición de sweep previo. Función enteramente      #
# nueva y aislada — NO modifica `_detect_sweep_at`/`_detect_bos`/             #
# `trigger_A_sweep_bos`, que permanecen exactamente iguales.                  #
# --------------------------------------------------------------------------- #
def trigger_C_bos_only(
    df1h: pd.DataFrame, bos_lookback: int = 5, bos_max_candles: int = 3,
) -> list[TriggerEvent]:
    """Capa 2 — candidato C: ruptura de estructura (BOS) sin requisito de
    Liquidity Sweep previo. Diseño formal cerrado 2026-08-19 (sesión de
    trabajo dedicada — inspección de código, formalización matemática,
    prueba de ablación, análisis de causalidad, y resolución del filtro de
    riesgo degenerado — antes de escribir esta implementación).

    Para cada índice `i` ("ancla", `bos_lookback-1 <= i <= len(df1h)-2`): la
    ventana de referencia es `df1h.iloc[i-bos_lookback+1 : i+1]` —
    EXACTAMENTE las mismas `bos_lookback` velas, INCLUYENDO `i`, que usa
    `_detect_bos` para su vela de sweep (`ref = df1h.iloc[max(0,
    sweep_idx-bos_lookback+1):sweep_idx+1]`) — fidelidad literal a esa
    fórmula, no una reinterpretación. `level_long` = máximo de `high` de esa
    ventana; `level_short` = mínimo de `low`. La ventana de confirmación es
    `df1h.iloc[i+1 : i+bos_max_candles+1]` (truncada al final de la serie),
    misma fórmula que `_detect_bos`.

    A diferencia de `trigger_A_sweep_bos` (donde la dirección viene dada por
    el sweep, una sola evaluada), acá LONG y SHORT se evalúan de forma
    INDEPENDIENTE en cada ancla: se busca, por separado, la primera vela de
    la ventana de confirmación cuyo cierre rompe `level_long` (evento LONG)
    y la primera cuyo cierre rompe `level_short` (evento SHORT). Ambos
    pueden coexistir desde el mismo ancla `i` si ambas direcciones se
    confirman dentro de la misma ventana (whipsaw) — un caso que no puede
    ocurrir en `trigger_A_sweep_bos`, donde la dirección ya viene fijada de
    antemano. Esta regla — evaluación independiente, NO "primera
    confirmación gana" — es la que garantiza la propiedad de ablación: para
    todo `(i, dirección)` donde `trigger_A_sweep_bos` produce un evento
    (sweep confirmado + BOS confirmado), esta función produce el MISMO
    evento (mismo `bos_level`, mismo `bos_idx`) para ese `(i, dirección)`,
    porque ambas evalúan exactamente la misma fórmula sobre las mismas
    ventanas — es decir, Eventos(`trigger_A_sweep_bos`) ⊆
    Eventos(`trigger_C_bos_only`), una relación de subconjunto demostrable,
    no aproximada (ver `research/tests/test_layers.py`,
    `test_trigger_c_events_subset_property_vs_sweep_bos`). Con la regla
    alternativa ("primera confirmación gana") esa propiedad NO se cumple en
    casos raros de whipsaw en un ancla que además fue sweep — por eso se
    descartó en el diseño formal.

    `entry_idx` es SIEMPRE la vela de confirmación (`bos_idx`), NUNCA el
    ancla `i` — usar `i` sería look-ahead (la ruptura todavía no está
    confirmada en `i`). `meta` queda vacío (`{}`): a diferencia de
    `trigger_A_sweep_bos`, este candidato no tiene un concepto de
    `swing_low`/`swing_high` (esos provienen específicamente de la ventana
    de swing del sweep, que no existe acá) — fabricar esos campos
    artificialmente introduciría una convención sin respaldo, decisión
    explícita de no hacerlo. Por tanto, igual que `trigger_D_range_breakout`
    y `trigger_T1_ema_cross`, es compatible con `entry_C_market_close`/
    `entry_D_next_candle_open` pero NO con `entry_A_pullback_50` (requiere
    `event.meta["bos_level"]`/`swing_low`/`swing_high`, ausentes acá).

    Sin filtro de riesgo degenerado interno (decisión explícita, ver diseño
    formal): a diferencia de `trigger_T1_ema_cross` (que lo replica
    ÚNICAMENTE para preservar paridad exacta con una implementación legacy
    previa a la migración — una razón histórica específica de T1, no un
    requisito general del contrato `TriggerFn`, ver nota de composición más
    abajo), este candidato delega esa validación enteramente al orquestador
    (`find_entries_for_entry`), mismo patrón que `trigger_A_sweep_bos`/
    `trigger_D_range_breakout`: el chequeo de riesgo degenerado del
    orquestador se aplica de forma idéntica e incondicional a cualquier
    evento crudo, sin importar qué Trigger lo produjo — agregarlo acá no
    cambiaría ningún trade final (`n_trades`), solo introduciría en Capa 2
    una dependencia de ATR/Gestión que el contrato del módulo asigna a otra
    capa (ver docstring del módulo, arriba). Esta función no recibe
    `atr_mult`/`atr_period`/`cfg` en su firma — verificable estructuralmente,
    no solo por esta nota.

    Orden de salida: a diferencia de `trigger_A_sweep_bos`/
    `trigger_D_range_breakout` (donde cada ancla produce a lo sumo un
    evento, en orden creciente de `i` casi siempre coincidente con orden
    creciente de `entry_idx`), acá — con anclas densas (cada vela) y
    ventanas de confirmación que se solapan entre anclas consecutivas — el
    orden de generación (por ancla, luego por dirección) NO garantiza
    `entry_idx` no-decreciente. `backtest.run_config` recorre `entries` en
    el orden recibido y depende de ese orden cronológico para su lógica de
    `busy_until` ("una posición a la vez") — por eso, antes de devolver la
    lista, se ordena explícitamente por `entry_idx`. Decisión tomada
    durante la implementación, no parte del contrato original: no cambia
    ningún evento ni introduce ningún filtro, solo garantiza el orden que
    el resto del motor ya asume.
    """
    events: list[TriggerEvent] = []
    n = len(df1h)
    for i in range(bos_lookback - 1, n - 1):
        ref = df1h.iloc[i - bos_lookback + 1: i + 1]
        level_long = ref["high"].max()
        level_short = ref["low"].min()

        window = df1h.iloc[i + 1: min(i + bos_max_candles + 1, n)]

        for idx, row in window.iterrows():
            if row["close"] > level_long:
                events.append(TriggerEvent(
                    entry_idx=df1h.index.get_loc(idx), direction="long", meta={},
                ))
                break
        for idx, row in window.iterrows():
            if row["close"] < level_short:
                events.append(TriggerEvent(
                    entry_idx=df1h.index.get_loc(idx), direction="short", meta={},
                ))
                break

    events.sort(key=lambda ev: ev.entry_idx)
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
# Capa 3 — candidato D: apertura de la vela siguiente al evento de Capa 2     #
# (FRAMEWORK.md: "apertura de vela siguiente al BOS"). Generalizado a         #
# "vela siguiente al evento" con el mismo criterio ya aplicado a C: el        #
# mecanismo no depende de qué candidato de Capa 2 produjo el evento. Nunca    #
# existió en bot.py/backtest.py — candidato declarado en FRAMEWORK.md pero    #
# no implementado hasta ahora (a diferencia de A/C, no hay legacy que portar; #
# ver research/tests/test_layers.py para su test de comportamiento en vez de  #
# paridad).                                                                   #
# --------------------------------------------------------------------------- #
def entry_D_next_candle_open(df1h: pd.DataFrame, event: TriggerEvent) -> EntrySignal:
    """Precio de entrada = apertura de la vela siguiente a `event.entry_idx`
    (orden a mercado, un paso después que C). No usa `event.meta` — igual que
    entry_C_market_close, el precio no depende de niveles de sweep/BOS."""
    return EntrySignal(price=float(df1h["open"].iloc[event.entry_idx + 1]))


# --------------------------------------------------------------------------- #
# Registros: nombre de candidato (FRAMEWORK.md) -> función.                  #
# --------------------------------------------------------------------------- #
BIAS_LAYERS: dict[str, BiasFn] = {
    "A_ema200_neutral": bias_A_ema200_neutral,
    "B_ema50_ema200_cross": bias_B_ema50_ema200_cross,
}
TRIGGER_LAYERS: dict[str, TriggerFn] = {
    "A_sweep_bos": trigger_A_sweep_bos,
    "T1_ema_cross": trigger_T1_ema_cross,
    "D_range_breakout": trigger_D_range_breakout,
    "C_bos_only": trigger_C_bos_only,
}
ENTRY_LAYERS: dict[str, EntryFn] = {
    "A_pullback_50": entry_A_pullback_50,
    "C_market_close": entry_C_market_close,
    "D_next_candle_open": entry_D_next_candle_open,
}
