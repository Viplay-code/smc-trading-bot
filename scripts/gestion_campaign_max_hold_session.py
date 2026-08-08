#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/gestion_campaign_max_hold_session.py — Espacio 2 (post-cierre I1
y Espacio 3), único sub-bloque: `max_hold`, el primero de los 3 parámetros
"periféricos" de Gestión (`max_hold`/`atr_period`/`risk`, nunca variados en
ninguna campaña anterior) en tener un contrato experimental ejecutable bajo
la arquitectura actual. Bajo Bias=A/Trigger=T1_ema_cross/Entry=
C_market_close/atr_mult=1.5/atr_period=14/be=1.0R/activation=2.0R/
distance=1.0R fijos (Gestión V3-A completa, salvo `max_hold`). Contrato
acordado 2026-08-08.

Alcance de Espacio 2 — dos exclusiones explícitas, no supuestos heredados:
  - `risk`: excluido del objetivo científico principal. Verificado en código
    (research/metrics.py, backtest.py::metrics) y confirmado empíricamente:
    pf/wr/exp_r/total_r/freq son EXACTAMENTE invariantes a `risk` — solo
    entra en la curva de equity (max_dd/ret). Escaneados los 12 CSV de
    resultados ya publicados del programa completo: cero filas bloqueadas
    exclusivamente por max_dd (con pf/exp_r/freq ya en regla) — hoy no
    existe ninguna configuración que un ajuste de `risk` pudiera rescatar.
    Válido para la arquitectura actual de sizing; revisitable si cambia el
    modelo de gestión monetaria.
  - `atr_period`: excluido de Espacio 2, no por "sin efecto" sino porque el
    pipeline de investigación actual (bias_campaign.to_backtest_frame +
    trigger_campaign.find_entries_for_trigger) no puede medirlo:
    `to_backtest_frame` fija `atr` = columna `atr14` de dc_v1 (pin
    ratificado, DC-v1_Precisiones_Implementacion.md P-7); `risk_pts` de
    cada entrada se calcula desde esa columna fija, nunca desde
    `cfg.atr_period`. Confirmado empíricamente sobre datos sintéticos:
    n_entries/n_trades/pf/freq/risk_pts bit-idénticos barriendo
    atr_period ∈ {7,14,21,28}. Estudiarlo requeriría una evolución acotada
    del pipeline de investigación (ATR de período arbitrario sobre la serie
    continua, P-3, con su propio test de equivalencia) — propuesta como
    iniciativa de infraestructura independiente, fuera de este contrato.
    `atr_period` queda fijo en 14 (el valor de dc_v1) en todo este script.

Hipótesis (Espacio 2 — max_hold) a falsificar: bajo Bias=A/Trigger=
T1_ema_cross/Entry=C_market_close/Gestión V3-A (be/activation/distance) fija/
atr_mult=1.5/atr_period=14 fijos, existe al menos un activo donde, bajo la
combinación experimental (max_hold, sesión), el candidato supera los 4 gates
de FRAMEWORK.md en 2022 Y 2023. Falsificada si, evaluados los 3 activos,
ninguno sobrevive ambos años.

Justificación del patrón de sesión (sesión × parámetro, protocolo I1 —
decisión 2026-08-08, NO el patrón "un solo control_8h" de H2): la
precondición que permitió a H2 correr solo bajo control_8h sin perder
información — que las entradas no dependen del parámetro que se varía — NO
se cumple para `max_hold` de la misma forma que para distance/activation/be.
`run_config` bloquea nuevas entradas hasta `busy_until = exit_idx` de la
operación abierta, y `simulate_v3` limita el timeout a
`min(i0+cfg.max_hold+1, n)`: reducir `max_hold` solo puede adelantar o
igualar el `exit_time` de cada trade, nunca atrasarlo — mecanismo
estructural verificado de interacción con `freq`, ausente en cualquier
parámetro de H2. El freq base bajo control_8h/T1_ema_cross
(gestion_campaign_trailing_distance_results.csv) es 4.0-5.6/mes — cerca del
piso de 6, no un orden de magnitud por debajo como en Espacio 3 — por lo que
correr bajo una sola sesión arriesgaba subestimar el efecto (control_8h sin
margen si nunca cruza 6) o enmascararlo (dcv1_activo_15h ya resuelve freq
por sí sola). NOTA ESTRUCTURAL: aunque max_hold puede afectar `freq` (vía
duración de trade/bloqueo de entradas), NO afecta qué entradas se generan —
`find_entries_for_trigger` nunca lee `cfg.max_hold` — así que `frame`/
`entries` se calculan una sola vez por (activo, año, sesión) y se reutilizan
para todo el barrido de `max_hold`, igual que H2 reutilizó entradas para
distance/activation/be.

Grilla experimental — criterio de selección explícito, NO valores
arbitrarios: mismas proporciones relativas al ancla que ya usó H2.3 para
`be` (0.25x/0.5x/1x/1.5x/2.0x, diseño simétrico), reutilizadas en vez de
inventar un esquema nuevo, redondeadas a enteros porque `max_hold` es un
conteo de velas:
    MAX_HOLD_VALUES_BASE = (10, 20, 30)   # 0.5x / 1x (ancla) / 1.5x
    MAX_HOLD_EXT_LOWER    = 5             # 0.25x
    MAX_HOLD_EXT_UPPER    = 40            # 2.0x
Diseño de contingencia: SIMÉTRICO (`_is_extreme_best`, PF-only, máximo una
extensión por lado), evaluado independientemente por (activo, año, sesión) —
mismo patrón que H2.2/H2.3, porque no hay mecanismo probado de
monotonicidad de PF en `max_hold` (el mecanismo verificado es sobre `freq`,
no sobre PF). El ancla (20) es el punto medio de la grilla base — por
construcción, siempre se computa en la Fase B para las 2 sesiones.

Rol dual del ancla (max_hold=20, mismo patrón que I1-activation/I1-be):
como el ancla integra la grilla base, se computa DOS VECES — una como
control (Fase A) y otra como candidato normal de la Fase B (participa en
CANDIDATES/summarize_decision()/--blind igual que cualquier otro valor).
`verify_anchor_dual_role` exige que la fila role='control' de max_hold=20 y
su fila role='candidate' equivalente (misma sesión) coincidan EXACTO en
TODAS las métricas publicadas — ambas son, por construcción, la misma
computación alcanzada por caminos de código distintos.

Orden de ejecución OBLIGATORIO dentro de la corrida 2022+2023 (Fase 1+2):
  - Fase A (verificación de integridad, 24 verificaciones independientes en
    total): para las 6 combinaciones (activo, año), corre las 2 filas de
    control (max_hold=20 bajo control_8h y bajo dcv1_activo_15h) y las
    compara EXACTO contra DOS referencias independientes por sesión (más
    estricto que I1, que usó 1 por sesión — posible acá porque existen 2
    referencias ya publicadas que coinciden entre sí en ambas sesiones,
    verificado antes de escribir este script):
      * control_8h + max_hold=20 -> trigger_campaign_results.csv (candidate=
        T1_ema_cross, exit_config="V3-A (1R/2R/1R)") Y gestion_campaign_
        atr_mult_results.csv (candidate=1.5, exit_config="V3-A (1R/2R/1R)")
        — 12 verificaciones (6 combos x 2 referencias).
      * dcv1_activo_15h + max_hold=20 -> gestion_campaign_session_results.csv
        (candidate="dcv1_activo_15h", exit_config="V3-A (1R/2R/1R)") Y
        integration_campaign_activation_results.csv (role="candidate",
        candidate="2.0 | dcv1_activo_15h") — 12 verificaciones más.
    Si CUALQUIERA de las 24 comparaciones falla, `AssertionError` inmediato
    — la corrida completa aborta antes de calcular una sola fila
    experimental. Campos verificados: SOLO los presentes en las 4
    referencias (pf, wr, exp_r, max_dd, freq) — NO avg_win/avg_loss (ausente
    en trigger_campaign_results.csv).
  - Fase B (barrido experimental): arranca SOLO si la Fase A completa sin
    excepción. Por cada (activo, año, sesión): corre la grilla base (10, 20,
    30), aplica contingencia simétrica en cada extremo si corresponde (5 y/o
    40). Tras calcularse, `verify_anchor_dual_role` compara las filas de
    max_hold=20 (ambas sesiones) contra sus controles ya verificados;
    cualquier mismatch también aborta antes de exportar resultados.

Fijo durante toda la campaña: Bias=A, Trigger=T1_ema_cross, Entry=
C_market_close, atr_mult=1.5 (ancla H1), atr_period=14 (fijo — ver exclusión
arriba), be=1.0R/activation=2.0R/distance=1.0R (Gestión V3-A completa),
risk=0.005 (fuera del objetivo, ver exclusión arriba), una posición a la
vez, datasets dc_v1 canónicos, disciplina P-3, modelo de costos, gates
literales de FRAMEWORK.md, 2024 ciego.

Estructura de datos y criterio de decisión — igual que I1/Espacio 3:
`candidate` = f"{max_hold} | {session_label}" para que `summarize_decision()`
(reutilizada SIN modificar) no mezcle sesiones distintas bajo el mismo
`max_hold`. `summarize_decision()` opera EXCLUSIVAMENTE sobre filas
role="candidate" — role="control" existe únicamente para la verificación de
integridad de la Fase A (y para la verificación de rol dual) y nunca se
pasa a esa función, nunca aparece en CANDIDATES, nunca es elegible para
--blind.

Nota de alcance del cierre: el cierre de Espacio 2 sintetiza ÚNICAMENTE la
evidencia obtenida acá para `max_hold` — no reabre ni reinterpreta ninguna
decisión ya cerrada de H1, H2, I1 o Espacio 3. Cualquier implicación cruzada
con esos cierres (por ejemplo, sobre el mecanismo de `freq` bajo control_8h)
se documenta como observación nueva de este contrato, no como revisión de
los anteriores.

Reutilización de infraestructura (sin modificar ninguno de los archivos
reutilizados, ni backtest.py): de scripts/bias_campaign.py —
to_backtest_frame, gate_check, summarize_decision. De
scripts/trigger_campaign.py — load_asset_year, find_entries_for_trigger.
De scripts/gestion_campaign_session.py — SESSION_WINDOWS.

Requiere `data/raw/` poblado. BLOQUEADO en este sandbox (HTTP 451,
data/raw/ vacío) — validado acá solo estructuralmente, ver
research/tests/test_gestion_campaign_max_hold_session.py.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/gestion_campaign_max_hold_session.py              # Fase 1+2 (incluye Fase A+B internas)
    python scripts/gestion_campaign_max_hold_session.py --blind        # Fase 3: 2024 ciego (requiere --candidate)
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
from market_data import ASSETS

# --------------------------------------------------------------------------- #
# Config de la campaña                                                        #
# --------------------------------------------------------------------------- #
BE_ANCHOR = 1.0           # V3-A, congelado
ACTIVATION_ANCHOR = 2.0   # V3-A, congelado
DISTANCE_ANCHOR = 1.0     # V3-A, congelado
ATR_MULT_ANCHOR = 1.5     # ancla de H1, congelado
ATR_PERIOD_ANCHOR = 14    # fijo — atr_period excluido de Espacio 2 (ver docstring)
EXIT_CFG = {"be": BE_ANCHOR, "activation": ACTIVATION_ANCHOR, "distance": DISTANCE_ANCHOR}

MAX_HOLD_ANCHOR = 20  # valor de todas las campañas anteriores; punto medio de la grilla base
# Mismas proporciones relativas al ancla que H2.3 usó para `be`
# (0.25x/0.5x/1x/1.5x/2.0x) — ver docstring, criterio explícito no arbitrario.
MAX_HOLD_VALUES_BASE = (10, 20, 30)
MAX_HOLD_EXT_LOWER = 5
MAX_HOLD_EXT_UPPER = 40

SESSION_LABELS = ("control_8h", "dcv1_activo_15h")
SESSION_WINDOWS = {label: session_camp.SESSION_WINDOWS[label] for label in SESSION_LABELS}

BIAS_CANDIDATE = "A"
TRIGGER_CANDIDATE = "T1_ema_cross"

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision

# Todos los valores que pueden llegar a aparecer (base + ambas extensiones),
# congelados de antemano — igual que H2.2/H2.3, independiente de si la
# contingencia efectivamente se dispara en 2022+2023.
_ALL_MAX_HOLD_VALUES = (MAX_HOLD_EXT_LOWER,) + MAX_HOLD_VALUES_BASE + (MAX_HOLD_EXT_UPPER,)
CANDIDATES = tuple(f"{v} | {s}" for v in _ALL_MAX_HOLD_VALUES for s in SESSION_LABELS)
EXIT_CONFIG_LABEL = (
    "Espacio 2 — max_hold (be=1.0R/activation=2.0R/distance=1.0R, "
    "atr_mult=1.5/atr_period=14 fijos; max_hold & sesión variable)"
)

_TRIGGER_REF_PATH = "trigger_campaign_results.csv"
_TRIGGER_REF_EXIT_CONFIG = "V3-A (1R/2R/1R)"
_ATR_MULT_REF_PATH = "gestion_campaign_atr_mult_results.csv"
_ATR_MULT_REF_EXIT_CONFIG = "V3-A (1R/2R/1R)"
_SESSION_REF_PATH = "gestion_campaign_session_results.csv"
_SESSION_REF_EXIT_CONFIG = "V3-A (1R/2R/1R)"
_I1_ACTIVATION_REF_PATH = "integration_campaign_activation_results.csv"
# Solo campos presentes en las 4 referencias (trigger_campaign_results.csv NO
# tiene avg_win/avg_loss) — NO se verifican esos dos campos, mismo criterio
# que Espacio 3.
_CHECK_FIELDS = ("pf", "wr", "exp_r", "max_dd", "freq")
# Campos completos para la verificación de rol dual (más estricta: toda
# métrica publicada, no un subconjunto).
_FULL_FIELDS = ("pf", "wr", "exp_r", "avg_win", "avg_loss", "total_r", "max_dd",
                 "freq", "be", "reason_stop", "reason_timeout", "n_entries", "n_trades")


def _label(max_hold: int, session_label: str) -> str:
    return f"{max_hold} | {session_label}"


# --------------------------------------------------------------------------- #
# Orquestación — entradas independientes de max_hold, un solo cálculo por     #
# (activo, año, sesión), reutilizado para todo el barrido                     #
# --------------------------------------------------------------------------- #
def _entries_for_session(asset: str, year: int, session_label: str):
    df_full = trigger_camp.load_asset_year(asset, year)
    # max_hold no participa en la construcción de entradas (find_entries_for_trigger
    # nunca lee cfg.max_hold) — se usa un cfg de referencia solo para atr_mult/
    # atr_period/sessions; el max_hold real se fija por separado en cada corrida.
    ref_cfg = backtest.Config(atr_mult=ATR_MULT_ANCHOR, atr_period=ATR_PERIOD_ANCHOR,
                               sessions=SESSION_WINDOWS[session_label])
    frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], ref_cfg)
    entries = trigger_camp.find_entries_for_trigger(frame, ref_cfg, TRIGGER_CANDIDATE)
    return frame, entries


def _run_max_hold(frame: pd.DataFrame, entries: list[dict], max_hold: int,
                   session_label: str) -> tuple[pd.DataFrame, dict | None]:
    cfg = backtest.Config(atr_mult=ATR_MULT_ANCHOR, atr_period=ATR_PERIOD_ANCHOR,
                           max_hold=max_hold, sessions=SESSION_WINDOWS[session_label])
    trades = backtest.run_config(frame, entries, EXIT_CFG, cfg)
    m = backtest.metrics(trades, cfg)
    return trades, m


def _row(asset: str, year: int, max_hold: int, session_label: str, entries: list[dict],
         trades: pd.DataFrame, m: dict | None, role: str, triggered_by: str | None = None) -> dict:
    return {
        "asset": asset, "year": year, "role": role, "session": session_label,
        "candidate": _label(max_hold, session_label), "exit_config": EXIT_CONFIG_LABEL,
        "n_entries": len(entries), "n_trades": len(trades),
        "metrics": m, "gate_pass": gate_check(m), "triggered_by": triggered_by,
    }


def _full_row_fields(row: dict) -> dict:
    m = row["metrics"] or {}
    reasons = m.get("reasons") or {}
    return {
        "pf": m.get("pf"), "wr": m.get("wr"), "exp_r": m.get("exp_r"),
        "avg_win": m.get("avg_win"), "avg_loss": m.get("avg_loss"),
        "total_r": m.get("total_r"), "max_dd": m.get("max_dd"), "freq": m.get("freq"),
        "be": m.get("be"), "reason_stop": reasons.get("stop", 0),
        "reason_timeout": reasons.get("timeout", 0),
        "n_entries": row["n_entries"], "n_trades": row["n_trades"],
    }


# --------------------------------------------------------------------------- #
# Fase A — verificación de integridad contra CUATRO referencias ya            #
# publicadas (2 por sesión, ya verificadas de que coinciden entre sí)         #
# --------------------------------------------------------------------------- #
def _trigger_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_TRIGGER_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["candidate"] == "T1_ema_cross")
               & (df["exit_config"] == _TRIGGER_REF_EXIT_CONFIG)]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para {asset}/{year}/T1_ema_cross "
            f"en {_TRIGGER_REF_PATH} — no se puede verificar la Fase A."
        )
    return match.iloc[0]


def _atr_mult_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_ATR_MULT_REF_PATH)
    df["candidate_f"] = df["candidate"].astype(float)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["candidate_f"] == ATR_MULT_ANCHOR)
               & (df["exit_config"] == _ATR_MULT_REF_EXIT_CONFIG)]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para {asset}/{year}/atr_mult="
            f"{ATR_MULT_ANCHOR} en {_ATR_MULT_REF_PATH} — no se puede verificar la Fase A."
        )
    return match.iloc[0]


def _session_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_SESSION_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["candidate"] == "dcv1_activo_15h")
               & (df["exit_config"] == _SESSION_REF_EXIT_CONFIG)]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para {asset}/{year}/dcv1_activo_15h "
            f"en {_SESSION_REF_PATH} — no se puede verificar la Fase A."
        )
    return match.iloc[0]


def _i1_activation_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_I1_ACTIVATION_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["role"] == "candidate")
               & (df["candidate"] == "2.0 | dcv1_activo_15h")]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para {asset}/{year}/"
            f"'2.0 | dcv1_activo_15h' en {_I1_ACTIVATION_REF_PATH} — no se puede "
            f"verificar la Fase A."
        )
    return match.iloc[0]


def _verify_against(m: dict | None, n_trades: int, ref_row: pd.Series, context: str) -> None:
    mismatches = []
    for field in _CHECK_FIELDS:
        actual = m.get(field) if m else None
        expected = ref_row[field]
        if actual != expected:
            mismatches.append(f"{field}: actual={actual!r} vs esperado={expected!r}")
    if n_trades != ref_row["n_trades"]:
        mismatches.append(f"n_trades: actual={n_trades} vs esperado={ref_row['n_trades']}")
    if mismatches:
        raise AssertionError(
            f"Fase A (verificación de integridad) falló en {context}: "
            f"{'; '.join(mismatches)} — el mecanismo de variación de max_hold/sesión no "
            f"reproduce un resultado histórico ya publicado. Corrida abortada antes de "
            f"calcular cualquier resultado de la Fase B."
        )


def run_control_rows(asset: str, year: int) -> list[dict]:
    """Corre las 2 filas de control (role='control') para un (activo, año),
    una por sesión, con max_hold=MAX_HOLD_ANCHOR."""
    rows = []
    for session_label in SESSION_LABELS:
        frame, entries = _entries_for_session(asset, year, session_label)
        trades, m = _run_max_hold(frame, entries, MAX_HOLD_ANCHOR, session_label)
        rows.append(_row(asset, year, MAX_HOLD_ANCHOR, session_label, entries, trades, m, role="control"))
    return rows


def run_control_checks(asset: str, year: int) -> list[dict]:
    """Fase A para un (activo, año) — 4 de las 24 verificaciones totales de
    la campaña (2 sesiones x 2 referencias). Corre y devuelve las 2 filas de
    control tras verificarlas exitosamente contra las 4 referencias
    históricas ya publicadas. Revienta con AssertionError (sin devolver
    nada parcial) si cualquiera de las 4 verificaciones falla."""
    rows = run_control_rows(asset, year)
    row_c8 = next(r for r in rows if r["session"] == "control_8h")
    row_15 = next(r for r in rows if r["session"] == "dcv1_activo_15h")

    ref_trigger = _trigger_reference(asset, year)
    _verify_against(row_c8["metrics"], row_c8["n_trades"], ref_trigger,
                     f"{asset}/{year} control_8h vs {_TRIGGER_REF_PATH}")

    ref_atr_mult = _atr_mult_reference(asset, year)
    _verify_against(row_c8["metrics"], row_c8["n_trades"], ref_atr_mult,
                     f"{asset}/{year} control_8h vs {_ATR_MULT_REF_PATH}")

    ref_session = _session_reference(asset, year)
    _verify_against(row_15["metrics"], row_15["n_trades"], ref_session,
                     f"{asset}/{year} dcv1_activo_15h vs {_SESSION_REF_PATH}")

    ref_i1_act = _i1_activation_reference(asset, year)
    _verify_against(row_15["metrics"], row_15["n_trades"], ref_i1_act,
                     f"{asset}/{year} dcv1_activo_15h vs {_I1_ACTIVATION_REF_PATH}")

    return rows


# --------------------------------------------------------------------------- #
# Fase B — barrido experimental (solo tras Fase A completa sin excepción)     #
# --------------------------------------------------------------------------- #
def _is_extreme_best(metrics_by_max_hold: dict[int, dict | None], extreme: int) -> bool:
    """True si `extreme` (uno de los dos extremos de la grilla base) tiene el
    mejor-o-empatado PF de todo el barrido base — ranking por PF en
    solitario, diseño simétrico, mismo criterio que H2.2/H2.3 (no hay
    mecanismo probado de monotonicidad de PF en max_hold)."""
    valid = {v: m for v, m in metrics_by_max_hold.items() if m is not None}
    if extreme not in valid or len(valid) < 2:
        return False
    pf_extreme = valid[extreme]["pf"]
    return all(pf_extreme >= m["pf"] for v, m in valid.items() if v != extreme)


def run_asset_year_experimental(asset: str, year: int) -> list[dict]:
    """Fase B para un (activo, año): grilla base x 2 sesiones, con
    contingencia simétrica evaluada independientemente por sesión (el
    contexto es (activo, año, sesión), no solo (activo, año))."""
    rows: list[dict] = []
    for session_label in SESSION_LABELS:
        frame, entries = _entries_for_session(asset, year, session_label)

        metrics_by_max_hold: dict[int, dict | None] = {}
        for max_hold in MAX_HOLD_VALUES_BASE:
            trades, m = _run_max_hold(frame, entries, max_hold, session_label)
            metrics_by_max_hold[max_hold] = m
            rows.append(_row(asset, year, max_hold, session_label, entries, trades, m,
                              role="candidate", triggered_by=None))

        if _is_extreme_best(metrics_by_max_hold, MAX_HOLD_VALUES_BASE[0]):
            trades, m = _run_max_hold(frame, entries, MAX_HOLD_EXT_LOWER, session_label)
            rows.append(_row(asset, year, MAX_HOLD_EXT_LOWER, session_label, entries, trades, m,
                              role="candidate", triggered_by="lower_contingency"))

        if _is_extreme_best(metrics_by_max_hold, MAX_HOLD_VALUES_BASE[-1]):
            trades, m = _run_max_hold(frame, entries, MAX_HOLD_EXT_UPPER, session_label)
            rows.append(_row(asset, year, MAX_HOLD_EXT_UPPER, session_label, entries, trades, m,
                              role="candidate", triggered_by="upper_contingency"))

    return rows


def verify_anchor_dual_role(control_rows: list[dict], experimental_rows: list[dict]) -> None:
    """Verifica que, para cada (activo, año, sesión), la fila role='control'
    de max_hold=MAX_HOLD_ANCHOR coincida EXACTO en TODOS los campos
    publicados (_FULL_FIELDS) con su fila role='candidate' equivalente
    generada en la Fase B — ambas son, por construcción, la misma
    computación alcanzada por caminos de código distintos. Cualquier
    divergencia revienta con AssertionError."""
    anchor_label_by_session = {s: _label(MAX_HOLD_ANCHOR, s) for s in SESSION_LABELS}
    exp_by_key = {(r["asset"], r["year"], r["candidate"]): r for r in experimental_rows}

    for ctrl in control_rows:
        key = (ctrl["asset"], ctrl["year"], anchor_label_by_session[ctrl["session"]])
        cand = exp_by_key.get(key)
        if cand is None:
            raise AssertionError(
                f"Verificación de rol dual: no se encontró la fila candidata "
                f"equivalente a {key} generada por la Fase B."
            )
        ctrl_fields = _full_row_fields(ctrl)
        cand_fields = _full_row_fields(cand)
        mismatches = [f"{k}: control={ctrl_fields[k]!r} vs candidate={cand_fields[k]!r}"
                      for k in _FULL_FIELDS if ctrl_fields[k] != cand_fields[k]]
        if mismatches:
            raise AssertionError(
                f"Verificación de rol dual falló para {key}: {'; '.join(mismatches)} — "
                f"la fila de control y la fila candidata de max_hold="
                f"{MAX_HOLD_ANCHOR} deberían ser IDÉNTICAS en todos los campos "
                f"publicados; la divergencia indica un bug interno de separación "
                f"de roles, no un desvío respecto de datos históricos."
            )


def run_campaign(assets: tuple[str, ...] = ASSETS,
                  years: tuple[int, ...] = (IN_SAMPLE_YEAR, VALIDATION_YEAR)) -> list[dict]:
    """Fase 1(2022)+Fase 2(2023). Internamente: Fase A completa para las 6
    combinaciones (activo, año) ANTES de que arranque la Fase B; tras la
    Fase B, verify_anchor_dual_role confirma la consistencia interna del rol
    dual del ancla antes de devolver ningún resultado. NO incluye 2024 — ver
    run_blind_test."""
    control_rows: list[dict] = []
    for year in years:
        for asset in assets:
            control_rows.extend(run_control_checks(asset, year))  # Fase A — aborta acá si falla

    experimental_rows: list[dict] = []
    for year in years:
        for asset in assets:
            experimental_rows.extend(run_asset_year_experimental(asset, year))  # Fase B

    verify_anchor_dual_role(control_rows, experimental_rows)  # aborta acá si el rol dual diverge

    return control_rows + experimental_rows


def run_blind_test(assets: tuple[str, ...] = ASSETS,
                    candidate: str | None = None) -> list[dict]:
    """Fase 3 (2024, ciego). Requiere `candidate` (string compuesto
    "{max_hold} | {session}") ya congelado tras decidir con 2022+2023. No
    corre Fase A ni verificación de rol dual acá (exclusivas de la fase
    2022+2023)."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere un candidato ya congelado {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una "
            "decisión previa."
        )
    max_hold_str, session_label = (p.strip() for p in candidate.split("|"))
    max_hold = int(max_hold_str)
    results: list[dict] = []
    for asset in assets:
        frame, entries = _entries_for_session(asset, BLIND_YEAR, session_label)
        trades, m = _run_max_hold(frame, entries, max_hold, session_label)
        results.append(_row(asset, BLIND_YEAR, max_hold, session_label, entries, trades, m,
                             role="candidate"))
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
            "candidate": r["candidate"], "exit_config": r["exit_config"],
            "n_entries": n_entries, "n_trades": n_trades,
            "entries_per_month": round(entries_per_month, 2) if entries_per_month is not None else None,
            "fill_rate": round(fill_rate, 3) if fill_rate is not None else None,
            "gate_pass": r["gate_pass"], "triggered_by": r.get("triggered_by"),
            "pf": m.get("pf"), "wr": m.get("wr"), "exp_r": m.get("exp_r"),
            "avg_win": m.get("avg_win"), "avg_loss": m.get("avg_loss"),
            "total_r": m.get("total_r"), "max_dd": m.get("max_dd"), "freq": freq,
            "be": m.get("be"), "reason_stop": reasons.get("stop", 0),
            "reason_timeout": reasons.get("timeout", 0),
        })
    return pd.DataFrame(rows)


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  Espacio 2 — max_hold: sesión x max_hold bajo Bias=A/Trigger=T1_ema_cross/"
          f"Entry=C_market_close/atr_mult=1.5/atr_period=14/be=1.0R/activation=2.0R/distance=1.0R "
          f"fijos\n{'='*100}")
    cols = ["asset", "year", "role", "session", "candidate", "n_entries", "n_trades",
            "entries_per_month", "fill_rate", "pf", "wr", "exp_r", "avg_win", "avg_loss",
            "total_r", "max_dd", "freq", "be", "reason_stop", "reason_timeout",
            "gate_pass", "triggered_by"]

    control = df[df["role"] == "control"]
    print(f"\n{'-'*100}\n  Fase A — filas de control (integridad verificada OK contra 4 referencias "
          f"ya publicadas):\n{'-'*100}")
    print(control[cols].to_string(index=False) if not control.empty else "  (sin filas de control)")

    candidate = df[df["role"] == "candidate"]
    print(f"\n{'-'*100}\n  Fase B — barrido experimental (incluye max_hold=20 por su rol dual, "
          f"verificado internamente contra la Fase A):\n{'-'*100}")
    print(candidate[cols].to_string(index=False) if not candidate.empty else "  (sin filas experimentales)")

    print(f"\n{'-'*100}\n  Combinaciones candidatas que pasan los 4 gates de FRAMEWORK.md (por año):\n{'-'*100}")
    passing = candidate[candidate["gate_pass"]]
    if passing.empty:
        print("  Ninguna combinación candidata pasa los 4 gates.")
    else:
        print(passing[cols].to_string(index=False))


def print_decision(decision: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  DECISIÓN — sobrevivientes (ambos años, por activo) y ranking por PF 2023\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
            print(f"\n  {asset}: ninguna combinación (max_hold, sesión) demuestra evidencia "
                  f"suficiente para cumplir los 4 gates de FRAMEWORK.md en 2022+2023 — "
                  f"Espacio 2 (max_hold) queda sin evidencia suficiente para este activo.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="candidato ya congelado ('{max_hold} | {sesión}') para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (el candidato ya congelado)")
        results = run_blind_test(candidate=args.candidate)
    else:
        results = run_campaign()

    df = results_to_frame(results)
    print_report(df)
    out_path = "gestion_campaign_max_hold_session_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas)")

    if not args.blind:
        candidates_only = df[df["role"] == "candidate"].reset_index(drop=True)
        decision = summarize_decision(candidates_only)
        print_decision(decision)
        decision_path = "gestion_campaign_max_hold_session_decision.csv"
        decision.to_csv(decision_path, index=False)
        print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
