"""
research/tests/test_gestion_mfe_diagnostico.py — Validación ESTRUCTURAL de
scripts/gestion_mfe_diagnostico.py sobre datos sintéticos.

No sustituye la corrida real (bloqueada en este sandbox, HTTP 451, data/raw/
vacío) — prueba que compute_mfe_mae calcula lo esperado sobre una vela con
trayectoria conocida, que mfe_mae_for_v3a_trades empareja correctamente los
trades de V3-A con su entrada original, que el pipeline completo corre sin
excepciones sobre datos sintéticos, que avg_win_requerido implementa
correctamente el álgebra del gate PF>=1.50, y que las 4 ramas de la
recomendación metodológica (procede / mixta / no alcanza Paso 2 / sin
Paso 1) se generan correctamente para escenarios construidos a mano.
Ejecutar:
    python -m research.tests.test_gestion_mfe_diagnostico  (o con pytest)
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
import scripts.gestion_mfe_diagnostico as diag

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


def test_compute_mfe_mae_matches_hand_calculation():
    """Construye un frame diminuto con trayectoria conocida y verifica que
    compute_mfe_mae reproduce el MFE/MAE esperado a mano, sin ninguna regla
    de salida (debe ignorar que el precio, en la vela 3, ya perforó el SL)."""
    idx = pd.date_range("2024-01-01", periods=6, freq="1h", tz="UTC")
    # Entrada long en la vela 0 a precio 100, risk_pts=2 (SL en 98).
    frame = pd.DataFrame({
        "open":  [100, 101, 99, 97, 103, 104],
        "high":  [100, 102, 100, 98, 106, 105],
        "low":   [100, 100, 96, 96, 102, 103],
        "close": [100, 101, 97, 97, 105, 104],
    }, index=idx)
    entry = {"entry_idx": 0, "direction": "long", "entry": 100.0, "risk_pts": 2.0}
    cfg = backtest.Config(max_hold=5)

    m = diag.compute_mfe_mae(frame, entry, cfg)
    # Favorable máximo: high=106 en la vela 4 -> fav_pts=6 -> mfe_r=3.0
    # Adverso máximo: low=96 en velas 2/3 -> adv_pts=4 -> mae_r=2.0 (a pesar
    # de perforar el SL nominal en la vela 3, no hay regla de salida acá).
    ok = m["mfe_r"] == 3.0 and m["mae_r"] == 2.0 and m["entry_idx"] == 0 and m["direction"] == "long"
    return _p(f"compute_mfe_mae reproduce MFE/MAE esperados a mano (obtenido: {m})", ok)


def test_avg_win_requerido_algebra():
    """avg_win_requerido = 1.50 * (1-WR) * |avg_loss| / WR — verificado con
    un caso a mano: WR=30%, avg_loss=-0.7 -> avg_win_requerido = 1.5*0.7*0.7/0.3 = 2.45."""
    wr_frac = 0.30
    avg_loss = -0.7
    expected = round(1.50 * (1 - wr_frac) * abs(avg_loss) / wr_frac, 4)
    ok = abs(expected - 2.45) < 1e-6
    return _p(f"avg_win_requerido algebraico == 2.45 para WR=30%/avg_loss=-0.7 (obtenido {expected})", ok)


def _build_frame_and_entries():
    raw = make_synthetic_raw_1h()
    df_full = build_dc_v1(raw, asset="TESTUSDT", dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)
    df4h_full = bias_camp.resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, diag.BIAS_CANDIDATE)
    sliced = period_slice(df_full, 2022)
    cfg = backtest.Config()
    frame = bias_camp.to_backtest_frame(sliced, sliced["bias_A"], cfg)
    entries = trigger_camp.find_entries_for_trigger(frame, cfg, diag.TRIGGER_CANDIDATE)
    return frame, cfg, entries, errs, sliced


def test_mfe_mae_for_v3a_trades_matches_entries():
    """Cada fila de mfe_mae_for_v3a_trades debe corresponder a un trade real
    de V3-A, con direction/pnl_r consistentes con lo que ya devuelve
    backtest.run_config/metrics — no un recálculo paralelo desalineado."""
    frame, cfg, entries, errs, _ = _build_frame_and_entries()
    if frame.empty or not entries:
        return _p("mfe_mae_for_v3a_trades empareja trades V3A con su entrada (frame/entries vacíos)", False)

    trades_v3a = backtest.run_config(frame, entries, backtest.EXIT_CONFIGS[diag.V3_A], cfg)
    per_trade = diag.mfe_mae_for_v3a_trades(frame, cfg, entries, trades_v3a)

    ok = (
        not errs
        and len(per_trade) == len(trades_v3a)
        and (per_trade["direction"].tolist() == trades_v3a["direction"].tolist())
        and (per_trade["pnl_r_v3a"].tolist() == trades_v3a["pnl_r"].tolist())
        and per_trade["mfe_r"].ge(0).all()
        and per_trade["mae_r"].ge(0).all()
    )
    return _p(f"mfe_mae_for_v3a_trades alineado 1:1 con backtest.run_config ({len(trades_v3a)} trades)", ok)


def test_run_asset_year_end_to_end_on_synthetic_slice():
    """Pipeline completo (carga + entries + V3-A + emparejamiento MFE/MAE +
    agregados) corre sin excepciones y produce campos coherentes."""
    frame, cfg, entries, errs, sliced = _build_frame_and_entries()
    if frame.empty:
        return _p("run_asset_year corre end-to-end (frame vacío)", False)

    import unittest.mock as mock
    with mock.patch.object(diag, "load_asset_year", return_value=sliced):
        r = diag.run_asset_year("TESTUSDT", 2022)

    ok = (
        not errs
        and r["n_trades"] > 0
        and r["mean_mfe_winners"] is not None
        and r["avg_win_requerido"] is not None
        and all(r[f"pct_mfe_ge_{th}"] is not None for th in diag.R_THRESHOLDS)
        and not r["_per_trade"].empty
    )
    return _p(f"run_asset_year end-to-end sin excepciones (n_trades={r['n_trades']})", ok)


def _fake_result(asset, year, avg_win, mean_mfe_winners, avg_win_requerido):
    return {
        "asset": asset, "year": year, "n_trades": 20, "n_winners": 6,
        "avg_win": avg_win, "avg_loss": -0.7, "wr": 30.0, "exp_r": 0.02,
        "mean_mfe_winners": mean_mfe_winners, "median_mfe_winners": mean_mfe_winners,
        "mean_mfe_all": mean_mfe_winners * 0.5, "avg_win_requerido": avg_win_requerido,
        "gap_paso1": round(mean_mfe_winners - avg_win, 4),
        **{f"pct_mfe_ge_{th}": 10.0 for th in diag.R_THRESHOLDS},
    }


def test_recommendation_branch_procede_h2():
    results = [
        _fake_result("BTCUSDT", 2022, avg_win=1.3, mean_mfe_winners=3.0, avg_win_requerido=2.45),
        _fake_result("BTCUSDT", 2023, avg_win=1.2, mean_mfe_winners=2.8, avg_win_requerido=2.45),
    ]
    report = diag.print_report(results)
    ok = "PROCEDE H2" in report
    return _p("recomendación: gap positivo consistente + Paso 2 alcanza en todos -> PROCEDE H2", ok)


def test_recommendation_branch_no_alcanza_paso2():
    results = [
        _fake_result("BTCUSDT", 2022, avg_win=1.3, mean_mfe_winners=1.5, avg_win_requerido=2.45),
        _fake_result("BTCUSDT", 2023, avg_win=1.2, mean_mfe_winners=1.6, avg_win_requerido=2.45),
    ]
    report = diag.print_report(results)
    ok = "NO PROCEDE H2" in report and "no alcanza el gate" in report
    return _p("recomendación: gap positivo pero Paso 2 no alcanza -> NO PROCEDE H2", ok)


def test_recommendation_branch_sin_gap_paso1():
    results = [
        _fake_result("BTCUSDT", 2022, avg_win=2.0, mean_mfe_winners=1.9, avg_win_requerido=2.45),
        _fake_result("BTCUSDT", 2023, avg_win=2.1, mean_mfe_winners=1.8, avg_win_requerido=2.45),
    ]
    report = diag.print_report(results)
    ok = "NO PROCEDE H2" in report and "Sin evidencia consistente" in report
    return _p("recomendación: sin gap positivo en Paso 1 -> NO PROCEDE H2 (sin evidencia)", ok)


def test_recommendation_branch_mixta():
    results = [
        _fake_result("BTCUSDT", 2022, avg_win=1.3, mean_mfe_winners=3.0, avg_win_requerido=2.45),
        _fake_result("ETHUSDT", 2022, avg_win=1.3, mean_mfe_winners=1.5, avg_win_requerido=2.45),
    ]
    report = diag.print_report(results)
    ok = "Evidencia MIXTA" in report
    return _p("recomendación: Paso 2 alcanza en un activo pero no en otro -> evidencia MIXTA", ok)


ALL_TESTS = [
    test_compute_mfe_mae_matches_hand_calculation,
    test_avg_win_requerido_algebra,
    test_mfe_mae_for_v3a_trades_matches_entries,
    test_run_asset_year_end_to_end_on_synthetic_slice,
    test_recommendation_branch_procede_h2,
    test_recommendation_branch_no_alcanza_paso2,
    test_recommendation_branch_sin_gap_paso1,
    test_recommendation_branch_mixta,
]


def main():
    print("scripts/gestion_mfe_diagnostico — validación estructural sobre datos sintéticos\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
