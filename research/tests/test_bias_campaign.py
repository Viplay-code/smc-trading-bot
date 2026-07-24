"""
research/tests/test_bias_campaign.py — Validación ESTRUCTURAL de
scripts/bias_campaign.py sobre datos sintéticos.

No sustituye la corrida real de la campaña (bloqueada en este sandbox, HTTP
451, data/raw/ vacío) — solo prueba que el pipeline nuevo (resample_4h,
apply_bias, to_backtest_frame, load_asset_year salvo la carga de CSV, gate_check)
no rompe y produce formas/tipos razonables, ejercitando el `build_dc_v1()`
real (no mockeado) sobre OHLCV sintético. Ejecutar:
    python -m research.tests.test_bias_campaign  (o con pytest)
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
import scripts.bias_campaign as camp

Path("smc_bot.log").unlink(missing_ok=True)


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def make_synthetic_raw_1h(start="2021-10-01", n=8000, seed=7) -> pd.DataFrame:
    """~333 días 1H (>> 90 días de buffer + un año completo), misma forma que
    make_synthetic_1h de research/tests/test_layers.py pero más larga —
    necesaria para cubrir buffer de warmup + el año 2022 completo."""
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


def test_resample_4h_matches_dcv1_convention():
    raw = make_synthetic_raw_1h()
    df4h = camp.resample_4h(raw)
    ok = (
        isinstance(df4h.index, pd.DatetimeIndex)
        and set(["open", "high", "low", "close", "volume"]).issubset(df4h.columns)
        and len(df4h) > 0
        and df4h.index[0].hour % 4 == 0
    )
    return _p("resample_4h produce OHLCV 4H bien formado, alineado a fronteras de 4h", ok)


def test_apply_bias_both_candidates_on_real_pipeline():
    raw = make_synthetic_raw_1h()
    df_full = build_dc_v1(raw, asset="TESTUSDT", dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)
    df4h_full = camp.resample_4h(df_full)

    bias_a = camp.apply_bias(df_full, df4h_full, "A")
    bias_a2 = camp.apply_bias(df_full, df4h_full, "A2")

    ok = (
        not errs
        and bias_a.index.equals(df_full.index)
        and bias_a2.index.equals(df_full.index)
        and set(bias_a.dropna().unique()).issubset({-1, 0, 1})
        and set(bias_a2.dropna().unique()).issubset({-1, 0, 1})
        and bias_a.dtype == np.int8
        and bias_a2.dtype == np.int8
    )
    return _p("apply_bias('A') y apply_bias('A2') corren sobre build_dc_v1() real, "
               "dominio {-1,0,1}, alineadas al índice 1H", ok)


def test_full_pipeline_end_to_end_on_2022_slice():
    raw = make_synthetic_raw_1h()
    df_full = build_dc_v1(raw, asset="TESTUSDT", dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    df4h_full = camp.resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = camp.apply_bias(df_full, df4h_full, "A")
    df_full["bias_A2"] = camp.apply_bias(df_full, df4h_full, "A2")

    sliced = period_slice(df_full, 2022)
    if sliced.empty:
        return _p("full pipeline end-to-end sobre slice 2022 (sintético cubre el año)", False)

    cfg = backtest.Config()
    ok = True
    for candidate in camp.CANDIDATES:
        frame = camp.to_backtest_frame(sliced, sliced[f"bias_{candidate}"], cfg)
        ok = ok and set(["open", "high", "low", "close", "atr", "in_session", "bias"]).issubset(frame.columns)
        ok = ok and set(frame["bias"].dropna().unique()).issubset({"long", "short", "neutral"})

        entries = backtest.find_entries(frame, cfg)
        ok = ok and isinstance(entries, list)

        for exit_cfg in backtest.EXIT_CONFIGS.values():
            trades = backtest.run_config(frame, entries, exit_cfg, cfg)
            m = backtest.metrics(trades, cfg)
            gate = camp.gate_check(m)
            ok = ok and isinstance(gate, bool)

    return _p("pipeline completo (adaptador + find_entries + run_config + metrics + "
               "gate_check) corre sin excepciones para A y A2 sobre slice 2022", ok)


def test_gate_check_uses_framework_freq_range_not_passes():
    m_low = {"pf": 2.0, "max_dd": -5, "exp_r": 0.1, "freq": 3}    # bajo el piso de FRAMEWORK (6)
    m_high = {"pf": 2.0, "max_dd": -5, "exp_r": 0.1, "freq": 15}  # sobre el techo de FRAMEWORK (12),
                                                                    # pero pasaría backtest.py::passes()
    m_ok = {"pf": 2.0, "max_dd": -5, "exp_r": 0.1, "freq": 9}
    ok = (
        camp.gate_check(m_low) is False
        and camp.gate_check(m_high) is False
        and camp.gate_check(m_ok) is True
        and camp.gate_check(None) is False
    )
    return _p("gate_check aplica el rango 6-12/mes de FRAMEWORK.md (rechaza freq=15, "
               "que backtest.py::passes() aceptaría)", ok)


def _fake_row(asset, year, candidate, exit_config, pf, gate_pass):
    return {
        "asset": asset, "year": year, "candidate": candidate,
        "exit_config": exit_config, "n_entries": 10, "n_trades": 10,
        "gate_pass": gate_pass, "pf": pf, "wr": 50.0, "exp_r": 0.1,
        "total_r": 5.0, "max_dd": -5.0, "freq": 8.0, "be": 0,
        "reason_stop": 5, "reason_timeout": 5,
    }


def test_summarize_decision_per_asset_no_cross_asset_compensation():
    """Construye 3 activos con desenlaces deliberadamente distintos para
    probar que summarize_decision (a) exige pasar los gates en AMBOS años
    para sobrevivir, (b) rankea por PF 2023 SOLO dentro de cada activo, y
    (c) un activo que falla no se "arregla" por el desempeño de otro —
    exactamente el requisito del ajuste de alcance del plan v2."""
    rows = [
        # BTCUSDT: A sobrevive ambos años, A2 falla 2023 -> solo A sobrevive, rank 1.
        _fake_row("BTCUSDT", 2022, "A",  "V3-A", pf=1.8, gate_pass=True),
        _fake_row("BTCUSDT", 2023, "A",  "V3-A", pf=1.6, gate_pass=True),
        _fake_row("BTCUSDT", 2022, "A2", "V3-A", pf=1.9, gate_pass=True),
        _fake_row("BTCUSDT", 2023, "A2", "V3-A", pf=1.2, gate_pass=False),

        # ETHUSDT: ambos sobreviven, A2 tiene mejor PF 2023 -> A2 rank 1, A rank 2.
        _fake_row("ETHUSDT", 2022, "A",  "V3-A", pf=1.7, gate_pass=True),
        _fake_row("ETHUSDT", 2023, "A",  "V3-A", pf=1.6, gate_pass=True),
        _fake_row("ETHUSDT", 2022, "A2", "V3-A", pf=1.8, gate_pass=True),
        _fake_row("ETHUSDT", 2023, "A2", "V3-A", pf=2.1, gate_pass=True),

        # SOLUSDT: ninguno sobrevive ambos años -> sin ranking, señal de tercer candidato.
        _fake_row("SOLUSDT", 2022, "A",  "V3-A", pf=1.4, gate_pass=False),
        _fake_row("SOLUSDT", 2023, "A",  "V3-A", pf=1.3, gate_pass=False),
        _fake_row("SOLUSDT", 2022, "A2", "V3-A", pf=1.5, gate_pass=False),
        _fake_row("SOLUSDT", 2023, "A2", "V3-A", pf=1.4, gate_pass=False),
    ]
    df = pd.DataFrame(rows)
    decision = camp.summarize_decision(df)

    def rank_of(asset, candidate):
        row = decision[(decision["asset"] == asset) & (decision["candidate"] == candidate)]
        return row["rank_within_asset"].iloc[0]

    def survives(asset, candidate):
        row = decision[(decision["asset"] == asset) & (decision["candidate"] == candidate)]
        return bool(row["survives_both_years"].iloc[0])

    ok = (
        survives("BTCUSDT", "A") is True
        and survives("BTCUSDT", "A2") is False
        and rank_of("BTCUSDT", "A") == 1
        # ETHUSDT: A2 (PF 2023=2.1) debe rankear antes que A (PF 2023=1.6),
        # SIN que importe lo que haya pasado en BTCUSDT o SOLUSDT.
        and survives("ETHUSDT", "A") is True
        and survives("ETHUSDT", "A2") is True
        and rank_of("ETHUSDT", "A2") == 1
        and rank_of("ETHUSDT", "A") == 2
        # SOLUSDT: nadie sobrevive -> sin compensación desde BTC/ETH.
        and survives("SOLUSDT", "A") is False
        and survives("SOLUSDT", "A2") is False
    )
    return _p("summarize_decision: gates+ranking por activo, sin compensación cruzada "
               "entre activos (BTCUSDT/ETHUSDT/SOLUSDT con desenlaces independientes)", ok)


ALL_TESTS = [
    test_resample_4h_matches_dcv1_convention,
    test_apply_bias_both_candidates_on_real_pipeline,
    test_full_pipeline_end_to_end_on_2022_slice,
    test_gate_check_uses_framework_freq_range_not_passes,
    test_summarize_decision_per_asset_no_cross_asset_compensation,
]


def main():
    print("scripts/bias_campaign — validación estructural sobre datos sintéticos\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
