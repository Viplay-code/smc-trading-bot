"""
research/tests/test_trigger_campaign.py — Validación ESTRUCTURAL de
scripts/trigger_campaign.py sobre datos sintéticos.

No sustituye la corrida real de la campaña (bloqueada en este sandbox, HTTP
451, data/raw/ vacío) — solo prueba que el pipeline nuevo (_raw_events,
find_entries_for_trigger, results_to_frame) no rompe, produce formas/tipos
razonables, y que find_entries_for_trigger("T1_ema_cross") reproduce
exactamente lo que ya produce backtest.py::find_entries (chequeo de
paridad — T1_ema_cross + C_market_close es, por diseño, la misma
combinación que backtest.py ya usa). Ejecutar:
    python -m research.tests.test_trigger_campaign  (o con pytest)
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
import scripts.trigger_campaign as camp

Path("smc_bot.log").unlink(missing_ok=True)


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def make_synthetic_raw_1h(start="2021-10-01", n=8000, seed=7) -> pd.DataFrame:
    """~333 días 1H (>> 90 días de buffer + un año completo). Misma forma
    que research/tests/test_bias_campaign.py::make_synthetic_raw_1h,
    duplicada acá por la misma convención (cada archivo de test es
    standalone) ya usada entre test_layers.py y test_bias_campaign.py."""
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
    """Construye el frame adaptado (Bias=A ya resuelto) sobre el slice 2022
    sintético — mismos pasos que trigger_campaign.py::load_asset_year salvo
    la carga de CSV, igual que test_bias_campaign.py lo hace para bias_campaign.py."""
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
    return frame, cfg, errs, sliced


def test_find_entries_for_trigger_t1_matches_backtest_find_entries():
    """Paridad: find_entries_for_trigger(frame, cfg, "T1_ema_cross") debe
    producir EXACTAMENTE las mismas entradas que backtest.find_entries sobre
    el mismo frame — son la misma combinación Trigger+Entry, solo con el
    Trigger resuelto por nombre en vez de estar hardcodeado. Si esto
    diverge, el adaptador nuevo no es fiel al que ya está validado en
    producción."""
    frame, cfg, errs, _ = _build_2022_frame()
    if frame.empty:
        return _p("find_entries_for_trigger('T1_ema_cross') == backtest.find_entries (slice 2022 vacío)", False)

    expected = backtest.find_entries(frame, cfg)
    actual = camp.find_entries_for_trigger(frame, cfg, "T1_ema_cross")

    ok = (not errs) and expected == actual
    return _p("find_entries_for_trigger('T1_ema_cross') reproduce backtest.find_entries 1:1", ok)


def test_find_entries_for_trigger_runs_both_candidates_end_to_end():
    """Pipeline completo (adaptador + run_config + metrics + gate_check)
    para AMBOS candidatos de Trigger, sin excepciones, con formas/tipos
    razonables — análogo a
    test_bias_campaign.py::test_full_pipeline_end_to_end_on_2022_slice."""
    frame, cfg, errs, sliced = _build_2022_frame()
    if sliced.empty:
        return _p("pipeline completo (Trigger T1/A_sweep_bos + run_config + metrics + gate_check)", False)

    ok = not errs
    for trigger_name in camp.CANDIDATES:
        entries = camp.find_entries_for_trigger(frame, cfg, trigger_name)
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

    return _p("pipeline completo corre sin excepciones para T1_ema_cross y A_sweep_bos sobre slice 2022", ok)


def test_raw_events_rejects_unknown_trigger_name():
    frame, cfg, _, _ = _build_2022_frame()
    try:
        camp._raw_events(frame, "no_existe", cfg)
        ok = False
    except ValueError:
        ok = True
    return _p("_raw_events rechaza un nombre de Trigger desconocido con ValueError", ok)


def test_run_blind_test_requires_frozen_candidate():
    """Mismo guardrail que bias_campaign.py::run_blind_test — no se puede
    correr 2024 sin un candidato ya congelado tras 2022+2023. Se puede
    probar sin data/raw/ porque el chequeo ocurre antes de cualquier I/O."""
    ok = True
    try:
        camp.run_blind_test(candidate=None)
        ok = False
    except ValueError:
        pass
    try:
        camp.run_blind_test(candidate="bogus_trigger")
        ok = False
    except ValueError:
        pass
    return _p("run_blind_test exige --candidate en CANDIDATES antes de tocar data/raw/", ok)


def _fake_result(asset, year, candidate, exit_config, n_entries, n_trades, freq, pf=1.0, gate_pass=False):
    return {
        "asset": asset, "year": year, "candidate": candidate, "exit_config": exit_config,
        "n_entries": n_entries, "n_trades": n_trades, "gate_pass": gate_pass,
        "metrics": {"pf": pf, "wr": 30.0, "exp_r": 0.05, "total_r": 1.0, "max_dd": -3.0,
                    "freq": freq, "be": 0, "reasons": {"stop": n_trades, "timeout": 0}},
    }


def test_results_to_frame_computes_entries_per_month_and_fill_rate():
    """entries_per_month/fill_rate — el desglose que el diagnóstico manual
    de la campaña de Bias (2026-07-27) mostró útil para distinguir "el
    Trigger genera pocas oportunidades" de "se descartan después por la
    regla de una-posición-a-la-vez". months = n_trades/freq (misma fórmula
    que se usó manualmente sobre bias_campaign_results.csv)."""
    results = [
        _fake_result("BTCUSDT", 2022, "T1_ema_cross", "V3-A (1R/2R/1R)",
                     n_entries=63, n_trades=62, freq=5.2),
        # n_entries=0 -> fill_rate debe ser None, no ZeroDivisionError
        _fake_result("ETHUSDT", 2022, "A_sweep_bos", "V3-A (1R/2R/1R)",
                     n_entries=0, n_trades=0, freq=None),
    ]
    df = camp.results_to_frame(results)

    row0 = df.iloc[0]
    months0 = 62 / 5.2
    expected_epm0 = round(63 / months0, 2)
    expected_fill0 = round(62 / 63, 3)

    row1 = df.iloc[1]

    ok = (
        row0["entries_per_month"] == expected_epm0
        and row0["fill_rate"] == expected_fill0
        and pd.isna(row1["entries_per_month"])
        and pd.isna(row1["fill_rate"])
    )
    return _p("results_to_frame calcula entries_per_month/fill_rate (y maneja n_entries=0/freq=None sin excepción)", ok)


ALL_TESTS = [
    test_find_entries_for_trigger_t1_matches_backtest_find_entries,
    test_find_entries_for_trigger_runs_both_candidates_end_to_end,
    test_raw_events_rejects_unknown_trigger_name,
    test_run_blind_test_requires_frozen_candidate,
    test_results_to_frame_computes_entries_per_month_and_fill_rate,
]


def main():
    print("scripts/trigger_campaign — validación estructural sobre datos sintéticos\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
