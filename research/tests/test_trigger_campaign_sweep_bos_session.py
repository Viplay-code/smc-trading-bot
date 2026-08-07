"""
research/tests/test_trigger_campaign_sweep_bos_session.py — Validación
ESTRUCTURAL de scripts/trigger_campaign_sweep_bos_session.py (Espacio 3).

No sustituye la corrida real (bloqueada en este sandbox, HTTP 451,
data/raw/ vacío) — prueba: (1) la lógica de comparación NaN-consciente que
sostiene la Fase A, (2) que las DOS referencias históricas ya publicadas
(trigger_campaign_results.csv / entry_campaign_sweep_bos_results.csv) siguen
coincidiendo entre sí sobre datos reales — no un supuesto sin comprobar sino
una regresión sobre el hecho ya verificado antes de escribir el contrato,
(3) que Fase A efectivamente bloquea un mismatch (sintético vs referencia
real), (4) que la Fase B corre end-to-end sobre datos sintéticos, y (5) el
resto del pipeline (results_to_frame/summarize_decision/run_blind_test
guardrail). Ejecutar:
    python -m research.tests.test_trigger_campaign_sweep_bos_session  (o con pytest)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from dc_v1 import build_dc_v1, validate_dc_v1
from periods import period_slice
from versions import PIPELINE_VERSION, DATASET_VERSION

Path("smc_bot.log").unlink(missing_ok=True)

sys.path.insert(0, ".")
import scripts.trigger_campaign as trigger_camp
import scripts.trigger_campaign_sweep_bos_session as camp


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def make_synthetic_raw_1h(start="2021-10-01", n=8000, seed=11) -> pd.DataFrame:
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
# _eq_or_both_nan — base de toda comparación de Fase A                        #
# --------------------------------------------------------------------------- #
def test_eq_or_both_nan_true_when_both_nan():
    ok = camp._eq_or_both_nan(float("nan"), float("nan")) is True
    return _p("_eq_or_both_nan True cuando ambos son NaN", ok)


def test_eq_or_both_nan_true_when_both_none():
    ok = camp._eq_or_both_nan(None, None) is True
    return _p("_eq_or_both_nan True cuando ambos son None", ok)


def test_eq_or_both_nan_false_when_only_one_nan():
    ok = (camp._eq_or_both_nan(float("nan"), 1.5) is False
          and camp._eq_or_both_nan(1.5, float("nan")) is False)
    return _p("_eq_or_both_nan False si solo uno es NaN (no enmascara mismatches reales)", ok)


def test_eq_or_both_nan_true_when_equal_numbers():
    ok = camp._eq_or_both_nan(1.234, 1.234) is True
    return _p("_eq_or_both_nan True si los números son iguales", ok)


def test_eq_or_both_nan_false_when_different_numbers():
    ok = camp._eq_or_both_nan(1.234, 1.235) is False
    return _p("_eq_or_both_nan False si los números difieren", ok)


# --------------------------------------------------------------------------- #
# Las dos referencias históricas siguen coincidiendo entre sí (regresión      #
# sobre datos reales ya publicados, no un supuesto sin comprobar)             #
# --------------------------------------------------------------------------- #
def test_historical_references_still_agree_with_each_other():
    mismatches = []
    checked = 0
    for asset in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        for year in (2022, 2023):
            ref_t = camp._trigger_reference(asset, year)
            ref_e = camp._entry_reference(asset, year)
            checked += 1
            for field in ("n_entries", "n_trades", *camp._CHECK_FIELDS):
                if not camp._eq_or_both_nan(ref_t[field], ref_e[field]):
                    mismatches.append((asset, year, field, ref_t[field], ref_e[field]))
    ok = checked == 6 and not mismatches
    return _p(f"trigger_campaign_results.csv y entry_campaign_sweep_bos_results.csv "
              f"siguen coincidiendo en los 6 combos ({checked} verificados, "
              f"{len(mismatches)} mismatches: {mismatches})", ok)


# --------------------------------------------------------------------------- #
# _verify_against — bloquea mismatch, acepta coincidencia exacta              #
# --------------------------------------------------------------------------- #
def _fake_ref_row(**kw) -> pd.Series:
    base = {"n_entries": 10, "n_trades": 10, "pf": 1.2, "wr": 30.0,
            "exp_r": 0.05, "max_dd": -3.0, "freq": 5.0}
    base.update(kw)
    return pd.Series(base)


def test_verify_against_raises_on_mismatch():
    ref = _fake_ref_row()
    m = {"pf": 1.5, "wr": 30.0, "exp_r": 0.05, "max_dd": -3.0, "freq": 5.0}  # pf distinto
    ok = True
    try:
        camp._verify_against(10, 10, m, ref, "contexto de prueba")
        ok = False
    except AssertionError as e:
        ok = "pf" in str(e)
    return _p("_verify_against revienta con AssertionError si algún campo no coincide", ok)


def test_verify_against_passes_on_exact_match_including_nan():
    ref = _fake_ref_row(pf=float("nan"), wr=float("nan"), exp_r=float("nan"),
                         max_dd=float("nan"), freq=float("nan"), n_entries=4, n_trades=4)
    ok = True
    try:
        camp._verify_against(4, 4, None, ref, "contexto de prueba")
    except AssertionError:
        ok = False
    return _p("_verify_against NO revienta si actual=None (metrics NaN) coincide con "
              "referencia NaN — mismo patrón que las filas de 2023 reales", ok)


def test_verify_against_raises_on_n_trades_mismatch_even_if_metrics_both_nan():
    ref = _fake_ref_row(pf=float("nan"), wr=float("nan"), exp_r=float("nan"),
                         max_dd=float("nan"), freq=float("nan"), n_entries=4, n_trades=4)
    ok = True
    try:
        camp._verify_against(2, 2, None, ref, "contexto de prueba")  # n_entries/n_trades distintos
        ok = False
    except AssertionError as e:
        ok = "n_entries" in str(e) or "n_trades" in str(e)
    return _p("_verify_against SÍ revienta si n_entries/n_trades difieren, aun con métricas "
              "NaN en ambos lados — el NaN-aware equality no exime de verificar conteos crudos", ok)


# --------------------------------------------------------------------------- #
# Fase A end-to-end: datos sintéticos vs referencia REAL debe fallar          #
# (prueba que la verificación bloquea de verdad, no solo en el papel)        #
# --------------------------------------------------------------------------- #
def test_run_control_checks_raises_on_synthetic_vs_real_reference():
    sliced = _build_frame_and_sliced()
    if sliced.empty:
        return _p("run_control_checks bloquea mismatch sintético vs referencia real (slice vacío)", False)

    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    ok = True
    try:
        try:
            camp.run_control_checks("BTCUSDT", 2022)
            ok = False  # no debería llegar acá: datos sintéticos no reproducen la referencia real
        except AssertionError:
            pass
    finally:
        trigger_camp.load_asset_year = orig
    return _p("run_control_checks revienta con AssertionError cuando los datos sintéticos "
              "no reproducen trigger_campaign_results.csv/entry_campaign_sweep_bos_results.csv "
              "(la Fase A bloquea de verdad, no solo estructuralmente)", ok)


# --------------------------------------------------------------------------- #
# Fase B end-to-end sobre datos sintéticos (no depende de las referencias)    #
# --------------------------------------------------------------------------- #
def _build_frame_and_sliced():
    raw = make_synthetic_raw_1h()
    df_full = build_dc_v1(raw, asset="TESTUSDT", dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)
    if errs:
        return pd.DataFrame()
    import scripts.bias_campaign as bias_camp
    df4h_full = bias_camp.resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, camp.BIAS_CANDIDATE)
    return period_slice(df_full, 2022)


def test_run_asset_year_experimental_end_to_end_on_synthetic_slice():
    sliced = _build_frame_and_sliced()
    if sliced.empty:
        return _p("run_asset_year_experimental corre end-to-end (slice 2022 vacío)", False)

    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        row = camp.run_asset_year_experimental("TESTUSDT", 2022)
    finally:
        trigger_camp.load_asset_year = orig

    ok = (
        row["role"] == "candidate"
        and row["session"] == "dcv1_activo_15h"
        and row["candidate"] == "dcv1_activo_15h"
        and isinstance(row["gate_pass"], bool)
    )
    return _p(f"run_asset_year_experimental corre sin excepciones y produce una fila "
              f"candidate/dcv1_activo_15h válida (n_entries={row['n_entries']})", ok)


# --------------------------------------------------------------------------- #
# Candidatos / guardrail de --blind                                          #
# --------------------------------------------------------------------------- #
def test_candidates_single_level_dcv1_only():
    ok = camp.CANDIDATES == ("dcv1_activo_15h",) and "control_8h" not in camp.CANDIDATES
    return _p("CANDIDATES contiene únicamente 'dcv1_activo_15h' — control_8h nunca es candidato", ok)


def test_run_blind_test_requires_frozen_candidate():
    ok = True
    try:
        camp.run_blind_test(candidate=None)
        ok = False
    except ValueError:
        pass
    try:
        camp.run_blind_test(candidate="control_8h")  # no es un candidato válido
        ok = False
    except ValueError:
        pass
    return _p("run_blind_test exige --candidate == 'dcv1_activo_15h' antes de tocar data/raw/", ok)


# --------------------------------------------------------------------------- #
# results_to_frame / summarize_decision                                      #
# --------------------------------------------------------------------------- #
def _fake_result(asset, year, role, n_entries, n_trades, m, gate_pass=False):
    return {
        "asset": asset, "year": year, "role": role, "session": "dcv1_activo_15h",
        "candidate": "dcv1_activo_15h", "exit_config": camp.EXIT_CONFIG_LABEL,
        "n_entries": n_entries, "n_trades": n_trades, "metrics": m, "gate_pass": gate_pass,
    }


def test_results_to_frame_exports_metrics_computable_and_avg_win_avg_loss():
    m_ok = {"pf": 1.6, "wr": 40.0, "exp_r": 0.1, "avg_win": 0.9, "avg_loss": -0.4,
            "total_r": 5.0, "max_dd": -3.0, "freq": 7.0, "be": 0,
            "reasons": {"stop": 8, "timeout": 2}}
    r_computable = _fake_result("BTCUSDT", 2022, "candidate", 12, 10, m_ok, gate_pass=True)
    r_not_computable = _fake_result("ETHUSDT", 2022, "candidate", 3, 3, None, gate_pass=False)
    df = camp.results_to_frame([r_computable, r_not_computable])

    row_ok = df[df["asset"] == "BTCUSDT"].iloc[0]
    row_none = df[df["asset"] == "ETHUSDT"].iloc[0]
    ok = (
        row_ok["metrics_computable"] == True and row_ok["avg_win"] == 0.9 and row_ok["avg_loss"] == -0.4
        and row_none["metrics_computable"] == False and pd.isna(row_none["pf"])
    )
    return _p("results_to_frame distingue metrics_computable=True/False y exporta "
              "avg_win/avg_loss sin transformarlos", ok)


def test_summarize_decision_compatible_with_single_candidate():
    m1 = {"pf": 1.6, "wr": 40.0, "exp_r": 0.1, "avg_win": 0.9, "avg_loss": -0.4,
          "total_r": 5.0, "max_dd": -3.0, "freq": 7.0, "be": 0, "reasons": {}}
    m2 = {"pf": 1.55, "wr": 38.0, "exp_r": 0.09, "avg_win": 0.85, "avg_loss": -0.42,
          "total_r": 4.8, "max_dd": -3.5, "freq": 6.5, "be": 0, "reasons": {}}
    results = [
        _fake_result("BTCUSDT", 2022, "candidate", 20, 18, m1, gate_pass=True),
        _fake_result("BTCUSDT", 2023, "candidate", 20, 18, m2, gate_pass=True),
    ]
    df = camp.results_to_frame(results)
    decision = camp.summarize_decision(df)
    row = decision[(decision.asset == "BTCUSDT") & (decision.candidate == "dcv1_activo_15h")].iloc[0]
    ok = bool(row["survives_both_years"]) and row["rank_within_asset"] == 1
    return _p("summarize_decision funciona sin modificarse con un único valor de candidate "
              "('dcv1_activo_15h')", ok)


ALL_TESTS = [
    test_eq_or_both_nan_true_when_both_nan,
    test_eq_or_both_nan_true_when_both_none,
    test_eq_or_both_nan_false_when_only_one_nan,
    test_eq_or_both_nan_true_when_equal_numbers,
    test_eq_or_both_nan_false_when_different_numbers,
    test_historical_references_still_agree_with_each_other,
    test_verify_against_raises_on_mismatch,
    test_verify_against_passes_on_exact_match_including_nan,
    test_verify_against_raises_on_n_trades_mismatch_even_if_metrics_both_nan,
    test_run_control_checks_raises_on_synthetic_vs_real_reference,
    test_run_asset_year_experimental_end_to_end_on_synthetic_slice,
    test_candidates_single_level_dcv1_only,
    test_run_blind_test_requires_frozen_candidate,
    test_results_to_frame_exports_metrics_computable_and_avg_win_avg_loss,
    test_summarize_decision_compatible_with_single_candidate,
]


def main():
    print("scripts/trigger_campaign_sweep_bos_session — validación estructural (Espacio 3)\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
