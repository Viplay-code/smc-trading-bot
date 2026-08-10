"""
research/tests/test_bias_campaign_session.py — Validación ESTRUCTURAL de
scripts/bias_campaign_session.py sobre datos sintéticos.

No sustituye la corrida real (bloqueada en este sandbox, HTTP 451,
data/raw/ vacío) ni la verificación real contra los 4 CSV históricos
(trigger_campaign_results.csv, bias_campaign_results.csv,
gestion_campaign_session_results.csv, integration_campaign_activation_
results.csv) — prueba que _verify_against detecta coincidencias/mismatches
con mensajes detallados (celda/activo/año/referencia/campo), que
run_integrity_checks/run_campaign respetan el orden Fase A -> Fase B, que
compute_deltas/assess_level2_consistency calculan ΔPF/ΔΔPF correctamente
sobre datos controlados, y que el pipeline completo corre sin excepciones
sobre datos sintéticos.
Ejecutar:
    python -m research.tests.test_bias_campaign_session  (o con pytest)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from dc_v1 import build_dc_v1, validate_dc_v1
from periods import period_slice
from versions import PIPELINE_VERSION, DATASET_VERSION

sys.path.insert(0, ".")
import scripts.bias_campaign as bias_camp
import scripts.bias_campaign_session as camp

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
# Estructura del diseño factorial 2x2                                        #
# --------------------------------------------------------------------------- #
def test_candidates_is_2x2_factorial():
    ok = camp.CANDIDATES == ("A | control_8h", "A | dcv1_activo_15h",
                              "A2 | control_8h", "A2 | dcv1_activo_15h")
    return _p(f"CANDIDATES es el factorial 2x2 completo (bias x sesión) ({camp.CANDIDATES})", ok)


def test_exit_cfg_is_v3a_only():
    ok = camp.EXIT_CFG == {"be": 1.0, "activation": 2.0, "distance": 1.0}
    return _p("EXIT_CFG es V3-A única (be=1.0/activation=2.0/distance=1.0), sin V3-B", ok)


# --------------------------------------------------------------------------- #
# _verify_against — mensaje detallado (celda/activo/año/referencia/campo)    #
# --------------------------------------------------------------------------- #
def _ref_row(**overrides):
    base = {"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 5.0,
            "n_entries": 50, "n_trades": 48}
    base.update(overrides)
    return pd.Series(base)


def test_verify_against_passes_on_exact_match():
    m = {"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 5.0}
    ok = True
    try:
        camp._verify_against("A|control_8h", "BTCUSDT", 2022, "ref.csv", 50, 48, m, _ref_row())
    except AssertionError:
        ok = False
    return _p("_verify_against no revienta cuando todos los campos coinciden exacto", ok)


def test_verify_against_raises_with_detailed_message():
    m = {"pf": 1.05, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 5.0}
    ok = False
    try:
        camp._verify_against("A|control_8h", "BTCUSDT", 2022, "trigger_campaign_results.csv",
                              50, 48, m, _ref_row())
    except AssertionError as e:
        msg = str(e)
        ok = ("celda=A|control_8h" in msg and "activo=BTCUSDT" in msg and "año=2022" in msg
              and "referencia=trigger_campaign_results.csv" in msg
              and "pf:" in msg and "esperado=" in msg and "obtenido=1.05" in msg)
    return _p("_verify_against revienta con mensaje detallado: celda/activo/año/referencia/campo", ok)


def test_verify_against_raises_on_n_entries_mismatch():
    m = {"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 5.0}
    ok = False
    try:
        camp._verify_against("A2|control_8h", "ETHUSDT", 2023, "bias_campaign_results.csv",
                              49, 48, m, _ref_row())
    except AssertionError as e:
        msg = str(e)
        ok = "n_entries:" in msg and "esperado=" in msg and "obtenido=49" in msg
    return _p("_verify_against revienta si n_entries difiere, con esperado/obtenido explícitos", ok)


def test_verify_against_reports_multiple_mismatches():
    m = {"pf": 2.0, "wr": 30.0, "exp_r": -0.05, "max_dd": -5.0, "freq": 5.0}
    ok = False
    try:
        camp._verify_against("A|dcv1_activo_15h", "SOLUSDT", 2022, "ref.csv", 50, 48, m, _ref_row())
    except AssertionError as e:
        msg = str(e)
        ok = "pf:" in msg and "exp_r:" in msg
    return _p("_verify_against reporta TODOS los campos divergentes, no solo el primero", ok)


# --------------------------------------------------------------------------- #
# compute_deltas / assess_level2_consistency — matemática sobre datos        #
# controlados (sin necesidad de simular backtest)                            #
# --------------------------------------------------------------------------- #
def _fake_results_row(asset, year, bias, session, pf, freq=8.0):
    return {
        "asset": asset, "year": year, "bias": bias, "session": session,
        "candidate": camp._label(bias, session), "exit_config": camp.EXIT_CONFIG_LABEL,
        "n_entries": 50, "n_trades": 48,
        "entries_per_month": 4.0, "fill_rate": 0.96,
        "gate_pass": False,
        "pf": pf, "wr": 30.0, "exp_r": 0.05, "avg_win": 1.0, "avg_loss": -0.5,
        "total_r": 1.0, "max_dd": -5.0, "freq": freq, "be": 0,
        "reason_stop": 40, "reason_timeout": 8,
    }


def test_compute_deltas_arithmetic():
    rows = [
        _fake_results_row("BTCUSDT", 2022, "A", "control_8h", pf=1.00, freq=5.0),
        _fake_results_row("BTCUSDT", 2022, "A2", "control_8h", pf=1.08, freq=5.2),
        _fake_results_row("BTCUSDT", 2022, "A", "dcv1_activo_15h", pf=1.00, freq=9.0),
        _fake_results_row("BTCUSDT", 2022, "A2", "dcv1_activo_15h", pf=1.30, freq=9.5),
    ]
    df = pd.DataFrame(rows)
    deltas = camp.compute_deltas(df)
    row = deltas.iloc[0]
    ok = (
        abs(row["delta_pf_control"] - 0.08) < 1e-9
        and abs(row["delta_pf_dcv1"] - 0.30) < 1e-9
        and abs(row["delta_delta_pf"] - 0.22) < 1e-9
        and abs(row["delta_freq_control"] - 0.2) < 1e-9
        and abs(row["delta_freq_dcv1"] - 0.5) < 1e-9
        and abs(row["delta_delta_freq"] - 0.3) < 1e-9
    )
    return _p(f"compute_deltas: ΔPF_control=0.08, ΔPF_dcv1=0.30, ΔΔPF=0.22 ({row.to_dict()})", ok)


def test_assess_level2_consistency_detects_consistent_direction():
    rows = []
    for year, pf_a, pf_a2 in [(2022, 1.00, 1.10), (2023, 0.90, 1.05)]:
        rows.append(_fake_results_row("BTCUSDT", year, "A", "control_8h", pf=pf_a))
        rows.append(_fake_results_row("BTCUSDT", year, "A2", "control_8h", pf=pf_a2))
        rows.append(_fake_results_row("BTCUSDT", year, "A", "dcv1_activo_15h", pf=pf_a))
        rows.append(_fake_results_row("BTCUSDT", year, "A2", "dcv1_activo_15h", pf=pf_a2))
    df = pd.DataFrame(rows)
    deltas = camp.compute_deltas(df)
    level2 = camp.assess_level2_consistency(deltas)
    ok = level2["delta_pf_control"]["por_activo"]["BTCUSDT"] is True
    return _p("assess_level2_consistency detecta dirección consistente (ΔPF>0 ambos años)", ok)


def test_assess_level2_consistency_detects_sign_flip():
    rows = []
    for year, pf_a, pf_a2 in [(2022, 1.00, 1.10), (2023, 1.00, 0.90)]:
        rows.append(_fake_results_row("ETHUSDT", year, "A", "control_8h", pf=pf_a))
        rows.append(_fake_results_row("ETHUSDT", year, "A2", "control_8h", pf=pf_a2))
        rows.append(_fake_results_row("ETHUSDT", year, "A", "dcv1_activo_15h", pf=pf_a))
        rows.append(_fake_results_row("ETHUSDT", year, "A2", "dcv1_activo_15h", pf=pf_a2))
    df = pd.DataFrame(rows)
    deltas = camp.compute_deltas(df)
    level2 = camp.assess_level2_consistency(deltas)
    ok = level2["delta_pf_control"]["por_activo"]["ETHUSDT"] is False
    return _p("assess_level2_consistency detecta cambio de signo entre años (no consistente)", ok)


def test_assess_level2_no_magnitude_gate():
    """Nivel 2 no debe aplicar ningún umbral de magnitud — un delta minúsculo
    pero de signo estable debe marcarse igual de 'consistente' que uno
    grande; la distinción de magnitud queda fuera de esta función."""
    rows = []
    for year in (2022, 2023):
        rows.append(_fake_results_row("SOLUSDT", year, "A", "control_8h", pf=1.000))
        rows.append(_fake_results_row("SOLUSDT", year, "A2", "control_8h", pf=1.001))
        rows.append(_fake_results_row("SOLUSDT", year, "A", "dcv1_activo_15h", pf=1.000))
        rows.append(_fake_results_row("SOLUSDT", year, "A2", "dcv1_activo_15h", pf=1.001))
    df = pd.DataFrame(rows)
    deltas = camp.compute_deltas(df)
    level2 = camp.assess_level2_consistency(deltas)
    ok = level2["delta_pf_control"]["por_activo"]["SOLUSDT"] is True
    return _p("assess_level2_consistency marca consistente un delta mínimo (0.001) — sin gate de magnitud", ok)


def test_summarize_decision_treats_all_four_cells_as_candidates():
    rows = []
    for year in (2022, 2023):
        for bias in ("A", "A2"):
            for session in ("control_8h", "dcv1_activo_15h"):
                rows.append(_fake_results_row("BTCUSDT", year, bias, session, pf=1.0))
    df = pd.DataFrame(rows)
    decision = camp.summarize_decision(df)
    ok = len(decision) == 4 and set(decision["candidate"]) == set(camp.CANDIDATES)
    return _p("summarize_decision evalúa las 4 celdas (A|control_8h, A|dcv1, A2|control_8h, A2|dcv1)", ok)


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
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, "A")
    df_full["bias_A2"] = bias_camp.apply_bias(df_full, df4h_full, "A2")
    sliced = period_slice(df_full, 2022)
    return sliced, errs


def _series_from_row(r, fields):
    m = r["metrics"]
    d = {k: m[k] for k in fields}
    d["n_entries"] = r["n_entries"]
    d["n_trades"] = r["n_trades"]
    return pd.Series(d)


def test_run_integrity_checks_pass_when_all_five_references_match_exactly():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_integrity_checks pasa con las 5 referencias exactas (slice vacío)", False)

    orig_load = bias_camp.load_asset_year
    bias_camp.load_asset_year = lambda asset, year: sliced

    # Construir las referencias directamente vía _run_cell (NO vía
    # run_integrity_checks, que ya exige verificación — acá todavía no hay
    # nada mockeado).
    entries_a_c8, trades_a_c8, m_a_c8 = camp._run_cell(sliced, "A", "control_8h")
    entries_a_15, trades_a_15, m_a_15 = camp._run_cell(sliced, "A", "dcv1_activo_15h")
    entries_a2_c8, trades_a2_c8, m_a2_c8 = camp._run_cell(sliced, "A2", "control_8h")
    ref_a_c8 = pd.Series({**{k: m_a_c8[k] for k in camp._CHECK_FIELDS},
                           "n_entries": len(entries_a_c8), "n_trades": len(trades_a_c8)})
    ref_a_15 = pd.Series({**{k: m_a_15[k] for k in camp._CHECK_FIELDS},
                           "n_entries": len(entries_a_15), "n_trades": len(trades_a_15)})
    ref_a2_c8 = pd.Series({**{k: m_a2_c8[k] for k in camp._CHECK_FIELDS},
                            "n_entries": len(entries_a2_c8), "n_trades": len(trades_a2_c8)})

    orig_trigger = camp._trigger_reference
    orig_bias = camp._bias_reference
    orig_session = camp._session_reference
    orig_i1act = camp._i1_activation_reference
    camp._trigger_reference = lambda asset, year: ref_a_c8
    camp._bias_reference = lambda asset, year, bias: ref_a_c8 if bias == "A" else ref_a2_c8
    camp._session_reference = lambda asset, year: ref_a_15
    camp._i1_activation_reference = lambda asset, year: ref_a_15
    ok = True
    try:
        known2 = camp.run_integrity_checks("TESTUSDT", 2022)
        ok = (not errs) and len(known2) == 4  # 3 celdas + _df_full
    except AssertionError as e:
        ok = False
        print(f"    (excepción inesperada: {e})")
    finally:
        camp._trigger_reference = orig_trigger
        camp._bias_reference = orig_bias
        camp._session_reference = orig_session
        camp._i1_activation_reference = orig_i1act
        bias_camp.load_asset_year = orig_load

    return _p("run_integrity_checks pasa (sin excepción) cuando las 5 referencias coinciden exacto", ok)


def test_run_integrity_checks_raises_when_reference_wrong():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_integrity_checks revienta con referencia incorrecta (slice vacío)", False)

    wrong_ref = pd.Series({"pf": 999.0, "wr": 1.0, "exp_r": 1.0, "max_dd": -1.0,
                            "freq": 1.0, "n_entries": 1, "n_trades": 1})

    orig_load = bias_camp.load_asset_year
    orig_trigger = camp._trigger_reference
    orig_bias = camp._bias_reference
    bias_camp.load_asset_year = lambda asset, year: sliced
    camp._trigger_reference = lambda asset, year: wrong_ref
    camp._bias_reference = lambda asset, year, bias: wrong_ref
    ok = False
    try:
        camp.run_integrity_checks("TESTUSDT", 2022)
    except AssertionError as e:
        ok = (not errs) and "celda=A|control_8h" in str(e)
    finally:
        camp._trigger_reference = orig_trigger
        camp._bias_reference = orig_bias
        bias_camp.load_asset_year = orig_load

    return _p("run_integrity_checks revienta con AssertionError detallado si una referencia NO coincide", ok)


def test_run_campaign_never_computes_new_cell_if_phase_a_fails():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_campaign nunca calcula la celda nueva si Fase A falla (slice vacío)", False)

    def _boom(df_full, asset, year):
        raise RuntimeError("Fase B (celda nueva) NO debería haberse invocado — Fase A ya había fallado")

    orig_checks = camp.run_integrity_checks
    orig_new = camp.run_new_cell
    camp.run_integrity_checks = lambda asset, year: (_ for _ in ()).throw(AssertionError("Fase A simulada: falla"))
    camp.run_new_cell = _boom
    ok = False
    try:
        camp.run_campaign(assets=("TESTUSDT",), years=(2022,))
    except AssertionError:
        ok = True
    except RuntimeError:
        ok = False
    finally:
        camp.run_integrity_checks = orig_checks
        camp.run_new_cell = orig_new

    return _p("run_campaign() propaga la falla de Fase A sin invocar run_new_cell", ok)


def test_full_pipeline_end_to_end_on_synthetic_slice():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("pipeline completo corre end-to-end (slice vacío)", False)

    orig_load = bias_camp.load_asset_year
    orig_trigger = camp._trigger_reference
    orig_bias = camp._bias_reference
    orig_session = camp._session_reference
    orig_i1act = camp._i1_activation_reference
    bias_camp.load_asset_year = lambda asset, year: sliced

    def _matching_ref(asset, year, bias, session_label):
        entries, trades, m = camp._run_cell(sliced, bias, session_label)
        d = {k: m[k] for k in camp._CHECK_FIELDS}
        d["n_entries"] = len(entries)
        d["n_trades"] = len(trades)
        return pd.Series(d)

    camp._trigger_reference = lambda asset, year: _matching_ref(asset, year, "A", "control_8h")
    camp._bias_reference = lambda asset, year, bias: _matching_ref(asset, year, bias, "control_8h")
    camp._session_reference = lambda asset, year: _matching_ref(asset, year, "A", "dcv1_activo_15h")
    camp._i1_activation_reference = lambda asset, year: _matching_ref(asset, year, "A", "dcv1_activo_15h")

    ok = True
    try:
        results = camp.run_campaign(assets=("TESTUSDT",), years=(2022,))
        df = camp.results_to_frame(results)
        deltas = camp.compute_deltas(df)
        level2 = camp.assess_level2_consistency(deltas)
        decision = camp.summarize_decision(df)
        ok = ((not errs) and len(results) == 4 and set(df["candidate"]) == set(camp.CANDIDATES)
              and len(deltas) == 1 and len(decision) == 4 and "delta_pf_control" in level2)
    except AssertionError as e:
        ok = False
        print(f"    (excepción inesperada: {e})")
    finally:
        bias_camp.load_asset_year = orig_load
        camp._trigger_reference = orig_trigger
        camp._bias_reference = orig_bias
        camp._session_reference = orig_session
        camp._i1_activation_reference = orig_i1act

    return _p("pipeline completo (Fase A + Fase B + deltas + decision) corre sin excepciones", ok)


def test_run_blind_test_requires_frozen_candidate():
    ok = True
    try:
        camp.run_blind_test(candidate=None)
        ok = False
    except ValueError:
        pass
    try:
        camp.run_blind_test(candidate="B | control_8h")  # no está en CANDIDATES
        ok = False
    except ValueError:
        pass
    return _p("run_blind_test exige --candidate en CANDIDATES antes de tocar data/raw/", ok)


def test_run_blind_test_parses_candidate_string():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_blind_test parsea 'bias | session' (slice vacío)", False)
    orig = bias_camp.load_asset_year
    bias_camp.load_asset_year = lambda asset, year: sliced
    try:
        results = camp.run_blind_test(assets=("TESTUSDT",), candidate="A2 | dcv1_activo_15h")
    finally:
        bias_camp.load_asset_year = orig
    ok = (not errs) and len(results) == 1 and results[0]["bias"] == "A2" \
        and results[0]["session"] == "dcv1_activo_15h" \
        and results[0]["candidate"] == "A2 | dcv1_activo_15h"
    return _p("run_blind_test parsea correctamente el candidato compuesto", ok)


ALL_TESTS = [
    test_candidates_is_2x2_factorial,
    test_exit_cfg_is_v3a_only,
    test_verify_against_passes_on_exact_match,
    test_verify_against_raises_with_detailed_message,
    test_verify_against_raises_on_n_entries_mismatch,
    test_verify_against_reports_multiple_mismatches,
    test_compute_deltas_arithmetic,
    test_assess_level2_consistency_detects_consistent_direction,
    test_assess_level2_consistency_detects_sign_flip,
    test_assess_level2_no_magnitude_gate,
    test_summarize_decision_treats_all_four_cells_as_candidates,
    test_run_integrity_checks_pass_when_all_five_references_match_exactly,
    test_run_integrity_checks_raises_when_reference_wrong,
    test_run_campaign_never_computes_new_cell_if_phase_a_fails,
    test_full_pipeline_end_to_end_on_synthetic_slice,
    test_run_blind_test_requires_frozen_candidate,
    test_run_blind_test_parses_candidate_string,
]


def main():
    print("scripts/bias_campaign_session — validación estructural sobre datos sintéticos\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
