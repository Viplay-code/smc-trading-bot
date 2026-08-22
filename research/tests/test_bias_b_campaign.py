"""
research/tests/test_bias_b_campaign.py — Validación de
scripts/bias_b_campaign.py.

Dos categorías de test:
  1. ESTRUCTURAL sobre datos sintéticos (no sustituye la corrida real,
     bloqueada en este sandbox, HTTP 451, data/raw/ vacío).
  2. REAL sobre gestion_campaign_session_results.csv (ya committeado, no
     requiere data/raw/) — la referencia de Fase A (Bias A bajo
     T1_ema_cross/C_market_close/dcv1_activo_15h/V3-A) se prueba contra el
     valor real publicado, no mockeado.

Ejecutar:
    python -m research.tests.test_bias_b_campaign  (o con pytest)
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
from market_data import ASSETS

sys.path.insert(0, ".")
import scripts.bias_campaign as bias_camp
import scripts.bias_b_campaign as camp

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


def _build_sliced_for(seed, year=2022, start="2021-10-01"):
    """Réplica de camp.load_asset_year sin tocar data/raw/ — misma
    disciplina P-3 (bias_A/bias_B calculados sobre el frame COMPLETO, recién
    entonces se corta)."""
    raw = make_synthetic_raw_1h(start=start, seed=seed)
    df_full = build_dc_v1(raw, asset="TESTUSDT", dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)
    df4h_full = bias_camp.resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, camp.BIAS_COMPARATOR)
    df_full["bias_B"] = bias_camp.apply_bias(df_full, df4h_full, camp.BIAS_TARGET)
    sliced = period_slice(df_full, year)
    return sliced, errs


def _series_from_cell(m, n_entries, n_trades, fields):
    d = {k: m[k] for k in fields}
    d["n_entries"] = n_entries
    d["n_trades"] = n_trades
    return pd.Series(d)


# --------------------------------------------------------------------------- #
# Contrato — una sola celda de candidato, sin grid                           #
# --------------------------------------------------------------------------- #
def test_candidate_is_single_cell_bias_b():
    ok = (
        camp.CANDIDATES == ("B_ema50_ema200_cross",)
        and camp.CANDIDATE_LABEL == "B_ema50_ema200_cross"
        and camp.BIAS_TARGET == "B"
        and camp.BIAS_COMPARATOR == "A"
    )
    return _p(f"CANDIDATES es una única celda B_ema50_ema200_cross ({camp.CANDIDATES})", ok)


def test_bias_b_registered_and_reachable_via_registry():
    ok = research.BIAS_LAYERS.get("B_ema50_ema200_cross") is not None
    return _p("BIAS_LAYERS['B_ema50_ema200_cross'] está registrado y es alcanzable por el script", ok)


def test_default_cardinality_is_6_plus_6():
    """Confirma por construcción (no por corrida real): 3 activos × 2 años =
    6 celdas objetivo B, y las mismas 6 combinaciones para Fase A (Bias A
    auxiliar) — sin grid, sin años adicionales, 2024 excluido del flujo
    normal."""
    ok = (
        ASSETS == ("BTCUSDT", "ETHUSDT", "SOLUSDT")
        and len(ASSETS) == 3
        and (camp.IN_SAMPLE_YEAR, camp.VALIDATION_YEAR) == (2022, 2023)
        and camp.BLIND_YEAR == 2024
        and camp.BLIND_YEAR not in (camp.IN_SAMPLE_YEAR, camp.VALIDATION_YEAR)
    )
    return _p("3 activos x 2 años = 6 celdas objetivo B + 6 verificaciones Fase A; "
              "2024 (BLIND_YEAR=2024) excluido del flujo normal", ok)


# --------------------------------------------------------------------------- #
# _values_match — comparación NaN-consciente                                 #
# --------------------------------------------------------------------------- #
def test_values_match_nan_aware():
    ok = (
        camp._values_match(np.nan, np.nan) is True
        and camp._values_match(1.0, np.nan) is False
        and camp._values_match(np.nan, 1.0) is False
        and camp._values_match(1.5, 1.5) is True
        and camp._values_match(1.5, 1.6) is False
    )
    return _p("_values_match: NaN==NaN True, NaN vs valor False, valores iguales/distintos OK", ok)


# --------------------------------------------------------------------------- #
# Fase A — referencia REAL (sin data/raw/, CSV ya committeado)               #
# --------------------------------------------------------------------------- #
def test_bias_a_session_reference_reads_real_csv():
    ref = camp._bias_a_session_reference("BTCUSDT", 2022)
    ok = ref["n_entries"] == 119 and ref["n_trades"] == 115 and ref["pf"] == 0.681
    return _p(f"_bias_a_session_reference lee el valor real publicado (Bias A, T1_ema_cross, "
              f"dcv1_activo_15h, V3-A) de BTCUSDT/2022 (n_entries={ref['n_entries']}, "
              f"pf={ref['pf']})", ok)


def test_bias_a_session_reference_covers_all_6_target_cells():
    """Las 6 combinaciones (activo, año 2022/2023) de la referencia de Bias A
    bajo este contrato existen y son numéricamente computables (a diferencia
    de Rama B/Trigger C, esta referencia concreta no tiene ninguna celda con
    n_trades<5 — se verifica explícitamente, no se asume)."""
    ok = True
    for asset in ASSETS:
        for year in (2022, 2023):
            ref = camp._bias_a_session_reference(asset, year)
            ok = ok and not pd.isna(ref["pf"])
    return _p("las 6 filas de referencia de Bias A (3 activos x 2 años) existen y son "
              "computables (sin NaN)", ok)


# --------------------------------------------------------------------------- #
# _verify_against                                                             #
# --------------------------------------------------------------------------- #
def _ref_row(**overrides):
    base = {"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 8.0,
            "n_entries": 100, "n_trades": 95}
    base.update(overrides)
    return pd.Series(base)


def test_verify_against_passes_on_exact_match():
    m = {"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 8.0}
    ok = True
    try:
        camp._verify_against("celda", "BTCUSDT", 2022, "ref.csv", 100, 95, m, _ref_row())
    except AssertionError:
        ok = False
    return _p("_verify_against no revienta cuando todos los campos coinciden exacto", ok)


def test_verify_against_raises_with_detailed_message():
    m = {"pf": 1.05, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 8.0}
    ok = False
    try:
        camp._verify_against("Bias A (verificación de pipeline compartido)", "BTCUSDT", 2022,
                              "ref.csv", 100, 95, m, _ref_row())
    except AssertionError as e:
        msg = str(e)
        ok = ("Bias A" in msg and "BTCUSDT" in msg and "2022" in msg
              and "ref.csv" in msg and "pf:" in msg and "esperado=" in msg and "obtenido=1.05" in msg)
    return _p("_verify_against identifica celda/activo/año/referencia/campo/esperado/obtenido", ok)


def test_verify_against_passes_when_both_nan():
    ok = True
    try:
        camp._verify_against("celda", "ETHUSDT", 2023, "ref.csv", 4, 4, None,
                              _ref_row(pf=np.nan, wr=np.nan, exp_r=np.nan, max_dd=np.nan, freq=np.nan,
                                       n_entries=4, n_trades=4))
    except AssertionError:
        ok = False
    return _p("_verify_against no revienta cuando ambos lados son NaN (celda no computable)", ok)


# --------------------------------------------------------------------------- #
# run_integrity_check — sintético                                            #
# --------------------------------------------------------------------------- #
def test_run_integrity_check_passes_when_reference_matches_exactly():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_integrity_check pasa con referencia exacta (slice vacío)", False)

    orig_load = camp.load_asset_year
    camp.load_asset_year = lambda asset, year: sliced
    try:
        entries, trades, m = camp._run_combo(sliced, "bias_A", camp._cfg())
    finally:
        camp.load_asset_year = orig_load
    ref = _series_from_cell(m, len(entries), len(trades), camp._CHECK_FIELDS)

    orig_ref = camp._bias_a_session_reference
    camp._bias_a_session_reference = lambda asset, year: ref
    camp.load_asset_year = lambda asset, year: sliced
    ok = True
    try:
        df_full, cfg = camp.run_integrity_check("TESTUSDT", 2022)
        ok = (not errs) and df_full is not None
    except AssertionError:
        ok = False
    finally:
        camp._bias_a_session_reference = orig_ref
        camp.load_asset_year = orig_load

    return _p("run_integrity_check pasa (sin excepción) cuando la referencia coincide exacto", ok)


def test_run_integrity_check_raises_when_reference_wrong():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_integrity_check revienta con referencia incorrecta (slice vacío)", False)

    wrong_ref = pd.Series({"pf": 999.0, "wr": 1.0, "exp_r": 1.0, "max_dd": -1.0,
                            "freq": 1.0, "n_entries": 1, "n_trades": 1})
    orig_ref = camp._bias_a_session_reference
    orig_load = camp.load_asset_year
    camp._bias_a_session_reference = lambda asset, year: wrong_ref
    camp.load_asset_year = lambda asset, year: sliced
    ok = False
    try:
        camp.run_integrity_check("TESTUSDT", 2022)
    except AssertionError:
        ok = not errs
    finally:
        camp._bias_a_session_reference = orig_ref
        camp.load_asset_year = orig_load

    return _p("run_integrity_check revienta con AssertionError si la referencia NO coincide", ok)


def test_run_campaign_never_reaches_phase_b_if_phase_a_fails():
    def _boom(asset, year, df_full, cfg):
        raise RuntimeError("Fase B NO debería haberse invocado — Fase A ya había fallado")

    orig_check = camp.run_integrity_check
    orig_target = camp.run_asset_year_target
    camp.run_integrity_check = lambda asset, year: (_ for _ in ()).throw(
        AssertionError("Fase A simulada: falla"))
    camp.run_asset_year_target = _boom
    ok = False
    try:
        camp.run_campaign(assets=("TESTUSDT",), years=(2022,))
    except AssertionError:
        ok = True
    except RuntimeError:
        ok = False
    finally:
        camp.run_integrity_check = orig_check
        camp.run_asset_year_target = orig_target

    return _p("run_campaign() propaga la falla de Fase A sin invocar Fase B", ok)


# --------------------------------------------------------------------------- #
# Fase B — la celda objetivo                                                 #
# --------------------------------------------------------------------------- #
def test_run_asset_year_target_produces_exactly_one_row():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_asset_year_target produce 1 fila (slice vacío)", False)
    row = camp.run_asset_year_target("TESTUSDT", 2022, sliced, camp._cfg())
    ok = (
        not errs and row["candidate"] == camp.CANDIDATE_LABEL
        and row["bias"] == "B" and row["trigger"] == "T1_ema_cross"
        and row["entry"] == "C_market_close" and isinstance(row["gate_pass"], bool)
    )
    return _p(f"run_asset_year_target produce exactamente 1 fila objetivo ({row['candidate']})", ok)


def test_bias_is_the_only_column_that_differs_between_frames():
    """Prueba directa de la condición científica del contrato congelado: los
    frames construidos para Bias A y Bias B deben ser IDÉNTICOS en toda
    columna salvo 'bias' — Bias es la ÚNICA variable experimental, Trigger/
    Entry/sesión/Gestión quedan exactamente iguales."""
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("frames A/B idénticos salvo 'bias' (slice vacío)", False)
    cfg = camp._cfg()
    frame_a = bias_camp.to_backtest_frame(sliced, sliced["bias_A"], cfg)
    frame_b = bias_camp.to_backtest_frame(sliced, sliced["bias_B"], cfg)
    other_cols = [c for c in frame_a.columns if c != "bias"]
    ok = (not errs) and list(frame_a.columns) == list(frame_b.columns) \
        and frame_a[other_cols].equals(frame_b[other_cols])
    return _p("frame(Bias A) y frame(Bias B) son idénticos en TODA columna salvo 'bias' "
              "(open/high/low/close/atr/in_session) — Bias es la única variable", ok)


def test_full_pipeline_end_to_end_on_synthetic_slice():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("pipeline completo corre end-to-end (slice vacío)", False)

    orig_load = camp.load_asset_year
    orig_ref = camp._bias_a_session_reference
    camp.load_asset_year = lambda asset, year: sliced

    def _matching_ref(asset, year):
        entries, trades, m = camp._run_combo(sliced, "bias_A", camp._cfg())
        return _series_from_cell(m, len(entries), len(trades), camp._CHECK_FIELDS)

    camp._bias_a_session_reference = _matching_ref

    ok = True
    try:
        results = camp.run_campaign(assets=("TESTUSDT",), years=(2022,))
        df = camp.results_to_frame(results)
        ok = (not errs) and len(df) == 1 and set(df["candidate"]) == {camp.CANDIDATE_LABEL}
    except AssertionError as e:
        ok = False
        print(f"    (excepción inesperada: {e})")
    finally:
        camp.load_asset_year = orig_load
        camp._bias_a_session_reference = orig_ref

    return _p("run_campaign() end-to-end (Fase A + Fase B) corre sin excepciones, 1 fila objetivo", ok)


def test_results_to_frame_includes_bias_trigger_entry_columns():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("results_to_frame incluye bias/trigger/entry (slice vacío)", False)
    row = camp.run_asset_year_target("TESTUSDT", 2022, sliced, camp._cfg())
    df = camp.results_to_frame([row])
    ok = (
        {"bias", "trigger", "entry"}.issubset(df.columns)
        and set(df["bias"]) == {"B"} and set(df["trigger"]) == {"T1_ema_cross"}
        and set(df["entry"]) == {"C_market_close"}
    )
    return _p("results_to_frame conserva columnas bias/trigger/entry", ok)


# --------------------------------------------------------------------------- #
# run_blind_test                                                             #
# --------------------------------------------------------------------------- #
def test_run_blind_test_requires_frozen_candidate():
    ok = True
    try:
        camp.run_blind_test(candidate=None)
        ok = False
    except ValueError:
        pass
    try:
        camp.run_blind_test(candidate="A_ema200_neutral")  # no existe como candidato de esta campaña
        ok = False
    except ValueError:
        pass
    return _p("run_blind_test exige --candidate en CANDIDATES (rechaza combos inexistentes) "
              "antes de tocar data/raw/", ok)


def test_run_blind_test_parses_candidate_string():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_blind_test corre para el candidato congelado (slice vacío)", False)
    orig = camp.load_asset_year
    camp.load_asset_year = lambda asset, year: sliced
    try:
        results = camp.run_blind_test(assets=("TESTUSDT",), candidate=camp.CANDIDATE_LABEL)
    finally:
        camp.load_asset_year = orig
    ok = (not errs) and len(results) == 1 and results[0]["bias"] == "B" \
        and results[0]["trigger"] == "T1_ema_cross" and results[0]["entry"] == "C_market_close" \
        and results[0]["year"] == camp.BLIND_YEAR
    return _p("run_blind_test corre correctamente para el único candidato congelado", ok)


ALL_TESTS = [
    test_candidate_is_single_cell_bias_b,
    test_bias_b_registered_and_reachable_via_registry,
    test_default_cardinality_is_6_plus_6,
    test_values_match_nan_aware,
    test_bias_a_session_reference_reads_real_csv,
    test_bias_a_session_reference_covers_all_6_target_cells,
    test_verify_against_passes_on_exact_match,
    test_verify_against_raises_with_detailed_message,
    test_verify_against_passes_when_both_nan,
    test_run_integrity_check_passes_when_reference_matches_exactly,
    test_run_integrity_check_raises_when_reference_wrong,
    test_run_campaign_never_reaches_phase_b_if_phase_a_fails,
    test_run_asset_year_target_produces_exactly_one_row,
    test_bias_is_the_only_column_that_differs_between_frames,
    test_full_pipeline_end_to_end_on_synthetic_slice,
    test_results_to_frame_includes_bias_trigger_entry_columns,
    test_run_blind_test_requires_frozen_candidate,
    test_run_blind_test_parses_candidate_string,
]


def main():
    print("scripts/bias_b_campaign — validación estructural + real (CSV histórico)\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
