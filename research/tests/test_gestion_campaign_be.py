"""
research/tests/test_gestion_campaign_be.py — Validación ESTRUCTURAL de
scripts/gestion_campaign_be.py sobre datos sintéticos.

No sustituye la corrida real (bloqueada en este sandbox, HTTP 451,
data/raw/ vacío) — prueba que la regla de contingencia (_is_extreme_best,
misma función que H2.2, reutilizada acá para `be`) dispara y NO dispara
según el criterio acordado, que el tope duro de la extensión superior
(2.0 == ACTIVATION_ANCHOR) queda codificado tal cual, que el pipeline
(run_asset_year/run_blind_test/results_to_frame) corre sin excepciones
sobre datos sintéticos, y que las entradas son invariantes a `be` por
construcción. Ejecutar:
    python -m research.tests.test_gestion_campaign_be  (o con pytest)
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
import scripts.gestion_campaign_be as camp

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
# Configuración: anclas, tope duro, dimensiones de la grilla                  #
# --------------------------------------------------------------------------- #
def test_be_anchor_matches_v3a():
    ok = camp.BE_VALUES_BASE == (0.5, 1.0, 1.5) and camp._exit_cfg(1.0) == {
        "be": 1.0, "activation": 2.0, "distance": 1.0,
    }
    return _p("grilla base {0.5,1.0,1.5} y ancla 1.0R coincide exactamente con V3-A", ok)


def test_upper_extension_hard_cap_equals_activation_anchor():
    """El tope duro de la extensión superior (2.0) debe coincidir EXACTAMENTE
    con ACTIVATION_ANCHOR — no un número aparte que pueda desincronizarse."""
    ok = camp.BE_EXT_UPPER == camp.ACTIVATION_ANCHOR == 2.0
    return _p("BE_EXT_UPPER == ACTIVATION_ANCHOR (tope duro, no un valor independiente)", ok)


def test_lower_extension_matches_h2_1_precedent():
    ok = camp.BE_EXT_LOWER == 0.25
    return _p("BE_EXT_LOWER == 0.25 (mismo piso ya validado con datos reales en H2.1)", ok)


# --------------------------------------------------------------------------- #
# Regla de contingencia — unitaria, con métricas construidas a mano           #
# --------------------------------------------------------------------------- #
def _m(pf):
    return {"pf": pf}


def test_is_extreme_best_true_when_lower_strictly_best():
    metrics_by_be = {0.5: _m(1.4), 1.0: _m(1.0), 1.5: _m(0.9)}
    ok = camp._is_extreme_best(metrics_by_be, camp.BE_VALUES_BASE[0]) is True
    return _p("_is_extreme_best True si be=0.5 tiene el mejor PF del barrido base", ok)


def test_is_extreme_best_true_when_upper_strictly_best():
    metrics_by_be = {0.5: _m(0.9), 1.0: _m(1.0), 1.5: _m(1.4)}
    ok = camp._is_extreme_best(metrics_by_be, camp.BE_VALUES_BASE[-1]) is True
    return _p("_is_extreme_best True si be=1.5 tiene el mejor PF del barrido base", ok)


def test_is_extreme_best_true_on_tie():
    metrics_by_be = {0.5: _m(1.2), 1.0: _m(1.2), 1.5: _m(0.9)}
    ok = camp._is_extreme_best(metrics_by_be, camp.BE_VALUES_BASE[0]) is True
    return _p("_is_extreme_best True si be=0.5 empata en el mejor PF", ok)


def test_is_extreme_best_false_when_interior_optimum():
    metrics_by_be = {0.5: _m(0.9), 1.0: _m(1.5), 1.5: _m(0.9)}
    ok = (
        camp._is_extreme_best(metrics_by_be, camp.BE_VALUES_BASE[0]) is False
        and camp._is_extreme_best(metrics_by_be, camp.BE_VALUES_BASE[-1]) is False
    )
    return _p("_is_extreme_best False en ambos extremos si el óptimo es interior (el ancla)", ok)


def test_is_extreme_best_false_when_missing_data():
    ok = camp._is_extreme_best({1.0: _m(1.0)}, 0.5) is False
    return _p("_is_extreme_best False si el extremo no tiene metrics() válidas", ok)


def test_no_cascade_beyond_single_extension_per_side():
    """Confirma que run_asset_year no vuelve a evaluar contingencia sobre el
    valor de extensión (0.25/2.0) — máximo una extensión por lado, sin
    cascada, mismo diseño que H2.1/H2.2."""
    import inspect
    src = inspect.getsource(camp.run_asset_year)
    ok = src.count("_is_extreme_best") == 2  # una vez por lado, no recursivo
    return _p("run_asset_year evalúa cada regla de contingencia exactamente una vez (sin cascada)", ok)


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
        and len(rows) >= len(camp.BE_VALUES_BASE)
        and all(r["candidate"] in camp.CANDIDATES for r in rows)
        and all(isinstance(r["gate_pass"], bool) for r in rows)
        and sum(1 for r in rows if r["triggered_by"] is None) == len(camp.BE_VALUES_BASE)
    )
    return _p(f"run_asset_year corre sin excepciones ({len(rows)} filas, base={len(camp.BE_VALUES_BASE)})", ok)


def test_entries_invariant_to_be_by_construction():
    sliced, errs = _build_frame_and_sliced()
    if sliced.empty:
        return _p("n_entries invariante a be (slice 2022 vacío)", False)

    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        rows = camp.run_asset_year("TESTUSDT", 2022)
    finally:
        trigger_camp.load_asset_year = orig

    n_entries_values = {r["n_entries"] for r in rows}
    ok = (not errs) and len(n_entries_values) == 1
    return _p(f"n_entries invariante a be en todas las filas ({n_entries_values})", ok)


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
        _fake_result("BTCUSDT", 2022, "0.25", n_entries=50, n_trades=48, freq=4.0,
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
        _fake_result("BTCUSDT", 2022, "0.5", n_entries=50, n_trades=48, freq=6.0, pf=1.6, gate_pass=True),
        _fake_result("BTCUSDT", 2023, "0.5", n_entries=50, n_trades=48, freq=6.0, pf=1.55, gate_pass=True),
    ]
    df = camp.results_to_frame(results)
    decision = camp.summarize_decision(df)
    row = decision[(decision.asset == "BTCUSDT") & (decision.candidate == "0.5")].iloc[0]
    ok = bool(row["survives_both_years"]) and row["rank_within_asset"] == 1
    return _p("summarize_decision funciona sin modificarse con exit_config constante", ok)


ALL_TESTS = [
    test_be_anchor_matches_v3a,
    test_upper_extension_hard_cap_equals_activation_anchor,
    test_lower_extension_matches_h2_1_precedent,
    test_is_extreme_best_true_when_lower_strictly_best,
    test_is_extreme_best_true_when_upper_strictly_best,
    test_is_extreme_best_true_on_tie,
    test_is_extreme_best_false_when_interior_optimum,
    test_is_extreme_best_false_when_missing_data,
    test_no_cascade_beyond_single_extension_per_side,
    test_run_asset_year_end_to_end_on_synthetic_slice,
    test_entries_invariant_to_be_by_construction,
    test_run_blind_test_requires_frozen_candidate,
    test_results_to_frame_exports_triggered_by_and_avg_win_avg_loss,
    test_summarize_decision_compatible_with_constant_exit_config,
]


def main():
    print("scripts/gestion_campaign_be — validación estructural sobre datos sintéticos\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
