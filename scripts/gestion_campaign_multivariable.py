#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/gestion_campaign_multivariable.py — Espacio 1: interacción
multivariable de Gestión (`distance` × `activation` × `be` variando
SIMULTÁNEAMENTE, no uno a la vez como H2/I1), bajo Bias=A/Trigger=
T1_ema_cross/Entry=C_market_close/atr_mult=1.5/atr_period=14/max_hold=20/
risk=0.005/sesión=dcv1_activo_15h fijos. Contrato acordado 2026-08-13
(versión final, tras 2 correcciones metodológicas: contabilidad de
evidencia nueva vs. réplica, y terminología del ancla como "referencia
interna" en vez de "control").

Contexto: H2.1/H2.2/H2.3 e I1-distance/I1-activation/I1-be barrieron estos
3 parámetros DE A UNO A LA VEZ (156 filas candidatas de I1, 0 con
`gate_pass`, máximo PF 1.476) — ninguna campaña anterior probó si una
combinación conjunta de los 3 parámetros produce una interacción que
ninguno muestra aisladamente. Esa es la celda que este script evalúa.

Hipótesis (Espacio 1) a falsificar — hipótesis de FAMILIA, sin combinación
motivadora individual (a diferencia de `atr_mult`=3.0 en `atr_mult`×sesión,
que sí tenía un antecedente concreto que apuntaba a ese valor; acá ningún
CSV del repositorio señala una combinación multivariada específica):
existe al menos una combinación (`distance`, `activation`, `be`) dentro del
grid de 36 que, bajo Bias=A/Trigger=T1_ema_cross/Entry=C_market_close/
atr_mult=1.5/sesión=dcv1_activo_15h fijos, supera los 4 gates de
FRAMEWORK.md en 2022 Y 2023 para al menos un activo. Falsificada si,
evaluadas las 36 combinaciones, ninguna sobrevive ambos años en ningún
activo. El mejor resultado observado NO se reinterpreta retroactivamente
como "hipótesis primaria" tras ver los datos.

Sesión: ÚNICAMENTE `dcv1_activo_15h` — NO se corre `control_8h` en esta
campaña (decisión explícita 2026-08-13: la evidencia acumulada ya
caracteriza `control_8h` como estructuralmente incapaz de resolver
frecuencia; correr esta campaña también bajo esa sesión duplicaría un
problema ya cerrado en vez de aislar la pregunta de interacción
multivariable de Gestión, que es la pregunta nueva). Consecuencia: no hay
brazo de control bajo otra sesión, por lo que no se calcula ΔPF/Δfreq
(no existe contraparte de sesión contra la cual restar) — a diferencia de
toda campaña "×sesión" anterior del programa.

Grid — EXCLUSIVAMENTE las grillas base de H2, sin extensiones por
contingencia, sin el conjunto no-dominado de I1 (decisión explícita
2026-08-13, para no ampliar el espacio de comparaciones múltiples más allá
de lo ya usado en H2):
    distance   ∈ {0.5, 0.75, 1.0, 1.5}   (grid base H2.1)
    activation ∈ {1.5, 2.0, 2.5}         (grid base H2.2)
    be         ∈ {0.5, 1.0, 1.5}         (grid base H2.3)
4 × 3 × 3 = 36 combinaciones. El punto ancla V3-A (distance=1.0,
activation=2.0, be=1.0) está DENTRO de este grid — a diferencia del
conjunto no-dominado de I1 (Paso 0), que había excluido `distance`=1.0 por
estar dominada en todos los contextos de H2.1.

Ancla / referencia interna (terminología corregida 2026-08-13 — NO
"control", porque no existe un brazo bajo otra sesión; es el punto V3-A de
referencia dentro del MISMO espacio experimental dcv1_activo_15h):
`distance`=1.0/`activation`=2.0/`be`=1.0. Se identifica con `role="anchor"`
— nunca `hypothesis="primary"` ni ningún campo que sugiera que es la
hipótesis motivadora. Participa en `summarize_decision()` exactamente
igual que las otras 35 combinaciones — su estatus de ancla no la excluye
de ser reportada como sobreviviente si lo fuera.

Contabilidad de evidencia (corregida 2026-08-13 — la contabilidad original
decía "216 filas, todas nuevas", lo cual era incorrecto): de las 36
combinaciones, 7 tienen antecedente histórico exacto bajo dcv1_activo_15h
(el ancla + los 2 bordes univariados de cada uno de los 3 parámetros, con
los otros 2 parámetros en su ancla) y se usan como referencia de Fase A.
Esas 7 combinaciones también se recalculan como parte del barrido uniforme
de Fase B (NO se reutiliza el objeto ya computado en Fase A — a diferencia
del rol dual de `atr_mult`×sesión; acá se recalculan de cero, simplemente
para mantener el barrido de las 36 combinaciones uniforme en el código, sin
un caso especial). Por eso:
  - 216 filas candidatas físicas (36 combinaciones × 3 activos × 2 años).
  - 42 filas (7 combinaciones × 6 activo/año) son RÉPLICA/verificación —
    no cuentan como evidencia científica nueva.
  - 174 filas (29 combinaciones × 6 activo/año) son evidencia
    GENUINAMENTE NUEVA.
  - `distance`=0.75 NUNCA tiene antecedente bajo dcv1_activo_15h en ningún
    CSV del repositorio (H2.1 solo la probó bajo `control_8h`; el Paso 0
    de I1 la podó del grid de I1-distance por estar dominada) — pese a ser
    un "borde" univariado del grid, es evidencia nueva, no réplica.

Fase A (48 verificaciones) — SOLO contra referencias reales ya publicadas,
sin inventar ninguna para las 29 combinaciones sin antecedente:
  - Ancla (1.0/2.0/1.0): 2 referencias independientes —
    `gestion_campaign_session_results.csv` (candidate="dcv1_activo_15h")
    y `integration_campaign_activation_results.csv` (candidate=
    "2.0 | dcv1_activo_15h", que fijó be=1.0R/distance=1.0R — es la MISMA
    celda vista desde el contrato de I1-activation). 6 combos × 2 = 12.
  - `distance` sola (activation=2.0/be=1.0 fijos), valores {0.5, 1.5}
    (excluye 1.0, ya cubierto por el ancla): contra
    `integration_campaign_distance_results.csv`. 6 combos × 2 valores = 12.
  - `activation` sola (distance=1.0/be=1.0 fijos), valores {1.5, 2.5}:
    contra `integration_campaign_activation_results.csv`. 6 × 2 = 12.
  - `be` sola (distance=1.0/activation=2.0 fijos), valores {0.5, 1.5}:
    contra `integration_campaign_be_results.csv`. 6 × 2 = 12.
  Total: 48. Si CUALQUIERA falla, `AssertionError` inmediato — la corrida
  aborta antes de calcular una sola de las 216 filas candidatas.
  `distance`=0.75 y las 28 combinaciones restantes (2 o 3 parámetros
  simultáneamente distintos del ancla) NO tienen verificación cruzada —
  se calculan en Fase B sin control de integridad externo, por diseño.

Riesgo de comparaciones múltiples: 36 combinaciones candidatas — el mayor
número de candidatos simultáneos evaluado en una sola campaña de este
programa. Documentado explícitamente en el reporte (`print_decision`). El
máximo PF observado entre las 36 combinaciones NO se interpreta como
evidencia confirmatoria aislada. Si hay múltiples sobrevivientes, se
reportan TODOS, rankeados por PF 2023 dentro de cada activo — sin elegir
retroactivamente un "ganador" del conjunto.

Fijo durante toda la campaña: Bias=A, Trigger=T1_ema_cross, Entry=
C_market_close, `atr_mult`=1.5 (ancla de H1), `atr_period`=14 (excluido,
no-op estructural, Espacio 2), `max_hold`=20 (fijo, ya evaluado y
falsificado en Espacio 2), `risk`=0.005 (excluido, invariante a gates,
Espacio 2), sesión=`dcv1_activo_15h` ÚNICA, una posición a la vez, datasets
dc_v1 canónicos, disciplina P-3, modelo de costos, gates literales de
FRAMEWORK.md, 2024 ciego. Sin V3-B en paralelo.

Invarianza estructural: `distance`/`activation`/`be` no afectan la
generación de entradas (verificado repetidamente en H2.1/H2.2/H2.3/I1×3 —
estos 3 parámetros solo actúan dentro de `simulate_v3`, nunca en la
detección de eventos ni en `risk_pts`). Las entradas se computan UNA SOLA
VEZ por (activo, año) bajo `dcv1_activo_15h` y se reutilizan para las 36
combinaciones de salida — mismo principio ya usado en H2.1/H2.2/H2.3, ahora
extendido a variación simultánea de 3 parámetros.

Reutilización de infraestructura (sin modificar ninguno de los archivos
reutilizados, ni `backtest.py`): de scripts/bias_campaign.py —
`to_backtest_frame`, `gate_check`, `summarize_decision`. De
scripts/trigger_campaign.py — `load_asset_year`, `find_entries_for_trigger`.
De scripts/gestion_campaign_session.py — `SESSION_WINDOWS` (una sola
ventana usada acá, `dcv1_activo_15h`).

Requiere `data/raw/` poblado. BLOQUEADO en este sandbox (HTTP 451,
data/raw/ vacío) — validado acá solo estructuralmente, más una porción real
sobre los CSV históricos ya committeados (que no requieren data/raw/), ver
research/tests/test_gestion_campaign_multivariable.py.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/gestion_campaign_multivariable.py              # Fase 1+2 (incluye Fase A+B internas)
    python scripts/gestion_campaign_multivariable.py --blind        # Fase 3: 2024 ciego (requiere --candidate)
"""
from __future__ import annotations

import itertools
import sys
sys.path.insert(0, ".")

import argparse

import pandas as pd

import backtest
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as trigger_camp
import scripts.gestion_campaign_session as session_camp
from market_data import ASSETS

# --------------------------------------------------------------------------- #
# Config de la campaña                                                        #
# --------------------------------------------------------------------------- #
BIAS_CANDIDATE = "A"              # fijado en trigger_camp.load_asset_year, no parametrizado acá
TRIGGER_CANDIDATE = "T1_ema_cross"

ATR_MULT_ANCHOR = 1.5    # ancla de H1, congelado
ATR_PERIOD_ANCHOR = 14   # fijo — excluido, ver Espacio 2
MAX_HOLD_ANCHOR = 20     # fijo — ya evaluado y falsificado en Espacio 2

SESSION_LABEL = "dcv1_activo_15h"   # ÚNICA sesión de esta campaña — sin control_8h
SESSION_WINDOW = session_camp.SESSION_WINDOWS[SESSION_LABEL]

# Grillas BASE de H2 — sin extensión por contingencia, sin el conjunto
# no-dominado de I1 (Paso 0). Decisión explícita 2026-08-13.
DISTANCE_VALUES = (0.5, 0.75, 1.0, 1.5)
ACTIVATION_VALUES = (1.5, 2.0, 2.5)
BE_VALUES = (0.5, 1.0, 1.5)

GRID = tuple(itertools.product(DISTANCE_VALUES, ACTIVATION_VALUES, BE_VALUES))
assert len(GRID) == 36, f"grid mal formado: {len(GRID)} combinaciones, se esperaban 36"

ANCHOR = (1.0, 2.0, 1.0)  # (distance, activation, be) — V3-A, referencia interna
assert ANCHOR in GRID, "el ancla V3-A debe estar dentro del grid"

# Las 7 combinaciones con antecedente histórico bajo dcv1_activo_15h (ancla +
# 2 bordes por cada uno de los 3 parámetros, con los otros 2 en su ancla) —
# ver docstring del módulo, sección "Fase A". distance=0.75 NUNCA tiene
# antecedente bajo dcv1_activo_15h (podada del grid de I1-distance por el
# Paso 0), por eso NO aparece acá pese a ser un valor "de borde".
REPLICA_COMBOS = frozenset({
    ANCHOR,
    (0.5, 2.0, 1.0), (1.5, 2.0, 1.0),   # distance sola
    (1.0, 1.5, 1.0), (1.0, 2.5, 1.0),   # activation sola
    (1.0, 2.0, 0.5), (1.0, 2.0, 1.5),   # be sola
})
assert len(REPLICA_COMBOS) == 7, f"se esperaban 7 combinaciones con antecedente, hay {len(REPLICA_COMBOS)}"
assert REPLICA_COMBOS <= set(GRID), "las combinaciones de referencia deben estar dentro del grid"

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision

EXIT_CONFIG_LABEL = (
    "Espacio 1 — Gestión multivariable (distance x activation x be simultáneos; "
    "atr_mult=1.5/atr_period=14/max_hold=20 fijos; sesión=dcv1_activo_15h única, "
    "sin control_8h)"
)

_SESSION_REF_PATH = "gestion_campaign_session_results.csv"
_SESSION_REF_EXIT_CONFIG = "V3-A (1R/2R/1R)"
_I1_ACTIVATION_REF_PATH = "integration_campaign_activation_results.csv"
_I1_DISTANCE_REF_PATH = "integration_campaign_distance_results.csv"
_I1_BE_REF_PATH = "integration_campaign_be_results.csv"

# Campos comparables entre TODAS las referencias.
_CHECK_FIELDS = ("pf", "wr", "exp_r", "max_dd", "freq")


def _label(distance: float, activation: float, be: float) -> str:
    return f"{distance} | {activation} | {be}"


CANDIDATES = tuple(_label(*combo) for combo in GRID)


# --------------------------------------------------------------------------- #
# Orquestación — entradas independientes de (distance, activation, be),       #
# computadas UNA sola vez por (activo, año) y reutilizadas en las 36          #
# combinaciones (ver docstring, "Invarianza estructural").                    #
# --------------------------------------------------------------------------- #
def _entries_for_asset_year(asset: str, year: int):
    df_full = trigger_camp.load_asset_year(asset, year)
    cfg = backtest.Config(atr_mult=ATR_MULT_ANCHOR, atr_period=ATR_PERIOD_ANCHOR,
                           max_hold=MAX_HOLD_ANCHOR, sessions=SESSION_WINDOW)
    frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
    entries = trigger_camp.find_entries_for_trigger(frame, cfg, TRIGGER_CANDIDATE)
    return frame, cfg, entries


def _run_combo(frame: pd.DataFrame, cfg: "backtest.Config", entries: list[dict],
               distance: float, activation: float, be: float):
    exit_cfg = {"be": be, "activation": activation, "distance": distance}
    trades = backtest.run_config(frame, entries, exit_cfg, cfg)
    m = backtest.metrics(trades, cfg)
    return trades, m


def _row(asset: str, year: int, distance: float, activation: float, be: float,
          entries: list[dict], trades: pd.DataFrame, m: dict | None, role: str) -> dict:
    combo = (distance, activation, be)
    return {
        "asset": asset, "year": year, "role": role, "session": SESSION_LABEL,
        "distance": distance, "activation": activation, "be": be,
        "candidate": _label(distance, activation, be),
        "evidence": "replica" if combo in REPLICA_COMBOS else "new",
        "exit_config": EXIT_CONFIG_LABEL,
        "n_entries": len(entries), "n_trades": len(trades),
        "metrics": m, "gate_pass": gate_check(m),
    }


# --------------------------------------------------------------------------- #
# Fase A — 48 verificaciones, SOLO contra referencias reales ya publicadas    #
# --------------------------------------------------------------------------- #
def _session_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_SESSION_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["candidate"] == SESSION_LABEL)
               & (df["exit_config"] == _SESSION_REF_EXIT_CONFIG)]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para el ancla (distance=1.0/"
            f"activation=2.0/be=1.0), activo={asset}, año={year} en "
            f"{_SESSION_REF_PATH} — no se puede verificar la Fase A."
        )
    return match.iloc[0]


def _i1_activation_anchor_reference(asset: str, year: int) -> pd.Series:
    """La celda activation=2.0 de I1-activation fijó be=1.0R/distance=1.0R
    en su ancla — es la MISMA combinación (1.0/2.0/1.0), computada por un
    script independiente."""
    df = pd.read_csv(_I1_ACTIVATION_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["role"] == "candidate")
               & (df["candidate"] == f"2.0 | {SESSION_LABEL}")]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para el ancla (distance=1.0/"
            f"activation=2.0/be=1.0), activo={asset}, año={year} en "
            f"{_I1_ACTIVATION_REF_PATH} — no se puede verificar la Fase A."
        )
    return match.iloc[0]


def _i1_distance_reference(asset: str, year: int, distance: float) -> pd.Series:
    df = pd.read_csv(_I1_DISTANCE_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["role"] == "candidate")
               & (df["candidate"] == f"{distance} | {SESSION_LABEL}")]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para distance={distance} "
            f"(activation=2.0/be=1.0), activo={asset}, año={year} en "
            f"{_I1_DISTANCE_REF_PATH} — no se puede verificar la Fase A."
        )
    return match.iloc[0]


def _i1_activation_reference(asset: str, year: int, activation: float) -> pd.Series:
    df = pd.read_csv(_I1_ACTIVATION_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["role"] == "candidate")
               & (df["candidate"] == f"{activation} | {SESSION_LABEL}")]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para activation={activation} "
            f"(distance=1.0/be=1.0), activo={asset}, año={year} en "
            f"{_I1_ACTIVATION_REF_PATH} — no se puede verificar la Fase A."
        )
    return match.iloc[0]


def _i1_be_reference(asset: str, year: int, be: float) -> pd.Series:
    df = pd.read_csv(_I1_BE_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["role"] == "candidate")
               & (df["candidate"] == f"{be} | {SESSION_LABEL}")]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para be={be} (distance=1.0/"
            f"activation=2.0), activo={asset}, año={year} en {_I1_BE_REF_PATH} "
            f"— no se puede verificar la Fase A."
        )
    return match.iloc[0]


def _verify_against(cell_label: str, asset: str, year: int, ref_name: str,
                     n_entries: int, n_trades: int, m: dict | None,
                     ref_row: pd.Series) -> None:
    mismatches = []
    if n_entries != ref_row["n_entries"]:
        mismatches.append(f"n_entries: esperado={ref_row['n_entries']!r}, obtenido={n_entries!r}")
    if n_trades != ref_row["n_trades"]:
        mismatches.append(f"n_trades: esperado={ref_row['n_trades']!r}, obtenido={n_trades!r}")
    for field in _CHECK_FIELDS:
        expected = ref_row[field]
        actual = m.get(field) if m else None
        if actual != expected:
            mismatches.append(f"{field}: esperado={expected!r}, obtenido={actual!r}")
    if mismatches:
        raise AssertionError(
            f"Fase A (verificación de integridad) falló — celda={cell_label}, "
            f"activo={asset}, año={year}, referencia={ref_name}:\n  "
            + "\n  ".join(mismatches) +
            f"\nLa corrida aborta antes de calcular las 216 filas candidatas."
        )


def run_integrity_check(asset: str, year: int):
    """Fase A para un (activo, año) — 8 de las 48 verificaciones totales (2
    para el ancla + 1 para cada uno de los 6 bordes univariados). Corre las
    7 combinaciones con antecedente y las verifica; devuelve frame/cfg/
    entries (compartidos con Fase B) — las 7 filas ya computadas acá NO se
    reutilizan en Fase B, que las recalcula de cero como parte del barrido
    uniforme de 36 combinaciones (ver docstring del módulo). Revienta con
    AssertionError (sin devolver nada parcial) si cualquiera de las 8
    verificaciones falla."""
    frame, cfg, entries = _entries_for_asset_year(asset, year)

    # Ancla — 2 referencias independientes.
    trades_anchor, m_anchor = _run_combo(frame, cfg, entries, *ANCHOR)
    anchor_label = _label(*ANCHOR)
    _verify_against(anchor_label, asset, year, _SESSION_REF_PATH,
                     len(entries), len(trades_anchor), m_anchor, _session_reference(asset, year))
    _verify_against(anchor_label, asset, year, _I1_ACTIVATION_REF_PATH,
                     len(entries), len(trades_anchor), m_anchor,
                     _i1_activation_anchor_reference(asset, year))

    # Borde de distance (activation=2.0/be=1.0 fijos).
    for d in (0.5, 1.5):
        combo = (d, 2.0, 1.0)
        trades, m = _run_combo(frame, cfg, entries, *combo)
        _verify_against(_label(*combo), asset, year, _I1_DISTANCE_REF_PATH,
                         len(entries), len(trades), m, _i1_distance_reference(asset, year, d))

    # Borde de activation (distance=1.0/be=1.0 fijos).
    for a in (1.5, 2.5):
        combo = (1.0, a, 1.0)
        trades, m = _run_combo(frame, cfg, entries, *combo)
        _verify_against(_label(*combo), asset, year, _I1_ACTIVATION_REF_PATH,
                         len(entries), len(trades), m, _i1_activation_reference(asset, year, a))

    # Borde de be (distance=1.0/activation=2.0 fijos).
    for b in (0.5, 1.5):
        combo = (1.0, 2.0, b)
        trades, m = _run_combo(frame, cfg, entries, *combo)
        _verify_against(_label(*combo), asset, year, _I1_BE_REF_PATH,
                         len(entries), len(trades), m, _i1_be_reference(asset, year, b))

    return frame, cfg, entries


# --------------------------------------------------------------------------- #
# Fase B — barrido completo de las 36 combinaciones (solo tras Fase A         #
# completa sin excepción para las 6 combinaciones activo/año)                 #
# --------------------------------------------------------------------------- #
def run_campaign(assets: tuple[str, ...] = ASSETS,
                  years: tuple[int, ...] = (IN_SAMPLE_YEAR, VALIDATION_YEAR)) -> list[dict]:
    """Fase 1(2022)+Fase 2(2023). Fase A completa para las 6 combinaciones
    (activo, año) ANTES de que arranque la Fase B — si run_integrity_check
    revienta en cualquier combinación, la excepción se propaga acá y la
    función nunca llega a calcular una sola fila candidata. NO incluye
    2024 — ver run_blind_test."""
    known_by_combo: dict[tuple[str, int], tuple] = {}
    for year in years:
        for asset in assets:
            known_by_combo[(asset, year)] = run_integrity_check(asset, year)  # Fase A

    rows: list[dict] = []
    for year in years:
        for asset in assets:
            frame, cfg, entries = known_by_combo[(asset, year)]
            for distance, activation, be in GRID:  # Fase B — las 36 combinaciones
                trades, m = _run_combo(frame, cfg, entries, distance, activation, be)
                role = "anchor" if (distance, activation, be) == ANCHOR else "candidate"
                rows.append(_row(asset, year, distance, activation, be, entries, trades, m, role))
    return rows


def run_blind_test(assets: tuple[str, ...] = ASSETS,
                    candidate: str | None = None) -> list[dict]:
    """Fase 3 (2024, ciego). Requiere `candidate` (string compuesto
    "{distance} | {activation} | {be}") ya congelado tras decidir con
    2022+2023. No corre Fase A acá (exclusiva de la fase 2022+2023)."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere un candidato ya congelado {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una "
            "decisión previa."
        )
    distance_str, activation_str, be_str = (p.strip() for p in candidate.split("|"))
    distance, activation, be = float(distance_str), float(activation_str), float(be_str)
    results: list[dict] = []
    for asset in assets:
        frame, cfg, entries = _entries_for_asset_year(asset, BLIND_YEAR)
        trades, m = _run_combo(frame, cfg, entries, distance, activation, be)
        role = "anchor" if (distance, activation, be) == ANCHOR else "candidate"
        results.append(_row(asset, BLIND_YEAR, distance, activation, be, entries, trades, m, role))
    return results


# --------------------------------------------------------------------------- #
# Reporte                                                                     #
# --------------------------------------------------------------------------- #
def results_to_frame(results: list[dict]) -> pd.DataFrame:
    rows = []
    for r in results:
        m = r["metrics"] or {}
        reasons = m.get("reasons") or {}
        freq = m.get("freq")
        n_entries = r["n_entries"]
        n_trades = r["n_trades"]
        months = (n_trades / freq) if freq else None
        entries_per_month = (n_entries / months) if months else None
        fill_rate = (n_trades / n_entries) if n_entries else None
        rows.append({
            "asset": r["asset"], "year": r["year"], "role": r["role"], "session": r["session"],
            "distance": r["distance"], "activation": r["activation"], "be": r["be"],
            "candidate": r["candidate"], "evidence": r["evidence"], "exit_config": r["exit_config"],
            "n_entries": n_entries, "n_trades": n_trades,
            "entries_per_month": round(entries_per_month, 2) if entries_per_month is not None else None,
            "fill_rate": round(fill_rate, 3) if fill_rate is not None else None,
            "gate_pass": r["gate_pass"],
            "pf": m.get("pf"), "wr": m.get("wr"), "exp_r": m.get("exp_r"),
            "avg_win": m.get("avg_win"), "avg_loss": m.get("avg_loss"),
            "total_r": m.get("total_r"), "max_dd": m.get("max_dd"), "freq": freq,
            # OJO: "be" ya es el parámetro de Gestión (columna arriba) — el
            # conteo de salidas por breakeven que backtest.metrics() llama
            # "be" se exporta acá como "be_exits" para evitar la colisión de
            # nombres (decisión técnica, ver informe de implementación).
            "be_exits": m.get("be"),
            "reason_stop": reasons.get("stop", 0), "reason_timeout": reasons.get("timeout", 0),
        })
    return pd.DataFrame(rows)


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  Espacio 1 — Gestión multivariable (distance x activation x be) bajo "
          f"dcv1_activo_15h única\n  Bias=A/Trigger=T1_ema_cross/Entry=C_market_close/"
          f"atr_mult=1.5 fijos\n{'='*100}")
    cols = ["asset", "year", "role", "distance", "activation", "be", "evidence",
            "n_entries", "n_trades", "entries_per_month", "fill_rate", "pf", "wr", "exp_r",
            "avg_win", "avg_loss", "total_r", "max_dd", "freq", "be_exits",
            "reason_stop", "reason_timeout", "gate_pass"]
    print(df[cols].to_string(index=False))

    replica = df[df["evidence"] == "replica"]
    new = df[df["evidence"] == "new"]
    print(f"\n{'-'*100}\n  Contabilidad de evidencia: {len(df)} filas físicas totales — "
          f"{len(replica)} réplica/verificación (7 combinaciones con antecedente) + "
          f"{len(new)} genuinamente nueva (29 combinaciones)\n{'-'*100}")

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (por año):\n{'-'*100}")
    passing = df[df["gate_pass"]]
    if passing.empty:
        print("  Ninguna combinación pasa los 4 gates.")
    else:
        print(passing[cols].to_string(index=False))


def print_decision(decision: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  DECISIÓN — sobrevivientes (ambos años, por activo) y ranking por PF 2023\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    survivors_any = decision[decision["survives_both_years"]]
    if not survivors_any.empty:
        print(
            f"\n  ADVERTENCIA — riesgo de comparaciones múltiples: este barrido evaluó "
            f"36 combinaciones candidatas (4 distance x 3 activation x 3 be) — el mayor "
            f"número de candidatos simultáneos evaluado en una sola campaña de este "
            f"programa. Todos los sobrevivientes se reportan sin elegir retroactivamente "
            f"un 'ganador'. La supervivencia 2022+2023 sigue siendo el criterio de "
            f"aceptación, no elimina por sí sola el riesgo de selección entre múltiples "
            f"candidatos evaluados."
        )

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
            print(f"\n  {asset}: ninguna de las 36 combinaciones (distance, activation, be) "
                  f"demuestra evidencia suficiente para cumplir los 4 gates de FRAMEWORK.md "
                  f"en 2022+2023 bajo dcv1_activo_15h.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="candidato ya congelado ('{distance} | {activation} | {be}') para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (el candidato ya congelado)")
        results = run_blind_test(candidate=args.candidate)
        df = results_to_frame(results)
        print_report(df)
        out_path = "gestion_campaign_multivariable_results.csv"
        df.to_csv(out_path, index=False)
        print(f"\nResultados exportados a {out_path} ({len(df)} filas)")
        return

    results = run_campaign()
    df = results_to_frame(results)
    print_report(df)
    out_path = "gestion_campaign_multivariable_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas — "
          f"36 combinaciones x 3 activos x 2 años = 216)")

    # Sin filtro por role: no existe role="control" en esta campaña (sin
    # control_8h) — el ancla (role="anchor") participa en la decisión igual
    # que las 35 combinaciones role="candidate".
    decision = summarize_decision(df)
    print_decision(decision)
    decision_path = "gestion_campaign_multivariable_decision.csv"
    decision.to_csv(decision_path, index=False)
    print(f"Decisión exportada a {decision_path} ({len(decision)} filas — "
          f"36 combinaciones x 3 activos = 108)")


if __name__ == "__main__":
    main()
