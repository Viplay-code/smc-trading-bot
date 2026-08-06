"""
research/tests/test_integration_campaign_activation.py — Validación
ESTRUCTURAL de scripts/integration_campaign_activation.py sobre datos
sintéticos.

No sustituye la corrida real (bloqueada en este sandbox, HTTP 451,
data/raw/ vacío) ni la verificación real contra los CSV históricos
(gestion_campaign_activation_results.csv/gestion_campaign_session_
results.csv) — prueba que _verify_against y verify_anchor_dual_role
detectan coincidencias y mismatches correctamente, que
ACTIVATION_ANCHOR (2.0) SÍ aparece en CANDIDATES (a diferencia de
DISTANCE_ANCHOR en I1-distance, por su rol dual acordado), que
run_control_checks/run_campaign respetan el orden Fase A -> Fase B, y que
el pipeline completo corre sin excepciones sobre datos sintéticos.
Ejecutar:
    python -m research.tests.test_integration_campaign_activation  (o con pytest)
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
import scripts.integration_campaign_activation as camp

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
# Congelamiento del espacio experimental (Paso 0) y rol dual del ancla       #
# --------------------------------------------------------------------------- #
def test_activation_candidates_frozen_from_paso_0_no_pruning():
    ok = camp.ACTIVATION_CANDIDATES == (1.25, 1.5, 2.0, 2.5, 3.0)
    return _p("ACTIVATION_CANDIDATES == conjunto no-dominado del Paso 0, sin poda (5 valores)", ok)


def test_anchor_is_in_candidates_unlike_distance():
    """A diferencia de I1-distance, acá el ancla (2.0) SÍ debe estar en
    CANDIDATES — rol dual acordado 2026-08-06."""
    ok = any(c.startswith(f"{camp.ACTIVATION_ANCHOR} |") for c in camp.CANDIDATES)
    return _p(f"ACTIVATION_ANCHOR (2.0) SÍ aparece en CANDIDATES (rol dual) ({camp.CANDIDATES})", ok)


def test_candidates_size_matches_grid():
    ok = len(camp.CANDIDATES) == len(camp.ACTIVATION_CANDIDATES) * len(camp.SESSION_LABELS) == 10
    return _p("CANDIDATES tiene exactamente 5 activation x 2 sesiones = 10 combinaciones", ok)


# --------------------------------------------------------------------------- #
# _verify_against — igual patrón que I1-distance                             #
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
    return _p("_verify_against revienta con AssertionError si pf no coincide", ok)


# --------------------------------------------------------------------------- #
# verify_anchor_dual_role                                                     #
# --------------------------------------------------------------------------- #
def _fake_row(asset, year, activation, session, role, pf, n_trades=48, n_entries=50):
    m = {"pf": pf, "wr": 30.0, "exp_r": 0.05, "avg_win": 0.8, "avg_loss": -0.4,
         "total_r": 1.0, "max_dd": -3.0, "freq": 6.0, "be": 0,
         "reasons": {"stop": 40, "timeout": 8}}
    return {
        "asset": asset, "year": year, "role": role, "session": session,
        "candidate": camp._label(activation, session), "exit_config": camp.EXIT_CONFIG_LABEL,
        "n_entries": n_entries, "n_trades": n_trades, "metrics": m,
        "gate_pass": camp.gate_check(m),
    }


def test_verify_anchor_dual_role_passes_when_identical():
    ctrl = [_fake_row("BTCUSDT", 2022, 2.0, "control_8h", "control", pf=1.0)]
    cand = [_fake_row("BTCUSDT", 2022, 2.0, "control_8h", "candidate", pf=1.0)]
    ok = True
    try:
        camp.verify_anchor_dual_role(ctrl, cand)
    except AssertionError:
        ok = False
    return _p("verify_anchor_dual_role no revienta cuando control y candidate son idénticos", ok)


def test_verify_anchor_dual_role_raises_on_pf_mismatch():
    ctrl = [_fake_row("BTCUSDT", 2022, 2.0, "control_8h", "control", pf=1.0)]
    cand = [_fake_row("BTCUSDT", 2022, 2.0, "control_8h", "candidate", pf=1.05)]
    ok = False
    try:
        camp.verify_anchor_dual_role(ctrl, cand)
    except AssertionError as e:
        ok = "pf" in str(e)
    return _p("verify_anchor_dual_role revienta si pf difiere entre control y candidate", ok)


def test_verify_anchor_dual_role_raises_on_n_trades_mismatch():
    ctrl = [_fake_row("BTCUSDT", 2022, 2.0, "control_8h", "control", pf=1.0, n_trades=48)]
    cand = [_fake_row("BTCUSDT", 2022, 2.0, "control_8h", "candidate", pf=1.0, n_trades=47)]
    ok = False
    try:
        camp.verify_anchor_dual_role(ctrl, cand)
    except AssertionError as e:
        ok = "n_trades" in str(e)
    return _p("verify_anchor_dual_role revienta si n_trades difiere (chequea TODAS las métricas, no solo pf)", ok)


def test_verify_anchor_dual_role_raises_when_candidate_row_missing():
    ctrl = [_fake_row("BTCUSDT", 2022, 2.0, "control_8h", "control", pf=1.0)]
    cand: list[dict] = []  # Fase B no generó la fila esperada
    ok = False
    try:
        camp.verify_anchor_dual_role(ctrl, cand)
    except AssertionError:
        ok = True
    return _p("verify_anchor_dual_role revienta si falta la fila candidata equivalente", ok)


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


def test_run_control_checks_pass_when_reference_matches_exactly():
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

    ref_h22 = _series_from_row(row_c8)
    ref_sess = _series_from_row(row_15)

    orig_h22 = camp._h22_reference
    orig_sess = camp._session_reference
    camp._h22_reference = lambda asset, year: ref_h22
    camp._session_reference = lambda asset, year: ref_sess
    trigger_camp.load_asset_year = lambda asset, year: sliced
    ok = True
    try:
        rows2 = camp.run_control_checks("TESTUSDT", 2022)
        ok = (not errs) and len(rows2) == 2
    except AssertionError:
        ok = False
    finally:
        camp._h22_reference = orig_h22
        camp._session_reference = orig_sess
        trigger_camp.load_asset_year = orig

    return _p("run_control_checks pasa (sin excepción) cuando la referencia coincide exacto", ok)


def test_run_control_checks_raises_when_reference_wrong():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_control_checks revienta con referencia incorrecta (slice vacío)", False)

    wrong_ref = pd.Series({"pf": 999.0, "wr": 1.0, "exp_r": 1.0, "avg_win": 1.0,
                            "avg_loss": -1.0, "max_dd": -1.0, "freq": 1.0, "n_trades": 1})

    orig_h22 = camp._h22_reference
    orig_sess = camp._session_reference
    orig_load = trigger_camp.load_asset_year
    camp._h22_reference = lambda asset, year: wrong_ref
    camp._session_reference = lambda asset, year: wrong_ref
    trigger_camp.load_asset_year = lambda asset, year: sliced
    ok = False
    try:
        camp.run_control_checks("TESTUSDT", 2022)
    except AssertionError:
        ok = not errs
    finally:
        camp._h22_reference = orig_h22
        camp._session_reference = orig_sess
        trigger_camp.load_asset_year = orig_load

    return _p("run_control_checks revienta con AssertionError si la referencia NO coincide", ok)


def test_run_campaign_never_reaches_phase_b_if_phase_a_fails():
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
        ok = False
    finally:
        camp.run_control_checks = orig_checks
        camp.run_asset_year_experimental = orig_exp

    return _p("run_campaign() propaga la falla de Fase A sin invocar Fase B", ok)


def test_run_campaign_propagates_dual_role_mismatch():
    """Si verify_anchor_dual_role revienta (rol dual inconsistente), la
    excepción debe propagarse desde run_campaign()."""
    orig_verify = camp.verify_anchor_dual_role
    camp.verify_anchor_dual_role = lambda ctrl, exp: (_ for _ in ()).throw(
        AssertionError("rol dual simulado: inconsistente"))
    orig_checks = camp.run_control_checks
    orig_exp_fn = camp.run_asset_year_experimental
    camp.run_control_checks = lambda asset, year: []
    camp.run_asset_year_experimental = lambda asset, year: []
    ok = False
    try:
        camp.run_campaign(assets=("TESTUSDT",), years=(2022,))
    except AssertionError:
        ok = True
    finally:
        camp.verify_anchor_dual_role = orig_verify
        camp.run_control_checks = orig_checks
        camp.run_asset_year_experimental = orig_exp_fn

    return _p("run_campaign() propaga una falla de verify_anchor_dual_role", ok)


def test_run_asset_year_experimental_produces_ten_candidate_rows():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_asset_year_experimental produce 10 filas candidate (slice vacío)", False)

    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        rows = camp.run_asset_year_experimental("TESTUSDT", 2022)
    finally:
        trigger_camp.load_asset_year = orig

    ok = (
        not errs
        and len(rows) == 10
        and all(r["role"] == "candidate" for r in rows)
        and all(r["candidate"] in camp.CANDIDATES for r in rows)
        and all(isinstance(r["gate_pass"], bool) for r in rows)
    )
    return _p(f"run_asset_year_experimental produce 10 filas role='candidate' ({len(rows)})", ok)


def test_full_pipeline_end_to_end_on_synthetic_slice():
    """run_campaign() completo (Fase A real contra referencia mockeada +
    Fase B + verify_anchor_dual_role) corre sin excepciones sobre datos
    sintéticos consistentes consigo mismos."""
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("pipeline completo corre end-to-end (slice vacío)", False)

    orig_load = trigger_camp.load_asset_year
    orig_h22 = camp._h22_reference
    orig_sess = camp._session_reference
    trigger_camp.load_asset_year = lambda asset, year: sliced

    def _matching_ref(asset, year, session_label):
        frame, cfg, entries = camp._entries_for_session(asset, year, session_label)
        _, m = camp._run_activation(frame, cfg, entries, camp.ACTIVATION_ANCHOR)
        d = {k: m[k] for k in camp._CHECK_FIELDS}
        d["n_trades"] = len(backtest.run_config(frame, entries, camp._exit_cfg(camp.ACTIVATION_ANCHOR), cfg))
        return pd.Series(d)

    camp._h22_reference = lambda asset, year: _matching_ref(asset, year, "control_8h")
    camp._session_reference = lambda asset, year: _matching_ref(asset, year, "dcv1_activo_15h")

    ok = True
    try:
        results = camp.run_campaign(assets=("TESTUSDT",), years=(2022,))
        df = camp.results_to_frame(results)
        ok = (not errs) and not df.empty and set(df["role"]) == {"control", "candidate"}
    except AssertionError as e:
        ok = False
        print(f"    (excepción inesperada: {e})")
    finally:
        trigger_camp.load_asset_year = orig_load
        camp._h22_reference = orig_h22
        camp._session_reference = orig_sess

    return _p("run_campaign() end-to-end (Fase A + Fase B + rol dual) corre sin excepciones", ok)


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
    rows = [
        _fake_row("BTCUSDT", 2022, 1.5, "dcv1_activo_15h", "candidate", pf=1.6),
        _fake_row("BTCUSDT", 2023, 1.5, "dcv1_activo_15h", "candidate", pf=1.55),
        _fake_row("BTCUSDT", 2022, 1.5, "control_8h", "candidate", pf=0.9),
        _fake_row("BTCUSDT", 2023, 1.5, "control_8h", "candidate", pf=0.8),
    ]
    df = camp.results_to_frame(rows)
    decision = camp.summarize_decision(df[df["role"] == "candidate"].reset_index(drop=True))

    row_15 = decision[decision.candidate == "1.5 | dcv1_activo_15h"].iloc[0]
    row_c8 = decision[decision.candidate == "1.5 | control_8h"].iloc[0]
    ok = bool(row_15["survives_both_years"]) and not bool(row_c8["survives_both_years"])
    return _p("summarize_decision distingue sesiones distintas del mismo activation sin mezclarlas", ok)


def test_run_blind_test_requires_frozen_candidate():
    ok = True
    try:
        camp.run_blind_test(candidate=None)
        ok = False
    except ValueError:
        pass
    try:
        camp.run_blind_test(candidate="1.75 | control_8h")  # no está en CANDIDATES
        ok = False
    except ValueError:
        pass
    return _p("run_blind_test exige --candidate en CANDIDATES antes de tocar data/raw/", ok)


def test_run_blind_test_parses_candidate_string():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_blind_test parsea 'activation | session' (slice vacío)", False)
    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        results = camp.run_blind_test(assets=("TESTUSDT",), candidate="1.5 | dcv1_activo_15h")
    finally:
        trigger_camp.load_asset_year = orig
    ok = (not errs) and len(results) == 1 and results[0]["session"] == "dcv1_activo_15h" \
        and results[0]["candidate"] == "1.5 | dcv1_activo_15h" and results[0]["role"] == "candidate"
    return _p("run_blind_test parsea correctamente el candidato compuesto", ok)


ALL_TESTS = [
    test_activation_candidates_frozen_from_paso_0_no_pruning,
    test_anchor_is_in_candidates_unlike_distance,
    test_candidates_size_matches_grid,
    test_verify_against_passes_on_exact_match,
    test_verify_against_raises_on_pf_mismatch,
    test_verify_anchor_dual_role_passes_when_identical,
    test_verify_anchor_dual_role_raises_on_pf_mismatch,
    test_verify_anchor_dual_role_raises_on_n_trades_mismatch,
    test_verify_anchor_dual_role_raises_when_candidate_row_missing,
    test_run_control_checks_pass_when_reference_matches_exactly,
    test_run_control_checks_raises_when_reference_wrong,
    test_run_campaign_never_reaches_phase_b_if_phase_a_fails,
    test_run_campaign_propagates_dual_role_mismatch,
    test_run_asset_year_experimental_produces_ten_candidate_rows,
    test_full_pipeline_end_to_end_on_synthetic_slice,
    test_results_to_frame_includes_role_and_session_columns,
    test_summarize_decision_after_filtering_control_rows,
    test_run_blind_test_requires_frozen_candidate,
    test_run_blind_test_parses_candidate_string,
]


def main():
    print("scripts/integration_campaign_activation — validación estructural sobre datos sintéticos\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
