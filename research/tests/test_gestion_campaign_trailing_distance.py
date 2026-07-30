"""
research/tests/test_gestion_campaign_trailing_distance.py — Validación
ESTRUCTURAL de scripts/gestion_campaign_trailing_distance.py sobre datos
sintéticos.

No sustituye la corrida real (bloqueada en este sandbox, HTTP 451,
data/raw/ vacío) — prueba que las dos reglas de contingencia pre-
especificadas (_no_deterioration, _is_lower_extreme_best) implementan
exactamente el criterio acordado 2026-07-30 (4 métricas de gate_check()
para la regla 1, no una aislada; PF en solitario para la regla 2), que el
pipeline (run_asset_year/run_blind_test/results_to_frame) corre sin
excepciones sobre datos sintéticos, y que las entradas son invariantes a
`distance` por construcción. Ejecutar:
    python -m research.tests.test_gestion_campaign_trailing_distance  (o con pytest)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import backtest
from dc_v1 import build_dc_v1, validate_dc_v1
from periods import period_slice
from versions import PIPELINE_VERSION, DATASET_VERSION

sys.path.insert(0, ".")
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as trigger_camp
import scripts.gestion_campaign_trailing_distance as camp

Path("smc_bot.log").unlink(missing_ok=True)


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def make_synthetic_raw_1h(start="2021-10-01", n=8000, seed=7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq="1h", tz="UTC")
    ret = rng.normal(0, 0.006, n)
    close = 20000 * np.exp(np.cumsum(ret))
    open_ = np.empty(n)
    open_[0] = close[0]
    open_[1:] = close[:-1]
    spread = np.abs(rng.normal(0, 0.003, n)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    volume = rng.uniform(10, 100, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


# --------------------------------------------------------------------------- #
# Reglas de contingencia — unitarias, con métricas construidas a mano         #
# --------------------------------------------------------------------------- #
def _m(pf, max_dd, exp_r, freq):
    return {"pf": pf, "max_dd": max_dd, "exp_r": exp_r, "freq": freq}


def test_no_deterioration_true_when_strictly_better_on_all_four():
    anchor = _m(pf=1.0, max_dd=-5.0, exp_r=0.01, freq=5.0)
    candidate = _m(pf=1.2, max_dd=-4.0, exp_r=0.02, freq=5.5)
    ok = camp._no_deterioration(candidate, anchor) is True
    return _p("_no_deterioration True si el candidato es mejor en las 4 métricas", ok)


def test_no_deterioration_true_when_exactly_equal():
    anchor = _m(pf=1.0, max_dd=-5.0, exp_r=0.01, freq=5.0)
    ok = camp._no_deterioration(dict(anchor), anchor) is True
    return _p("_no_deterioration True si el candidato es exactamente igual al ancla", ok)


def test_no_deterioration_false_when_isolated_pf_gain_but_other_metric_worse():
    """El caso central del ajuste 2026-07-30: una mejora aislada de PF NO debe
    disparar la contingencia si otra métrica (acá max_dd) empeora."""
    anchor = _m(pf=1.0, max_dd=-5.0, exp_r=0.01, freq=5.0)
    candidate = _m(pf=1.3, max_dd=-8.0, exp_r=0.01, freq=5.0)  # pf mejor, max_dd peor
    ok = camp._no_deterioration(candidate, anchor) is False
    return _p("_no_deterioration False si PF mejora pero max_dd empeora (métrica aislada no alcanza)", ok)


def test_no_deterioration_false_when_any_missing_metrics():
    anchor = _m(pf=1.0, max_dd=-5.0, exp_r=0.01, freq=5.0)
    ok = (camp._no_deterioration(None, anchor) is False) and (camp._no_deterioration(anchor, None) is False)
    return _p("_no_deterioration False si falta metrics() de cualquiera de los dos lados", ok)


def test_is_lower_extreme_best_true_when_0_5_strictly_best():
    metrics_by_distance = {
        0.5: _m(pf=1.4, max_dd=-3.0, exp_r=0.05, freq=6.0),
        0.75: _m(pf=1.2, max_dd=-4.0, exp_r=0.03, freq=6.0),
        1.0: _m(pf=1.0, max_dd=-5.0, exp_r=0.01, freq=5.0),
        1.5: _m(pf=0.9, max_dd=-6.0, exp_r=-0.01, freq=5.0),
    }
    ok = camp._is_lower_extreme_best(metrics_by_distance) is True
    return _p("_is_lower_extreme_best True si distance=0.5 tiene el mejor PF del barrido base", ok)


def test_is_lower_extreme_best_true_on_tie():
    metrics_by_distance = {
        0.5: _m(pf=1.2, max_dd=-3.0, exp_r=0.05, freq=6.0),
        0.75: _m(pf=1.2, max_dd=-4.0, exp_r=0.03, freq=6.0),  # empate con 0.5
        1.0: _m(pf=1.0, max_dd=-5.0, exp_r=0.01, freq=5.0),
        1.5: _m(pf=0.9, max_dd=-6.0, exp_r=-0.01, freq=5.0),
    }
    ok = camp._is_lower_extreme_best(metrics_by_distance) is True
    return _p("_is_lower_extreme_best True si distance=0.5 empata en el mejor PF", ok)


def test_is_lower_extreme_best_false_when_interior_optimum():
    metrics_by_distance = {
        0.5: _m(pf=0.9, max_dd=-6.0, exp_r=-0.01, freq=5.0),
        0.75: _m(pf=1.5, max_dd=-3.0, exp_r=0.06, freq=6.5),  # óptimo interior
        1.0: _m(pf=1.0, max_dd=-5.0, exp_r=0.01, freq=5.0),
        1.5: _m(pf=0.9, max_dd=-6.0, exp_r=-0.01, freq=5.0),
    }
    ok = camp._is_lower_extreme_best(metrics_by_distance) is False
    return _p("_is_lower_extreme_best False si el óptimo está en un punto interior (0.75)", ok)


def test_is_lower_extreme_best_false_when_missing_data():
    ok = camp._is_lower_extreme_best({0.75: _m(1.0, -5.0, 0.01, 5.0)}) is False
    return _p("_is_lower_extreme_best False si distance=0.5 no tiene metrics() válidas", ok)


# --------------------------------------------------------------------------- #
# Pipeline end-to-end sobre datos sintéticos                                  #
# --------------------------------------------------------------------------- #
def _build_frame_and_sliced():
    raw = make_synthetic_raw_1h()
    df_full = build_dc_v1(raw, asset="TESTUSDT", dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)
    df4h_full = bias_camp.resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, camp.BIAS_CANDIDATE)
    sliced = period_slice(df_full, 2022)
    return sliced, errs


def test_run_asset_year_end_to_end_on_synthetic_slice():
    """Pipeline completo (rango base + evaluación de ambas reglas de
    contingencia) corre sin excepciones y produce al menos las 4 filas base,
    todas con gate_pass booleano."""
    sliced, errs = _build_frame_and_sliced()
    if sliced.empty:
        return _p("run_asset_year corre end-to-end (slice 2022 vacío)", False)

    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        rows = camp.run_asset_year("TESTUSDT", 2022)
    finally:
        trigger_camp.load_asset_year = orig

    ok = (
        not errs
        and len(rows) >= len(camp.DISTANCE_VALUES_BASE)
        and all(r["candidate"] in camp.CANDIDATES for r in rows)
        and all(isinstance(r["gate_pass"], bool) for r in rows)
        and sum(1 for r in rows if r["triggered_by"] is None) == len(camp.DISTANCE_VALUES_BASE)
    )
    return _p(f"run_asset_year corre sin excepciones ({len(rows)} filas, base={len(camp.DISTANCE_VALUES_BASE)})", ok)


def test_entries_invariant_to_distance_by_construction():
    """n_entries debe ser IDÉNTICO en todas las filas de un mismo (activo,
    año) — las entradas se calculan una sola vez y se reutilizan para cada
    `distance` (invarianza estructural, no requiere aserción empírica como
    en atr_mult)."""
    sliced, errs = _build_frame_and_sliced()
    if sliced.empty:
        return _p("n_entries invariante a distance (slice 2022 vacío)", False)

    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        rows = camp.run_asset_year("TESTUSDT", 2022)
    finally:
        trigger_camp.load_asset_year = orig

    n_entries_values = {r["n_entries"] for r in rows}
    ok = (not errs) and len(n_entries_values) == 1
    return _p(f"n_entries invariante a distance en todas las filas ({n_entries_values})", ok)


def test_run_blind_test_requires_frozen_candidate():
    ok = True
    try:
        camp.run_blind_test(candidate=None)
        ok = False
    except ValueError:
        pass
    try:
        camp.run_blind_test(candidate="0.9")  # no está en CANDIDATES
        ok = False
    except ValueError:
        pass
    return _p("run_blind_test exige --candidate en CANDIDATES antes de tocar data/raw/", ok)


def _fake_result(asset, year, candidate, n_entries, n_trades, freq,
                  pf=1.0, avg_win=0.5, avg_loss=-0.3, gate_pass=False, triggered_by=None):
    return {
        "asset": asset, "year": year, "candidate": candidate,
        "exit_config": camp.EXIT_CONFIG_LABEL,
        "n_entries": n_entries, "n_trades": n_trades, "gate_pass": gate_pass,
        "triggered_by": triggered_by,
        "metrics": {"pf": pf, "wr": 30.0, "exp_r": 0.05, "avg_win": avg_win, "avg_loss": avg_loss,
                    "total_r": 1.0, "max_dd": -3.0, "freq": freq, "be": 0,
                    "reasons": {"stop": n_trades, "timeout": 0}},
    }


def test_results_to_frame_exports_triggered_by_and_avg_win_avg_loss():
    results = [
        _fake_result("BTCUSDT", 2022, "1.25", n_entries=50, n_trades=48, freq=4.0,
                     avg_win=0.83, avg_loss=-0.41, triggered_by="upper_contingency"),
    ]
    df = camp.results_to_frame(results)
    row = df.iloc[0]
    ok = (
        row["avg_win"] == 0.83 and row["avg_loss"] == -0.41
        and row["triggered_by"] == "upper_contingency"
        and "triggered_by" in df.columns
    )
    return _p("results_to_frame exporta triggered_by y avg_win/avg_loss sin transformarlos", ok)


def test_summarize_decision_compatible_with_constant_exit_config():
    """summarize_decision (reutilizada sin modificar) agrupa por
    (asset, candidate, exit_config) — acá exit_config es constante
    (EXIT_CONFIG_LABEL), así que el agrupamiento efectivo es por
    (asset, candidate); confirma que no revienta y produce columnas
    esperadas."""
    results = [
        _fake_result("BTCUSDT", 2022, "0.75", n_entries=50, n_trades=48, freq=6.0, pf=1.6, gate_pass=True),
        _fake_result("BTCUSDT", 2023, "0.75", n_entries=50, n_trades=48, freq=6.0, pf=1.55, gate_pass=True),
    ]
    df = camp.results_to_frame(results)
    decision = camp.summarize_decision(df)
    row = decision[(decision.asset == "BTCUSDT") & (decision.candidate == "0.75")].iloc[0]
    ok = bool(row["survives_both_years"]) and row["rank_within_asset"] == 1
    return _p("summarize_decision funciona sin modificarse con exit_config constante", ok)


ALL_TESTS = [
    test_no_deterioration_true_when_strictly_better_on_all_four,
    test_no_deterioration_true_when_exactly_equal,
    test_no_deterioration_false_when_isolated_pf_gain_but_other_metric_worse,
    test_no_deterioration_false_when_any_missing_metrics,
    test_is_lower_extreme_best_true_when_0_5_strictly_best,
    test_is_lower_extreme_best_true_on_tie,
    test_is_lower_extreme_best_false_when_interior_optimum,
    test_is_lower_extreme_best_false_when_missing_data,
    test_run_asset_year_end_to_end_on_synthetic_slice,
    test_entries_invariant_to_distance_by_construction,
    test_run_blind_test_requires_frozen_candidate,
    test_results_to_frame_exports_triggered_by_and_avg_win_avg_loss,
    test_summarize_decision_compatible_with_constant_exit_config,
]


def main():
    print("scripts/gestion_campaign_trailing_distance — validación estructural sobre datos sintéticos\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
