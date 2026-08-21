#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/trigger_c_campaign.py — Trigger C: BOS-only, ablación de
A_sweep_bos (candidato "C" de Capa 2 de FRAMEWORK.md, "Solo BOS sin sweep
previo"). Diseño científico formal cerrado 2026-08-19 (inspección de código,
formalización matemática de BOS-only, prueba de ablación Eventos(A) ⊆
Eventos(C), análisis de causalidad, resolución de la ambigüedad de
dirección, y resolución del filtro de riesgo degenerado — todo en sesión de
trabajo, ver `research.layers::trigger_C_bos_only` para la formalización
completa). Prioridad #1 de Espacio 5 (checkpoint 2026-08-19,
`docs/research/EXPERIMENTAL_ROADMAP.md`, "Estado de priorización — Espacio
5"), fundamentada exclusivamente en propiedades ex ante del mecanismo, sin
usar ningún resultado de campaña previa.

Objetivo científico: ¿eliminar el requisito de Liquidity Sweep y usar
únicamente BOS como Trigger permite aumentar la disponibilidad de señales
sin destruir la calidad de la señal, manteniendo constantes las demás capas
del armazón? Trigger como ÚNICA variable experimental — Bias/Entry/sesión/
Gestión permanecen exactamente en su ancla ya usada en el resto del
programa.

Comparador principal: `A_sweep_bos` bajo el MISMO contrato (misma sesión,
mismo Entry, mismo resto) — único comparador que aísla la variable bajo
prueba (presencia/ausencia del requisito de sweep). `T1_ema_cross` y
`D_range_breakout` son contexto únicamente, NO válidos para concluir sobre
esta hipótesis (familias de mecanismo distintas — ver diseño formal).

Contrato congelado (2026-08-19, sin modificar): Bias=A/Trigger=C_bos_only
(`bos_lookback`=5/`bos_max_candles`=3, defaults ya declarados en
`_detect_bos`)/Entry=C_market_close/Gestión V3-A ancla (`be`=1.0R/
`activation`=2.0R/`distance`=1.0R)/`atr_mult`=1.5/`atr_period`=14/
`max_hold`=20/`risk`=0.005/sesión=`dcv1_activo_15h` única/BTCUSDT/ETHUSDT/
SOLUSDT/2022+2023 (2024 no ejecutado en esta fase). Sin filtro de riesgo
degenerado interno en Trigger C (decisión explícita, ver diseño formal:
delegado enteramente al orquestador, `find_entries_for_entry`, mismo patrón
que `A_sweep_bos`/`D_range_breakout`). `meta={}` siempre — incompatible con
`entry_A_pullback_50` (requiere `event.meta["bos_level"]`/`swing_low`/
`swing_high`, ausentes acá), compatible con `entry_C_market_close` (la
Entry congelada de esta campaña).

Verificación de integridad (Fase A) — mismo diseño que Rama B, porque la
celda objetivo (Trigger C) no tiene ningún antecedente histórico bajo
ninguna sesión: se verifica el pipeline COMPARTIDO (frame/Bias/sesión/
filtro genérico de entradas) vía la celda auxiliar `A_sweep_bos`+
`C_market_close` bajo `dcv1_activo_15h`, contra la referencia ya publicada
de Espacio 3 (`trigger_campaign_sweep_bos_session_results.csv`, ver
`_SWEEP_BOS_SESSION_REF_PATH`). 6 verificaciones totales (una por
activo/año), comparación NaN-consciente (ETHUSDT/2023 no computable en la
referencia). Si CUALQUIERA falla, `AssertionError` inmediato — la corrida
aborta antes de calcular una sola de las 6 filas candidatas.

Reutilización de infraestructura (sin modificar ninguno de los archivos
reutilizados, ni `backtest.py`, ni `_detect_sweep_at`/`_detect_bos`/
`trigger_A_sweep_bos`/`trigger_D_range_breakout`/`trigger_T1_ema_cross`):
de `scripts/bias_campaign.py` — `to_backtest_frame`, `gate_check`,
`summarize_decision`. De `scripts/trigger_campaign.py` — `load_asset_year`
(fija Bias=A). De `scripts/gestion_campaign_session.py` — `SESSION_WINDOWS`.
De `scripts/entry_campaign_sweep_bos.py` — `find_entries_for_entry`
(Trigger-agnóstica, ya confirmada — recibe los eventos crudos como
parámetro, sin ningún dispatch por nombre de Trigger). De
`research.TRIGGER_LAYERS` — `A_sweep_bos` (auxiliar de Fase A) y
`C_bos_only` (nuevo, implementado en `research/layers.py`).

Requiere `data/raw/` poblado. BLOQUEADO en este sandbox (HTTP 451,
data/raw/ vacío) — validado acá solo estructuralmente, más una porción real
sobre `trigger_campaign_sweep_bos_session_results.csv` (ya committeado, no
requiere data/raw/), ver research/tests/test_trigger_c_campaign.py.

Uso (desde la raíz del repo, con data/raw/ poblado — NO ejecutado todavía,
requiere autorización explícita separada):
    python scripts/trigger_c_campaign.py              # Fase 1+2 (incluye Fase A+B internas)
    python scripts/trigger_c_campaign.py --blind        # Fase 3: 2024 ciego (requiere --candidate)
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import argparse

import pandas as pd

import backtest
import research
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as trigger_camp
import scripts.gestion_campaign_session as session_camp
import scripts.entry_campaign_sweep_bos as entry_sweep_bos
from market_data import ASSETS

# --------------------------------------------------------------------------- #
# Config de la campaña — contrato congelado 2026-08-19                       #
# --------------------------------------------------------------------------- #
BIAS_CANDIDATE = "A"                  # fijado en trigger_camp.load_asset_year, no parametrizado acá
TRIGGER_CANDIDATE = "C_bos_only"      # único Trigger variable de esta campaña
ENTRY_CANDIDATE = "C_market_close"    # congelado (aprobado 2026-08-19, no D_next_candle_open)
SESSION_LABEL = "dcv1_activo_15h"     # ÚNICA sesión de esta campaña
SESSION_WINDOW = session_camp.SESSION_WINDOWS[SESSION_LABEL]

ATR_MULT_ANCHOR = 1.5     # ancla de H1, congelado
ATR_PERIOD_ANCHOR = 14    # fijo — excluido, ver Espacio 2
MAX_HOLD_ANCHOR = 20      # fijo — ya evaluado y falsificado en Espacio 2
BE_ANCHOR = 1.0            # V3-A, congelado
ACTIVATION_ANCHOR = 2.0    # V3-A, congelado
DISTANCE_ANCHOR = 1.0      # V3-A, congelado
EXIT_CFG = {"be": BE_ANCHOR, "activation": ACTIVATION_ANCHOR, "distance": DISTANCE_ANCHOR}

CANDIDATE_LABEL = f"{TRIGGER_CANDIDATE} + {ENTRY_CANDIDATE}"
CANDIDATES = (CANDIDATE_LABEL,)  # una sola celda de candidato — sin grid, sin variar Entry

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision

EXIT_CONFIG_LABEL = (
    "Trigger C — BOS-only (Bias=A/Entry=C_market_close/Gestión V3-A ancla/"
    "atr_mult=1.5/atr_period=14/max_hold=20/risk=0.005 fijos; sesión="
    "dcv1_activo_15h única; comparador principal: A_sweep_bos bajo el "
    "mismo contrato, ver diseño formal de Trigger C — T1_ema_cross y "
    "D_range_breakout son contexto únicamente, no comparador válido)"
)

# Referencia de Fase A — celda AUXILIAR (A_sweep_bos + C_market_close bajo
# dcv1_activo_15h), NO la celda objetivo. Mismo patrón que Rama B: la celda
# objetivo (Trigger C) no tiene ningún antecedente histórico bajo ninguna
# sesión, así que Fase A verifica el pipeline COMPARTIDO por ambas.
_SWEEP_BOS_SESSION_REF_PATH = "trigger_campaign_sweep_bos_session_results.csv"
_SWEEP_BOS_SESSION_REF_EXIT_CONFIG = (
    "Espacio 3 — A_sweep_bos (V3-A anchor: be=1.0R/activation=2.0R/"
    "distance=1.0R, session variable)"
)
_CHECK_FIELDS = ("pf", "wr", "exp_r", "max_dd", "freq")


# --------------------------------------------------------------------------- #
# Orquestación                                                                #
# --------------------------------------------------------------------------- #
def _frame_for_asset_year(asset: str, year: int):
    df_full = trigger_camp.load_asset_year(asset, year)
    cfg = backtest.Config(atr_mult=ATR_MULT_ANCHOR, atr_period=ATR_PERIOD_ANCHOR,
                           max_hold=MAX_HOLD_ANCHOR, sessions=SESSION_WINDOW)
    frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
    return frame, cfg


def _run_combo(frame: pd.DataFrame, cfg: "backtest.Config", trigger_name: str, entry_name: str):
    """Genera los eventos crudos del Trigger indicado directamente desde
    `research.TRIGGER_LAYERS` (sin ningún dispatch especial por nombre) y
    reutiliza `entry_sweep_bos.find_entries_for_entry` — Trigger-agnóstica,
    ya confirmada — para aplicar el filtro de bias/sesión/riesgo degenerado
    y calcular el precio de entrada. Ninguna rama de este código depende de
    qué Trigger se pasó."""
    raw_events = research.TRIGGER_LAYERS[trigger_name](frame)
    entries = entry_sweep_bos.find_entries_for_entry(frame, cfg, raw_events, entry_name)
    trades = backtest.run_config(frame, entries, EXIT_CFG, cfg)
    m = backtest.metrics(trades, cfg)
    return entries, trades, m


def _row(asset: str, year: int, trigger_name: str, entry_name: str,
         entries: list[dict], trades: pd.DataFrame, m: dict | None) -> dict:
    return {
        "asset": asset, "year": year, "trigger": trigger_name, "entry": entry_name,
        "candidate": CANDIDATE_LABEL, "exit_config": EXIT_CONFIG_LABEL,
        "n_entries": len(entries), "n_trades": len(trades),
        "metrics": m, "gate_pass": gate_check(m),
    }


# --------------------------------------------------------------------------- #
# Fase A — verificación de integridad del pipeline COMPARTIDO (6 checks)      #
# --------------------------------------------------------------------------- #
def _sweep_bos_dcv1_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_SWEEP_BOS_SESSION_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["role"] == "candidate") & (df["candidate"] == SESSION_LABEL)
               & (df["exit_config"] == _SWEEP_BOS_SESSION_REF_EXIT_CONFIG)]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para celda=A_sweep_bos + C_market_close "
            f"(verificación), activo={asset}, año={year} en {_SWEEP_BOS_SESSION_REF_PATH} — "
            f"no se puede verificar la Fase A."
        )
    return match.iloc[0]


def _values_match(actual, expected) -> bool:
    """Comparación NaN-consciente: ETHUSDT/2023 es no-computable en la
    referencia de Espacio 3 (NaN != NaN normalmente), mismo criterio ya
    usado en el cierre de Espacio 3 y en Rama B."""
    if pd.isna(actual) and pd.isna(expected):
        return True
    return actual == expected


def _verify_against(cell_label: str, asset: str, year: int, ref_name: str,
                     n_entries: int, n_trades: int, m: dict | None,
                     ref_row: pd.Series) -> None:
    mismatches = []
    if not _values_match(n_entries, ref_row["n_entries"]):
        mismatches.append(f"n_entries: esperado={ref_row['n_entries']!r}, obtenido={n_entries!r}")
    if not _values_match(n_trades, ref_row["n_trades"]):
        mismatches.append(f"n_trades: esperado={ref_row['n_trades']!r}, obtenido={n_trades!r}")
    for field in _CHECK_FIELDS:
        expected = ref_row[field]
        actual = m.get(field) if m else None
        if not _values_match(actual, expected):
            mismatches.append(f"{field}: esperado={expected!r}, obtenido={actual!r}")
    if mismatches:
        raise AssertionError(
            f"Fase A (verificación de integridad del pipeline compartido) falló — "
            f"celda={cell_label}, activo={asset}, año={year}, referencia={ref_name}:\n  "
            + "\n  ".join(mismatches) +
            f"\nLa corrida aborta antes de calcular la celda objetivo de Trigger C."
        )


def run_integrity_check(asset: str, year: int):
    """Fase A para un (activo, año) — 1 de las 6 verificaciones totales de
    la campaña. Verifica ÚNICAMENTE la celda auxiliar A_sweep_bos+
    C_market_close (NO la celda objetivo de Trigger C, que carece de
    antecedente histórico bajo cualquier sesión). Devuelve frame/cfg
    (compartidos con Fase B) tras verificar. Revienta con AssertionError si
    la verificación falla."""
    frame, cfg = _frame_for_asset_year(asset, year)
    entries, trades, m = _run_combo(frame, cfg, "A_sweep_bos", "C_market_close")
    ref = _sweep_bos_dcv1_reference(asset, year)
    _verify_against("A_sweep_bos + C_market_close (verificación de pipeline compartido)",
                     asset, year, _SWEEP_BOS_SESSION_REF_PATH, len(entries), len(trades), m, ref)
    return frame, cfg


# --------------------------------------------------------------------------- #
# Fase B — la celda objetivo (solo tras Fase A completa sin excepción)        #
# --------------------------------------------------------------------------- #
def run_asset_year_target(asset: str, year: int, frame: pd.DataFrame, cfg: "backtest.Config") -> dict:
    entries, trades, m = _run_combo(frame, cfg, TRIGGER_CANDIDATE, ENTRY_CANDIDATE)
    return _row(asset, year, TRIGGER_CANDIDATE, ENTRY_CANDIDATE, entries, trades, m)


def run_campaign(assets: tuple[str, ...] = ASSETS,
                  years: tuple[int, ...] = (IN_SAMPLE_YEAR, VALIDATION_YEAR)) -> list[dict]:
    """Fase 1(2022)+Fase 2(2023). Fase A completa para las 6 combinaciones
    (activo, año) ANTES de que arranque la Fase B — si run_integrity_check
    revienta en cualquier combinación, la excepción se propaga acá y la
    función nunca llega a calcular la celda objetivo. NO incluye 2024 — ver
    run_blind_test."""
    known: dict[tuple[str, int], tuple] = {}
    for year in years:
        for asset in assets:
            known[(asset, year)] = run_integrity_check(asset, year)  # Fase A

    rows: list[dict] = []
    for year in years:
        for asset in assets:
            frame, cfg = known[(asset, year)]
            rows.append(run_asset_year_target(asset, year, frame, cfg))  # Fase B
    return rows


def run_blind_test(assets: tuple[str, ...] = ASSETS,
                    candidate: str | None = None) -> list[dict]:
    """Fase 3 (2024, ciego). Requiere `candidate` ya congelado ("C_bos_only
    + C_market_close" — la única celda de esta campaña). No corre Fase A
    acá (exclusiva de la fase 2022+2023)."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere el candidato ya congelado {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una "
            "decisión previa."
        )
    results: list[dict] = []
    for asset in assets:
        frame, cfg = _frame_for_asset_year(asset, BLIND_YEAR)
        entries, trades, m = _run_combo(frame, cfg, TRIGGER_CANDIDATE, ENTRY_CANDIDATE)
        results.append(_row(asset, BLIND_YEAR, TRIGGER_CANDIDATE, ENTRY_CANDIDATE, entries, trades, m))
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
            "asset": r["asset"], "year": r["year"], "trigger": r["trigger"], "entry": r["entry"],
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


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  Trigger C — BOS-only + C_market_close (comparador: A_sweep_bos)\n"
          f"  Bias=A/Gestión V3-A ancla/sesión=dcv1_activo_15h única fijos\n{'='*100}")
    cols = ["asset", "year", "trigger", "entry", "n_entries", "n_trades",
            "entries_per_month", "fill_rate", "pf", "wr", "exp_r", "avg_win", "avg_loss",
            "total_r", "max_dd", "freq", "be", "reason_stop", "reason_timeout", "gate_pass"]
    print(df[cols].to_string(index=False))

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (por año):\n{'-'*100}")
    passing = df[df["gate_pass"]]
    if passing.empty:
        print("  Ninguna combinación pasa los 4 gates.")
    else:
        print(passing[cols].to_string(index=False))


def print_decision(decision: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  DECISIÓN: sobrevivientes (ambos años, por activo) y ranking por PF 2023\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
            print(f"\n  {asset}: Trigger C no demuestra evidencia suficiente para cumplir los 4 "
                  f"gates de FRAMEWORK.md en 2022+2023.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="candidato ya congelado para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (el candidato ya congelado)")
        results = run_blind_test(candidate=args.candidate)
        df = results_to_frame(results)
        print_report(df)
        out_path = "trigger_c_campaign_results.csv"
        df.to_csv(out_path, index=False)
        print(f"\nResultados exportados a {out_path} ({len(df)} filas)")
        return

    results = run_campaign()
    df = results_to_frame(results)
    print_report(df)
    out_path = "trigger_c_campaign_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas — 1 combo x 3 activos x 2 "
          f"años = 6, todas genuinamente nuevas)")

    decision = summarize_decision(df)
    print_decision(decision)
    decision_path = "trigger_c_campaign_decision.csv"
    decision.to_csv(decision_path, index=False)
    print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
