"""
research/tests/test_gestion_campaign_session.py — Validación ESTRUCTURAL de
scripts/gestion_campaign_session.py sobre datos sintéticos.

No sustituye la corrida real (bloqueada en este sandbox, HTTP 451,
data/raw/ vacío). Además de las pruebas de pipeline end-to-end habituales,
verifica explícitamente las dos propiedades formales del diseño (2026-07-29):
(1) eventos crudos de T1 idénticos entre ventanas de sesión, (2) n_entries
monótono no decreciente entre ventanas anidadas — Y que ambos sanity-checks
detectan una violación real cuando se les da una, no solo que pasan en el
caso feliz. También verifica que note_concurrency_effects señala (sin
excepción) un caso de n_trades NO monótono, el contraejemplo construido
durante el diseño para demostrar que esa propiedad NO está garantizada.
Ejecutar:
    python -m research.tests.test_gestion_campaign_session  (o con pytest)
"""
from __future__ import annotations

import contextlib
import io
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
import scripts.gestion_campaign_session as camp

Path("smc_bot.log").unlink(missing_ok=True)


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def make_synthetic_raw_1h(start="2021-10-01", n=8000, seed=7) -> pd.DataFrame:
    """Misma forma que en los tests de las campañas anteriores, duplicada
    acá por la misma convención (cada archivo de test es standalone)."""
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


def _build_2022_sliced():
    raw = make_synthetic_raw_1h()
    df_full = build_dc_v1(raw, asset="TESTUSDT", dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)
    df4h_full = bias_camp.resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, camp.BIAS_CANDIDATE)
    sliced = period_slice(df_full, 2022)
    return sliced, errs


def _raw_and_entry_counts(sliced: pd.DataFrame) -> tuple[dict, dict]:
    raw_counts, entry_counts = {}, {}
    for label in camp.NESTED_ORDER:
        cfg = camp._cfg_for(label)
        frame = bias_camp.to_backtest_frame(sliced, sliced["bias_A"], cfg)
        raw_counts[label] = len(trigger_camp._raw_events(frame, camp.TRIGGER_CANDIDATE, cfg))
        entry_counts[label] = len(trigger_camp.find_entries_for_trigger(frame, cfg, camp.TRIGGER_CANDIDATE))
    return raw_counts, entry_counts


def test_raw_events_identical_across_session_windows_on_synthetic_data():
    """Prueba 1 del diseño: eventos crudos de T1 idénticos (no solo
    monótonos) entre control_8h/dcv1_activo_15h/sin_filtro_24h, porque
    `sessions` no está en la firma de trigger_T1_ema_cross."""
    sliced, errs = _build_2022_sliced()
    if sliced.empty:
        return _p("eventos crudos idénticos entre ventanas de sesión (slice 2022 vacío)", False)
    raw_counts, _ = _raw_and_entry_counts(sliced)
    ok = (not errs) and len(set(raw_counts.values())) == 1
    return _p(f"eventos crudos de T1 idénticos entre las 3 ventanas en datos sintéticos ({raw_counts})", ok)


def test_n_entries_monotonic_across_nested_session_windows_on_synthetic_data():
    """Prueba 2 del diseño: n_entries monótono no decreciente entre las 3
    ventanas anidadas."""
    sliced, errs = _build_2022_sliced()
    if sliced.empty:
        return _p("n_entries monótono entre ventanas anidadas (slice 2022 vacío)", False)
    _, entry_counts = _raw_and_entry_counts(sliced)
    counts = [entry_counts[label] for label in camp.NESTED_ORDER]
    ok = (not errs) and counts[0] <= counts[1] <= counts[2]
    try:
        camp.assert_n_entries_monotonic(entry_counts, "TESTUSDT", 2022)
    except AssertionError:
        ok = False
    return _p(f"n_entries monótono no decreciente en datos sintéticos ({dict(zip(camp.NESTED_ORDER, counts))})", ok)


def test_sanity_checks_detect_real_violations():
    """Que ninguno de los dos sanity-checks sea un chequeo vacío: si se les
    da una divergencia/no-monotonicidad real, deben revenir con
    AssertionError. Prueba la lógica de detección en sí."""
    ok = True
    try:
        camp.assert_raw_events_session_invariant(
            {"control_8h": 10, "dcv1_activo_15h": 12, "sin_filtro_24h": 10}, "TESTUSDT", 2022)
        ok = False
    except AssertionError:
        pass
    try:
        camp.assert_n_entries_monotonic(
            {"control_8h": 10, "dcv1_activo_15h": 8, "sin_filtro_24h": 12}, "TESTUSDT", 2022)
        ok = False
    except AssertionError:
        pass
    # casos felices: no deben revenir
    try:
        camp.assert_raw_events_session_invariant(
            {"control_8h": 10, "dcv1_activo_15h": 10, "sin_filtro_24h": 10}, "TESTUSDT", 2022)
        camp.assert_n_entries_monotonic(
            {"control_8h": 10, "dcv1_activo_15h": 12, "sin_filtro_24h": 15}, "TESTUSDT", 2022)
    except AssertionError:
        ok = False
    return _p("ambos sanity-checks revientan con violaciones reales y pasan en el caso feliz", ok)


def test_note_concurrency_effects_flags_non_monotonic_n_trades_without_raising():
    """El contraejemplo del diseño (2026-07-29): n_entries sube (3->4) pero
    n_trades baja (3->2) por una entrada larga que bloquea dos entradas más
    cortas — note_concurrency_effects debe señalarlo en el output SIN
    lanzar ninguna excepción (es información, no un error)."""
    rows = [
        {"asset": "BTCUSDT", "year": 2022, "candidate": "control_8h", "exit_config": "V3-A (1R/2R/1R)",
         "n_entries": 3, "n_trades": 3},
        {"asset": "BTCUSDT", "year": 2022, "candidate": "dcv1_activo_15h", "exit_config": "V3-A (1R/2R/1R)",
         "n_entries": 4, "n_trades": 2},  # el contraejemplo: n_entries sube, n_trades baja
        {"asset": "BTCUSDT", "year": 2022, "candidate": "sin_filtro_24h", "exit_config": "V3-A (1R/2R/1R)",
         "n_entries": 5, "n_trades": 2},
    ]
    df = pd.DataFrame(rows)

    buf = io.StringIO()
    ok = True
    try:
        with contextlib.redirect_stdout(buf):
            camp.note_concurrency_effects(df)
    except Exception:
        ok = False
    output = buf.getvalue()
    ok = ok and ("BTCUSDT" in output) and ("no es un error" in output or "Nota" in output)
    return _p("note_concurrency_effects señala n_trades no monótono sin lanzar excepción", ok)


def test_run_asset_year_end_to_end_all_session_windows():
    """Pipeline completo (ambos sanity-checks + las 3 ventanas x 2
    exit_configs) para un (activo, año) sintético, sin excepciones."""
    sliced, errs = _build_2022_sliced()
    if sliced.empty:
        return _p("run_asset_year end-to-end (las 3 ventanas)", False)

    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        rows = camp.run_asset_year("TESTUSDT", 2022)
    finally:
        trigger_camp.load_asset_year = orig

    ok = (
        not errs
        and len(rows) == len(camp.NESTED_ORDER) * len(backtest.EXIT_CONFIGS)
        and all(r["candidate"] in camp.CANDIDATES for r in rows)
        and all(isinstance(r["gate_pass"], bool) for r in rows)
    )
    return _p("run_asset_year corre sin excepciones para las 3 ventanas x 2 exit_configs", ok)


def test_run_blind_test_requires_frozen_candidate():
    ok = True
    try:
        camp.run_blind_test(candidate=None)
        ok = False
    except ValueError:
        pass
    try:
        camp.run_blind_test(candidate="ventana_inventada")
        ok = False
    except ValueError:
        pass
    return _p("run_blind_test exige --candidate en CANDIDATES antes de tocar data/raw/", ok)


def test_run_blind_test_also_runs_sanity_checks():
    """Corrección 2026-07-29: run_blind_test no pasaba por
    _build_windows_and_verify — ninguno de los dos sanity-checks corría en
    la ruta --blind. Se confirma con un espía sobre
    assert_n_entries_monotonic: antes de la corrección, `calls` habría
    quedado vacío."""
    sliced, errs = _build_2022_sliced()
    if sliced.empty:
        return _p("run_blind_test invoca los sanity-checks", False)

    calls = []
    orig_assert = camp.assert_n_entries_monotonic

    def spy(counts, asset, year):
        calls.append((asset, year))
        return orig_assert(counts, asset, year)

    orig_load = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    camp.assert_n_entries_monotonic = spy
    try:
        results = camp.run_blind_test(assets=("TESTUSDT",), candidate="dcv1_activo_15h")
    finally:
        trigger_camp.load_asset_year = orig_load
        camp.assert_n_entries_monotonic = orig_assert

    ok = (
        not errs
        and calls == [("TESTUSDT", camp.BLIND_YEAR)]
        and len(results) == len(backtest.EXIT_CONFIGS)
        and all(r["candidate"] == "dcv1_activo_15h" for r in results)
    )
    return _p("run_blind_test invoca assert_n_entries_monotonic (antes no lo hacía)", ok)


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
    results = [
        _fake_result("BTCUSDT", 2022, "dcv1_activo_15h", "V3-A (1R/2R/1R)",
                     n_entries=90, n_trades=85, freq=7.5, avg_win=0.7, avg_loss=-0.35),
    ]
    df = camp.results_to_frame(results)
    row = df.iloc[0]
    ok = (row["avg_win"] == 0.7) and (row["avg_loss"] == -0.35)
    return _p("results_to_frame exporta avg_win/avg_loss sin transformarlos", ok)


ALL_TESTS = [
    test_raw_events_identical_across_session_windows_on_synthetic_data,
    test_n_entries_monotonic_across_nested_session_windows_on_synthetic_data,
    test_sanity_checks_detect_real_violations,
    test_note_concurrency_effects_flags_non_monotonic_n_trades_without_raising,
    test_run_asset_year_end_to_end_all_session_windows,
    test_run_blind_test_requires_frozen_candidate,
    test_run_blind_test_also_runs_sanity_checks,
    test_results_to_frame_exports_avg_win_avg_loss,
]


def main():
    print("scripts/gestion_campaign_session — validación estructural sobre datos sintéticos\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
