"""
research/tests/test_entry_campaign_sweep_bos.py — Validación ESTRUCTURAL de
scripts/entry_campaign_sweep_bos.py sobre datos sintéticos.

No sustituye la corrida real (bloqueada en este sandbox, HTTP 451, data/raw/
vacío) — prueba que find_entries_for_entry("A_pullback_50") reproduce
backtest.py::find_entries (misma combinación Bias=A/Trigger=A_sweep_bos/
Entry=A que backtest.py NO usa hoy pero que sí coincide con la que
research/tests/test_layers.py::test_trigger_matches_legacy ya valida contra
bot.py — acá se compara contra el propio adaptador de esta campaña, no
contra bot.py directamente, porque backtest.py no corre A_sweep_bos), que
las 3 variantes de Entry corren sin excepciones, y que D_next_candle_open
descarta correctamente eventos en el borde final de la serie en vez de
lanzar IndexError. Ejecutar:
    python -m research.tests.test_entry_campaign_sweep_bos  (o con pytest)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import backtest
import research
from dc_v1 import build_dc_v1, validate_dc_v1
from periods import period_slice
from versions import PIPELINE_VERSION, DATASET_VERSION

sys.path.insert(0, ".")
import scripts.bias_campaign as bias_camp
import scripts.entry_campaign_sweep_bos as camp

Path("smc_bot.log").unlink(missing_ok=True)


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def make_synthetic_raw_1h(start="2021-10-01", n=8000, seed=7) -> pd.DataFrame:
    """Misma forma que research/tests/test_bias_campaign.py::make_synthetic_raw_1h,
    duplicada por la misma convención de archivos de test standalone."""
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


def test_find_entries_for_entry_a_pullback_50_matches_manual_filter():
    """Paridad estructural: aplicar el filtro de bias/sesión/riesgo manualmente
    sobre los mismos eventos crudos de A_sweep_bos + entry_A_pullback_50 debe
    coincidir 1:1 con find_entries_for_entry — es el mismo chequeo que
    backtest.py::find_entries aplica, solo que acá el Trigger no es T1."""
    frame, cfg, errs = _build_2022_frame()
    if frame.empty:
        return _p("find_entries_for_entry('A_pullback_50') vs filtro manual (slice 2022 vacío)", False)

    raw_events = camp._raw_events(frame)
    entry_fn = research.ENTRY_LAYERS["A_pullback_50"]
    expected = []
    for ev in raw_events:
        row = frame.iloc[ev.entry_idx]
        if not row["in_session"] or row["bias"] != ev.direction:
            continue
        entry = entry_fn(frame, ev).price
        atr = row["atr"]
        sl = min(row["low"], entry - cfg.atr_mult * atr) if ev.direction == "long" \
            else max(row["high"], entry + cfg.atr_mult * atr)
        risk_pts = abs(entry - sl)
        if risk_pts < 1e-9:
            continue
        expected.append({"entry_idx": ev.entry_idx, "direction": ev.direction,
                          "entry": entry, "sl0": sl, "risk_pts": risk_pts})

    actual = camp.find_entries_for_entry(frame, cfg, raw_events, "A_pullback_50")
    ok = (not errs) and expected == actual and len(expected) > 0
    return _p("find_entries_for_entry('A_pullback_50') == filtro bias/sesión/riesgo manual "
               f"({len(expected)} entradas)", ok)


def test_all_entry_candidates_run_end_to_end():
    """Pipeline completo (adaptador + run_config + metrics + gate_check) para
    los 3 candidatos de Entry, sin excepciones."""
    frame, cfg, errs = _build_2022_frame()
    if frame.empty:
        return _p("pipeline completo (Entry A/C/D bajo A_sweep_bos)", False)

    raw_events = camp._raw_events(frame)
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

    return _p("pipeline completo corre sin excepciones para A_pullback_50/C_market_close/"
               "D_next_candle_open sobre slice 2022", ok)


def test_d_next_candle_open_discards_event_at_series_end():
    """A_sweep_bos NO deja margen al final de la serie (a diferencia de T1) —
    D_next_candle_open debe descartar cualquier evento cuyo entry_idx+1 caiga
    fuera de la serie, no lanzar IndexError."""
    frame, cfg, errs = _build_2022_frame()
    if frame.empty:
        return _p("D_next_candle_open descarta eventos en el borde final (slice 2022 vacío)", False)

    raw_events = camp._raw_events(frame)
    n = len(frame)
    # Fuerza un evento sintético justo en la última vela de la serie.
    from research.layers import TriggerEvent
    boundary_event = TriggerEvent(entry_idx=n - 1, direction="long", meta={
        "sweep_level": frame["low"].iloc[-1] * 0.99, "bos_level": frame["high"].iloc[-1] * 1.01,
        "swing_low": frame["low"].iloc[-1] * 0.99,
    })
    events_with_boundary = list(raw_events) + [boundary_event]

    try:
        entries = camp.find_entries_for_entry(frame, cfg, events_with_boundary, "D_next_candle_open")
        boundary_included = any(e["entry_idx"] == n - 1 for e in entries)
        ok = (not errs) and not boundary_included
    except IndexError:
        ok = False

    return _p("D_next_candle_open descarta (no lanza IndexError) un evento en la última vela "
               "de la serie", ok)


ALL_TESTS = [
    test_find_entries_for_entry_a_pullback_50_matches_manual_filter,
    test_all_entry_candidates_run_end_to_end,
    test_d_next_candle_open_discards_event_at_series_end,
]


def main():
    print("scripts/entry_campaign_sweep_bos — validación estructural sobre datos sintéticos\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
