"""
research/tests/test_gestion_campaign_atr_mult.py — Validación ESTRUCTURAL de
scripts/gestion_campaign_atr_mult.py sobre datos sintéticos.

No sustituye la corrida real (bloqueada en este sandbox, HTTP 451,
data/raw/ vacío) — prueba que el pipeline nuevo (raw_trigger_event_counts,
assert_counts_invariant, run_asset_year, results_to_frame con
avg_win/avg_loss) no rompe, produce formas/tipos razonables, y que el
sanity-check de invarianza del Trigger efectivamente detecta una divergencia
cuando se le da una (no solo que pasa en el caso feliz). Ejecutar:
    python -m research.tests.test_gestion_campaign_atr_mult  (o con pytest)
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
import scripts.gestion_campaign_atr_mult as camp

Path("smc_bot.log").unlink(missing_ok=True)


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def make_synthetic_raw_1h(start="2021-10-01", n=8000, seed=7) -> pd.DataFrame:
    """Misma forma que en test_bias_campaign.py/test_trigger_campaign.py,
    duplicada acá por la misma convención (cada archivo de test es
    standalone)."""
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


def _build_2022_frame():
    raw = make_synthetic_raw_1h()
    df_full = build_dc_v1(raw, asset="TESTUSDT", dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)
    df4h_full = bias_camp.resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, camp.BIAS_CANDIDATE)
    sliced = period_slice(df_full, 2022)
    base_cfg = backtest.Config()
    frame = bias_camp.to_backtest_frame(sliced, sliced["bias_A"], base_cfg)
    return frame, errs, sliced


def test_raw_trigger_event_counts_identical_across_atr_mult_on_synthetic_data():
    """Confirma en datos sintéticos (caso feliz) lo que
    research/layers.py:376-380 demuestra por código: T1_ema_cross genera el
    mismo conjunto de eventos crudos sin importar atr_mult."""
    frame, errs, sliced = _build_2022_frame()
    if sliced.empty:
        return _p("raw_trigger_event_counts idéntico entre atr_mult (slice 2022 vacío)", False)

    counts = camp.raw_trigger_event_counts(frame)
    ok = (not errs) and len(set(counts.values())) == 1 and len(counts) == len(camp.ATR_MULT_VALUES)
    return _p(f"raw_trigger_event_counts idéntico entre atr_mult {camp.ATR_MULT_VALUES} en datos sintéticos ({counts})", ok)


def test_assert_counts_invariant_detects_real_divergence():
    """Que el sanity-check no sea un chequeo vacío: si le paso conteos que
    SÍ divergen, debe reventar con AssertionError. Prueba la lógica de
    detección en sí, independiente de si T1 realmente diverge alguna vez."""
    ok = True
    try:
        camp.assert_counts_invariant({1.0: 10, 1.5: 10, 2.0: 12, 3.0: 10}, "TESTUSDT", 2022)
        ok = False  # no debería llegar acá
    except AssertionError:
        pass
    # caso feliz: no debe reventar si todos son iguales
    try:
        camp.assert_counts_invariant({1.0: 10, 1.5: 10, 2.0: 10, 3.0: 10}, "TESTUSDT", 2022)
    except AssertionError:
        ok = False
    return _p("assert_counts_invariant revienta con conteos distintos y pasa con conteos iguales", ok)


def test_run_asset_year_end_to_end_all_atr_mult_values():
    """Pipeline completo (sanity-check + los 4 atr_mult × 2 exit_configs)
    para un (activo, año) sintético, sin excepciones, con gate_check booleano."""
    raw = make_synthetic_raw_1h()
    df_full = build_dc_v1(raw, asset="TESTUSDT", dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)

    # monkeypatch liviano: forzar trigger_camp.load_asset_year a devolver
    # nuestro frame sintético en vez de leer data/raw/ (bloqueado en este
    # sandbox) — mismo patrón que test_bias_campaign.py/test_trigger_campaign.py
    # usan para no depender de I/O real.
    df4h_full = bias_camp.resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, camp.BIAS_CANDIDATE)
    sliced = period_slice(df_full, 2022)
    if sliced.empty:
        return _p("run_asset_year end-to-end (todos los atr_mult)", False)

    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        rows = camp.run_asset_year("TESTUSDT", 2022)
    finally:
        trigger_camp.load_asset_year = orig

    ok = (
        not errs
        and len(rows) == len(camp.ATR_MULT_VALUES) * len(backtest.EXIT_CONFIGS)
        and all(r["candidate"] in camp.CANDIDATES for r in rows)
        and all(isinstance(r["gate_pass"], bool) for r in rows)
    )
    return _p("run_asset_year corre sin excepciones para los 4 atr_mult x 2 exit_configs", ok)


def test_run_blind_test_requires_frozen_candidate():
    ok = True
    try:
        camp.run_blind_test(candidate=None)
        ok = False
    except ValueError:
        pass
    try:
        camp.run_blind_test(candidate="2.75")  # no está en CANDIDATES
        ok = False
    except ValueError:
        pass
    return _p("run_blind_test exige --candidate en CANDIDATES antes de tocar data/raw/", ok)


def _fake_result(asset, year, candidate, exit_config, n_entries, n_trades, freq,
                  pf=1.0, avg_win=0.5, avg_loss=-0.3, gate_pass=False):
    return {
        "asset": asset, "year": year, "candidate": candidate, "exit_config": exit_config,
        "n_entries": n_entries, "n_trades": n_trades, "gate_pass": gate_pass,
        "metrics": {"pf": pf, "wr": 30.0, "exp_r": 0.05, "avg_win": avg_win, "avg_loss": avg_loss,
                    "total_r": 1.0, "max_dd": -3.0, "freq": freq, "be": 0,
                    "reasons": {"stop": n_trades, "timeout": 0}},
    }


def test_results_to_frame_exports_avg_win_avg_loss():
    """La instrumentación nueva acordada 2026-07-28: avg_win/avg_loss deben
    pasar tal cual desde metrics() al CSV — ya se calculaban, nunca se
    exportaban."""
    results = [
        _fake_result("BTCUSDT", 2022, "2.0", "V3-A (1R/2R/1R)",
                     n_entries=50, n_trades=48, freq=4.0, avg_win=0.83, avg_loss=-0.41),
    ]
    df = camp.results_to_frame(results)
    row = df.iloc[0]
    ok = (row["avg_win"] == 0.83) and (row["avg_loss"] == -0.41) and ("avg_win" in df.columns) and ("avg_loss" in df.columns)
    return _p("results_to_frame exporta avg_win/avg_loss sin transformarlos", ok)


ALL_TESTS = [
    test_raw_trigger_event_counts_identical_across_atr_mult_on_synthetic_data,
    test_assert_counts_invariant_detects_real_divergence,
    test_run_asset_year_end_to_end_all_atr_mult_values,
    test_run_blind_test_requires_frozen_candidate,
    test_results_to_frame_exports_avg_win_avg_loss,
]


def main():
    print("scripts/gestion_campaign_atr_mult — validación estructural sobre datos sintéticos\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
