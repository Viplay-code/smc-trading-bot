#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/gestion_espacio6_costo_cero_diagnostico.py — DIAGNÓSTICO de
costos (NO una campaña experimental, NO produce un candidato): cuánto del
techo de PF/ExpR observado bajo V3-A está explicado por el modelo de
costos (0.09%/trade) y cuánto permanece cuando se elimina ese costo.

Autorizado explícitamente como diagnóstico controlado sobre evidencia ya
existente (contrato de Espacio 6: Bias=A/Trigger=T1_ema_cross/Entry=
C_market_close/sesión=dcv1_activo_15h/BTCUSDT-ETHUSDT-SOLUSDT/2022+2023),
comparando ÚNICAMENTE `backtest.COST_PER_TRADE=0.0009` (real) vs `=0.0`
sobre el mecanismo V3-A, sin cambiar ninguna otra variable.

Restricciones del contrato (todas verificadas en este script, no solo
declaradas):
  - No se modifica backtest.py ni simulate_v3 en disco — se reutilizan
    sin editar, con backtest.COST_PER_TRADE monkeypatcheado
    TEMPORALMENTE (try/finally, restaurado siempre) para el brazo
    costo=0. Fundamento estructural (verificado en código,
    backtest.py:144-236): `cost_r = (e * COST_PER_TRADE) / risk_pts` se
    calcula en la línea 226, DESPUÉS de que el bucle de salida (stop/BE/
    trailing/timeout, líneas 168-211) ya determinó exit_idx/exit_price/
    reason — el costo NUNCA participa en ninguna decisión de salida, solo
    resta al final. Esto garantiza, por construcción, que cambiar
    COST_PER_TRADE no puede alterar qué trade ocurre, cuándo, ni por qué
    — solo reescala pnl_r.
  - No se cambia Bias/Trigger/Entry/sesión/SL/BE/trailing/TP/ningún
    parámetro — ambos brazos usan `backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"]`
    sin modificar y las MISMAS entradas (mismo objeto, no recomputado).
  - No se hace grid search — una sola celda de comparación (con costo /
    sin costo) por (activo, año), 6 celdas, sin barrido de parámetros.
  - No se usa 2024 — solo 2022+2023, `run_blind_test` no existe en este
    módulo.
  - No se crea ningún candidato — `MECHANISM_LABEL` está marcado
    explícitamente como "diagnóstico", no participa en ningún flujo de
    selección de variantes ni se declara PASS/FAIL en el sentido del
    framework (el gate de producción sigue siendo el de costos reales).

Verificación estructural (Fase A extendida, obligatoria antes de aceptar
cualquier resultado):
  1. Reproducir V3-A con costo real (0.0009) contra
     `gestion_campaign_session_results.csv` — 6/6, igual que en E1/E2/
     Raw/E3.
  2. Correr el brazo costo=0 sobre las MISMAS entradas.
  3. Verificar, trade por trade, que ambos brazos tienen exactamente el
     mismo n_trades, mismo `entry_time`/`exit_time`/`reason` (el costo no
     movió ninguna decisión de salida).
  4. Verificar, trade por trade, que
     `pnl_r(costo=0) - pnl_r(costo=0.0009) == cost_r_esperado`, donde
     `cost_r_esperado = entry["entry"] * 0.0009 / entry["risk_pts"]`,
     calculado independientemente desde las entradas — no leído de
     ningún resultado ya calculado.
Si CUALQUIERA de estas verificaciones falla, el script aborta con
AssertionError antes de exportar ningún resultado.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/gestion_espacio6_costo_cero_diagnostico.py
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import pandas as pd

import backtest
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as trigger_camp
import scripts.gestion_campaign_session as session_camp
from market_data import ASSETS

# --------------------------------------------------------------------------- #
# Contrato — idéntico al ancla de Espacio 6, sin ninguna variable nueva      #
# --------------------------------------------------------------------------- #
BIAS_CANDIDATE = "A"
TRIGGER_CANDIDATE = "T1_ema_cross"
ENTRY_CANDIDATE = "C_market_close"
SESSION_LABEL = "dcv1_activo_15h"
SESSION_WINDOW = session_camp.SESSION_WINDOWS[SESSION_LABEL]

ATR_MULT_ANCHOR = 1.5
ATR_PERIOD_ANCHOR = 14
MAX_HOLD_ANCHOR = 20

V3A_EXIT_CFG = backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"]
COST_REAL = 0.0009    # backtest.COST_PER_TRADE, valor real de producción
COST_ZERO = 0.0

MECHANISM_LABEL = "DIAGNOSTICO_costo_cero__NO_es_un_candidato"

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
gate_check = bias_camp.gate_check

_V3A_REF_PATH = "gestion_campaign_session_results.csv"
_V3A_REF_CANDIDATE = "dcv1_activo_15h"
_V3A_REF_EXIT_CONFIG = "V3-A (1R/2R/1R)"
_CHECK_FIELDS = ("pf", "wr", "exp_r", "max_dd", "freq")


# --------------------------------------------------------------------------- #
# Orquestación                                                                #
# --------------------------------------------------------------------------- #
def _cfg() -> "backtest.Config":
    return backtest.Config(atr_mult=ATR_MULT_ANCHOR, atr_period=ATR_PERIOD_ANCHOR,
                            max_hold=MAX_HOLD_ANCHOR, sessions=SESSION_WINDOW)


def _entries_for_asset_year(asset: str, year: int):
    df_full = trigger_camp.load_asset_year(asset, year)
    cfg = _cfg()
    frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
    entries = backtest.find_entries(frame, cfg)
    return frame, cfg, entries


def _v3a_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_V3A_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["candidate"] == _V3A_REF_CANDIDATE)
               & (df["exit_config"] == _V3A_REF_EXIT_CONFIG)]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia V3-A para activo={asset}, "
            f"año={year} en {_V3A_REF_PATH}."
        )
    return match.iloc[0]


def run_config_with_cost(frame: pd.DataFrame, entries: list[dict], cfg: "backtest.Config",
                          cost: float) -> pd.DataFrame:
    """Corre backtest.run_config/simulate_v3 SIN MODIFICAR, con
    backtest.COST_PER_TRADE parcheado TEMPORALMENTE al valor pedido —
    restaurado siempre, incluso si run_config lanza una excepción."""
    orig_cost = backtest.COST_PER_TRADE
    backtest.COST_PER_TRADE = cost
    try:
        trades = backtest.run_config(frame, entries, V3A_EXIT_CFG, cfg)
    finally:
        backtest.COST_PER_TRADE = orig_cost
    return trades


def _verify_pair(asset: str, year: int, frame: pd.DataFrame, entries: list[dict],
                  trades_real: pd.DataFrame, trades_zero: pd.DataFrame) -> dict:
    entry_by_time = {frame.index[e["entry_idx"]]: e for e in entries}
    problems = []
    cost_r_deltas = []
    cost_r_expected_list = []

    if len(trades_real) != len(trades_zero):
        problems.append(f"n_trades difiere: costo_real={len(trades_real)} costo_cero={len(trades_zero)}")

    n = min(len(trades_real), len(trades_zero))
    for i in range(n):
        r_real = trades_real.iloc[i]
        r_zero = trades_zero.iloc[i]
        if r_real["entry_time"] != r_zero["entry_time"]:
            problems.append(f"fila {i}: entry_time difiere ({r_real['entry_time']} vs {r_zero['entry_time']})")
            continue
        if r_real["exit_time"] != r_zero["exit_time"]:
            problems.append(f"fila {i}: exit_time difiere para entry_time={r_real['entry_time']}")
        if r_real["reason"] != r_zero["reason"]:
            problems.append(f"fila {i}: reason difiere para entry_time={r_real['entry_time']} "
                             f"({r_real['reason']!r} vs {r_zero['reason']!r})")

        ent = entry_by_time.get(r_real["entry_time"])
        if ent is None:
            problems.append(f"fila {i}: sin entrada original emparejable por entry_time")
            continue
        cost_r_expected = round((ent["entry"] * COST_REAL) / ent["risk_pts"], 4)
        delta_observed = round(r_zero["pnl_r"] - r_real["pnl_r"], 4)
        cost_r_deltas.append(delta_observed)
        cost_r_expected_list.append(cost_r_expected)
        if abs(delta_observed - cost_r_expected) > 1e-3:
            problems.append(f"fila {i}: delta pnl_r observado ({delta_observed}) != "
                             f"cost_r esperado ({cost_r_expected})")

    stats = None
    if cost_r_expected_list:
        s = pd.Series(cost_r_expected_list)
        stats = {"asset": asset, "year": year, "n": len(cost_r_expected_list),
                  "cost_r_min": round(s.min(), 4), "cost_r_mean": round(s.mean(), 4),
                  "cost_r_max": round(s.max(), 4)}

    return {"ok": len(problems) == 0, "problems": problems, "cost_r_stats": stats}


def run_integrity_and_diagnostic(asset: str, year: int) -> dict:
    """Fase A (paso 1, contra la referencia real) + Fase B (ambos
    brazos) + verificación estructural — todo en un solo lugar, revienta
    con AssertionError si CUALQUIER verificación falla."""
    frame, cfg, entries = _entries_for_asset_year(asset, year)

    # Paso 1 — Fase A estándar (costo real) contra la referencia publicada
    trades_real = run_config_with_cost(frame, entries, cfg, COST_REAL)
    m_real = backtest.metrics(trades_real, cfg)
    ref = _v3a_reference(asset, year)
    mismatches = []
    if len(entries) != ref["n_entries"]:
        mismatches.append(f"n_entries: esperado={ref['n_entries']}, obtenido={len(entries)}")
    if len(trades_real) != ref["n_trades"]:
        mismatches.append(f"n_trades: esperado={ref['n_trades']}, obtenido={len(trades_real)}")
    for field in _CHECK_FIELDS:
        if m_real.get(field) != ref[field]:
            mismatches.append(f"{field}: esperado={ref[field]!r}, obtenido={m_real.get(field)!r}")
    if mismatches:
        raise AssertionError(
            f"Fase A (costo real) falló — activo={asset}, año={year}:\n  "
            + "\n  ".join(mismatches)
        )

    # Paso 2 — brazo costo=0, MISMAS entradas
    trades_zero = run_config_with_cost(frame, entries, cfg, COST_ZERO)
    m_zero = backtest.metrics(trades_zero, cfg)

    # Paso 3/4 — verificación estructural
    verification = _verify_pair(asset, year, frame, entries, trades_real, trades_zero)
    if not verification["ok"]:
        raise AssertionError(
            f"Verificación estructural (costo=0 vs costo real) falló — activo={asset}, "
            f"año={year}:\n  " + "\n  ".join(verification["problems"])
        )

    return {"asset": asset, "year": year, "n_entries": len(entries),
            "n_trades": len(trades_real), "m_real": m_real, "m_zero": m_zero,
            "verification": verification}


def run_diagnostic(assets: tuple[str, ...] = ASSETS,
                    years: tuple[int, ...] = (IN_SAMPLE_YEAR, VALIDATION_YEAR)) -> list[dict]:
    results = []
    for year in years:
        for asset in assets:
            results.append(run_integrity_and_diagnostic(asset, year))
    return results


# --------------------------------------------------------------------------- #
# Reporte                                                                     #
# --------------------------------------------------------------------------- #
def results_to_frame(results: list[dict]) -> pd.DataFrame:
    rows = []
    for r in results:
        mr, mz = r["m_real"], r["m_zero"]
        stats = r["verification"]["cost_r_stats"] or {}
        rows.append({
            "asset": r["asset"], "year": r["year"], "mechanism": MECHANISM_LABEL,
            "n_entries": r["n_entries"], "n_trades": r["n_trades"],
            "pf_costo_real": mr.get("pf"), "pf_costo_cero": mz.get("pf"),
            "delta_pf": round(mz.get("pf") - mr.get("pf"), 4),
            "exp_r_costo_real": mr.get("exp_r"), "exp_r_costo_cero": mz.get("exp_r"),
            "delta_exp_r": round(mz.get("exp_r") - mr.get("exp_r"), 4),
            "max_dd_costo_real": mr.get("max_dd"), "max_dd_costo_cero": mz.get("max_dd"),
            "delta_max_dd": round(mz.get("max_dd") - mr.get("max_dd"), 4),
            "avg_win_costo_real": mr.get("avg_win"), "avg_win_costo_cero": mz.get("avg_win"),
            "avg_loss_costo_real": mr.get("avg_loss"), "avg_loss_costo_cero": mz.get("avg_loss"),
            "freq_costo_real": mr.get("freq"), "freq_costo_cero": mz.get("freq"),
            "total_r_costo_real": mr.get("total_r"), "total_r_costo_cero": mz.get("total_r"),
            "gate_pass_costo_real": gate_check(mr), "gate_pass_costo_cero": gate_check(mz),
            "pf_ge_1_5_solo_sin_costo": (mz.get("pf") >= 1.50) and not (mr.get("pf") >= 1.50),
            "exp_r_gt_0_solo_sin_costo": (mz.get("exp_r") > 0) and not (mr.get("exp_r") > 0),
            "cost_r_min": stats.get("cost_r_min"), "cost_r_mean": stats.get("cost_r_mean"),
            "cost_r_max": stats.get("cost_r_max"),
        })
    return pd.DataFrame(rows)


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  DIAGNÓSTICO DE COSTOS — V3-A, costo=0.09% vs costo=0%"
          f"  (NO es una campaña, NO produce un candidato)\n"
          f"  Bias=A/Trigger=T1_ema_cross/Entry=C_market_close/sesión=dcv1_activo_15h única fijos\n{'='*100}")
    cols = ["asset", "year", "n_trades", "pf_costo_real", "pf_costo_cero", "delta_pf",
            "exp_r_costo_real", "exp_r_costo_cero", "delta_exp_r",
            "max_dd_costo_real", "max_dd_costo_cero", "delta_max_dd",
            "freq_costo_real", "gate_pass_costo_real", "gate_pass_costo_cero",
            "cost_r_min", "cost_r_mean", "cost_r_max"]
    print(df[cols].to_string(index=False))

    print(f"\n{'-'*100}\n  Resumen\n{'-'*100}")
    print(f"  Celdas con PF>=1.50 CON costo real: {(df['pf_costo_real']>=1.50).sum()}/6")
    print(f"  Celdas con PF>=1.50 SIN costo: {(df['pf_costo_cero']>=1.50).sum()}/6")
    print(f"  Celdas con exp_r>0 CON costo real: {(df['exp_r_costo_real']>0).sum()}/6")
    print(f"  Celdas con exp_r>0 SIN costo: {(df['exp_r_costo_cero']>0).sum()}/6")
    print(f"  Celdas con PF>=1.50 Y exp_r>0 simultáneos, CON costo: "
          f"{((df['pf_costo_real']>=1.50)&(df['exp_r_costo_real']>0)).sum()}/6")
    print(f"  Celdas con PF>=1.50 Y exp_r>0 simultáneos, SIN costo: "
          f"{((df['pf_costo_cero']>=1.50)&(df['exp_r_costo_cero']>0)).sum()}/6")
    print(f"  Celdas con los 4 gates completos, CON costo real: {df['gate_pass_costo_real'].sum()}/6")
    print(f"  Celdas con los 4 gates completos, SIN costo: {df['gate_pass_costo_cero'].sum()}/6")
    print(f"  Delta PF medio (sin costo - con costo): {df['delta_pf'].mean():.4f}")
    print(f"  Delta exp_r medio (sin costo - con costo): {df['delta_exp_r'].mean():.4f}")
    print(f"\n  RECORDATORIO: el gate de producción sigue siendo el de costos reales "
          f"(columna *_costo_real). Este diagnóstico no autoriza ninguna promoción de "
          f"variante ni cierra Espacio 6.")


def main() -> None:
    results = run_diagnostic()
    df = results_to_frame(results)
    print_report(df)
    out_path = "gestion_espacio6_costo_cero_diagnostico_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas)")


if __name__ == "__main__":
    main()
