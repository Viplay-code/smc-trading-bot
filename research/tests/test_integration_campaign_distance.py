"""
research/tests/test_integration_campaign_distance.py — Validación
ESTRUCTURAL de scripts/integration_campaign_distance.py sobre datos
sintéticos.

No sustituye la corrida real (bloqueada en este sandbox, HTTP 451,
data/raw/ vacío) ni la verificación real contra los CSV históricos
(gestion_campaign_trailing_distance_results.csv/gestion_campaign_
session_results.csv) — prueba que _verify_against detecta coincidencias y
mismatches correctamente, que run_control_checks revienta con
AssertionError ante una referencia que no coincide y pasa cuando sí
coincide, que run_campaign() NUNCA llega a calcular filas experimentales
si la Fase A falla, que CANDIDATES nunca incluye distance=1.0 (ancla de
control), y que el pipeline completo corre sin excepciones sobre datos
sintéticos cuando la Fase A pasa. Ejecutar:
    python -m research.tests.test_integration_campaign_distance  (o con pytest)
"""
from __future__ import annotations

import sys
import unittest.mock as mock
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
import scripts.integration_campaign_distance as camp

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
# Congelamiento del espacio experimental (Paso 0)                            #
# --------------------------------------------------------------------------- #
def test_distance_candidates_frozen_from_paso_0():
    ok = camp.DISTANCE_CANDIDATES == (0.25, 0.5, 1.5)
    return _p("DISTANCE_CANDIDATES == conjunto no-dominado congelado en Paso 0 {0.25,0.5,1.5}", ok)


def test_anchor_never_in_candidates():
    """distance=1.0 (ancla, solo control) no debe aparecer en NINGÚN string
    de CANDIDATES bajo ninguna sesión."""
    ok = all(not c.startswith(f"{camp.DISTANCE_ANCHOR} |") for c in camp.CANDIDATES)
    return _p(f"DISTANCE_ANCHOR (1.0) nunca aparece en CANDIDATES ({camp.CANDIDATES})", ok)


def test_candidates_size_matches_grid():
    ok = len(camp.CANDIDATES) == len(camp.DISTANCE_CANDIDATES) * len(camp.SESSION_LABELS) == 6
    return _p("CANDIDATES tiene exactamente 3 distance x 2 sesiones = 6 combinaciones", ok)


# --------------------------------------------------------------------------- #
# _verify_against — detecta coincidencia y mismatch                          #
# --------------------------------------------------------------------------- #
def _ref_row(**overrides):
    base = {"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "avg_win": 0.8, "avg_loss": -0.4,
            "max_dd": -5.0, "freq": 5.0, "n_trades": 48}
    base.update(overrides)
    return pd.Series(base)


def test_verify_against_passes_on_exact_match():
    m = {"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "avg_win": 0.8, "avg_loss": -0.4, "max_dd": -5.0, "freq": 5.0}
    ok = True
    try:
        camp._verify_against(m, 48, _ref_row(), "contexto de prueba")
    except AssertionError:
        ok = False
    return _p("_verify_against no revienta cuando todos los campos coinciden exacto", ok)


def test_verify_against_raises_on_pf_mismatch():
    m = {"pf": 1.05, "wr": 30.0, "exp_r": 0.05, "avg_win": 0.8, "avg_loss": -0.4, "max_dd": -5.0, "freq": 5.0}
    ok = False
    try:
        camp._verify_against(m, 48, _ref_row(), "contexto de prueba")
    except AssertionError as e:
        ok = "pf" in str(e)
    return _p("_verify_against revienta con AssertionError si pf no coincide (y lo menciona)", ok)


def test_verify_against_raises_on_n_trades_mismatch():
    m = {"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "avg_win": 0.8, "avg_loss": -0.4, "max_dd": -5.0, "freq": 5.0}
    ok = False
    try:
        camp._verify_against(m, 47, _ref_row(), "contexto de prueba")
    except AssertionError as e:
        ok = "n_trades" in str(e)
    return _p("_verify_against revienta con AssertionError si n_trades no coincide", ok)


def test_verify_against_raises_on_none_metrics():
    ok = False
    try:
        camp._verify_against(None, 0, _ref_row(), "contexto de prueba")
    except AssertionError:
        ok = True
    return _p("_verify_against revienta si metrics() es None (insuficientes trades)", ok)


# --------------------------------------------------------------------------- #
# Pipeline end-to-end sobre datos sintéticos                                  #
# --------------------------------------------------------------------------- #
def _build_sliced_for(seed, start="2021-10-01"):
    raw = make_synthetic_raw_1h(start=start, seed=seed)
    df_full = build_dc_v1(raw, asset="TESTUSDT", dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)
    df4h_full = bias_camp.resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, camp.BIAS_CANDIDATE)
    sliced = period_slice(df_full, 2022)
    return sliced, errs


def test_run_control_rows_and_checks_pass_when_reference_matches_exactly():
    """Corre run_control_rows sobre datos sintéticos, construye una
    referencia que coincide EXACTO con lo que produjo, y confirma que
    run_control_checks (con los loaders de referencia monkeypatcheados)
    NO revienta y devuelve las 2 filas de control."""
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_control_checks pasa con referencia exacta (slice vacío)", False)

    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        rows = camp.run_control_rows("TESTUSDT", 2022)
    finally:
        trigger_camp.load_asset_year = orig

    row_c8 = next(r for r in rows if r["session"] == "control_8h")
    row_15 = next(r for r in rows if r["session"] == "dcv1_activo_15h")

    def _series_from_row(r):
        m = r["metrics"]
        d = {k: m[k] for k in camp._CHECK_FIELDS}
        d["n_trades"] = r["n_trades"]
        return pd.Series(d)

    ref_h21 = _series_from_row(row_c8)
    ref_sess = _series_from_row(row_15)

    orig_h21 = camp._h21_reference
    orig_sess = camp._session_reference
    camp._h21_reference = lambda asset, year: ref_h21
    camp._session_reference = lambda asset, year: ref_sess
    trigger_camp.load_asset_year = lambda asset, year: sliced
    ok = True
    try:
        rows2 = camp.run_control_checks("TESTUSDT", 2022)
        ok = (not errs) and len(rows2) == 2
    except AssertionError:
        ok = False
    finally:
        camp._h21_reference = orig_h21
        camp._session_reference = orig_sess
        trigger_camp.load_asset_year = orig

    return _p("run_control_checks pasa (sin excepción) cuando la referencia coincide exacto", ok)


def test_run_control_checks_raises_when_reference_wrong():
    """Con una referencia deliberadamente incorrecta, run_control_checks
    debe reventar con AssertionError."""
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_control_checks revienta con referencia incorrecta (slice vacío)", False)

    wrong_ref = pd.Series({"pf": 999.0, "wr": 1.0, "exp_r": 1.0, "avg_win": 1.0,
                            "avg_loss": -1.0, "max_dd": -1.0, "freq": 1.0, "n_trades": 1})

    orig_h21 = camp._h21_reference
    orig_sess = camp._session_reference
    orig_load = trigger_camp.load_asset_year
    camp._h21_reference = lambda asset, year: wrong_ref
    camp._session_reference = lambda asset, year: wrong_ref
    trigger_camp.load_asset_year = lambda asset, year: sliced
    ok = False
    try:
        camp.run_control_checks("TESTUSDT", 2022)
    except AssertionError:
        ok = not errs
    finally:
        camp._h21_reference = orig_h21
        camp._session_reference = orig_sess
        trigger_camp.load_asset_year = orig_load

    return _p("run_control_checks revienta con AssertionError si la referencia NO coincide", ok)


def test_run_campaign_never_reaches_phase_b_if_phase_a_fails():
    """Si la Fase A falla, run_campaign() debe propagar la excepción SIN
    haber calculado ninguna fila experimental — confirmado monkeypatcheando
    run_asset_year_experimental para que reviente si llega a invocarse."""
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_campaign nunca llega a Fase B si Fase A falla (slice vacío)", False)

    def _boom(asset, year):
        raise RuntimeError("Fase B NO debería haberse invocado — Fase A ya había fallado")

    orig_checks = camp.run_control_checks
    orig_exp = camp.run_asset_year_experimental
    camp.run_control_checks = lambda asset, year: (_ for _ in ()).throw(AssertionError("Fase A simulada: falla"))
    camp.run_asset_year_experimental = _boom
    ok = False
    try:
        camp.run_campaign(assets=("TESTUSDT",), years=(2022,))
    except AssertionError:
        ok = True
    except RuntimeError:
        ok = False  # Fase B se invocó pese a que Fase A falló -> mal
    finally:
        camp.run_control_checks = orig_checks
        camp.run_asset_year_experimental = orig_exp

    return _p("run_campaign() propaga la falla de Fase A sin invocar Fase B", ok)


def test_run_asset_year_experimental_produces_six_candidate_rows():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_asset_year_experimental produce 6 filas candidate (slice vacío)", False)

    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        rows = camp.run_asset_year_experimental("TESTUSDT", 2022)
    finally:
        trigger_camp.load_asset_year = orig

    ok = (
        not errs
        and len(rows) == 6
        and all(r["role"] == "candidate" for r in rows)
        and all(r["candidate"] in camp.CANDIDATES for r in rows)
        and all(isinstance(r["gate_pass"], bool) for r in rows)
    )
    return _p(f"run_asset_year_experimental produce 6 filas role='candidate' ({len(rows)})", ok)


def test_results_to_frame_includes_role_and_session_columns():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("results_to_frame incluye role/session (slice vacío)", False)
    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        rows = camp.run_asset_year_experimental("TESTUSDT", 2022)
    finally:
        trigger_camp.load_asset_year = orig
    df = camp.results_to_frame(rows)
    ok = "role" in df.columns and "session" in df.columns and set(df["role"]) == {"candidate"}
    return _p("results_to_frame conserva columnas role/session", ok)


def test_summarize_decision_after_filtering_control_rows():
    """summarize_decision (reutilizada sin modificar) debe recibir SOLO
    filas role='candidate' — el candidate string compuesto ('distance |
    session') asegura que sesiones distintas no se mezclen en el mismo
    grupo de agregación."""
    def _fake_row(asset, year, distance, session, pf, gate_pass):
        return {"asset": asset, "year": year, "role": "candidate", "session": session,
                "candidate": camp._label(distance, session), "exit_config": camp.EXIT_CONFIG_LABEL,
                "n_entries": 50, "n_trades": 48, "gate_pass": gate_pass,
                "metrics": {"pf": pf, "wr": 30.0, "exp_r": 0.05, "avg_win": 0.8, "avg_loss": -0.4,
                            "total_r": 1.0, "max_dd": -3.0, "freq": 6.0, "be": 0,
                            "reasons": {"stop": 40, "timeout": 8}}}

    rows = [
        _fake_row("BTCUSDT", 2022, 0.5, "dcv1_activo_15h", pf=1.6, gate_pass=True),
        _fake_row("BTCUSDT", 2023, 0.5, "dcv1_activo_15h", pf=1.55, gate_pass=True),
        _fake_row("BTCUSDT", 2022, 0.5, "control_8h", pf=0.9, gate_pass=False),
        _fake_row("BTCUSDT", 2023, 0.5, "control_8h", pf=0.8, gate_pass=False),
    ]
    df = camp.results_to_frame(rows)
    decision = camp.summarize_decision(df[df["role"] == "candidate"].reset_index(drop=True))

    row_15 = decision[decision.candidate == "0.5 | dcv1_activo_15h"].iloc[0]
    row_c8 = decision[decision.candidate == "0.5 | control_8h"].iloc[0]
    ok = bool(row_15["survives_both_years"]) and not bool(row_c8["survives_both_years"])
    return _p("summarize_decision distingue sesiones distintas del mismo distance sin mezclarlas", ok)


def test_run_blind_test_requires_frozen_candidate():
    ok = True
    try:
        camp.run_blind_test(candidate=None)
        ok = False
    except ValueError:
        pass
    try:
        camp.run_blind_test(candidate="1.0 | control_8h")  # ancla, nunca en CANDIDATES
        ok = False
    except ValueError:
        pass
    return _p("run_blind_test exige --candidate en CANDIDATES (nunca el ancla) antes de tocar data/raw/", ok)


def test_run_blind_test_parses_candidate_string():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_blind_test parsea 'distance | session' (slice vacío)", False)
    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        results = camp.run_blind_test(assets=("TESTUSDT",), candidate="0.5 | dcv1_activo_15h")
    finally:
        trigger_camp.load_asset_year = orig
    ok = (not errs) and len(results) == 1 and results[0]["session"] == "dcv1_activo_15h" \
        and results[0]["candidate"] == "0.5 | dcv1_activo_15h" and results[0]["role"] == "candidate"
    return _p("run_blind_test parsea correctamente el candidato compuesto", ok)


ALL_TESTS = [
    test_distance_candidates_frozen_from_paso_0,
    test_anchor_never_in_candidates,
    test_candidates_size_matches_grid,
    test_verify_against_passes_on_exact_match,
    test_verify_against_raises_on_pf_mismatch,
    test_verify_against_raises_on_n_trades_mismatch,
    test_verify_against_raises_on_none_metrics,
    test_run_control_rows_and_checks_pass_when_reference_matches_exactly,
    test_run_control_checks_raises_when_reference_wrong,
    test_run_campaign_never_reaches_phase_b_if_phase_a_fails,
    test_run_asset_year_experimental_produces_six_candidate_rows,
    test_results_to_frame_includes_role_and_session_columns,
    test_summarize_decision_after_filtering_control_rows,
    test_run_blind_test_requires_frozen_candidate,
    test_run_blind_test_parses_candidate_string,
]


def main():
    print("scripts/integration_campaign_distance — validación estructural sobre datos sintéticos\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
