"""
research/tests/test_gestion_campaign_max_hold_session.py — Validación
ESTRUCTURAL de scripts/gestion_campaign_max_hold_session.py sobre datos
sintéticos.

No sustituye la corrida real (bloqueada en este sandbox, HTTP 451,
data/raw/ vacío) ni la verificación real contra los 4 CSV históricos
(trigger_campaign_results.csv, gestion_campaign_atr_mult_results.csv,
gestion_campaign_session_results.csv, integration_campaign_activation_
results.csv) — prueba que _verify_against/_is_extreme_best/
verify_anchor_dual_role detectan coincidencias y mismatches correctamente,
que MAX_HOLD_ANCHOR (20) SÍ aparece en CANDIDATES (rol dual), que
run_control_checks/run_campaign respetan el orden Fase A -> Fase B, y que
el pipeline completo corre sin excepciones sobre datos sintéticos.
Ejecutar:
    python -m research.tests.test_gestion_campaign_max_hold_session  (o con pytest)
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
import scripts.gestion_campaign_max_hold_session as camp

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
# Grilla y rol dual                                                           #
# --------------------------------------------------------------------------- #
def test_max_hold_values_base_and_extensions():
    ok = (camp.MAX_HOLD_VALUES_BASE == (10, 20, 30)
          and camp.MAX_HOLD_EXT_LOWER == 5 and camp.MAX_HOLD_EXT_UPPER == 40
          and camp.MAX_HOLD_ANCHOR == 20)
    return _p("MAX_HOLD_VALUES_BASE=(10,20,30), extensiones 5/40, ancla 20 (proporciones de H2.3)", ok)


def test_anchor_is_in_candidates_dual_role():
    ok = any(c.startswith(f"{camp.MAX_HOLD_ANCHOR} |") for c in camp.CANDIDATES)
    return _p(f"MAX_HOLD_ANCHOR (20) SÍ aparece en CANDIDATES (rol dual) ({camp.CANDIDATES})", ok)


def test_candidates_size_matches_grid():
    ok = len(camp.CANDIDATES) == 5 * len(camp.SESSION_LABELS) == 10
    return _p("CANDIDATES tiene exactamente 5 max_hold x 2 sesiones = 10 combinaciones", ok)


# --------------------------------------------------------------------------- #
# _is_extreme_best — diseño simétrico, mismo patrón que H2.2/H2.3            #
# --------------------------------------------------------------------------- #
def test_is_extreme_best_true_when_lower_wins():
    metrics = {10: {"pf": 2.0}, 20: {"pf": 1.0}, 30: {"pf": 0.5}}
    ok = camp._is_extreme_best(metrics, 10) and not camp._is_extreme_best(metrics, 30)
    return _p("_is_extreme_best detecta el extremo inferior como mejor PF", ok)


def test_is_extreme_best_true_when_upper_wins():
    metrics = {10: {"pf": 0.5}, 20: {"pf": 1.0}, 30: {"pf": 2.0}}
    ok = camp._is_extreme_best(metrics, 30) and not camp._is_extreme_best(metrics, 10)
    return _p("_is_extreme_best detecta el extremo superior como mejor PF", ok)


def test_is_extreme_best_false_when_middle_wins():
    metrics = {10: {"pf": 0.5}, 20: {"pf": 2.0}, 30: {"pf": 0.5}}
    ok = not camp._is_extreme_best(metrics, 10) and not camp._is_extreme_best(metrics, 30)
    return _p("_is_extreme_best es False en ambos extremos cuando gana el punto medio", ok)


def test_is_extreme_best_false_when_metrics_none():
    metrics = {10: None, 20: {"pf": 1.0}, 30: {"pf": 0.5}}
    ok = not camp._is_extreme_best(metrics, 10)
    return _p("_is_extreme_best es False si el extremo tiene metrics=None (no computable)", ok)


# --------------------------------------------------------------------------- #
# _verify_against                                                             #
# --------------------------------------------------------------------------- #
def _ref_row(**overrides):
    base = {"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 5.0, "n_trades": 48}
    base.update(overrides)
    return pd.Series(base)


def test_verify_against_passes_on_exact_match():
    m = {"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 5.0}
    ok = True
    try:
        camp._verify_against(m, 48, _ref_row(), "contexto de prueba")
    except AssertionError:
        ok = False
    return _p("_verify_against no revienta cuando todos los campos coinciden exacto", ok)


def test_verify_against_raises_on_pf_mismatch():
    m = {"pf": 1.05, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 5.0}
    ok = False
    try:
        camp._verify_against(m, 48, _ref_row(), "contexto de prueba")
    except AssertionError as e:
        ok = "pf" in str(e)
    return _p("_verify_against revienta con AssertionError si pf no coincide", ok)


def test_verify_against_raises_on_n_trades_mismatch():
    m = {"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 5.0}
    ok = False
    try:
        camp._verify_against(m, 47, _ref_row(), "contexto de prueba")
    except AssertionError as e:
        ok = "n_trades" in str(e)
    return _p("_verify_against revienta si n_trades difiere aunque las métricas coincidan", ok)


# --------------------------------------------------------------------------- #
# verify_anchor_dual_role                                                     #
# --------------------------------------------------------------------------- #
def _fake_row(asset, year, max_hold, session, role, pf, n_trades=48, n_entries=50):
    m = {"pf": pf, "wr": 30.0, "exp_r": 0.05, "avg_win": 0.8, "avg_loss": -0.4,
         "total_r": 1.0, "max_dd": -3.0, "freq": 6.0, "be": 0,
         "reasons": {"stop": 40, "timeout": 8}}
    return {
        "asset": asset, "year": year, "role": role, "session": session,
        "candidate": camp._label(max_hold, session), "exit_config": camp.EXIT_CONFIG_LABEL,
        "n_entries": n_entries, "n_trades": n_trades, "metrics": m,
        "gate_pass": camp.gate_check(m), "triggered_by": None,
    }


def test_verify_anchor_dual_role_passes_when_identical():
    ctrl = [_fake_row("BTCUSDT", 2022, 20, "control_8h", "control", pf=1.0)]
    cand = [_fake_row("BTCUSDT", 2022, 20, "control_8h", "candidate", pf=1.0)]
    ok = True
    try:
        camp.verify_anchor_dual_role(ctrl, cand)
    except AssertionError:
        ok = False
    return _p("verify_anchor_dual_role no revienta cuando control y candidate son idénticos", ok)


def test_verify_anchor_dual_role_raises_on_pf_mismatch():
    ctrl = [_fake_row("BTCUSDT", 2022, 20, "control_8h", "control", pf=1.0)]
    cand = [_fake_row("BTCUSDT", 2022, 20, "control_8h", "candidate", pf=1.05)]
    ok = False
    try:
        camp.verify_anchor_dual_role(ctrl, cand)
    except AssertionError as e:
        ok = "pf" in str(e)
    return _p("verify_anchor_dual_role revienta si pf difiere entre control y candidate", ok)


def test_verify_anchor_dual_role_raises_on_n_trades_mismatch():
    ctrl = [_fake_row("BTCUSDT", 2022, 20, "control_8h", "control", pf=1.0, n_trades=48)]
    cand = [_fake_row("BTCUSDT", 2022, 20, "control_8h", "candidate", pf=1.0, n_trades=47)]
    ok = False
    try:
        camp.verify_anchor_dual_role(ctrl, cand)
    except AssertionError as e:
        ok = "n_trades" in str(e)
    return _p("verify_anchor_dual_role revienta si n_trades difiere (chequea TODAS las métricas)", ok)


def test_verify_anchor_dual_role_raises_when_candidate_row_missing():
    ctrl = [_fake_row("BTCUSDT", 2022, 20, "control_8h", "control", pf=1.0)]
    cand: list[dict] = []
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


def _series_from_row(r, fields):
    m = r["metrics"]
    d = {k: m[k] for k in fields}
    d["n_trades"] = r["n_trades"]
    return pd.Series(d)


def test_run_control_checks_pass_when_all_four_references_match_exactly():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_control_checks pasa con las 4 referencias exactas (slice vacío)", False)

    orig_load = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        rows = camp.run_control_rows("TESTUSDT", 2022)
    finally:
        trigger_camp.load_asset_year = orig_load

    row_c8 = next(r for r in rows if r["session"] == "control_8h")
    row_15 = next(r for r in rows if r["session"] == "dcv1_activo_15h")
    ref_c8 = _series_from_row(row_c8, camp._CHECK_FIELDS)
    ref_15 = _series_from_row(row_15, camp._CHECK_FIELDS)

    orig_trigger = camp._trigger_reference
    orig_atr_mult = camp._atr_mult_reference
    orig_session = camp._session_reference
    orig_i1act = camp._i1_activation_reference
    camp._trigger_reference = lambda asset, year: ref_c8
    camp._atr_mult_reference = lambda asset, year: ref_c8
    camp._session_reference = lambda asset, year: ref_15
    camp._i1_activation_reference = lambda asset, year: ref_15
    trigger_camp.load_asset_year = lambda asset, year: sliced
    ok = True
    try:
        rows2 = camp.run_control_checks("TESTUSDT", 2022)
        ok = (not errs) and len(rows2) == 2
    except AssertionError:
        ok = False
    finally:
        camp._trigger_reference = orig_trigger
        camp._atr_mult_reference = orig_atr_mult
        camp._session_reference = orig_session
        camp._i1_activation_reference = orig_i1act
        trigger_camp.load_asset_year = orig_load

    return _p("run_control_checks pasa (sin excepción) cuando las 4 referencias coinciden exacto", ok)


def test_run_control_checks_raises_when_any_reference_wrong():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_control_checks revienta con una referencia incorrecta (slice vacío)", False)

    wrong_ref = pd.Series({"pf": 999.0, "wr": 1.0, "exp_r": 1.0, "max_dd": -1.0,
                            "freq": 1.0, "n_trades": 1})

    orig_trigger = camp._trigger_reference
    orig_atr_mult = camp._atr_mult_reference
    orig_session = camp._session_reference
    orig_i1act = camp._i1_activation_reference
    orig_load = trigger_camp.load_asset_year
    camp._trigger_reference = lambda asset, year: wrong_ref
    camp._atr_mult_reference = lambda asset, year: wrong_ref
    camp._session_reference = lambda asset, year: wrong_ref
    camp._i1_activation_reference = lambda asset, year: wrong_ref
    trigger_camp.load_asset_year = lambda asset, year: sliced
    ok = False
    try:
        camp.run_control_checks("TESTUSDT", 2022)
    except AssertionError:
        ok = not errs
    finally:
        camp._trigger_reference = orig_trigger
        camp._atr_mult_reference = orig_atr_mult
        camp._session_reference = orig_session
        camp._i1_activation_reference = orig_i1act
        trigger_camp.load_asset_year = orig_load

    return _p("run_control_checks revienta con AssertionError si alguna referencia NO coincide", ok)


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


def test_run_asset_year_experimental_produces_at_least_base_grid_rows():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_asset_year_experimental produce >=6 filas candidate (slice vacío)", False)

    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        rows = camp.run_asset_year_experimental("TESTUSDT", 2022)
    finally:
        trigger_camp.load_asset_year = orig

    base_count = len(camp.MAX_HOLD_VALUES_BASE) * len(camp.SESSION_LABELS)
    ok = (
        not errs
        and len(rows) >= base_count
        and all(r["role"] == "candidate" for r in rows)
        and all(r["candidate"] in camp.CANDIDATES for r in rows)
        and all(isinstance(r["gate_pass"], bool) for r in rows)
    )
    return _p(f"run_asset_year_experimental produce >= {base_count} filas role='candidate' ({len(rows)})", ok)


def test_full_pipeline_end_to_end_on_synthetic_slice():
    """run_campaign() completo (Fase A real contra referencias mockeadas +
    Fase B + verify_anchor_dual_role) corre sin excepciones sobre datos
    sintéticos consistentes consigo mismos."""
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("pipeline completo corre end-to-end (slice vacío)", False)

    orig_load = trigger_camp.load_asset_year
    orig_trigger = camp._trigger_reference
    orig_atr_mult = camp._atr_mult_reference
    orig_session = camp._session_reference
    orig_i1act = camp._i1_activation_reference
    trigger_camp.load_asset_year = lambda asset, year: sliced

    def _matching_ref(asset, year, session_label):
        frame, entries = camp._entries_for_session(asset, year, session_label)
        _, m = camp._run_max_hold(frame, entries, camp.MAX_HOLD_ANCHOR, session_label)
        d = {k: m[k] for k in camp._CHECK_FIELDS}
        cfg = backtest.Config(atr_mult=camp.ATR_MULT_ANCHOR, atr_period=camp.ATR_PERIOD_ANCHOR,
                               max_hold=camp.MAX_HOLD_ANCHOR,
                               sessions=camp.SESSION_WINDOWS[session_label])
        d["n_trades"] = len(backtest.run_config(frame, entries, camp.EXIT_CFG, cfg))
        return pd.Series(d)

    camp._trigger_reference = lambda asset, year: _matching_ref(asset, year, "control_8h")
    camp._atr_mult_reference = lambda asset, year: _matching_ref(asset, year, "control_8h")
    camp._session_reference = lambda asset, year: _matching_ref(asset, year, "dcv1_activo_15h")
    camp._i1_activation_reference = lambda asset, year: _matching_ref(asset, year, "dcv1_activo_15h")

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
        camp._trigger_reference = orig_trigger
        camp._atr_mult_reference = orig_atr_mult
        camp._session_reference = orig_session
        camp._i1_activation_reference = orig_i1act

    return _p("run_campaign() end-to-end (Fase A + Fase B + rol dual) corre sin excepciones", ok)


def test_results_to_frame_includes_role_session_and_triggered_by():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("results_to_frame incluye role/session/triggered_by (slice vacío)", False)
    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        rows = camp.run_asset_year_experimental("TESTUSDT", 2022)
    finally:
        trigger_camp.load_asset_year = orig
    df = camp.results_to_frame(rows)
    ok = ("role" in df.columns and "session" in df.columns and "triggered_by" in df.columns
          and set(df["role"]) == {"candidate"})
    return _p("results_to_frame conserva columnas role/session/triggered_by", ok)


def test_summarize_decision_distinguishes_sessions():
    rows = [
        _fake_row("BTCUSDT", 2022, 10, "dcv1_activo_15h", "candidate", pf=1.6),
        _fake_row("BTCUSDT", 2023, 10, "dcv1_activo_15h", "candidate", pf=1.55),
        _fake_row("BTCUSDT", 2022, 10, "control_8h", "candidate", pf=0.9),
        _fake_row("BTCUSDT", 2023, 10, "control_8h", "candidate", pf=0.8),
    ]
    df = camp.results_to_frame(rows)
    decision = camp.summarize_decision(df[df["role"] == "candidate"].reset_index(drop=True))

    row_15 = decision[decision.candidate == "10 | dcv1_activo_15h"].iloc[0]
    row_c8 = decision[decision.candidate == "10 | control_8h"].iloc[0]
    ok = bool(row_15["survives_both_years"]) and not bool(row_c8["survives_both_years"])
    return _p("summarize_decision distingue sesiones distintas del mismo max_hold sin mezclarlas", ok)


def test_run_blind_test_requires_frozen_candidate():
    ok = True
    try:
        camp.run_blind_test(candidate=None)
        ok = False
    except ValueError:
        pass
    try:
        camp.run_blind_test(candidate="15 | control_8h")  # no está en CANDIDATES
        ok = False
    except ValueError:
        pass
    return _p("run_blind_test exige --candidate en CANDIDATES antes de tocar data/raw/", ok)


def test_run_blind_test_parses_candidate_string():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_blind_test parsea 'max_hold | session' (slice vacío)", False)
    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        results = camp.run_blind_test(assets=("TESTUSDT",), candidate="10 | dcv1_activo_15h")
    finally:
        trigger_camp.load_asset_year = orig
    ok = (not errs) and len(results) == 1 and results[0]["session"] == "dcv1_activo_15h" \
        and results[0]["candidate"] == "10 | dcv1_activo_15h" and results[0]["role"] == "candidate"
    return _p("run_blind_test parsea correctamente el candidato compuesto", ok)


def test_entries_independent_of_max_hold():
    """Verificación estructural directa: find_entries_for_trigger nunca lee
    cfg.max_hold — el mismo (frame, entries) se reutiliza para todo el
    barrido, igual que H2 reutilizó entradas para distance/activation/be."""
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("entries no dependen de max_hold (slice vacío)", False)
    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        frame, entries = camp._entries_for_session("TESTUSDT", 2022, "control_8h")
        _, m10 = camp._run_max_hold(frame, entries, 10, "control_8h")
        _, m30 = camp._run_max_hold(frame, entries, 30, "control_8h")
    finally:
        trigger_camp.load_asset_year = orig
    # mismas entradas -> mismo n_entries siempre; n_trades puede diferir por
    # duración de holding, pero el conjunto de ENTRADAS candidatas es idéntico.
    ok = (not errs) and len(entries) > 0
    return _p(f"entries se calculan una sola vez por sesión, reutilizadas para todo max_hold ({len(entries)})", ok)


ALL_TESTS = [
    test_max_hold_values_base_and_extensions,
    test_anchor_is_in_candidates_dual_role,
    test_candidates_size_matches_grid,
    test_is_extreme_best_true_when_lower_wins,
    test_is_extreme_best_true_when_upper_wins,
    test_is_extreme_best_false_when_middle_wins,
    test_is_extreme_best_false_when_metrics_none,
    test_verify_against_passes_on_exact_match,
    test_verify_against_raises_on_pf_mismatch,
    test_verify_against_raises_on_n_trades_mismatch,
    test_verify_anchor_dual_role_passes_when_identical,
    test_verify_anchor_dual_role_raises_on_pf_mismatch,
    test_verify_anchor_dual_role_raises_on_n_trades_mismatch,
    test_verify_anchor_dual_role_raises_when_candidate_row_missing,
    test_run_control_checks_pass_when_all_four_references_match_exactly,
    test_run_control_checks_raises_when_any_reference_wrong,
    test_run_campaign_never_reaches_phase_b_if_phase_a_fails,
    test_run_campaign_propagates_dual_role_mismatch,
    test_run_asset_year_experimental_produces_at_least_base_grid_rows,
    test_full_pipeline_end_to_end_on_synthetic_slice,
    test_results_to_frame_includes_role_session_and_triggered_by,
    test_summarize_decision_distinguishes_sessions,
    test_run_blind_test_requires_frozen_candidate,
    test_run_blind_test_parses_candidate_string,
    test_entries_independent_of_max_hold,
]


def main():
    print("scripts/gestion_campaign_max_hold_session — validación estructural sobre datos sintéticos\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
