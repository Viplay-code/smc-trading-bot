"""
research/tests/test_entry_campaign_t1.py — Validación ESTRUCTURAL de
scripts/entry_campaign_t1.py sobre datos sintéticos.

No sustituye la corrida real (bloqueada en este sandbox, HTTP 451, data/raw/
vacío) — prueba que find_entries_for_entry("C_market_close") reproduce
exactamente backtest.py::find_entries (misma combinación Bias=A/Trigger=T1/
Entry=C que backtest.py ya usa en producción), que ambos candidatos de Entry
corren sin excepciones, y que el guard de borde para D_next_candle_open no
descarta de más bajo T1 (que sí deja margen al final de la serie, a
diferencia de A_sweep_bos). Ejecutar:
    python -m research.tests.test_entry_campaign_t1  (o con pytest)
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
import scripts.entry_campaign_t1 as camp

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


def _build_2022_frame():
    raw = make_synthetic_raw_1h()
    df_full = build_dc_v1(raw, asset="TESTUSDT", dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)
    df4h_full = bias_camp.resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, camp.BIAS_CANDIDATE)
    sliced = period_slice(df_full, 2022)
    cfg = backtest.Config()
    frame = bias_camp.to_backtest_frame(sliced, sliced["bias_A"], cfg)
    return frame, cfg, errs


def test_find_entries_for_entry_c_matches_backtest_find_entries():
    """Paridad: find_entries_for_entry(frame, cfg, raw_events, "C_market_close")
    debe producir EXACTAMENTE las mismas entradas que backtest.find_entries
    sobre el mismo frame — es la combinación Bias=A/Trigger=T1/Entry=C que
    backtest.py ya usa hoy en producción."""
    frame, cfg, errs = _build_2022_frame()
    if frame.empty:
        return _p("find_entries_for_entry('C_market_close') == backtest.find_entries (slice 2022 vacío)", False)

    expected = backtest.find_entries(frame, cfg)
    raw_events = camp._raw_events(frame, cfg)
    actual = camp.find_entries_for_entry(frame, cfg, raw_events, "C_market_close")

    ok = (not errs) and expected == actual and len(expected) > 0
    return _p("find_entries_for_entry('C_market_close') reproduce backtest.find_entries 1:1", ok)


def test_all_entry_candidates_run_end_to_end():
    """Pipeline completo (adaptador + run_config + metrics + gate_check) para
    los 2 candidatos de Entry, sin excepciones."""
    frame, cfg, errs = _build_2022_frame()
    if frame.empty:
        return _p("pipeline completo (Entry C/D bajo T1)", False)

    raw_events = camp._raw_events(frame, cfg)
    ok = not errs
    for entry_name in camp.CANDIDATES:
        entries = camp.find_entries_for_entry(frame, cfg, raw_events, entry_name)
        ok = ok and isinstance(entries, list)
        ok = ok and all(
            {"entry_idx", "direction", "entry", "sl0", "risk_pts"}.issubset(e.keys())
            for e in entries
        )
        for exit_cfg in backtest.EXIT_CONFIGS.values():
            trades = backtest.run_config(frame, entries, exit_cfg, cfg)
            m = backtest.metrics(trades, cfg)
            gate = camp.gate_check(m)
            ok = ok and isinstance(gate, bool)

    return _p("pipeline completo corre sin excepciones para C_market_close/D_next_candle_open "
               "sobre slice 2022", ok)


def test_t1_margin_means_d_never_discards_valid_events():
    """trigger_T1_ema_cross itera range(warmup, n-2) — ningún evento de T1
    puede caer en las últimas 2 velas, así que D_next_candle_open no debería
    descartar ningún evento por el guard de borde (a diferencia de
    A_sweep_bos, que sí puede necesitar descartar el último)."""
    frame, cfg, errs = _build_2022_frame()
    if frame.empty:
        return _p("D_next_candle_open no descarta eventos válidos de T1 por borde (slice vacío)", False)

    raw_events = camp._raw_events(frame, cfg)
    n = len(frame)
    max_idx = max((ev.entry_idx for ev in raw_events), default=-1)

    entries_c = camp.find_entries_for_entry(frame, cfg, raw_events, "C_market_close")
    entries_d = camp.find_entries_for_entry(frame, cfg, raw_events, "D_next_candle_open")

    ok = (not errs) and max_idx < n - 2 and len(entries_c) == len(entries_d) and len(entries_c) > 0
    return _p("margen de T1 (range hasta n-2) evita que D_next_candle_open pierda eventos "
              f"por borde ({len(entries_c)} entradas C, {len(entries_d)} entradas D)", ok)


ALL_TESTS = [
    test_find_entries_for_entry_c_matches_backtest_find_entries,
    test_all_entry_candidates_run_end_to_end,
    test_t1_margin_means_d_never_discards_valid_events,
]


def main():
    print("scripts/entry_campaign_t1 — validación estructural sobre datos sintéticos\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
