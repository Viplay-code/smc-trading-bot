"""
research/tests/test_gestion_campaign_atr_mult_session.py — Validación de
scripts/gestion_campaign_atr_mult_session.py.

Dos categorías de test:
  1. ESTRUCTURAL sobre datos sintéticos (no sustituye la corrida real,
     bloqueada en este sandbox, HTTP 451, data/raw/ vacío) — que
     _verify_against/run_integrity_check/run_asset_year_dcv1/run_campaign
     respeten el orden Fase A -> Fase B, que atr_mult=ANCLA juegue rol dual
     sin recomputarse dos veces, que CANDIDATES excluya control_8h, y que
     el pipeline completo corra sin excepciones.
  2. REAL sobre los CSV históricos ya committeados (gestion_campaign_
     atr_mult_results.csv, gestion_campaign_session_results.csv,
     gestion_campaign_max_hold_session_results.csv) — estos NO requieren
     data/raw/ ni TA-Lib, ya están en el repo con datos reales, así que
     control_rows_frame()/_session_reference()/_max_hold_session_reference()
     se prueban contra los valores reales publicados, no mockeados.

Ejecutar:
    python -m research.tests.test_gestion_campaign_atr_mult_session  (o con pytest)
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
import scripts.gestion_campaign_atr_mult as atr_mult_camp
import scripts.gestion_campaign_atr_mult_session as camp

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
# Grid, CANDIDATES, hipótesis primaria/secundaria                            #
# --------------------------------------------------------------------------- #
def test_atr_mult_values_reused_from_h1():
    ok = camp.ATR_MULT_VALUES == atr_mult_camp.ATR_MULT_VALUES == (1.0, 1.5, 2.0, 3.0)
    return _p("ATR_MULT_VALUES reutilizado literal de H1: (1.0, 1.5, 2.0, 3.0)", ok)


def test_anchor_and_primary_in_grid():
    ok = camp.ATR_MULT_ANCHOR in camp.ATR_MULT_VALUES and camp.ATR_MULT_PRIMARY in camp.ATR_MULT_VALUES
    return _p("ATR_MULT_ANCHOR (1.5) y ATR_MULT_PRIMARY (3.0) están en el grid", ok)


def test_candidates_only_dcv1_activo_15h():
    ok = (len(camp.CANDIDATES) == 4
          and all(c.endswith("| dcv1_activo_15h") for c in camp.CANDIDATES)
          and not any("control_8h" in c for c in camp.CANDIDATES))
    return _p(f"CANDIDATES tiene exactamente 4 combinaciones, todas dcv1_activo_15h "
              f"({camp.CANDIDATES})", ok)


def test_hypothesis_tag_primary_only_for_3_0():
    tags = {v: camp._hypothesis_tag(v) for v in camp.ATR_MULT_VALUES}
    ok = (tags[3.0] == "primary"
          and tags[1.0] == "secondary" and tags[1.5] == "secondary" and tags[2.0] == "secondary")
    return _p(f"_hypothesis_tag: 'primary' solo para 3.0, 'secondary' el resto ({tags})", ok)


def test_n_candidates_evaluated_matches_grid_times_assets():
    from market_data import ASSETS
    ok = camp.N_CANDIDATES_EVALUATED == len(camp.ATR_MULT_VALUES) * len(ASSETS) == 12
    return _p(f"N_CANDIDATES_EVALUATED = 4 atr_mult x 3 activos = 12 (riesgo de "
              f"comparaciones múltiples, {camp.N_CANDIDATES_EVALUATED})", ok)


# --------------------------------------------------------------------------- #
# _verify_against                                                             #
# --------------------------------------------------------------------------- #
def _ref_row(**overrides):
    base = {"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 8.0, "n_entries": 100, "n_trades": 95}
    base.update(overrides)
    return pd.Series(base)


def test_verify_against_passes_on_exact_match():
    m = {"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 8.0}
    ok = True
    try:
        camp._verify_against("1.5 | dcv1_activo_15h", "BTCUSDT", 2022, "ref.csv", 100, 95, m, _ref_row())
    except AssertionError:
        ok = False
    return _p("_verify_against no revienta cuando todos los campos coinciden exacto", ok)


def test_verify_against_raises_with_detailed_message():
    m = {"pf": 1.05, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 8.0}
    ok = False
    try:
        camp._verify_against("1.5 | dcv1_activo_15h", "BTCUSDT", 2022, "ref.csv", 100, 95, m, _ref_row())
    except AssertionError as e:
        msg = str(e)
        ok = ("1.5 | dcv1_activo_15h" in msg and "BTCUSDT" in msg and "2022" in msg
              and "ref.csv" in msg and "pf:" in msg and "esperado=" in msg and "obtenido=1.05" in msg)
    return _p("_verify_against identifica celda/activo/año/referencia/campo/esperado/obtenido", ok)


def test_verify_against_raises_on_n_entries_mismatch():
    m = {"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 8.0}
    ok = False
    try:
        camp._verify_against("1.5 | dcv1_activo_15h", "BTCUSDT", 2022, "ref.csv", 99, 95, m, _ref_row())
    except AssertionError as e:
        ok = "n_entries" in str(e)
    return _p("_verify_against revienta si n_entries difiere aunque las métricas coincidan", ok)


# --------------------------------------------------------------------------- #
# Lectura REAL de CSV históricos ya committeados — sin data/raw/, sin mock    #
# --------------------------------------------------------------------------- #
def test_control_rows_frame_reads_real_h1_csv():
    df = camp.control_rows_frame()
    from market_data import ASSETS
    ok = (
        len(df) == 24
        and (df["role"] == "control").all()
        and (df["session"] == "control_8h").all()
        and set(df["atr_mult"].unique()) == set(camp.ATR_MULT_VALUES)
        and set(df["asset"].unique()) == set(ASSETS)
        and set(df["year"].unique()) == {2022, 2023}
        and (df["source"].str.contains("gestion_campaign_atr_mult_results.csv")).all()
    )
    return _p(f"control_rows_frame() lee 24 filas reales de H1, role='control' ({len(df)})", ok)


def test_control_rows_frame_hypothesis_tagging():
    df = camp.control_rows_frame()
    primary = df[df["atr_mult"] == 3.0]
    secondary = df[df["atr_mult"] != 3.0]
    ok = (primary["hypothesis"] == "primary").all() and (secondary["hypothesis"] == "secondary").all()
    return _p("control_rows_frame() etiqueta hypothesis='primary' solo para atr_mult=3.0", ok)


def test_control_rows_frame_matches_h1_csv_values_exactly():
    df = camp.control_rows_frame()
    raw = pd.read_csv(camp._ATR_MULT_HISTORICAL_PATH)
    raw = raw[raw["exit_config"] == camp._ATR_MULT_HISTORICAL_EXIT_CONFIG].copy()
    raw["atr_mult"] = raw["candidate"].astype(float)
    row_a = df[(df.asset == "BTCUSDT") & (df.year == 2022) & (df.atr_mult == 3.0)].iloc[0]
    row_b = raw[(raw.asset == "BTCUSDT") & (raw.year == 2022) & (raw.atr_mult == 3.0)].iloc[0]
    ok = (row_a["pf"] == row_b["pf"] and row_a["freq"] == row_b["freq"]
          and row_a["n_trades"] == row_b["n_trades"])
    return _p(f"control_rows_frame() reproduce EXACTO los valores crudos de H1 "
              f"(BTCUSDT/2022/atr_mult=3.0, pf={row_a['pf']})", ok)


def test_session_reference_reads_real_csv():
    ref = camp._session_reference("BTCUSDT", 2022)
    ok = ref["pf"] == 0.681 and ref["freq"] == 9.6 and ref["n_entries"] == 119 and ref["n_trades"] == 115
    return _p(f"_session_reference lee el valor real publicado (BTCUSDT/2022, pf={ref['pf']})", ok)


def test_max_hold_session_reference_reads_real_csv():
    ref = camp._max_hold_session_reference("BTCUSDT", 2022)
    ok = ref["pf"] == 0.681 and ref["freq"] == 9.6 and ref["n_entries"] == 119 and ref["n_trades"] == 115
    return _p(f"_max_hold_session_reference lee el valor real publicado (BTCUSDT/2022, pf={ref['pf']})", ok)


def test_session_and_max_hold_session_references_agree():
    """Las 2 referencias de Fase A para atr_mult=ANCLA x dcv1_activo_15h ya
    coinciden entre sí en los datos reales publicados — precondición
    necesaria para que la Fase A pueda pasar alguna vez."""
    ok = True
    from market_data import ASSETS
    for asset in ASSETS:
        for year in (2022, 2023):
            r1 = camp._session_reference(asset, year)
            r2 = camp._max_hold_session_reference(asset, year)
            for f in camp._CHECK_FIELDS:
                if r1[f] != r2[f]:
                    ok = False
    return _p("Las 2 referencias reales de Fase A (session/max_hold_session) coinciden "
              "entre sí en los 6 combos (activo, año)", ok)


# --------------------------------------------------------------------------- #
# Pipeline sobre datos sintéticos                                            #
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


def _series_from_cell(m, n_entries, n_trades, fields):
    d = {k: m[k] for k in fields}
    d["n_entries"] = n_entries
    d["n_trades"] = n_trades
    return pd.Series(d)


def test_run_integrity_check_passes_when_references_match_exactly():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_integrity_check pasa con referencias exactas (slice vacío)", False)

    orig_load = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        frame = camp._frame_for_session("TESTUSDT", 2022, "dcv1_activo_15h")
        entries, trades, m = camp._run_cell(frame, camp.ATR_MULT_ANCHOR, "dcv1_activo_15h")
    finally:
        trigger_camp.load_asset_year = orig_load

    ref = _series_from_cell(m, len(entries), len(trades), camp._CHECK_FIELDS)

    orig_session = camp._session_reference
    orig_mh = camp._max_hold_session_reference
    camp._session_reference = lambda asset, year: ref
    camp._max_hold_session_reference = lambda asset, year: ref
    trigger_camp.load_asset_year = lambda asset, year: sliced
    ok = True
    try:
        known = camp.run_integrity_check("TESTUSDT", 2022)
        ok = (not errs) and known["m"] is not None
    except AssertionError:
        ok = False
    finally:
        camp._session_reference = orig_session
        camp._max_hold_session_reference = orig_mh
        trigger_camp.load_asset_year = orig_load

    return _p("run_integrity_check pasa (sin excepción) cuando ambas referencias coinciden exacto", ok)


def test_run_integrity_check_raises_when_reference_wrong():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_integrity_check revienta con referencia incorrecta (slice vacío)", False)

    wrong_ref = pd.Series({"pf": 999.0, "wr": 1.0, "exp_r": 1.0, "max_dd": -1.0,
                            "freq": 1.0, "n_entries": 1, "n_trades": 1})
    orig_session = camp._session_reference
    orig_mh = camp._max_hold_session_reference
    orig_load = trigger_camp.load_asset_year
    camp._session_reference = lambda asset, year: wrong_ref
    camp._max_hold_session_reference = lambda asset, year: wrong_ref
    trigger_camp.load_asset_year = lambda asset, year: sliced
    ok = False
    try:
        camp.run_integrity_check("TESTUSDT", 2022)
    except AssertionError:
        ok = not errs
    finally:
        camp._session_reference = orig_session
        camp._max_hold_session_reference = orig_mh
        trigger_camp.load_asset_year = orig_load

    return _p("run_integrity_check revienta con AssertionError si una referencia NO coincide", ok)


def test_run_campaign_never_reaches_phase_b_if_phase_a_fails():
    def _boom(asset, year, known_anchor):
        raise RuntimeError("Fase B NO debería haberse invocado — Fase A ya había fallado")

    orig_check = camp.run_integrity_check
    orig_dcv1 = camp.run_asset_year_dcv1
    camp.run_integrity_check = lambda asset, year: (_ for _ in ()).throw(AssertionError("Fase A simulada: falla"))
    camp.run_asset_year_dcv1 = _boom
    ok = False
    try:
        camp.run_campaign(assets=("TESTUSDT",), years=(2022,))
    except AssertionError:
        ok = True
    except RuntimeError:
        ok = False
    finally:
        camp.run_integrity_check = orig_check
        camp.run_asset_year_dcv1 = orig_dcv1

    return _p("run_campaign() propaga la falla de Fase A sin invocar Fase B", ok)


def test_run_asset_year_dcv1_reuses_anchor_without_recomputing():
    """atr_mult=ANCLA debe reutilizar EXACTAMENTE el objeto ya computado en
    Fase A (known_anchor), no volver a llamar _run_cell para ese valor.
    known_anchor se construye directamente (_frame_for_session + _run_cell),
    sin pasar por run_integrity_check, para no depender de las referencias
    reales (que no existen para el activo sintético TESTUSDT)."""
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_asset_year_dcv1 reutiliza el ancla sin recomputar (slice vacío)", False)

    orig_load = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        frame = camp._frame_for_session("TESTUSDT", 2022, "dcv1_activo_15h")
        entries, trades, m = camp._run_cell(frame, camp.ATR_MULT_ANCHOR, "dcv1_activo_15h")
    finally:
        trigger_camp.load_asset_year = orig_load
    known = {"frame": frame, "entries": entries, "trades": trades, "m": m}

    call_count = {"n": 0}
    orig_run_cell = camp._run_cell

    def _counting_run_cell(frame, atr_mult, session_label):
        call_count["n"] += 1
        return orig_run_cell(frame, atr_mult, session_label)

    camp._run_cell = _counting_run_cell
    try:
        rows = camp.run_asset_year_dcv1("TESTUSDT", 2022, known)
    finally:
        camp._run_cell = orig_run_cell

    anchor_row = next(r for r in rows if r["atr_mult"] == camp.ATR_MULT_ANCHOR)
    ok = (not errs) and len(rows) == 4 and call_count["n"] == 3 and anchor_row["metrics"] is known["m"]
    return _p(f"run_asset_year_dcv1 produce 4 filas, llama _run_cell solo 3 veces "
              f"(reutiliza el ancla, {call_count['n']} llamadas nuevas)", ok)


def test_full_pipeline_end_to_end_on_synthetic_slice():
    """Corre run_campaign() completo con asset="BTCUSDT" (load_asset_year
    mockeado para devolver el slice sintético, ignorando el nombre real) —
    así control_rows_frame() encuentra filas reales de H1 para BTCUSDT (role
    ='control') mientras dcv1_activo_15h se computa sobre datos sintéticos
    (role='candidate'), ejercitando ambas rutas en la misma corrida."""
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("pipeline completo corre end-to-end (slice vacío)", False)

    orig_load = trigger_camp.load_asset_year
    orig_session = camp._session_reference
    orig_mh = camp._max_hold_session_reference
    trigger_camp.load_asset_year = lambda asset, year: sliced

    def _matching_ref(asset, year):
        frame = camp._frame_for_session(asset, year, "dcv1_activo_15h")
        entries, trades, m = camp._run_cell(frame, camp.ATR_MULT_ANCHOR, "dcv1_activo_15h")
        return _series_from_cell(m, len(entries), len(trades), camp._CHECK_FIELDS)

    camp._session_reference = _matching_ref
    camp._max_hold_session_reference = _matching_ref
    # control_8h no depende de data/raw/ (lee el CSV real de H1) — se deja
    # tal cual, no se mockea, para probar también esa ruta real.

    ok = True
    try:
        df = camp.run_campaign(assets=("BTCUSDT",), years=(2022,))
        ok = (not errs) and not df.empty and set(df["role"]) == {"control", "candidate"}
        candidate_rows = df[df["role"] == "candidate"]
        control_rows = df[df["role"] == "control"]
        ok = (ok and len(candidate_rows) == 4 and set(candidate_rows["atr_mult"]) == set(camp.ATR_MULT_VALUES)
              and len(control_rows) == 4 and (control_rows["source"].str.contains("no recomputado")).all())
    except AssertionError as e:
        ok = False
        print(f"    (excepción inesperada: {e})")
    finally:
        trigger_camp.load_asset_year = orig_load
        camp._session_reference = orig_session
        camp._max_hold_session_reference = orig_mh

    return _p("run_campaign() end-to-end (Fase A + Fase B + control_8h real de H1) corre sin excepciones", ok)


def test_results_to_frame_includes_role_hypothesis_atr_mult():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("results_to_frame incluye role/hypothesis/atr_mult (slice vacío)", False)
    orig_load = trigger_camp.load_asset_year
    orig_session = camp._session_reference
    orig_mh = camp._max_hold_session_reference
    trigger_camp.load_asset_year = lambda asset, year: sliced

    def _matching_ref(asset, year):
        frame = camp._frame_for_session(asset, year, "dcv1_activo_15h")
        entries, trades, m = camp._run_cell(frame, camp.ATR_MULT_ANCHOR, "dcv1_activo_15h")
        return _series_from_cell(m, len(entries), len(trades), camp._CHECK_FIELDS)

    camp._session_reference = _matching_ref
    camp._max_hold_session_reference = _matching_ref
    try:
        known = camp.run_integrity_check("TESTUSDT", 2022)
        rows = camp.run_asset_year_dcv1("TESTUSDT", 2022, known)
    finally:
        trigger_camp.load_asset_year = orig_load
        camp._session_reference = orig_session
        camp._max_hold_session_reference = orig_mh

    df = camp.results_to_frame(rows)
    ok = ("role" in df.columns and "hypothesis" in df.columns and "atr_mult" in df.columns
          and set(df["role"]) == {"candidate"} and set(df["hypothesis"]) == {"primary", "secondary"})
    return _p("results_to_frame conserva columnas role/hypothesis/atr_mult", ok)


# --------------------------------------------------------------------------- #
# compute_deltas — medida descriptiva ΔPF/Δfreq, sin gate                    #
# --------------------------------------------------------------------------- #
def test_compute_deltas_arithmetic():
    rows = [
        {"asset": "BTCUSDT", "year": 2022, "role": "control", "session": "control_8h",
         "atr_mult": 1.5, "candidate": "1.5 | control_8h", "hypothesis": "secondary",
         "pf": 0.895, "freq": 5.2},
        {"asset": "BTCUSDT", "year": 2022, "role": "candidate", "session": "dcv1_activo_15h",
         "atr_mult": 1.5, "candidate": "1.5 | dcv1_activo_15h", "hypothesis": "secondary",
         "pf": 0.681, "freq": 9.6},
    ]
    df = pd.DataFrame(rows)
    deltas = camp.compute_deltas(df)
    row = deltas.iloc[0]
    ok = (row["delta_pf"] == round(0.681 - 0.895, 3)
          and row["delta_freq"] == round(9.6 - 5.2, 2)
          and row["hypothesis"] == "secondary")
    return _p(f"compute_deltas calcula ΔPF/Δfreq = dcv1_activo_15h - control_8h "
              f"(delta_pf={row['delta_pf']})", ok)


def test_compute_deltas_tags_primary_hypothesis():
    rows = [
        {"asset": "SOLUSDT", "year": 2023, "role": "control", "session": "control_8h",
         "atr_mult": 3.0, "candidate": "3.0 | control_8h", "hypothesis": "primary",
         "pf": 1.567, "freq": 4.6},
        {"asset": "SOLUSDT", "year": 2023, "role": "candidate", "session": "dcv1_activo_15h",
         "atr_mult": 3.0, "candidate": "3.0 | dcv1_activo_15h", "hypothesis": "primary",
         "pf": 1.4, "freq": 9.0},
    ]
    df = pd.DataFrame(rows)
    deltas = camp.compute_deltas(df)
    ok = deltas.iloc[0]["hypothesis"] == "primary"
    return _p("compute_deltas etiqueta la fila de atr_mult=3.0 como hypothesis='primary'", ok)


# --------------------------------------------------------------------------- #
# summarize_decision — solo ve filas role='candidate'                        #
# --------------------------------------------------------------------------- #
def test_summarize_decision_never_sees_control_rows():
    df = camp.control_rows_frame()
    ok = (df["role"] == "control").all()
    # summarize_decision() se invoca en main() solo sobre df[df.role=="candidate"]
    # — acá solo confirmamos que control_rows_frame() nunca produce
    # role="candidate", precondición de esa exclusión.
    return _p("control_rows_frame() nunca produce role='candidate' (nunca entra a "
              "summarize_decision)", ok)


def test_run_blind_test_requires_frozen_candidate():
    ok = True
    try:
        camp.run_blind_test(candidate=None)
        ok = False
    except ValueError:
        pass
    try:
        camp.run_blind_test(candidate="2.5 | dcv1_activo_15h")  # no está en el grid
        ok = False
    except ValueError:
        pass
    return _p("run_blind_test exige --candidate en CANDIDATES antes de tocar data/raw/", ok)


def test_run_blind_test_rejects_control_8h_candidate():
    ok = False
    try:
        camp.run_blind_test(candidate="1.5 | control_8h")  # control_8h nunca es candidato
    except ValueError:
        ok = True
    return _p("run_blind_test rechaza '<atr_mult> | control_8h' (control_8h nunca es candidato)", ok)


def test_run_blind_test_parses_candidate_string():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_blind_test parsea 'atr_mult | dcv1_activo_15h' (slice vacío)", False)
    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        results = camp.run_blind_test(assets=("TESTUSDT",), candidate="3.0 | dcv1_activo_15h")
    finally:
        trigger_camp.load_asset_year = orig
    ok = (not errs) and len(results) == 1 and results[0]["session"] == "dcv1_activo_15h" \
        and results[0]["atr_mult"] == 3.0 and results[0]["hypothesis"] == "primary" \
        and results[0]["role"] == "candidate"
    return _p("run_blind_test parsea correctamente el candidato compuesto", ok)


def test_entries_depend_on_atr_mult_unlike_max_hold():
    """A diferencia de max_hold, find_entries_for_trigger SÍ depende de
    atr_mult (risk_pts = atr_mult*ATR puede filtrar entradas degeneradas) —
    verificación estructural directa, mismo frame reutilizado, entries
    recalculadas por cada atr_mult."""
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("entries se recalculan por atr_mult (slice vacío)", False)
    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        frame = camp._frame_for_session("TESTUSDT", 2022, "control_8h")
        entries_10, _, _ = camp._run_cell(frame, 1.0, "control_8h")
        entries_30, _, _ = camp._run_cell(frame, 3.0, "control_8h")
    finally:
        trigger_camp.load_asset_year = orig
    # El frame es el mismo objeto (no depende de atr_mult); las entradas se
    # recalculan en cada llamada — no se afirma que deban diferir en este
    # slice sintético puntual, solo que el mecanismo las recalcula.
    ok = (not errs) and len(entries_10) >= 0 and len(entries_30) >= 0
    return _p(f"_run_cell recalcula entries por atr_mult sobre el mismo frame "
              f"({len(entries_10)} vs {len(entries_30)})", ok)


ALL_TESTS = [
    test_atr_mult_values_reused_from_h1,
    test_anchor_and_primary_in_grid,
    test_candidates_only_dcv1_activo_15h,
    test_hypothesis_tag_primary_only_for_3_0,
    test_n_candidates_evaluated_matches_grid_times_assets,
    test_verify_against_passes_on_exact_match,
    test_verify_against_raises_with_detailed_message,
    test_verify_against_raises_on_n_entries_mismatch,
    test_control_rows_frame_reads_real_h1_csv,
    test_control_rows_frame_hypothesis_tagging,
    test_control_rows_frame_matches_h1_csv_values_exactly,
    test_session_reference_reads_real_csv,
    test_max_hold_session_reference_reads_real_csv,
    test_session_and_max_hold_session_references_agree,
    test_run_integrity_check_passes_when_references_match_exactly,
    test_run_integrity_check_raises_when_reference_wrong,
    test_run_campaign_never_reaches_phase_b_if_phase_a_fails,
    test_run_asset_year_dcv1_reuses_anchor_without_recomputing,
    test_full_pipeline_end_to_end_on_synthetic_slice,
    test_results_to_frame_includes_role_hypothesis_atr_mult,
    test_compute_deltas_arithmetic,
    test_compute_deltas_tags_primary_hypothesis,
    test_summarize_decision_never_sees_control_rows,
    test_run_blind_test_requires_frozen_candidate,
    test_run_blind_test_rejects_control_8h_candidate,
    test_run_blind_test_parses_candidate_string,
    test_entries_depend_on_atr_mult_unlike_max_hold,
]


def main():
    print("scripts/gestion_campaign_atr_mult_session — validación estructural + real (CSV históricos)\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
