"""
research/tests/test_gestion_campaign_activation.py — Validación ESTRUCTURAL
de scripts/gestion_campaign_activation.py sobre datos sintéticos.

No sustituye la corrida real (bloqueada en este sandbox, HTTP 451,
data/raw/ vacío) — prueba que la regla de contingencia única
(_is_extreme_best, parametrizada por extremo) implementa el criterio
acordado 2026-07-31 en ambos lados, que el pipeline (run_asset_year/
run_blind_test/results_to_frame) corre sin excepciones sobre datos
sintéticos, y que las entradas son invariantes a `activation` por
construcción. Ejecutar:
    python -m research.tests.test_gestion_campaign_activation  (o con pytest)
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
import scripts.gestion_campaign_activation as camp

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
# _exit_cfg — be/distance deben quedar fijos en el ancla para CUALQUIER       #
# valor de activation; es el único punto del archivo que construye el dict   #
# be/activation/distance que llega a backtest.run_config.                    #
# --------------------------------------------------------------------------- #
def test_exit_cfg_freezes_be_and_distance_for_any_activation_value():
    for activation in (1.25, 1.5, 2.0, 2.5, 3.0):
        cfg = camp._exit_cfg(activation)
        ok = (
            cfg["be"] == camp.BE_ANCHOR == 1.0
            and cfg["distance"] == camp.DISTANCE_ANCHOR == 1.0
            and cfg["activation"] == activation
            and set(cfg.keys()) == {"be", "activation", "distance"}
        )
        if not ok:
            return _p(f"_exit_cfg fija be=1.0R/distance=1.0R para activation={activation}", False)
    return _p("_exit_cfg fija be=1.0R/distance=1.0R para todo el rango candidato, solo activation varía", True)


# --------------------------------------------------------------------------- #
# Regla de contingencia — unitaria, con métricas construidas a mano           #
# --------------------------------------------------------------------------- #
def _m(pf, max_dd=-5.0, exp_r=0.01, freq=5.0):
    return {"pf": pf, "max_dd": max_dd, "exp_r": exp_r, "freq": freq}


def test_is_extreme_best_true_when_lower_extreme_strictly_best():
    metrics = {1.5: _m(pf=1.4), 2.0: _m(pf=1.0), 2.5: _m(pf=0.9)}
    ok = camp._is_extreme_best(metrics, camp.ACTIVATION_VALUES_BASE[0]) is True
    return _p("_is_extreme_best True si el extremo inferior (1.5) tiene el mejor PF", ok)


def test_is_extreme_best_true_when_upper_extreme_strictly_best():
    metrics = {1.5: _m(pf=0.9), 2.0: _m(pf=1.0), 2.5: _m(pf=1.4)}
    ok = camp._is_extreme_best(metrics, camp.ACTIVATION_VALUES_BASE[-1]) is True
    return _p("_is_extreme_best True si el extremo superior (2.5) tiene el mejor PF", ok)


def test_is_extreme_best_true_on_tie():
    metrics = {1.5: _m(pf=1.2), 2.0: _m(pf=1.2), 2.5: _m(pf=0.9)}
    ok = camp._is_extreme_best(metrics, camp.ACTIVATION_VALUES_BASE[0]) is True
    return _p("_is_extreme_best True si el extremo empata en el mejor PF", ok)


def test_is_extreme_best_false_when_interior_optimum():
    metrics = {1.5: _m(pf=0.9), 2.0: _m(pf=1.5), 2.5: _m(pf=0.95)}
    ok_lower = camp._is_extreme_best(metrics, camp.ACTIVATION_VALUES_BASE[0]) is False
    ok_upper = camp._is_extreme_best(metrics, camp.ACTIVATION_VALUES_BASE[-1]) is False
    return _p("_is_extreme_best False en ambos lados si el óptimo es interior (2.0, el ancla)",
               ok_lower and ok_upper)


def test_is_extreme_best_false_when_missing_data():
    ok = camp._is_extreme_best({2.0: _m(pf=1.0)}, camp.ACTIVATION_VALUES_BASE[0]) is False
    return _p("_is_extreme_best False si el extremo a chequear no tiene metrics() válidas", ok)


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
    contingencia) corre sin excepciones y produce al menos las 3 filas base,
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
        and len(rows) >= len(camp.ACTIVATION_VALUES_BASE)
        and all(r["candidate"] in camp.CANDIDATES for r in rows)
        and all(isinstance(r["gate_pass"], bool) for r in rows)
        and sum(1 for r in rows if r["triggered_by"] is None) == len(camp.ACTIVATION_VALUES_BASE)
    )
    return _p(f"run_asset_year corre sin excepciones ({len(rows)} filas, base={len(camp.ACTIVATION_VALUES_BASE)})", ok)


def test_entries_invariant_to_activation_by_construction():
    """n_entries debe ser IDÉNTICO en todas las filas de un mismo (activo,
    año) — las entradas se calculan una sola vez y se reutilizan para cada
    `activation` (invarianza estructural)."""
    sliced, errs = _build_frame_and_sliced()
    if sliced.empty:
        return _p("n_entries invariante a activation (slice 2022 vacío)", False)

    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        rows = camp.run_asset_year("TESTUSDT", 2022)
    finally:
        trigger_camp.load_asset_year = orig

    n_entries_values = {r["n_entries"] for r in rows}
    ok = (not errs) and len(n_entries_values) == 1
    return _p(f"n_entries invariante a activation en todas las filas ({n_entries_values})", ok)


def test_run_blind_test_requires_frozen_candidate():
    ok = True
    try:
        camp.run_blind_test(candidate=None)
        ok = False
    except ValueError:
        pass
    try:
        camp.run_blind_test(candidate="1.75")  # no está en CANDIDATES
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
                     avg_win=0.83, avg_loss=-0.41, triggered_by="lower_contingency"),
    ]
    df = camp.results_to_frame(results)
    row = df.iloc[0]
    ok = (
        row["avg_win"] == 0.83 and row["avg_loss"] == -0.41
        and row["triggered_by"] == "lower_contingency"
        and "triggered_by" in df.columns
    )
    return _p("results_to_frame exporta triggered_by y avg_win/avg_loss sin transformarlos", ok)


def test_summarize_decision_compatible_with_constant_exit_config():
    results = [
        _fake_result("BTCUSDT", 2022, "2.5", n_entries=50, n_trades=48, freq=6.0, pf=1.6, gate_pass=True),
        _fake_result("BTCUSDT", 2023, "2.5", n_entries=50, n_trades=48, freq=6.0, pf=1.55, gate_pass=True),
    ]
    df = camp.results_to_frame(results)
    decision = camp.summarize_decision(df)
    row = decision[(decision.asset == "BTCUSDT") & (decision.candidate == "2.5")].iloc[0]
    ok = bool(row["survives_both_years"]) and row["rank_within_asset"] == 1
    return _p("summarize_decision funciona sin modificarse con exit_config constante", ok)


ALL_TESTS = [
    test_exit_cfg_freezes_be_and_distance_for_any_activation_value,
    test_is_extreme_best_true_when_lower_extreme_strictly_best,
    test_is_extreme_best_true_when_upper_extreme_strictly_best,
    test_is_extreme_best_true_on_tie,
    test_is_extreme_best_false_when_interior_optimum,
    test_is_extreme_best_false_when_missing_data,
    test_run_asset_year_end_to_end_on_synthetic_slice,
    test_entries_invariant_to_activation_by_construction,
    test_run_blind_test_requires_frozen_candidate,
    test_results_to_frame_exports_triggered_by_and_avg_win_avg_loss,
    test_summarize_decision_compatible_with_constant_exit_config,
]


def main():
    print("scripts/gestion_campaign_activation — validación estructural sobre datos sintéticos\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
