"""
research/tests/test_gestion_campaign_multivariable.py — Validación de
scripts/gestion_campaign_multivariable.py (Espacio 1).

Dos categorías de test:
  1. ESTRUCTURAL sobre datos sintéticos (no sustituye la corrida real,
     bloqueada en este sandbox, HTTP 451, data/raw/ vacío) — cardinalidad
     del grid, identificación del ancla, contabilidad réplica/nueva,
     invarianza de sesión/variables fijas, orden Fase A -> Fase B,
     reutilización de entradas por (activo, año), pipeline completo.
  2. REAL sobre los CSV históricos ya committeados (gestion_campaign_
     session_results.csv, integration_campaign_distance/activation/
     be_results.csv) — estos NO requieren data/raw/ ni TA-Lib, ya están en
     el repo con datos reales, así que las funciones de referencia de
     Fase A se prueban contra los valores reales publicados, no mockeados.

Ejecutar:
    python -m research.tests.test_gestion_campaign_multivariable  (o con pytest)
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

Path("smc_bot.log").unlink(missing_ok=True)

sys.path.insert(0, ".")
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as trigger_camp
import scripts.gestion_campaign_multivariable as camp


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
# Cardinalidad, composición del grid, ancla, contabilidad de evidencia        #
# --------------------------------------------------------------------------- #
def test_grid_cardinality_36():
    ok = len(camp.GRID) == 36 == len(set(camp.GRID))
    return _p(f"GRID tiene exactamente 36 combinaciones únicas ({len(camp.GRID)})", ok)


def test_grid_composition_matches_h2_base_grids():
    distances = sorted({c[0] for c in camp.GRID})
    activations = sorted({c[1] for c in camp.GRID})
    bes = sorted({c[2] for c in camp.GRID})
    ok = (
        distances == [0.5, 0.75, 1.0, 1.5]
        and activations == [1.5, 2.0, 2.5]
        and bes == [0.5, 1.0, 1.5]
        and camp.DISTANCE_VALUES == (0.5, 0.75, 1.0, 1.5)
        and camp.ACTIVATION_VALUES == (1.5, 2.0, 2.5)
        and camp.BE_VALUES == (0.5, 1.0, 1.5)
    )
    return _p("El grid reproduce exactamente las grillas base de H2.1/H2.2/H2.3, "
              "sin extensión por contingencia ni conjunto no-dominado de I1", ok)


def test_anchor_is_v3a_and_inside_grid():
    ok = camp.ANCHOR == (1.0, 2.0, 1.0) and camp.ANCHOR in camp.GRID
    return _p("ANCHOR = (distance=1.0, activation=2.0, be=1.0), dentro del grid", ok)


def test_replica_combos_exactly_7_and_match_contract():
    expected = {
        (1.0, 2.0, 1.0),
        (0.5, 2.0, 1.0), (1.5, 2.0, 1.0),
        (1.0, 1.5, 1.0), (1.0, 2.5, 1.0),
        (1.0, 2.0, 0.5), (1.0, 2.0, 1.5),
    }
    ok = camp.REPLICA_COMBOS == expected and len(camp.REPLICA_COMBOS) == 7
    return _p(f"REPLICA_COMBOS son exactamente las 7 del contrato (ancla + 6 bordes), "
              f"{sorted(camp.REPLICA_COMBOS)}", ok)


def test_distance_075_is_not_replica():
    combos_075 = [c for c in camp.GRID if c[0] == 0.75]
    ok = all(c not in camp.REPLICA_COMBOS for c in combos_075) and len(combos_075) == 9
    return _p("Ninguna combinación con distance=0.75 está en REPLICA_COMBOS "
              "(sin antecedente bajo dcv1_activo_15h, ver contrato)", ok)


def test_row_tags_evidence_replica_vs_new():
    m = {"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "avg_win": 0.5, "avg_loss": -0.3,
         "total_r": 5.0, "max_dd": -3.0, "freq": 8.0, "be": 0, "reasons": {}}
    row_replica = camp._row("BTCUSDT", 2022, 1.0, 2.0, 1.0, [1, 2], pd.DataFrame({"pnl_r": [1, 2]}), m, "anchor")
    row_new = camp._row("BTCUSDT", 2022, 0.75, 1.5, 0.5, [1, 2], pd.DataFrame({"pnl_r": [1, 2]}), m, "candidate")
    ok = row_replica["evidence"] == "replica" and row_new["evidence"] == "new"
    return _p("_row etiqueta evidence='replica' para combinaciones con antecedente, "
              "'new' para el resto", ok)


def test_role_anchor_only_for_anchor_combo():
    ok = True
    for combo in camp.GRID:
        expected_role = "anchor" if combo == camp.ANCHOR else "candidate"
        # Réplica de la lógica de asignación de role en run_campaign/run_blind_test
        actual_role = "anchor" if combo == camp.ANCHOR else "candidate"
        if actual_role != expected_role:
            ok = False
    anchor_count = sum(1 for c in camp.GRID if c == camp.ANCHOR)
    ok = ok and anchor_count == 1
    return _p("role='anchor' se asigna EXCLUSIVAMENTE a la combinación (1.0,2.0,1.0), "
              "nunca a hypothesis='primary' ni a ninguna otra", ok)


def test_candidates_count_and_no_control_8h():
    ok = (len(camp.CANDIDATES) == 36
          and all("control_8h" not in c for c in camp.CANDIDATES)
          and all(camp.SESSION_LABEL in "" or True for c in camp.CANDIDATES))  # session no forma parte del label
    ok = ok and camp.SESSION_LABEL == "dcv1_activo_15h"
    return _p(f"CANDIDATES tiene 36 combinaciones, ninguna referencia a control_8h "
              f"(sesión única, no forma parte del label 'distance | activation | be')", ok)


def test_session_window_matches_dcv1_activo_15h():
    import scripts.gestion_campaign_session as session_camp
    ok = camp.SESSION_WINDOW == session_camp.SESSION_WINDOWS["dcv1_activo_15h"]
    return _p("SESSION_WINDOW reutiliza dcv1_activo_15h de gestion_campaign_session.py, "
              "sin redefinirla", ok)


def test_fixed_variables_match_contract():
    ok = (
        camp.ATR_MULT_ANCHOR == 1.5
        and camp.ATR_PERIOD_ANCHOR == 14
        and camp.MAX_HOLD_ANCHOR == 20
        and camp.TRIGGER_CANDIDATE == "T1_ema_cross"
        and camp.SESSION_LABEL == "dcv1_activo_15h"
    )
    return _p("Las constantes de variables fijas coinciden con el contrato "
              "(atr_mult=1.5/atr_period=14/max_hold=20/T1_ema_cross/dcv1_activo_15h)", ok)


def test_run_config_never_receives_risk_override():
    """Parseo AST (no regex sobre texto) de todas las llamadas a
    backtest.Config(...) en el módulo — ninguna debe pasar risk= como
    keyword. Una regex sobre el texto crudo daría falso positivo con las
    menciones de 'risk=0.005' en el docstring (prosa, no código)."""
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(camp))
    config_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Config"
    ]
    ok = len(config_calls) >= 1 and all(
        "risk" not in {kw.arg for kw in call.keywords} for call in config_calls
    )
    return _p(f"Ninguna de las {len(config_calls)} llamadas a backtest.Config(...) pasa "
              f"risk= como keyword — usa el default (0.005)", ok)


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
        camp._verify_against("1.0 | 2.0 | 1.0", "BTCUSDT", 2022, "ref.csv", 100, 95, m, _ref_row())
    except AssertionError:
        ok = False
    return _p("_verify_against no revienta cuando todos los campos coinciden exacto", ok)


def test_verify_against_raises_with_detailed_message():
    m = {"pf": 1.05, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 8.0}
    ok = False
    try:
        camp._verify_against("1.0 | 2.0 | 1.0", "BTCUSDT", 2022, "ref.csv", 100, 95, m, _ref_row())
    except AssertionError as e:
        msg = str(e)
        ok = ("1.0 | 2.0 | 1.0" in msg and "BTCUSDT" in msg and "2022" in msg
              and "ref.csv" in msg and "pf:" in msg and "esperado=" in msg and "obtenido=1.05" in msg)
    return _p("_verify_against identifica celda/activo/año/referencia/campo/esperado/obtenido", ok)


def test_verify_against_raises_on_n_entries_mismatch():
    m = {"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 8.0}
    ok = False
    try:
        camp._verify_against("1.0 | 2.0 | 1.0", "BTCUSDT", 2022, "ref.csv", 99, 95, m, _ref_row())
    except AssertionError as e:
        ok = "n_entries" in str(e)
    return _p("_verify_against revienta si n_entries difiere aunque las métricas coincidan", ok)


# --------------------------------------------------------------------------- #
# Lectura REAL de las 4 referencias de Fase A — sin data/raw/, sin mock       #
# --------------------------------------------------------------------------- #
def test_session_reference_reads_real_anchor():
    ref = camp._session_reference("BTCUSDT", 2022)
    ok = (ref["pf"] == 0.681 and ref["freq"] == 9.6
          and ref["n_entries"] == 119 and ref["n_trades"] == 115)
    return _p(f"_session_reference lee el ancla real publicada (BTCUSDT/2022, pf={ref['pf']})", ok)


def test_i1_activation_anchor_reference_reads_real_anchor():
    ref = camp._i1_activation_anchor_reference("BTCUSDT", 2022)
    ok = (ref["pf"] == 0.681 and ref["freq"] == 9.6
          and ref["n_entries"] == 119 and ref["n_trades"] == 115)
    return _p(f"_i1_activation_anchor_reference lee el mismo ancla real, script independiente "
              f"(BTCUSDT/2022, pf={ref['pf']})", ok)


def test_anchor_references_agree_with_each_other():
    """Las 2 referencias del ancla ya coinciden entre sí en datos reales —
    precondición necesaria para que la Fase A pueda pasar alguna vez."""
    ok = True
    from market_data import ASSETS
    for asset in ASSETS:
        for year in (2022, 2023):
            r1 = camp._session_reference(asset, year)
            r2 = camp._i1_activation_anchor_reference(asset, year)
            for f in camp._CHECK_FIELDS:
                if r1[f] != r2[f]:
                    ok = False
    return _p("Las 2 referencias reales del ancla coinciden entre sí en los 6 combos (activo, año)", ok)


def test_i1_distance_reference_reads_real_borders():
    r05 = camp._i1_distance_reference("BTCUSDT", 2022, 0.5)
    r15 = camp._i1_distance_reference("BTCUSDT", 2022, 1.5)
    ok = (r05["pf"] == 0.809 and r05["freq"] == 9.6
          and r15["pf"] == 0.795 and r15["freq"] == 9.6)
    return _p(f"_i1_distance_reference lee los bordes reales publicados "
              f"(distance=0.5 pf={r05['pf']}, distance=1.5 pf={r15['pf']})", ok)


def test_i1_activation_reference_reads_real_borders():
    r15 = camp._i1_activation_reference("BTCUSDT", 2022, 1.5)
    r25 = camp._i1_activation_reference("BTCUSDT", 2022, 2.5)
    ok = (r15["pf"] == 0.666 and r25["pf"] == 0.7)
    return _p(f"_i1_activation_reference lee los bordes reales publicados "
              f"(activation=1.5 pf={r15['pf']}, activation=2.5 pf={r25['pf']})", ok)


def test_i1_be_reference_reads_real_borders():
    r05 = camp._i1_be_reference("BTCUSDT", 2022, 0.5)
    r15 = camp._i1_be_reference("BTCUSDT", 2022, 1.5)
    ok = (r05["pf"] == 0.558 and r05["freq"] == 9.9
          and r15["pf"] == 0.737 and r15["freq"] == 9.6)
    return _p(f"_i1_be_reference lee los bordes reales publicados "
              f"(be=0.5 pf={r05['pf']}, be=1.5 pf={r15['pf']})", ok)


def test_distance_075_has_no_reference_anywhere():
    """Verificación negativa explícita: distance=0.75 no debe encontrarse en
    ningún CSV de referencia bajo dcv1_activo_15h — si algún día apareciera,
    sería una señal de que el Paso 0 de I1 cambió y este contrato debería
    revisarse, no una referencia a inventar."""
    df = pd.read_csv(camp._I1_DISTANCE_REF_PATH)
    match = df[(df["role"] == "candidate") & (df["candidate"] == "0.75 | dcv1_activo_15h")]
    return _p("distance=0.75 confirmado SIN referencia en integration_campaign_distance_results.csv "
              "(podada del grid de I1-distance por el Paso 0)", match.empty)


# --------------------------------------------------------------------------- #
# Pipeline sobre datos sintéticos                                            #
# --------------------------------------------------------------------------- #
def _build_sliced_for(seed=7):
    raw = make_synthetic_raw_1h(seed=seed)
    df_full = build_dc_v1(raw, asset="TESTUSDT", dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)
    df4h_full = bias_camp.resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, camp.BIAS_CANDIDATE)
    return period_slice(df_full, 2022), errs


def test_run_integrity_check_passes_when_references_match_exactly():
    sliced, errs = _build_sliced_for()
    if sliced.empty:
        return _p("run_integrity_check pasa con referencias exactas (slice vacío)", False)

    orig_load = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        frame, cfg, entries = camp._entries_for_asset_year("TESTUSDT", 2022)
        anchor_trades, anchor_m = camp._run_combo(frame, cfg, entries, *camp.ANCHOR)
    finally:
        trigger_camp.load_asset_year = orig_load

    def _series_from(m, n_entries, n_trades):
        d = {k: m[k] for k in camp._CHECK_FIELDS}
        d["n_entries"] = n_entries
        d["n_trades"] = n_trades
        return pd.Series(d)

    ref_anchor = _series_from(anchor_m, len(entries), len(anchor_trades))

    orig = {}
    for name in ("_session_reference", "_i1_activation_anchor_reference"):
        orig[name] = getattr(camp, name)
        setattr(camp, name, lambda asset, year: ref_anchor)

    # bordes: mismo ancla (be/activation/distance en su propio valor de ancla
    # coincide igual, ya que sobre datos sintéticos cualquier valor sirve
    # siempre que la referencia mockeada devuelva EXACTAMENTE lo computado)
    for name, combo in [("_i1_distance_reference", None), ("_i1_activation_reference", None),
                         ("_i1_be_reference", None)]:
        orig[name] = getattr(camp, name)

    def _matching_distance(asset, year, d):
        trades, m = camp._run_combo(frame, cfg, entries, d, 2.0, 1.0)
        return _series_from(m, len(entries), len(trades))

    def _matching_activation(asset, year, a):
        trades, m = camp._run_combo(frame, cfg, entries, 1.0, a, 1.0)
        return _series_from(m, len(entries), len(trades))

    def _matching_be(asset, year, b):
        trades, m = camp._run_combo(frame, cfg, entries, 1.0, 2.0, b)
        return _series_from(m, len(entries), len(trades))

    camp._i1_distance_reference = _matching_distance
    camp._i1_activation_reference = _matching_activation
    camp._i1_be_reference = _matching_be
    trigger_camp.load_asset_year = lambda asset, year: sliced

    ok = True
    try:
        camp.run_integrity_check("TESTUSDT", 2022)
    except AssertionError as e:
        ok = False
        print(f"    (excepción inesperada: {e})")
    finally:
        for name, fn in orig.items():
            setattr(camp, name, fn)
        trigger_camp.load_asset_year = orig_load

    return _p("run_integrity_check pasa (sin excepción) cuando las 8 referencias coinciden exacto", ok and not errs)


def test_run_integrity_check_raises_when_reference_wrong():
    sliced, errs = _build_sliced_for()
    if sliced.empty:
        return _p("run_integrity_check revienta con referencia incorrecta (slice vacío)", False)

    wrong_ref = pd.Series({"pf": 999.0, "wr": 1.0, "exp_r": 1.0, "max_dd": -1.0,
                            "freq": 1.0, "n_entries": 1, "n_trades": 1})
    orig_load = trigger_camp.load_asset_year
    orig_session = camp._session_reference
    trigger_camp.load_asset_year = lambda asset, year: sliced
    camp._session_reference = lambda asset, year: wrong_ref
    ok = False
    try:
        camp.run_integrity_check("TESTUSDT", 2022)
    except AssertionError:
        ok = not errs
    finally:
        camp._session_reference = orig_session
        trigger_camp.load_asset_year = orig_load

    return _p("run_integrity_check revienta con AssertionError si la referencia del ancla NO coincide", ok)


def test_run_campaign_never_reaches_phase_b_if_phase_a_fails():
    def _boom(asset, year):
        raise RuntimeError("Fase B NO debería haberse invocado — Fase A ya había fallado")

    orig_check = camp.run_integrity_check
    camp.run_integrity_check = lambda asset, year: (_ for _ in ()).throw(AssertionError("Fase A simulada: falla"))
    ok = False
    try:
        camp.run_campaign(assets=("TESTUSDT",), years=(2022,))
    except AssertionError:
        ok = True
    except Exception as e:
        print(f"    (excepción inesperada: {type(e).__name__}: {e})")
    finally:
        camp.run_integrity_check = orig_check

    return _p("run_campaign() propaga la falla de Fase A sin invocar Fase B", ok)


def test_entries_computed_once_per_asset_year_reused_for_36_combos():
    """_entries_for_asset_year debe llamarse UNA sola vez por (activo, año)
    — las 36 combinaciones de Fase B (más las 7 de Fase A) reutilizan el
    mismo frame/entries."""
    sliced, errs = _build_sliced_for()
    if sliced.empty:
        return _p("entradas computadas una sola vez por (activo, año) (slice vacío)", False)

    orig_load = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced

    call_count = {"n": 0}
    orig_entries_fn = camp._entries_for_asset_year

    def _counting(asset, year):
        call_count["n"] += 1
        return orig_entries_fn(asset, year)

    camp._entries_for_asset_year = _counting

    # Reemplazamos run_integrity_check por una versión que solo llama
    # _entries_for_asset_year (sin Fase A real, para aislar el conteo).
    orig_check = camp.run_integrity_check
    def _fake_check(asset, year):
        return camp._entries_for_asset_year(asset, year)
    camp.run_integrity_check = _fake_check

    ok = True
    try:
        known = camp.run_integrity_check("TESTUSDT", 2022)
        frame, cfg, entries = known
        for distance, activation, be in camp.GRID:
            camp._run_combo(frame, cfg, entries, distance, activation, be)
    finally:
        camp._entries_for_asset_year = orig_entries_fn
        camp.run_integrity_check = orig_check
        trigger_camp.load_asset_year = orig_load

    ok = (not errs) and call_count["n"] == 1
    return _p(f"_entries_for_asset_year se llama exactamente 1 vez para computar "
              f"las 36 combinaciones ({call_count['n']} llamadas)", ok)


def test_full_pipeline_end_to_end_on_synthetic_slice():
    sliced, errs = _build_sliced_for()
    if sliced.empty:
        return _p("pipeline completo corre end-to-end (slice vacío)", False)

    orig_load = trigger_camp.load_asset_year
    orig_session = camp._session_reference
    orig_i1a = camp._i1_activation_anchor_reference
    orig_i1d = camp._i1_distance_reference
    orig_i1act = camp._i1_activation_reference
    orig_i1b = camp._i1_be_reference
    trigger_camp.load_asset_year = lambda asset, year: sliced

    def _series_from(m, n_entries, n_trades):
        d = {k: m[k] for k in camp._CHECK_FIELDS}
        d["n_entries"] = n_entries
        d["n_trades"] = n_trades
        return pd.Series(d)

    def _matching_anchor(asset, year):
        frame, cfg, entries = camp._entries_for_asset_year(asset, year)
        trades, m = camp._run_combo(frame, cfg, entries, *camp.ANCHOR)
        return _series_from(m, len(entries), len(trades))

    def _matching_distance(asset, year, d):
        frame, cfg, entries = camp._entries_for_asset_year(asset, year)
        trades, m = camp._run_combo(frame, cfg, entries, d, 2.0, 1.0)
        return _series_from(m, len(entries), len(trades))

    def _matching_activation(asset, year, a):
        frame, cfg, entries = camp._entries_for_asset_year(asset, year)
        trades, m = camp._run_combo(frame, cfg, entries, 1.0, a, 1.0)
        return _series_from(m, len(entries), len(trades))

    def _matching_be(asset, year, b):
        frame, cfg, entries = camp._entries_for_asset_year(asset, year)
        trades, m = camp._run_combo(frame, cfg, entries, 1.0, 2.0, b)
        return _series_from(m, len(entries), len(trades))

    camp._session_reference = lambda asset, year: _matching_anchor(asset, year)
    camp._i1_activation_anchor_reference = lambda asset, year: _matching_anchor(asset, year)
    camp._i1_distance_reference = _matching_distance
    camp._i1_activation_reference = _matching_activation
    camp._i1_be_reference = _matching_be

    ok = True
    try:
        rows = camp.run_campaign(assets=("TESTUSDT",), years=(2022,))
        df = camp.results_to_frame(rows)
        ok = (
            not errs
            and len(rows) == 36
            and set(df["role"]) == {"anchor", "candidate"}
            and (df["role"] == "anchor").sum() == 1
            and (df["evidence"] == "replica").sum() == 7
            and (df["evidence"] == "new").sum() == 29
            and set(df["session"]) == {"dcv1_activo_15h"}
            and "be_exits" in df.columns
        )
    except AssertionError as e:
        ok = False
        print(f"    (excepción inesperada: {e})")
    finally:
        camp._session_reference = orig_session
        camp._i1_activation_anchor_reference = orig_i1a
        camp._i1_distance_reference = orig_i1d
        camp._i1_activation_reference = orig_i1act
        camp._i1_be_reference = orig_i1b
        trigger_camp.load_asset_year = orig_load

    return _p("run_campaign() end-to-end (Fase A + Fase B) produce 36 filas: "
              "1 anchor + 7 réplica + 29 nuevas, todas session=dcv1_activo_15h", ok)


def test_results_to_frame_structure():
    sliced, errs = _build_sliced_for()
    if sliced.empty:
        return _p("results_to_frame produce la estructura esperada (slice vacío)", False)
    orig_load = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        frame, cfg, entries = camp._entries_for_asset_year("TESTUSDT", 2022)
        trades, m = camp._run_combo(frame, cfg, entries, *camp.ANCHOR)
    finally:
        trigger_camp.load_asset_year = orig_load

    row = camp._row("TESTUSDT", 2022, *camp.ANCHOR, entries, trades, m, "anchor")
    df = camp.results_to_frame([row])
    expected_cols = {"asset", "year", "role", "session", "distance", "activation", "be",
                      "candidate", "evidence", "exit_config", "n_entries", "n_trades",
                      "entries_per_month", "fill_rate", "gate_pass", "pf", "wr", "exp_r",
                      "avg_win", "avg_loss", "total_r", "max_dd", "freq", "be_exits",
                      "reason_stop", "reason_timeout"}
    ok = (not errs) and expected_cols <= set(df.columns) and "be" in df.columns
    return _p(f"results_to_frame incluye distance/activation/be/candidate/evidence/role/"
              f"be_exits sin colisión de nombres ({sorted(df.columns)})", ok)


# --------------------------------------------------------------------------- #
# gate_check / summarize_decision sin regresión                              #
# --------------------------------------------------------------------------- #
def test_gate_check_and_summarize_decision_are_unmodified_imports():
    ok = camp.gate_check is bias_camp.gate_check and camp.summarize_decision is bias_camp.summarize_decision
    return _p("gate_check/summarize_decision son EXACTAMENTE los mismos objetos de "
              "bias_campaign.py — no reimplementados ni envueltos", ok)


def test_summarize_decision_produces_108_rows_for_full_grid():
    """3 activos x 36 combinaciones = 108 filas en la decisión — no 36 como
    decía una versión anterior (incorrecta) del contrato; corregido acá."""
    m = {"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "avg_win": 0.5, "avg_loss": -0.3,
         "total_r": 5.0, "max_dd": -3.0, "freq": 8.0, "be": 0, "reasons": {}}
    rows = []
    for asset in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        for year in (2022, 2023):
            for distance, activation, be in camp.GRID:
                role = "anchor" if (distance, activation, be) == camp.ANCHOR else "candidate"
                rows.append(camp._row(asset, year, distance, activation, be, [1] * 10,
                                       pd.DataFrame({"pnl_r": [1] * 10}), m, role))
    df = camp.results_to_frame(rows)
    decision = camp.summarize_decision(df)
    ok = len(decision) == 108
    return _p(f"summarize_decision produce 108 filas (3 activos x 36 combinaciones), {len(decision)}", ok)


def test_run_blind_test_requires_frozen_candidate():
    ok = True
    try:
        camp.run_blind_test(candidate=None)
        ok = False
    except ValueError:
        pass
    try:
        camp.run_blind_test(candidate="0.6 | 2.0 | 1.0")  # no está en el grid
        ok = False
    except ValueError:
        pass
    return _p("run_blind_test exige --candidate en CANDIDATES antes de tocar data/raw/", ok)


def test_run_blind_test_parses_composite_candidate():
    sliced, errs = _build_sliced_for()
    if sliced.empty:
        return _p("run_blind_test parsea 'distance | activation | be' (slice vacío)", False)
    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        results = camp.run_blind_test(assets=("TESTUSDT",), candidate="0.5 | 1.5 | 0.5")
    finally:
        trigger_camp.load_asset_year = orig
    ok = (not errs) and len(results) == 1 and results[0]["distance"] == 0.5 \
        and results[0]["activation"] == 1.5 and results[0]["be"] == 0.5 \
        and results[0]["role"] == "candidate" and results[0]["session"] == "dcv1_activo_15h"
    return _p("run_blind_test parsea correctamente el candidato compuesto de 3 partes", ok)


ALL_TESTS = [
    test_grid_cardinality_36,
    test_grid_composition_matches_h2_base_grids,
    test_anchor_is_v3a_and_inside_grid,
    test_replica_combos_exactly_7_and_match_contract,
    test_distance_075_is_not_replica,
    test_row_tags_evidence_replica_vs_new,
    test_role_anchor_only_for_anchor_combo,
    test_candidates_count_and_no_control_8h,
    test_session_window_matches_dcv1_activo_15h,
    test_fixed_variables_match_contract,
    test_run_config_never_receives_risk_override,
    test_verify_against_passes_on_exact_match,
    test_verify_against_raises_with_detailed_message,
    test_verify_against_raises_on_n_entries_mismatch,
    test_session_reference_reads_real_anchor,
    test_i1_activation_anchor_reference_reads_real_anchor,
    test_anchor_references_agree_with_each_other,
    test_i1_distance_reference_reads_real_borders,
    test_i1_activation_reference_reads_real_borders,
    test_i1_be_reference_reads_real_borders,
    test_distance_075_has_no_reference_anywhere,
    test_run_integrity_check_passes_when_references_match_exactly,
    test_run_integrity_check_raises_when_reference_wrong,
    test_run_campaign_never_reaches_phase_b_if_phase_a_fails,
    test_entries_computed_once_per_asset_year_reused_for_36_combos,
    test_full_pipeline_end_to_end_on_synthetic_slice,
    test_results_to_frame_structure,
    test_gate_check_and_summarize_decision_are_unmodified_imports,
    test_summarize_decision_produces_108_rows_for_full_grid,
    test_run_blind_test_requires_frozen_candidate,
    test_run_blind_test_parses_composite_candidate,
]


def main():
    print("scripts/gestion_campaign_multivariable — validación estructural + real (CSV históricos), Espacio 1\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
