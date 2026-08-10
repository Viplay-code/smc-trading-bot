#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/bias_campaign_session.py — Iniciativa G × sesión: Bias A vs A2
bajo sesión (`control_8h`/`dcv1_activo_15h`), bajo Trigger=T1_ema_cross/
Entry=C_market_close/Gestión V3-A única (be=1.0R/activation=2.0R/
distance=1.0R, NO V3-A+V3-B en paralelo)/atr_mult=1.5 fijos. Contrato
acordado 2026-08-10.

Contexto: Iniciativa G (original) cerró bajo `control_8h` con datos reales
ya publicados (`scripts/bias_campaign.py`, commits `6687b46`/`487beb8`,
FRAMEWORK.md sección "Iniciativa G — Bias A vs A2 bajo control_8h"): A2
genera consistentemente más entradas que A, la diferencia de PF es moderada
(0.014-0.160) sin dirección estable entre activos/años, 0/12 combinaciones
sobreviven ambos años, máximo PF 1.386. Esa evidencia NO permite concluir
si la comparación cambia bajo `dcv1_activo_15h` — la pregunta que este
script responde.

Pregunta científica: ¿la diferencia entre Bias A y A2 se mantiene,
desaparece o cambia de magnitud bajo `dcv1_activo_15h`, comparada contra la
línea base `control_8h` ya cerrada? Formulado con más precisión: si el
efecto de cambiar A→A2 DEPENDE de la sesión (interacción Bias×sesión), no
solo si A2 es mejor o peor que A bajo una sesión aislada. Advertencia de
alcance explícita: un resultado en cualquier dirección es evidencia a favor
o en contra de la plausibilidad de que el Bias sea una palanca relevante —
NO identifica causalmente el cuello de botella del programa.

Diseño: factorial fijo 2×2 (Bias ∈ {A, A2} × sesión ∈ {control_8h,
dcv1_activo_15h}), SIN grilla ni reglas de contingencia — no hay parámetro
numérico que extender. 4 celdas × 3 activos × 2 años = 24 filas
experimentales (el N científico de esta campaña es 24, no se infla con las
verificaciones de integridad de la Fase A — ver abajo).

De las 4 celdas, 3 ya tienen antecedente computado en otro script/momento:
  - A|control_8h: ya publicado en trigger_campaign_results.csv y en
    bias_campaign_results.csv (candidate="A").
  - A|dcv1_activo_15h: ya publicado en gestion_campaign_session_results.csv
    y en integration_campaign_activation_results.csv (candidate=
    "2.0 | dcv1_activo_15h").
  - A2|control_8h: ya publicado en bias_campaign_results.csv
    (candidate="A2") — es el propio cierre de Iniciativa G (original).
Solo A2|dcv1_activo_15h es una celda genuinamente nueva.

Distinción epistemológica explícita (acordada 2026-08-10, no diluir en la
implementación): ninguna de estas referencias constituye evidencia
científicamente independiente en sentido estricto — todas describen la
MISMA secuencia histórica de precios (mismo activo/año/dataset dc_v1); lo
que varía es el camino de código que la calculó.
  - "Verificación de integridad": comparar la celda recién calculada acá
    contra una referencia calculada por un SCRIPT DISTINTO (mismo dato
    subyacente, código independiente) — sirve para detectar bugs de
    implementación, NO para acumular evidencia científica adicional.
    Aplica a A|control_8h (2 referencias: trigger_campaign.py,
    bias_campaign.py) y A|dcv1_activo_15h (2 referencias: campaña de
    sesión, I1-activation).
  - A2|control_8h NO es una verificación contra una fuente externa — es la
    reproducción exacta del propio cierre de Iniciativa G (original), del
    MISMO script (bias_campaign.py) que este acá extiende. Se trata como
    continuidad interna, no como segunda fuente independiente (solo existe
    1 referencia para esta celda, documentado como limitación, no resuelto
    inventando una segunda).
  - Total: (2+2+1) × 6 combos (activo, año) = 30 verificaciones de
    integridad de CÓDIGO — no 30 observaciones independientes del
    experimento. El N científico real son las 24 filas de resultados.

Orden de ejecución OBLIGATORIO dentro de la corrida 2022+2023 (Fase 1+2):
  - Fase A (30 verificaciones): para las 6 combinaciones (activo, año),
    computa las 3 celdas con antecedente y las compara EXACTO contra sus
    referencias (campos comparables entre TODAS: pf, wr, exp_r, max_dd,
    freq — trigger_campaign_results.csv y bias_campaign_results.csv no
    tienen avg_win/avg_loss). Si CUALQUIERA de las 30 falla,
    `AssertionError` inmediato, con el detalle completo (celda, activo,
    año, referencia, métrica, valor esperado, valor obtenido) — sin fallo
    opaco que obligue a reconstruir el mismatch manualmente. La corrida
    aborta antes de calcular la celda nueva.
  - Fase B (solo si la Fase A completa sin excepción): computa
    A2|dcv1_activo_15h para las 6 combinaciones, ensambla las 24 filas
    finales, calcula el reporte de niveles 1/2/3 y las medidas de
    interacción ΔΔPF/ΔΔfreq.

Criterios de aceptación — tres niveles, sin gate de magnitud post-hoc:
  - Nivel 1 (efecto descriptivo): ΔPF = PF(A2)-PF(A), Δfreq = freq(A2)-
    freq(A), por (activo, año, sesión). Sin umbral.
  - Nivel 2 (consistencia, SIN gate de magnitud): dirección de ΔPF
    consistente en 2022 Y 2023, en al menos 2 de 3 activos, por sesión. La
    magnitud se reporta, NO se convierte en corte numérico — ningún valor
    específico queda preespecificado como "material" (se descartó
    `|ΔPF|>=0.10` explícitamente por ser un umbral post-hoc, elegido
    después de observar la distribución de Iniciativa G original).
  - Nivel 3 (promoción): los 4 gates de `gate_check()` + supervivencia
    2022 Y 2023 vía `summarize_decision()` sin modificar — el estándar ya
    usado en todo el programa. Una diferencia consistente en dirección
    (Nivel 2) sin cumplir Nivel 3 NUNCA se interpreta como evidencia
    suficiente para promover A2.
  - Medida explícita de interacción Bias×sesión (no es un gate): por
    (activo, año), ΔPF_control = PF(A2,control_8h)-PF(A,control_8h),
    ΔPF_dcv1 = PF(A2,dcv1_activo_15h)-PF(A,dcv1_activo_15h),
    ΔΔPF = ΔPF_dcv1 - ΔPF_control (análogo para freq). Puramente
    descriptivo — responde directamente "¿el efecto de A2 depende de la
    sesión?", sin pretensión de significancia estadística formal sobre 6
    combos activo/año.

Reglas de interpretación pre-especificadas (acordadas 2026-08-10, antes de
ver resultados):
  1. A2 mejora de forma consistente bajo dcv1_activo_15h (dirección
     estable 2022→2023, en más de un activo) → Bias/definición temporal
     del Bias gana plausibilidad como fuente relevante, justifica
     investigación posterior.
  2. A y A2 siguen prácticamente indiferentes, o el signo sigue cambiando
     entre activos/años → reduce aún más la plausibilidad de que esta
     discrepancia de Bias sea una palanca útil, refuerza el caso para
     considerar Espacio 6.
  3. Resultado extremo aislado en un solo activo/año → NO se trata como
     evidencia suficiente por sí solo; debe pasar los mismos criterios de
     estabilidad interanual y gates (Nivel 3) que el resto del programa.

Fijo durante toda la campaña: Trigger=T1_ema_cross, Entry=C_market_close,
Gestión V3-A única (be=1.0R/activation=2.0R/distance=1.0R — NO V3-B en
paralelo, para aislar Bias×sesión sin introducir una segunda dimensión de
Gestión), atr_mult=1.5 (ancla H1), atr_period=14, max_hold=20, risk=0.005,
una posición a la vez, datasets dc_v1 canónicos, disciplina P-3, gates
literales de FRAMEWORK.md, 2024 ciego.

Reutilización de infraestructura (sin modificar ninguno de los archivos
reutilizados, ni backtest.py): de scripts/bias_campaign.py —
`load_asset_year` (ya computa bias_A Y bias_A2 sobre el frame continuo,
P-3), `to_backtest_frame`, `gate_check`, `summarize_decision`. De
scripts/trigger_campaign.py — `find_entries_for_trigger`. De
scripts/gestion_campaign_session.py — `SESSION_WINDOWS`.

Requiere `data/raw/` poblado. BLOQUEADO en este sandbox (HTTP 451,
data/raw/ vacío) — validado acá solo estructuralmente, ver
research/tests/test_bias_campaign_session.py.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/bias_campaign_session.py              # Fase 1+2 (incluye Fase A+B internas)
    python scripts/bias_campaign_session.py --blind        # Fase 3: 2024 ciego (requiere --candidate)
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
BE_ANCHOR = 1.0          # V3-A única, congelado — NO V3-B en paralelo
ACTIVATION_ANCHOR = 2.0
DISTANCE_ANCHOR = 1.0
ATR_MULT_ANCHOR = 1.5    # ancla de H1, congelado
EXIT_CFG = {"be": BE_ANCHOR, "activation": ACTIVATION_ANCHOR, "distance": DISTANCE_ANCHOR}

BIAS_CANDIDATES = ("A", "A2")
SESSION_LABELS = ("control_8h", "dcv1_activo_15h")
SESSION_WINDOWS = {label: session_camp.SESSION_WINDOWS[label] for label in SESSION_LABELS}

TRIGGER_CANDIDATE = "T1_ema_cross"

# Diseño factorial fijo 2x2 — sin grilla, sin contingencia.
CANDIDATES = tuple(f"{b} | {s}" for b in BIAS_CANDIDATES for s in SESSION_LABELS)
EXIT_CONFIG_LABEL = (
    "Iniciativa G x sesión (Bias A vs A2, be=1.0R/activation=2.0R/"
    "distance=1.0R, atr_mult=1.5; bias & sesión variable)"
)

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision

_TRIGGER_REF_PATH = "trigger_campaign_results.csv"
_TRIGGER_REF_EXIT_CONFIG = "V3-A (1R/2R/1R)"
_BIAS_REF_PATH = "bias_campaign_results.csv"
_BIAS_REF_EXIT_CONFIG = "V3-A (1R/2R/1R)"
_SESSION_REF_PATH = "gestion_campaign_session_results.csv"
_SESSION_REF_EXIT_CONFIG = "V3-A (1R/2R/1R)"
_I1_ACTIVATION_REF_PATH = "integration_campaign_activation_results.csv"
# Campos comparables entre TODAS las referencias — trigger_campaign_results.csv
# y bias_campaign_results.csv NO tienen avg_win/avg_loss.
_CHECK_FIELDS = ("pf", "wr", "exp_r", "max_dd", "freq")


def _label(bias: str, session_label: str) -> str:
    return f"{bias} | {session_label}"


# --------------------------------------------------------------------------- #
# Orquestación — entradas dependen de (bias, sesión): recomputar por celda    #
# --------------------------------------------------------------------------- #
def _entries_for_cell(df_full: pd.DataFrame, bias: str, session_label: str):
    cfg = backtest.Config(atr_mult=ATR_MULT_ANCHOR, sessions=SESSION_WINDOWS[session_label])
    bias_col = df_full[f"bias_{bias}"]
    frame = bias_camp.to_backtest_frame(df_full, bias_col, cfg)
    entries = trigger_camp.find_entries_for_trigger(frame, cfg, TRIGGER_CANDIDATE)
    return frame, cfg, entries


def _run_cell(df_full: pd.DataFrame, bias: str, session_label: str):
    frame, cfg, entries = _entries_for_cell(df_full, bias, session_label)
    trades = backtest.run_config(frame, entries, EXIT_CFG, cfg)
    m = backtest.metrics(trades, cfg)
    return entries, trades, m


def _row(asset: str, year: int, bias: str, session_label: str,
         entries: list[dict], trades: pd.DataFrame, m: dict | None) -> dict:
    return {
        "asset": asset, "year": year, "bias": bias, "session": session_label,
        "candidate": _label(bias, session_label), "exit_config": EXIT_CONFIG_LABEL,
        "n_entries": len(entries), "n_trades": len(trades),
        "metrics": m, "gate_pass": gate_check(m),
    }


# --------------------------------------------------------------------------- #
# Fase A — verificación de integridad de código (30 checks, NO 30            #
# observaciones independientes) contra las 3 celdas con antecedente          #
# --------------------------------------------------------------------------- #
def _trigger_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_TRIGGER_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["candidate"] == "T1_ema_cross")
               & (df["exit_config"] == _TRIGGER_REF_EXIT_CONFIG)]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para celda=A|control_8h, "
            f"activo={asset}, año={year} en {_TRIGGER_REF_PATH} — no se puede "
            f"verificar la Fase A."
        )
    return match.iloc[0]


def _bias_reference(asset: str, year: int, bias: str) -> pd.Series:
    df = pd.read_csv(_BIAS_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["candidate"] == bias)
               & (df["exit_config"] == _BIAS_REF_EXIT_CONFIG)]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para celda={bias}|control_8h, "
            f"activo={asset}, año={year} en {_BIAS_REF_PATH} — no se puede "
            f"verificar la Fase A."
        )
    return match.iloc[0]


def _session_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_SESSION_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["candidate"] == "dcv1_activo_15h")
               & (df["exit_config"] == _SESSION_REF_EXIT_CONFIG)]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para celda=A|dcv1_activo_15h, "
            f"activo={asset}, año={year} en {_SESSION_REF_PATH} — no se puede "
            f"verificar la Fase A."
        )
    return match.iloc[0]


def _i1_activation_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_I1_ACTIVATION_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["role"] == "candidate")
               & (df["candidate"] == "2.0 | dcv1_activo_15h")]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para celda=A|dcv1_activo_15h, "
            f"activo={asset}, año={year} en {_I1_ACTIVATION_REF_PATH} — no se "
            f"puede verificar la Fase A."
        )
    return match.iloc[0]


def _verify_against(cell_label: str, asset: str, year: int, ref_name: str,
                     n_entries: int, n_trades: int, m: dict | None,
                     ref_row: pd.Series) -> None:
    """Compara la celda recién calculada contra una referencia ya publicada.
    Si falla, el AssertionError identifica: celda, activo, año, referencia,
    y para cada campo divergente: nombre de la métrica, valor esperado,
    valor obtenido — sin fallo opaco."""
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
            f"\nLa corrida aborta antes de calcular la celda nueva "
            f"(A2|dcv1_activo_15h)."
        )


def run_integrity_checks(asset: str, year: int) -> dict[str, dict]:
    """Fase A para un (activo, año) — 5 de las 30 verificaciones totales de
    la campaña (2 para A|control_8h, 2 para A|dcv1_activo_15h, 1 para
    A2|control_8h). Corre y devuelve las 3 celdas con antecedente, tras
    verificarlas exitosamente. Revienta con AssertionError (sin devolver
    nada parcial) si cualquiera de las 5 falla."""
    df_full = bias_camp.load_asset_year(asset, year)

    entries_a_c8, trades_a_c8, m_a_c8 = _run_cell(df_full, "A", "control_8h")
    _verify_against("A|control_8h", asset, year, _TRIGGER_REF_PATH,
                     len(entries_a_c8), len(trades_a_c8), m_a_c8, _trigger_reference(asset, year))
    _verify_against("A|control_8h", asset, year, _BIAS_REF_PATH,
                     len(entries_a_c8), len(trades_a_c8), m_a_c8, _bias_reference(asset, year, "A"))

    entries_a_15, trades_a_15, m_a_15 = _run_cell(df_full, "A", "dcv1_activo_15h")
    _verify_against("A|dcv1_activo_15h", asset, year, _SESSION_REF_PATH,
                     len(entries_a_15), len(trades_a_15), m_a_15, _session_reference(asset, year))
    _verify_against("A|dcv1_activo_15h", asset, year, _I1_ACTIVATION_REF_PATH,
                     len(entries_a_15), len(trades_a_15), m_a_15, _i1_activation_reference(asset, year))

    entries_a2_c8, trades_a2_c8, m_a2_c8 = _run_cell(df_full, "A2", "control_8h")
    _verify_against("A2|control_8h", asset, year, _BIAS_REF_PATH,
                     len(entries_a2_c8), len(trades_a2_c8), m_a2_c8, _bias_reference(asset, year, "A2"))

    return {
        "A|control_8h": _row(asset, year, "A", "control_8h", entries_a_c8, trades_a_c8, m_a_c8),
        "A|dcv1_activo_15h": _row(asset, year, "A", "dcv1_activo_15h", entries_a_15, trades_a_15, m_a_15),
        "A2|control_8h": _row(asset, year, "A2", "control_8h", entries_a2_c8, trades_a2_c8, m_a2_c8),
        "_df_full": df_full,
    }


# --------------------------------------------------------------------------- #
# Fase B — solo la celda nueva (A2|dcv1_activo_15h) + ensamblado             #
# --------------------------------------------------------------------------- #
def run_new_cell(df_full: pd.DataFrame, asset: str, year: int) -> dict:
    entries, trades, m = _run_cell(df_full, "A2", "dcv1_activo_15h")
    return _row(asset, year, "A2", "dcv1_activo_15h", entries, trades, m)


def run_asset_year(asset: str, year: int) -> list[dict]:
    """Fase A (3 celdas con antecedente, verificadas) + Fase B (celda nueva)
    para un (activo, año). Devuelve las 4 filas."""
    known = run_integrity_checks(asset, year)  # aborta acá si Fase A falla
    df_full = known.pop("_df_full")
    new_cell = run_new_cell(df_full, asset, year)  # Fase B
    return [known["A|control_8h"], known["A|dcv1_activo_15h"],
            known["A2|control_8h"], new_cell]


def run_campaign(assets: tuple[str, ...] = ASSETS,
                  years: tuple[int, ...] = (IN_SAMPLE_YEAR, VALIDATION_YEAR)) -> list[dict]:
    """Fase 1(2022)+Fase 2(2023). Internamente: Fase A completa para las 6
    combinaciones (activo, año) ANTES de que se calcule ninguna celda nueva
    — si run_integrity_checks revienta en cualquier combinación, la
    excepción se propaga acá y la función nunca llega a calcular
    A2|dcv1_activo_15h para ningún combo. NO incluye 2024 — ver
    run_blind_test."""
    known_by_combo: dict[tuple[str, int], dict] = {}
    for year in years:
        for asset in assets:
            known_by_combo[(asset, year)] = run_integrity_checks(asset, year)  # Fase A

    results: list[dict] = []
    for year in years:
        for asset in assets:
            known = known_by_combo[(asset, year)]
            df_full = known["_df_full"]
            new_cell = run_new_cell(df_full, asset, year)  # Fase B
            results.extend([known["A|control_8h"], known["A|dcv1_activo_15h"],
                             known["A2|control_8h"], new_cell])

    return results


def run_blind_test(assets: tuple[str, ...] = ASSETS,
                    candidate: str | None = None) -> list[dict]:
    """Fase 3 (2024, ciego). Requiere `candidate` (string compuesto
    "{bias} | {session}") ya congelado tras decidir con 2022+2023. No corre
    Fase A acá (exclusiva de la fase 2022+2023)."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere un candidato ya congelado {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una "
            "decisión previa."
        )
    bias_str, session_label = (p.strip() for p in candidate.split("|"))
    results: list[dict] = []
    for asset in assets:
        df_full = bias_camp.load_asset_year(asset, BLIND_YEAR)
        entries, trades, m = _run_cell(df_full, bias_str, session_label)
        results.append(_row(asset, BLIND_YEAR, bias_str, session_label, entries, trades, m))
    return results


# --------------------------------------------------------------------------- #
# Reporte — resultados/decisión estándar + niveles 1/2/3 + interacción       #
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
            "asset": r["asset"], "year": r["year"], "bias": r["bias"], "session": r["session"],
            "candidate": r["candidate"], "exit_config": r["exit_config"],
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
    """Nivel 1 (efecto descriptivo) + medida explícita de interacción
    Bias×sesión. Por (activo, año): ΔPF_control, ΔPF_dcv1, ΔΔPF y los
    análogos de freq. Puramente descriptivo, sin gate."""
    rows = []
    for (asset, year), g in df.groupby(["asset", "year"]):
        by_cell = g.set_index("candidate")
        pf_a_c8 = by_cell.loc[_label("A", "control_8h"), "pf"]
        pf_a2_c8 = by_cell.loc[_label("A2", "control_8h"), "pf"]
        pf_a_15 = by_cell.loc[_label("A", "dcv1_activo_15h"), "pf"]
        pf_a2_15 = by_cell.loc[_label("A2", "dcv1_activo_15h"), "pf"]
        freq_a_c8 = by_cell.loc[_label("A", "control_8h"), "freq"]
        freq_a2_c8 = by_cell.loc[_label("A2", "control_8h"), "freq"]
        freq_a_15 = by_cell.loc[_label("A", "dcv1_activo_15h"), "freq"]
        freq_a2_15 = by_cell.loc[_label("A2", "dcv1_activo_15h"), "freq"]

        delta_pf_control = pf_a2_c8 - pf_a_c8
        delta_pf_dcv1 = pf_a2_15 - pf_a_15
        delta_freq_control = freq_a2_c8 - freq_a_c8
        delta_freq_dcv1 = freq_a2_15 - freq_a_15

        rows.append({
            "asset": asset, "year": year,
            "pf_A_control_8h": pf_a_c8, "pf_A2_control_8h": pf_a2_c8,
            "pf_A_dcv1_activo_15h": pf_a_15, "pf_A2_dcv1_activo_15h": pf_a2_15,
            "delta_pf_control": round(delta_pf_control, 3) if pd.notna(delta_pf_control) else None,
            "delta_pf_dcv1": round(delta_pf_dcv1, 3) if pd.notna(delta_pf_dcv1) else None,
            "delta_delta_pf": round(delta_pf_dcv1 - delta_pf_control, 3)
                               if pd.notna(delta_pf_dcv1) and pd.notna(delta_pf_control) else None,
            "delta_freq_control": round(delta_freq_control, 2) if pd.notna(delta_freq_control) else None,
            "delta_freq_dcv1": round(delta_freq_dcv1, 2) if pd.notna(delta_freq_dcv1) else None,
            "delta_delta_freq": round(delta_freq_dcv1 - delta_freq_control, 2)
                                  if pd.notna(delta_freq_dcv1) and pd.notna(delta_freq_control) else None,
        })
    return pd.DataFrame(rows)


def assess_level2_consistency(deltas: pd.DataFrame) -> dict:
    """Nivel 2 — consistencia de dirección de ΔPF entre 2022 y 2023, en al
    menos 2 de 3 activos, POR SESIÓN. Sin gate de magnitud: no se aplica
    ningún umbral numérico, solo se evalúa el signo. Devuelve un resumen
    descriptivo, no una decisión de promoción (eso es exclusivamente
    Nivel 3, vía gate_check/summarize_decision)."""
    def _consistent(col: str) -> dict:
        by_asset = deltas.pivot(index="asset", columns="year", values=col)
        same_sign = {}
        for asset in by_asset.index:
            vals = by_asset.loc[asset].dropna()
            if len(vals) < 2:
                same_sign[asset] = None
                continue
            same_sign[asset] = bool((vals > 0).all() or (vals < 0).all())
        n_consistent = sum(1 for v in same_sign.values() if v)
        return {"por_activo": same_sign, "n_activos_consistentes": n_consistent,
                "consistente_en_al_menos_2": n_consistent >= 2}

    return {
        "delta_pf_control": _consistent("delta_pf_control"),
        "delta_pf_dcv1": _consistent("delta_pf_dcv1"),
        "delta_delta_pf": _consistent("delta_delta_pf"),
    }


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  Iniciativa G x sesión — Bias A vs A2 bajo control_8h (ya cerrado) vs "
          f"dcv1_activo_15h (nuevo)\n  Trigger=T1_ema_cross/Entry=C_market_close/Gestión V3-A única\n{'='*100}")
    cols = ["asset", "year", "bias", "session", "n_entries", "n_trades",
            "entries_per_month", "fill_rate", "pf", "wr", "exp_r", "avg_win", "avg_loss",
            "total_r", "max_dd", "freq", "be", "reason_stop", "reason_timeout", "gate_pass"]
    print(df[cols].to_string(index=False))

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (Nivel 3, por año):\n{'-'*100}")
    passing = df[df["gate_pass"]]
    if passing.empty:
        print("  Ninguna combinación pasa los 4 gates.")
    else:
        print(passing[cols].to_string(index=False))


def print_deltas(deltas: pd.DataFrame, level2: dict) -> None:
    print(f"\n{'='*100}\n  Nivel 1 — efecto descriptivo (ΔPF, ΔΔPF por activo/año)\n{'='*100}")
    print(deltas.to_string(index=False))

    print(f"\n{'-'*100}\n  Nivel 2 — consistencia de dirección (SIN gate de magnitud, solo signo):\n{'-'*100}")
    for metric, res in level2.items():
        print(f"  {metric}: {res['por_activo']} -> consistente en >=2 activos: "
              f"{res['consistente_en_al_menos_2']}")


def print_decision(decision: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  Nivel 3 — DECISIÓN: sobrevivientes (ambos años, por activo) y ranking "
          f"por PF 2023\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
            print(f"\n  {asset}: ninguna combinación (bias, sesión) demuestra evidencia suficiente "
                  f"para cumplir los 4 gates de FRAMEWORK.md en 2022+2023 — Nivel 3 no alcanzado "
                  f"para este activo (independientemente de lo observado en Nivel 1/2).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="candidato ya congelado ('{bias} | {sesión}') para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (el candidato ya congelado)")
        results = run_blind_test(candidate=args.candidate)
        df = results_to_frame(results)
        print_report(df)
        out_path = "bias_campaign_session_results.csv"
        df.to_csv(out_path, index=False)
        print(f"\nResultados exportados a {out_path} ({len(df)} filas)")
        return

    results = run_campaign()
    df = results_to_frame(results)
    print_report(df)
    out_path = "bias_campaign_session_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas)")

    decision = summarize_decision(df)
    print_decision(decision)
    decision_path = "bias_campaign_session_decision.csv"
    decision.to_csv(decision_path, index=False)
    print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")

    deltas = compute_deltas(df)
    level2 = assess_level2_consistency(deltas)
    print_deltas(deltas, level2)
    deltas_path = "bias_campaign_session_deltas.csv"
    deltas.to_csv(deltas_path, index=False)
    print(f"Deltas (Nivel 1 + interacción) exportados a {deltas_path} ({len(deltas)} filas)")


if __name__ == "__main__":
    main()
