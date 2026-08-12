#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/gestion_campaign_atr_mult_session.py — `atr_mult` x sesión,
extensión residual de H1 hacia `dcv1_activo_15h`. Contrato acordado
2026-08-11. NO es una reapertura de Espacio 1 (Gestión multivariable,
cerrado por VoI insuficiente) ni de Espacio 2 (`max_hold`, falsificado) —
es una celda residual específica, con hipótesis previa concreta, nunca
descartada.

Contexto: H1 (`scripts/gestion_campaign_atr_mult.py`, cerrado,
`gestion_campaign_atr_mult_results.csv`) barrió `atr_mult` ∈
{1.0, 1.5(ancla), 2.0, 3.0} bajo `control_8h` ÚNICAMENTE. 0/48 filas pasan
los 4 gates. PF máximo de TODO el programa hasta la fecha: 1.567
(SOLUSDT/2023, `atr_mult`=3.0) — bloqueado EXCLUSIVAMENTE por frecuencia
(4.6/mes, bajo el piso de 6). `dcv1_activo_15h` ha resuelto sistemáticamente
el gate de frecuencia en cada bloque posterior (H2.1-3, I1x3, Espacio 2,
Espacio 3, G x sesión) sin haberse combinado nunca con `atr_mult`. Esa es la
celda que este script cierra.

Hipótesis PRIMARIA (la que motiva la campaña — ajuste acordado 2026-08-11,
NO diluir en el análisis): `atr_mult`=3.0 x `dcv1_activo_15h` supera los 4
gates de FRAMEWORK.md en 2022 Y 2023 para al menos un activo. El PF=1.567
es la motivación previa del experimento, NO evidencia de edge en sí mismo.

Grid SECUNDARIO, pre-especificado, NO motivador: `atr_mult` ∈ {1.0, 1.5, 2.0}
x `dcv1_activo_15h` se evalúan con el mismo protocolo y los mismos gates,
para mantener el grid completo de H1 (evitar sesgo de selección por omitir
valores ya probados) — no porque exista una hipótesis previa propia sobre
ellos. Cualquier resultado de estos tres valores se reporta explícitamente
etiquetado como grid secundario, nunca reformulado como pregunta original.

Paso 0 (dominancia Pareto, misma metodología de I1) — recalculado sobre las
24 filas V3-A de H1, por (activo, año), NO comparado entre activos: ningún
valor de `atr_mult` queda dominado (en pf, max_dd, exp_r) en los 6 contextos
simultáneamente (mismo patrón que `activation`/`be` en I1 — no se poda
nada). El grid se hereda completo de H1: {1.0, 1.5, 2.0, 3.0}
(`atr_mult_camp.ATR_MULT_VALUES`, reutilizado literal, no reintroducido acá)
— sin extensión por contingencia (no aplica: el grid ya viene fijado por
H1, no es un barrido nuevo que necesite regla de escalamiento).

Riesgo de comparaciones múltiples (ajuste acordado 2026-08-11): el grid
bajo `dcv1_activo_15h` evalúa 4 valores x 3 activos = 12 combinaciones
candidatas (`N_CANDIDATES_EVALUATED`). Un survivor aislado (una combinación
`atr_mult` x activo que sobrevive 2022+2023) se clasifica inicialmente como
CANDIDATO, no como hallazgo confirmado — sujeto al mismo escrutinio de
estabilidad interanual y de patrón ya aplicado en todo el programa. La
supervivencia 2022+2023 (`gate_check`/`summarize_decision`, sin modificar)
sigue siendo el criterio de aceptación, pero no elimina por sí sola el
riesgo de selección entre múltiples candidatos evaluados — no se aplica
ningún ajuste estadístico formal (tipo Bonferroni, sin precedente en este
programa), pero el riesgo se documenta explícitamente en el reporte
(`print_decision`) en vez de omitirse.

Diseño — dos tratamientos DISTINTOS por sesión, no un factorial simétrico:
  - `control_8h` (role="control"): las 24 filas (4 valores x 3 activos x
    2 años) se LEEN directamente de `gestion_campaign_atr_mult_results.csv`
    (H1), filtradas a `exit_config == "V3-A (1R/2R/1R)"`. NO se recomputan
    — recomputar estas 24 filas con el código de hoy no agregaría ninguna
    información científica (ya se conocen esos números), solo reproduciría
    H1 a costo de una verificación redundante. `atr_mult`=1.5 x
    `control_8h` ya fue verificado contra `trigger_campaign_results.csv` en
    el cierre de Espacio 2 (0 mismatches) — no se repite acá esa
    verificación, se cita como antecedente.
  - `dcv1_activo_15h` (role="candidate"): las 24 filas se COMPUTAN con el
    código de hoy. `atr_mult`=ATR_MULT_ANCHOR (1.5) juega rol dual: es
    simultáneamente la celda de verificación de integridad (Fase A) Y una
    fila candidata más del resultado — se computa UNA sola vez (reutilizada
    tal cual en ambos roles, no una segunda vez como en Espacio 2/max_hold,
    porque acá no hay dos rutas de código distintas que deban coincidir —
    la Fase A y la Fase B usan la MISMA función `_run_cell` para las 4
    valores del grid).

Contabilidad explícita de información nueva (mismo estándar que G x sesión
— no tratar todas las filas del CSV como si fueran evidencia nueva):
  - 24 filas `control_8h`: referencia histórica (H1), NO evidencia nueva.
  - 6 filas `atr_mult`=1.5 x `dcv1_activo_15h`: réplica/verificación de una
    celda ya publicada en 2 fuentes independientes, NO evidencia nueva.
  - 18 filas restantes (`atr_mult` ∈ {1.0, 2.0, 3.0} x `dcv1_activo_15h` x
    3 activos x 2 años): evidencia GENUINAMENTE NUEVA — el N científico de
    esta campaña es 18, no 48.

Orden de ejecución OBLIGATORIO dentro de la corrida 2022+2023 (Fase 1+2):
  - Fase A (12 verificaciones): para las 6 combinaciones (activo, año),
    computa `atr_mult`=ANCLA x `dcv1_activo_15h` y la compara EXACTO contra
    2 referencias independientes ya publicadas: `gestion_campaign_
    session_results.csv` (candidate="dcv1_activo_15h") y `gestion_campaign_
    max_hold_session_results.csv` (candidate="20 | dcv1_activo_15h",
    role="candidate" — Espacio 2, mismo cruce Bias=A/T1/C/V3-A/atr_mult=1.5/
    dcv1_activo_15h). Además corre `assert_trigger_invariant_to_atr_mult`
    (reutilizada literal de H1) sobre el frame de `dcv1_activo_15h` — H1
    solo la verificó bajo `control_8h`. Si CUALQUIERA de las 12
    verificaciones falla, `AssertionError` inmediato con celda/activo/año/
    referencia/métrica/esperado/obtenido — la corrida aborta antes de
    calcular el resto del grid de `dcv1_activo_15h`.
  - Fase B (solo si la Fase A completa sin excepción): computa `atr_mult`
    ∈ {1.0, 2.0, 3.0} x `dcv1_activo_15h` para las 6 combinaciones (18
    filas genuinamente nuevas), reutiliza la fila ya computada en Fase A
    para `atr_mult`=1.5, y lee las 24 filas de `control_8h` de H1.

Fijo durante toda la campaña: Bias=A (no A2 — cerrado en G/G x sesión sin
ventaja material, reabrirlo acá violaría "minimizar comparaciones
innecesarias"), Trigger=T1_ema_cross, Entry=C_market_close, Gestión V3-A
única (be=1.0R/activation=2.0R/distance=1.0R — sin V3-B en paralelo, a
diferencia del H1 original; sigue el patrón simplificado post-Espacio 3),
atr_period=14 (excluido, no-op estructural, Espacio 2), max_hold=20 (fijo,
ya evaluado y falsificado en Espacio 2), risk=0.005 (excluido, invariante a
gates, Espacio 2), una posición a la vez, datasets dc_v1 canónicos,
disciplina P-3, modelo de costos, gates literales de FRAMEWORK.md, 2024
ciego.

Medida descriptiva única (sin gate): `ΔPF(atr_mult) = PF(atr_mult,
dcv1_activo_15h) - PF(atr_mult, control_8h)`, por (activo, año, atr_mult) —
responde directamente la pregunta motivadora (¿`atr_mult`=3.0 conserva su
desempeño bajo la sesión que resuelve frecuencia?), reportada sin umbral. NO
se calcula una medida de interacción tipo ΔΔPF — no es un factorial 2x2 de
dos factores binarios (como Bias x sesión en G x sesión); acá `atr_mult` es
la única variable libre con 4 niveles, y uno de los dos lados de sesión
(`control_8h`) no es cómputo nuevo.

Qué este contrato explícitamente NO hace: no reabre `max_hold` ni
`atr_period` (Espacio 2 sigue cerrado); no reabre Bias (Bias=A fijo, sin
A2); no corre V3-B en paralelo; no amplía el grid de `atr_mult` más allá de
{1.0, 1.5, 2.0, 3.0}; no se interpreta como reapertura de Espacio 1.

Reutilización de infraestructura (sin modificar ninguno de los archivos
reutilizados, ni backtest.py): de scripts/bias_campaign.py —
`to_backtest_frame`, `gate_check`, `summarize_decision`. De
scripts/trigger_campaign.py — `load_asset_year`, `find_entries_for_trigger`.
De scripts/gestion_campaign_session.py — `SESSION_WINDOWS`. De
scripts/gestion_campaign_atr_mult.py (H1) — `ATR_MULT_VALUES` (grid
literal, nunca reintroducido), `assert_trigger_invariant_to_atr_mult`
(verificación de acoplamiento, literal, no reimplementada).

Requiere `data/raw/` poblado. BLOQUEADO en este sandbox (HTTP 451,
data/raw/ vacío) — validado acá solo estructuralmente (más una porción real
sobre los CSV históricos ya committeados, que no requieren data/raw/), ver
research/tests/test_gestion_campaign_atr_mult_session.py.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/gestion_campaign_atr_mult_session.py              # Fase 1+2 (incluye Fase A+B internas)
    python scripts/gestion_campaign_atr_mult_session.py --blind        # Fase 3: 2024 ciego (requiere --candidate)
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import argparse

import pandas as pd

import backtest
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as trigger_camp
import scripts.gestion_campaign_session as session_camp
import scripts.gestion_campaign_atr_mult as atr_mult_camp
from market_data import ASSETS

# --------------------------------------------------------------------------- #
# Config de la campaña                                                        #
# --------------------------------------------------------------------------- #
BE_ANCHOR = 1.0           # V3-A, congelado
ACTIVATION_ANCHOR = 2.0   # V3-A, congelado
DISTANCE_ANCHOR = 1.0     # V3-A, congelado
EXIT_CFG = {"be": BE_ANCHOR, "activation": ACTIVATION_ANCHOR, "distance": DISTANCE_ANCHOR}

ATR_PERIOD_ANCHOR = 14    # fijo — excluido, ver Espacio 2
MAX_HOLD_ANCHOR = 20      # fijo — ya evaluado y falsificado en Espacio 2

# Grid reutilizado literal de H1 — Paso 0 (dominancia Pareto) no podó nada,
# ver docstring. NO redefinir con otros valores sin repetir Paso 0.
ATR_MULT_VALUES = atr_mult_camp.ATR_MULT_VALUES  # (1.0, 1.5, 2.0, 3.0)
ATR_MULT_ANCHOR = 1.5     # ancla de H1/todo el programa; rol dual acá
ATR_MULT_PRIMARY = 3.0    # hipótesis PRIMARIA (motivadora) — ver docstring

SESSION_LABELS = ("control_8h", "dcv1_activo_15h")
SESSION_WINDOWS = {label: session_camp.SESSION_WINDOWS[label] for label in SESSION_LABELS}

BIAS_CANDIDATE = "A"
TRIGGER_CANDIDATE = "T1_ema_cross"

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision

# Solo dcv1_activo_15h es elegible como candidato/--blind — control_8h es
# lectura histórica (role="control"), nunca role="candidate", nunca entra a
# summarize_decision ni a CANDIDATES.
CANDIDATES = tuple(f"{v} | dcv1_activo_15h" for v in ATR_MULT_VALUES)

# Riesgo de comparaciones múltiples — ver docstring. 4 atr_mult x 3 activos.
N_CANDIDATES_EVALUATED = len(ATR_MULT_VALUES) * len(ASSETS)

EXIT_CONFIG_LABEL = (
    "atr_mult x sesión (be=1.0R/activation=2.0R/distance=1.0R, atr_period=14/"
    "max_hold=20 fijos; atr_mult & sesión variable — control_8h leído de H1, "
    "no recomputado)"
)

_SESSION_REF_PATH = "gestion_campaign_session_results.csv"
_SESSION_REF_EXIT_CONFIG = "V3-A (1R/2R/1R)"
_MAX_HOLD_SESSION_REF_PATH = "gestion_campaign_max_hold_session_results.csv"
_ATR_MULT_HISTORICAL_PATH = "gestion_campaign_atr_mult_results.csv"
_ATR_MULT_HISTORICAL_EXIT_CONFIG = "V3-A (1R/2R/1R)"

# Campos comparables entre las 2 referencias de Fase A.
_CHECK_FIELDS = ("pf", "wr", "exp_r", "max_dd", "freq")

_RESULT_COLUMNS = [
    "asset", "year", "role", "session", "atr_mult", "candidate", "hypothesis",
    "exit_config", "n_entries", "n_trades", "entries_per_month", "fill_rate",
    "gate_pass", "pf", "wr", "exp_r", "avg_win", "avg_loss", "total_r",
    "max_dd", "freq", "be", "reason_stop", "reason_timeout", "source",
]


def _label(atr_mult: float, session_label: str) -> str:
    return f"{atr_mult} | {session_label}"


def _hypothesis_tag(atr_mult: float) -> str:
    """'primary' únicamente para ATR_MULT_PRIMARY (3.0, la hipótesis
    motivadora) — el resto del grid es exploración secundaria pre-
    especificada. Ver ajuste acordado 2026-08-11."""
    return "primary" if atr_mult == ATR_MULT_PRIMARY else "secondary"


# --------------------------------------------------------------------------- #
# Orquestación — frame independiente de atr_mult (to_backtest_frame no lo     #
# usa), entries SÍ dependen de atr_mult (a diferencia de max_hold) —          #
# find_entries_for_trigger calcula risk_pts = atr_mult*ATR internamente       #
# --------------------------------------------------------------------------- #
def _frame_for_session(asset: str, year: int, session_label: str) -> pd.DataFrame:
    df_full = trigger_camp.load_asset_year(asset, year)
    ref_cfg = backtest.Config(atr_period=ATR_PERIOD_ANCHOR, max_hold=MAX_HOLD_ANCHOR,
                               sessions=SESSION_WINDOWS[session_label])
    return bias_camp.to_backtest_frame(df_full, df_full["bias_A"], ref_cfg)


def _run_cell(frame: pd.DataFrame, atr_mult: float, session_label: str):
    cfg = backtest.Config(atr_mult=atr_mult, atr_period=ATR_PERIOD_ANCHOR,
                           max_hold=MAX_HOLD_ANCHOR, sessions=SESSION_WINDOWS[session_label])
    entries = trigger_camp.find_entries_for_trigger(frame, cfg, TRIGGER_CANDIDATE)
    trades = backtest.run_config(frame, entries, EXIT_CFG, cfg)
    m = backtest.metrics(trades, cfg)
    return entries, trades, m


def _row(asset: str, year: int, atr_mult: float, session_label: str,
         entries: list[dict], trades: pd.DataFrame, m: dict | None) -> dict:
    return {
        "asset": asset, "year": year, "role": "candidate", "session": session_label,
        "atr_mult": atr_mult, "candidate": _label(atr_mult, session_label),
        "hypothesis": _hypothesis_tag(atr_mult), "exit_config": EXIT_CONFIG_LABEL,
        "n_entries": len(entries), "n_trades": len(trades),
        "metrics": m, "gate_pass": gate_check(m),
    }


# --------------------------------------------------------------------------- #
# control_8h — lectura directa de H1, SIN cómputo nuevo (ver docstring)       #
# --------------------------------------------------------------------------- #
def control_rows_frame() -> pd.DataFrame:
    """Lee las 24 filas de `control_8h` (4 atr_mult x 3 activos x 2 años)
    directamente de `gestion_campaign_atr_mult_results.csv` (H1), filtradas
    a V3-A. NO recomputa nada — deliberado, ver docstring del módulo."""
    df = pd.read_csv(_ATR_MULT_HISTORICAL_PATH)
    df = df[df["exit_config"] == _ATR_MULT_HISTORICAL_EXIT_CONFIG].copy()
    df["atr_mult"] = df["candidate"].astype(float)
    df = df[df["atr_mult"].isin(ATR_MULT_VALUES)].copy()

    out = pd.DataFrame({
        "asset": df["asset"].to_numpy(),
        "year": df["year"].astype(int).to_numpy(),
        "role": "control",
        "session": "control_8h",
        "atr_mult": df["atr_mult"].to_numpy(),
        "candidate": [_label(v, "control_8h") for v in df["atr_mult"]],
        "hypothesis": [_hypothesis_tag(v) for v in df["atr_mult"]],
        "exit_config": EXIT_CONFIG_LABEL,
        "n_entries": df["n_entries"].astype(int).to_numpy(),
        "n_trades": df["n_trades"].astype(int).to_numpy(),
        "entries_per_month": df["entries_per_month"].to_numpy(),
        "fill_rate": df["fill_rate"].to_numpy(),
        "gate_pass": df["gate_pass"].astype(bool).to_numpy(),
        "pf": df["pf"].to_numpy(), "wr": df["wr"].to_numpy(), "exp_r": df["exp_r"].to_numpy(),
        "avg_win": df["avg_win"].to_numpy(), "avg_loss": df["avg_loss"].to_numpy(),
        "total_r": df["total_r"].to_numpy(), "max_dd": df["max_dd"].to_numpy(),
        "freq": df["freq"].to_numpy(), "be": df["be"].to_numpy(),
        "reason_stop": df["reason_stop"].to_numpy(), "reason_timeout": df["reason_timeout"].to_numpy(),
        "source": f"{_ATR_MULT_HISTORICAL_PATH} (H1, no recomputado)",
    })
    return out[_RESULT_COLUMNS].reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Fase A — verificación de integridad de código (12 checks) contra la ÚNICA   #
# celda con antecedente bajo dcv1_activo_15h (atr_mult=ANCLA)                 #
# --------------------------------------------------------------------------- #
def _session_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_SESSION_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["candidate"] == "dcv1_activo_15h")
               & (df["exit_config"] == _SESSION_REF_EXIT_CONFIG)]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para celda=atr_mult={ATR_MULT_ANCHOR}|"
            f"dcv1_activo_15h, activo={asset}, año={year} en {_SESSION_REF_PATH} — no "
            f"se puede verificar la Fase A."
        )
    return match.iloc[0]


def _max_hold_session_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_MAX_HOLD_SESSION_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["role"] == "candidate")
               & (df["candidate"] == "20 | dcv1_activo_15h")]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para celda=atr_mult={ATR_MULT_ANCHOR}|"
            f"dcv1_activo_15h, activo={asset}, año={year} en "
            f"{_MAX_HOLD_SESSION_REF_PATH} — no se puede verificar la Fase A."
        )
    return match.iloc[0]


def _verify_against(cell_label: str, asset: str, year: int, ref_name: str,
                     n_entries: int, n_trades: int, m: dict | None,
                     ref_row: pd.Series) -> None:
    """Si falla, el AssertionError identifica: celda, activo, año,
    referencia, y para cada campo divergente: nombre de la métrica, valor
    esperado, valor obtenido — sin fallo opaco."""
    mismatches = []
    if n_entries != ref_row["n_entries"]:
        mismatches.append(
            f"n_entries: esperado={ref_row['n_entries']!r}, obtenido={n_entries!r}"
        )
    if n_trades != ref_row["n_trades"]:
        mismatches.append(
            f"n_trades: esperado={ref_row['n_trades']!r}, obtenido={n_trades!r}"
        )
    for field in _CHECK_FIELDS:
        expected = ref_row[field]
        actual = m.get(field) if m else None
        if actual != expected:
            mismatches.append(
                f"{field}: esperado={expected!r}, obtenido={actual!r}"
            )
    if mismatches:
        raise AssertionError(
            f"Fase A (verificación de integridad) falló — "
            f"celda={cell_label}, activo={asset}, año={year}, "
            f"referencia={ref_name}:\n  " + "\n  ".join(mismatches) +
            f"\nLa corrida aborta antes de calcular el resto del grid de "
            f"dcv1_activo_15h."
        )


def run_integrity_check(asset: str, year: int) -> dict:
    """Fase A para un (activo, año) — 2 de las 12 verificaciones totales de
    la campaña. Corre `atr_mult`=ATR_MULT_ANCHOR x `dcv1_activo_15h` UNA
    sola vez, corre la verificación de acoplamiento (H1, reutilizada
    literal) y verifica el resultado contra 2 referencias independientes.
    Devuelve el frame + la fila ya computada (rol dual: se reutiliza tal
    cual en la Fase B, no se recomputa una segunda vez). Revienta con
    AssertionError si cualquiera de las 2 verificaciones falla."""
    frame = _frame_for_session(asset, year, "dcv1_activo_15h")
    atr_mult_camp.assert_trigger_invariant_to_atr_mult(frame, asset, year)

    entries, trades, m = _run_cell(frame, ATR_MULT_ANCHOR, "dcv1_activo_15h")
    cell_label = _label(ATR_MULT_ANCHOR, "dcv1_activo_15h")

    ref_session = _session_reference(asset, year)
    _verify_against(cell_label, asset, year, _SESSION_REF_PATH,
                     len(entries), len(trades), m, ref_session)

    ref_max_hold = _max_hold_session_reference(asset, year)
    _verify_against(cell_label, asset, year, _MAX_HOLD_SESSION_REF_PATH,
                     len(entries), len(trades), m, ref_max_hold)

    return {"frame": frame, "entries": entries, "trades": trades, "m": m}


# --------------------------------------------------------------------------- #
# Fase B — grid completo bajo dcv1_activo_15h (solo tras Fase A sin excepción)#
# --------------------------------------------------------------------------- #
def run_asset_year_dcv1(asset: str, year: int, known_anchor: dict) -> list[dict]:
    """Fase B para un (activo, año): grid completo {1.0, 1.5, 2.0, 3.0} bajo
    dcv1_activo_15h. `atr_mult`=ANCLA reutiliza la fila ya computada en
    Fase A (`known_anchor`) — NO se recomputa una segunda vez."""
    frame = known_anchor["frame"]
    rows: list[dict] = []
    for atr_mult in ATR_MULT_VALUES:
        if atr_mult == ATR_MULT_ANCHOR:
            entries, trades, m = known_anchor["entries"], known_anchor["trades"], known_anchor["m"]
        else:
            entries, trades, m = _run_cell(frame, atr_mult, "dcv1_activo_15h")
        rows.append(_row(asset, year, atr_mult, "dcv1_activo_15h", entries, trades, m))
    return rows


def run_campaign(assets: tuple[str, ...] = ASSETS,
                  years: tuple[int, ...] = (IN_SAMPLE_YEAR, VALIDATION_YEAR)) -> pd.DataFrame:
    """Fase 1(2022)+Fase 2(2023). Fase A completa para las 6 combinaciones
    (activo, año) ANTES de que arranque el resto del grid de
    dcv1_activo_15h — si run_integrity_check revienta en cualquier
    combinación, la excepción se propaga acá. `control_8h` se lee completo
    de H1 (sin cómputo, independiente de la Fase A). Devuelve el DataFrame
    final ya ensamblado (control + candidate)."""
    known_by_combo: dict[tuple[str, int], dict] = {}
    for year in years:
        for asset in assets:
            known_by_combo[(asset, year)] = run_integrity_check(asset, year)  # Fase A

    candidate_rows: list[dict] = []
    for year in years:
        for asset in assets:
            candidate_rows.extend(run_asset_year_dcv1(asset, year, known_by_combo[(asset, year)]))  # Fase B

    candidates_df = results_to_frame(candidate_rows)
    candidates_df["source"] = "computado hoy (dcv1_activo_15h)"

    control_df = control_rows_frame()
    control_df = control_df[control_df["asset"].isin(assets) & control_df["year"].isin(years)]

    return pd.concat([control_df[_RESULT_COLUMNS], candidates_df[_RESULT_COLUMNS]],
                      ignore_index=True, sort=False)


def run_blind_test(assets: tuple[str, ...] = ASSETS,
                    candidate: str | None = None) -> list[dict]:
    """Fase 3 (2024, ciego). Requiere `candidate` (string compuesto
    "{atr_mult} | dcv1_activo_15h") ya congelado tras decidir con 2022+2023
    — solo dcv1_activo_15h es elegible (ver CANDIDATES). No corre Fase A
    acá (exclusiva de la fase 2022+2023)."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere un candidato ya congelado {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una "
            "decisión previa. control_8h nunca es elegible (rol='control', "
            "no candidato)."
        )
    atr_mult_str, session_label = (p.strip() for p in candidate.split("|"))
    atr_mult = float(atr_mult_str)
    results: list[dict] = []
    for asset in assets:
        frame = _frame_for_session(asset, BLIND_YEAR, session_label)
        entries, trades, m = _run_cell(frame, atr_mult, session_label)
        results.append(_row(asset, BLIND_YEAR, atr_mult, session_label, entries, trades, m))
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
            "atr_mult": r["atr_mult"], "candidate": r["candidate"], "hypothesis": r["hypothesis"],
            "exit_config": r["exit_config"],
            "n_entries": n_entries, "n_trades": n_trades,
            "entries_per_month": round(entries_per_month, 2) if entries_per_month is not None else None,
            "fill_rate": round(fill_rate, 3) if fill_rate is not None else None,
            "gate_pass": r["gate_pass"],
            "pf": m.get("pf"), "wr": m.get("wr"), "exp_r": m.get("exp_r"),
            "avg_win": m.get("avg_win"), "avg_loss": m.get("avg_loss"),
            "total_r": m.get("total_r"), "max_dd": m.get("max_dd"), "freq": freq,
            "be": m.get("be"), "reason_stop": reasons.get("stop", 0),
            "reason_timeout": reasons.get("timeout", 0),
        })
    return pd.DataFrame(rows)


def compute_deltas(df: pd.DataFrame) -> pd.DataFrame:
    """Medida descriptiva única (sin gate): ΔPF/Δfreq = (dcv1_activo_15h) -
    (control_8h), por (activo, año, atr_mult). Responde directamente la
    pregunta motivadora. NO es una medida de interacción tipo ΔΔPF (ver
    docstring del módulo)."""
    rows = []
    for (asset, year, atr_mult), g in df.groupby(["asset", "year", "atr_mult"]):
        by_session = g.set_index("session")
        if "control_8h" not in by_session.index or "dcv1_activo_15h" not in by_session.index:
            continue
        pf_c8 = by_session.loc["control_8h", "pf"]
        pf_15 = by_session.loc["dcv1_activo_15h", "pf"]
        freq_c8 = by_session.loc["control_8h", "freq"]
        freq_15 = by_session.loc["dcv1_activo_15h", "freq"]
        delta_pf = (pf_15 - pf_c8) if pd.notna(pf_15) and pd.notna(pf_c8) else None
        delta_freq = (freq_15 - freq_c8) if pd.notna(freq_15) and pd.notna(freq_c8) else None
        rows.append({
            "asset": asset, "year": year, "atr_mult": atr_mult,
            "hypothesis": _hypothesis_tag(atr_mult),
            "pf_control_8h": pf_c8, "pf_dcv1_activo_15h": pf_15,
            "delta_pf": round(delta_pf, 3) if delta_pf is not None else None,
            "freq_control_8h": freq_c8, "freq_dcv1_activo_15h": freq_15,
            "delta_freq": round(delta_freq, 2) if delta_freq is not None else None,
        })
    return pd.DataFrame(rows)


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  atr_mult x sesión — Bias=A/Trigger=T1_ema_cross/Entry=C_market_close/"
          f"Gestión V3-A única\n  control_8h leído de H1 (no recomputado) | dcv1_activo_15h "
          f"computado hoy\n{'='*100}")
    cols = ["asset", "year", "role", "session", "atr_mult", "hypothesis", "n_entries", "n_trades",
            "entries_per_month", "fill_rate", "pf", "wr", "exp_r", "avg_win", "avg_loss",
            "total_r", "max_dd", "freq", "be", "reason_stop", "reason_timeout", "gate_pass"]

    control = df[df["role"] == "control"]
    print(f"\n{'-'*100}\n  control_8h (role='control', leído de H1, NO evidencia nueva):\n{'-'*100}")
    print(control[cols].to_string(index=False) if not control.empty else "  (sin filas)")

    candidate = df[df["role"] == "candidate"]
    print(f"\n{'-'*100}\n  dcv1_activo_15h (role='candidate', N científico nuevo=18 — atr_mult=1.5 "
          f"es réplica de celda ya conocida, no cuenta como nueva):\n{'-'*100}")
    print(candidate[cols].to_string(index=False) if not candidate.empty else "  (sin filas)")

    print(f"\n{'-'*100}\n  Combinaciones candidatas que pasan los 4 gates de FRAMEWORK.md (por año):"
          f"\n{'-'*100}")
    passing = candidate[candidate["gate_pass"]]
    if passing.empty:
        print("  Ninguna combinación candidata pasa los 4 gates.")
    else:
        print(passing[cols].to_string(index=False))


def print_decision(decision: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  DECISIÓN — sobrevivientes (ambos años, por activo) y ranking por PF 2023 "
          f"(solo dcv1_activo_15h, único candidato)\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    survivors_any = decision[decision["survives_both_years"]]
    if not survivors_any.empty:
        print(
            f"\n  ADVERTENCIA — riesgo de comparaciones múltiples: este barrido evaluó "
            f"{N_CANDIDATES_EVALUATED} combinaciones candidatas ({len(ATR_MULT_VALUES)} atr_mult "
            f"x {len(ASSETS)} activos). Un sobreviviente aislado se clasifica como CANDIDATO, "
            f"sujeto al mismo escrutinio de estabilidad interanual y de patrón que el resto del "
            f"programa. La supervivencia 2022+2023 (Nivel 3) sigue siendo el criterio de "
            f"aceptación, pero no elimina por sí sola el riesgo de selección entre múltiples "
            f"candidatos evaluados."
        )

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
            print(f"\n  {asset}: ninguna combinación (atr_mult, dcv1_activo_15h) demuestra "
                  f"evidencia suficiente para cumplir los 4 gates de FRAMEWORK.md en 2022+2023.")


def print_deltas(deltas: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  Medida descriptiva — ΔPF/Δfreq (dcv1_activo_15h - control_8h), por "
          f"activo/año/atr_mult\n{'='*100}")
    print(deltas.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="candidato ya congelado ('{atr_mult} | dcv1_activo_15h') para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (el candidato ya congelado)")
        results = run_blind_test(candidate=args.candidate)
        df = results_to_frame(results)
        print_report(df)
        out_path = "gestion_campaign_atr_mult_session_results.csv"
        df.to_csv(out_path, index=False)
        print(f"\nResultados exportados a {out_path} ({len(df)} filas)")
        return

    df = run_campaign()
    print_report(df)
    out_path = "gestion_campaign_atr_mult_session_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas — 24 control_8h [H1, no nuevas] "
          f"+ 24 dcv1_activo_15h [6 réplica + 18 nuevas])")

    candidates_only = df[df["role"] == "candidate"].reset_index(drop=True)
    decision = summarize_decision(candidates_only)
    print_decision(decision)
    decision_path = "gestion_campaign_atr_mult_session_decision.csv"
    decision.to_csv(decision_path, index=False)
    print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")

    deltas = compute_deltas(df)
    print_deltas(deltas)
    deltas_path = "gestion_campaign_atr_mult_session_deltas.csv"
    deltas.to_csv(deltas_path, index=False)
    print(f"Deltas exportados a {deltas_path} ({len(deltas)} filas)")


if __name__ == "__main__":
    main()
