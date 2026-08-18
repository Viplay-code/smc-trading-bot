"""
research/tests/test_trigger_entry_campaign_rama_b.py — Validación de
scripts/trigger_entry_campaign_rama_b.py.

Dos categorías de test:
  1. ESTRUCTURAL sobre datos sintéticos (no sustituye la corrida real,
     bloqueada en este sandbox, HTTP 451, data/raw/ vacío).
  2. REAL sobre trigger_campaign_sweep_bos_session_results.csv (ya
     committeado, no requiere data/raw/) — la referencia de Fase A se
     prueba contra el valor real publicado, no mockeado.

Ejecutar:
    python -m research.tests.test_trigger_entry_campaign_rama_b  (o con pytest)
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

sys.path.insert(0, ".")
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as trigger_camp
import scripts.entry_campaign_sweep_bos as entry_sweep_bos
import scripts.trigger_entry_campaign_rama_b as camp

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
    raw = make_synthetic_raw_1h(start=start, seed=seed)
    df_full = build_dc_v1(raw, asset="TESTUSDT", dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)
    df4h_full = bias_camp.resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, camp.BIAS_CANDIDATE)
    sliced = period_slice(df_full, year)
    return sliced, errs


def _series_from_cell(m, n_entries, n_trades, fields):
    d = {k: m[k] for k in fields}
    d["n_entries"] = n_entries
    d["n_trades"] = n_trades
    return pd.Series(d)


# --------------------------------------------------------------------------- #
# Diseño — sin celda D_range_breakout+A_pullback_50 (ajuste 1)               #
# --------------------------------------------------------------------------- #
def test_combos_exactly_two_no_d_plus_a():
    ok = (
        len(camp.COMBOS) == 2
        and ("D_range_breakout", "A_pullback_50") not in camp.COMBOS
        and ("D_range_breakout", "C_market_close") in camp.COMBOS
        and ("A_sweep_bos", "A_pullback_50") in camp.COMBOS
    )
    return _p(f"COMBOS tiene exactamente 2 celdas, sin D_range_breakout+A_pullback_50 "
              f"({camp.COMBOS})", ok)


def test_candidates_labels():
    ok = camp.CANDIDATES == ("D_range_breakout + C_market_close", "A_sweep_bos + A_pullback_50")
    return _p(f"CANDIDATES etiqueta correctamente los 2 combos ({camp.CANDIDATES})", ok)


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
def test_sweep_bos_reference_reads_real_csv():
    ref = camp._sweep_bos_dcv1_reference("BTCUSDT", 2022)
    ok = ref["n_entries"] == 17 and ref["n_trades"] == 17 and ref["pf"] == 0.637
    return _p(f"_sweep_bos_dcv1_reference lee el valor real publicado de Espacio 3 "
              f"(BTCUSDT/2022, n_entries={ref['n_entries']}, pf={ref['pf']})", ok)


def test_sweep_bos_reference_handles_noncomputable_cell():
    ref = camp._sweep_bos_dcv1_reference("ETHUSDT", 2023)
    ok = pd.isna(ref["pf"])  # Espacio 3: ETHUSDT/2023 es no-computable (n_trades=4)
    return _p("_sweep_bos_dcv1_reference expone correctamente la celda no-computable "
              "(ETHUSDT/2023, pf=NaN)", ok)


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
        camp._verify_against("A_sweep_bos + C_market_close (verificación)", "BTCUSDT", 2022,
                              "ref.csv", 100, 95, m, _ref_row())
    except AssertionError as e:
        msg = str(e)
        ok = ("A_sweep_bos + C_market_close" in msg and "BTCUSDT" in msg and "2022" in msg
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

    orig_load = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        frame, cfg = camp._frame_for_asset_year("TESTUSDT", 2022)
        entries, trades, m = camp._run_combo(frame, cfg, "A_sweep_bos", "C_market_close")
    finally:
        trigger_camp.load_asset_year = orig_load
    ref = _series_from_cell(m, len(entries), len(trades), camp._CHECK_FIELDS)

    orig_ref = camp._sweep_bos_dcv1_reference
    camp._sweep_bos_dcv1_reference = lambda asset, year: ref
    trigger_camp.load_asset_year = lambda asset, year: sliced
    ok = True
    try:
        f2, c2 = camp.run_integrity_check("TESTUSDT", 2022)
        ok = (not errs) and f2 is not None
    except AssertionError:
        ok = False
    finally:
        camp._sweep_bos_dcv1_reference = orig_ref
        trigger_camp.load_asset_year = orig_load

    return _p("run_integrity_check pasa (sin excepción) cuando la referencia coincide exacto", ok)


def test_run_integrity_check_raises_when_reference_wrong():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_integrity_check revienta con referencia incorrecta (slice vacío)", False)

    wrong_ref = pd.Series({"pf": 999.0, "wr": 1.0, "exp_r": 1.0, "max_dd": -1.0,
                            "freq": 1.0, "n_entries": 1, "n_trades": 1})
    orig_ref = camp._sweep_bos_dcv1_reference
    orig_load = trigger_camp.load_asset_year
    camp._sweep_bos_dcv1_reference = lambda asset, year: wrong_ref
    trigger_camp.load_asset_year = lambda asset, year: sliced
    ok = False
    try:
        camp.run_integrity_check("TESTUSDT", 2022)
    except AssertionError:
        ok = not errs
    finally:
        camp._sweep_bos_dcv1_reference = orig_ref
        trigger_camp.load_asset_year = orig_load

    return _p("run_integrity_check revienta con AssertionError si la referencia NO coincide", ok)


def test_run_campaign_never_reaches_phase_b_if_phase_a_fails():
    def _boom(asset, year, frame, cfg):
        raise RuntimeError("Fase B NO debería haberse invocado — Fase A ya había fallado")

    orig_check = camp.run_integrity_check
    orig_targets = camp.run_asset_year_targets
    camp.run_integrity_check = lambda asset, year: (_ for _ in ()).throw(
        AssertionError("Fase A simulada: falla"))
    camp.run_asset_year_targets = _boom
    ok = False
    try:
        camp.run_campaign(assets=("TESTUSDT",), years=(2022,))
    except AssertionError:
        ok = True
    except RuntimeError:
        ok = False
    finally:
        camp.run_integrity_check = orig_check
        camp.run_asset_year_targets = orig_targets

    return _p("run_campaign() propaga la falla de Fase A sin invocar Fase B", ok)


# --------------------------------------------------------------------------- #
# Fase B — las 2 celdas objetivo                                             #
# --------------------------------------------------------------------------- #
def test_run_asset_year_targets_produces_exactly_two_rows():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_asset_year_targets produce 2 filas (slice vacío)", False)
    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        frame, cfg = camp._frame_for_asset_year("TESTUSDT", 2022)
        rows = camp.run_asset_year_targets("TESTUSDT", 2022, frame, cfg)
    finally:
        trigger_camp.load_asset_year = orig
    ok = (
        not errs and len(rows) == 2
        and {r["candidate"] for r in rows} == set(camp.CANDIDATES)
        and all(isinstance(r["gate_pass"], bool) for r in rows)
    )
    return _p(f"run_asset_year_targets produce exactamente 2 filas, una por combo ({len(rows)})", ok)


def test_pullback_entry_receives_trigger_metadata():
    """Verificación explícita (no asumida): A_pullback_50 recibe y usa
    correctamente event.meta["bos_level"]/swing_low/swing_high producidos
    por A_sweep_bos — precio de entrada distinto del cierre de mercado."""
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("A_pullback_50 recibe metadatos del Trigger (slice vacío)", False)
    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        frame, cfg = camp._frame_for_asset_year("TESTUSDT", 2022)
        entries_pullback, _, _ = camp._run_combo(frame, cfg, "A_sweep_bos", "A_pullback_50")
        entries_close, _, _ = camp._run_combo(frame, cfg, "A_sweep_bos", "C_market_close")
    finally:
        trigger_camp.load_asset_year = orig
    ok = (
        not errs and len(entries_pullback) > 0
        and any(e["entry"] != frame["close"].iloc[e["entry_idx"]] for e in entries_pullback)
    )
    return _p(f"A_pullback_50 usa metadatos de A_sweep_bos (precio != cierre de mercado, "
              f"{len(entries_pullback)} entradas)", ok)


def test_range_breakout_entries_no_t1_specific_logic():
    """Verificación de que _run_combo/find_entries_for_entry NO aplican
    ninguna lógica específica de T1: con Entry=C_market_close (que ignora
    meta), los eventos de D_range_breakout (meta={}) y de A_sweep_bos
    (meta con niveles) deben pasar por EXACTAMENTE el mismo camino de código
    y producir entradas con la misma estructura de campos."""
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("D_range_breakout+C_market_close no usa lógica de T1 (slice vacío)", False)
    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        frame, cfg = camp._frame_for_asset_year("TESTUSDT", 2022)
        entries_d, trades_d, m_d = camp._run_combo(frame, cfg, "D_range_breakout", "C_market_close")
    finally:
        trigger_camp.load_asset_year = orig
    ok = (
        not errs
        and all(set(e.keys()) == {"entry_idx", "direction", "entry", "sl0", "risk_pts"} for e in entries_d)
        and all(e["entry"] == frame["close"].iloc[e["entry_idx"]] for e in entries_d)
    )
    return _p(f"D_range_breakout + C_market_close corre por el camino genérico (mismo esquema "
              f"de entradas, sin campos ni ramas específicas de T1, {len(entries_d)} entradas)", ok)


def test_full_pipeline_end_to_end_on_synthetic_slice():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("pipeline completo corre end-to-end (slice vacío)", False)

    orig_load = trigger_camp.load_asset_year
    orig_ref = camp._sweep_bos_dcv1_reference
    trigger_camp.load_asset_year = lambda asset, year: sliced

    def _matching_ref(asset, year):
        frame, cfg = camp._frame_for_asset_year(asset, year)
        entries, trades, m = camp._run_combo(frame, cfg, "A_sweep_bos", "C_market_close")
        return _series_from_cell(m, len(entries), len(trades), camp._CHECK_FIELDS)

    camp._sweep_bos_dcv1_reference = _matching_ref

    ok = True
    try:
        results = camp.run_campaign(assets=("TESTUSDT",), years=(2022,))
        df = camp.results_to_frame(results)
        ok = (not errs) and len(df) == 2 and set(df["candidate"]) == set(camp.CANDIDATES)
    except AssertionError as e:
        ok = False
        print(f"    (excepción inesperada: {e})")
    finally:
        trigger_camp.load_asset_year = orig_load
        camp._sweep_bos_dcv1_reference = orig_ref

    return _p("run_campaign() end-to-end (Fase A + Fase B) corre sin excepciones", ok)


def test_results_to_frame_includes_trigger_and_entry_columns():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("results_to_frame incluye trigger/entry (slice vacío)", False)
    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        frame, cfg = camp._frame_for_asset_year("TESTUSDT", 2022)
        rows = camp.run_asset_year_targets("TESTUSDT", 2022, frame, cfg)
    finally:
        trigger_camp.load_asset_year = orig
    df = camp.results_to_frame(rows)
    ok = ("trigger" in df.columns and "entry" in df.columns
          and set(df["trigger"]) == {"D_range_breakout", "A_sweep_bos"})
    return _p("results_to_frame conserva columnas trigger/entry", ok)


# --------------------------------------------------------------------------- #
# assess_pf_ceiling_signal — 4 niveles, sin selección post-hoc                #
# --------------------------------------------------------------------------- #
def _fake_results_df(pf_by_asset_year: dict) -> pd.DataFrame:
    rows = []
    for (asset, year), pf in pf_by_asset_year.items():
        rows.append({"asset": asset, "year": year, "candidate": "X + Y", "pf": pf})
    return pd.DataFrame(rows)


def test_ceiling_nivel1_solo_una_celda():
    df = _fake_results_df({
        ("BTCUSDT", 2022): 1.6, ("BTCUSDT", 2023): 1.2,
        ("ETHUSDT", 2022): 1.1, ("ETHUSDT", 2023): 1.0,
        ("SOLUSDT", 2022): 1.3, ("SOLUSDT", 2023): 1.1,
    })
    out = camp.assess_pf_ceiling_signal(df)["X + Y"]
    ok = (out["nivel1_mejora_puntual"]["n_celdas"] == 1
          and not out["nivel2_mejora_consistente"]["alcanzado"]
          and not out["nivel3_cambio_de_techo"]["alcanzado"])
    return _p("assess_pf_ceiling_signal: 1 celda >1.5 -> solo Nivel 1, Nivel 2/3 no alcanzados", ok)


def test_ceiling_nivel2_un_activo_ambos_anios():
    df = _fake_results_df({
        ("BTCUSDT", 2022): 1.6, ("BTCUSDT", 2023): 1.55,
        ("ETHUSDT", 2022): 1.1, ("ETHUSDT", 2023): 1.0,
        ("SOLUSDT", 2022): 1.3, ("SOLUSDT", 2023): 1.1,
    })
    out = camp.assess_pf_ceiling_signal(df)["X + Y"]
    ok = (out["nivel2_mejora_consistente"]["por_activo"]["BTCUSDT"] is True
          and out["nivel2_mejora_consistente"]["alcanzado"]
          and not out["nivel3_cambio_de_techo"]["alcanzado"])
    return _p("assess_pf_ceiling_signal: BTC>1.5 ambos años -> Nivel 2 alcanzado, Nivel 3 no", ok)


def test_ceiling_nivel3_los_tres_activos_ambos_anios():
    df = _fake_results_df({
        ("BTCUSDT", 2022): 1.6, ("BTCUSDT", 2023): 1.55,
        ("ETHUSDT", 2022): 1.7, ("ETHUSDT", 2023): 1.52,
        ("SOLUSDT", 2022): 1.9, ("SOLUSDT", 2023): 1.6,
    })
    out = camp.assess_pf_ceiling_signal(df)["X + Y"]
    ok = out["nivel3_cambio_de_techo"]["alcanzado"] is True
    return _p("assess_pf_ceiling_signal: los 3 activos >1.5 ambos años -> Nivel 3 alcanzado", ok)


def test_ceiling_no_selecciona_mejor_punto_post_hoc():
    """Con una sola celda extrema (posible ruido) y el resto bajo, Nivel 2/3
    deben quedar en False — no se promueve el máximo aislado."""
    df = _fake_results_df({
        ("BTCUSDT", 2022): 3.0, ("BTCUSDT", 2023): 0.7,
        ("ETHUSDT", 2022): 0.9, ("ETHUSDT", 2023): 0.8,
        ("SOLUSDT", 2022): 1.0, ("SOLUSDT", 2023): 0.9,
    })
    out = camp.assess_pf_ceiling_signal(df)["X + Y"]
    ok = (out["nivel1_mejora_puntual"]["n_celdas"] == 1
          and not out["nivel2_mejora_consistente"]["alcanzado"]
          and not out["nivel3_cambio_de_techo"]["alcanzado"])
    return _p("assess_pf_ceiling_signal: un máximo aislado (ruido) no se promueve a Nivel 2/3", ok)


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
        camp.run_blind_test(candidate="D_range_breakout + A_pullback_50")  # no existe, ver ajuste 1
        ok = False
    except ValueError:
        pass
    return _p("run_blind_test exige --candidate en CANDIDATES (rechaza D+A) antes de tocar data/raw/", ok)


def test_run_blind_test_parses_candidate_string():
    sliced, errs = _build_sliced_for(seed=7)
    if sliced.empty:
        return _p("run_blind_test parsea 'trigger + entry' (slice vacío)", False)
    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        results = camp.run_blind_test(assets=("TESTUSDT",),
                                       candidate="D_range_breakout + C_market_close")
    finally:
        trigger_camp.load_asset_year = orig
    ok = (not errs) and len(results) == 1 and results[0]["trigger"] == "D_range_breakout" \
        and results[0]["entry"] == "C_market_close" and results[0]["year"] == camp.BLIND_YEAR
    return _p("run_blind_test parsea correctamente el candidato compuesto", ok)


ALL_TESTS = [
    test_combos_exactly_two_no_d_plus_a,
    test_candidates_labels,
    test_values_match_nan_aware,
    test_sweep_bos_reference_reads_real_csv,
    test_sweep_bos_reference_handles_noncomputable_cell,
    test_verify_against_passes_on_exact_match,
    test_verify_against_raises_with_detailed_message,
    test_verify_against_passes_when_both_nan,
    test_run_integrity_check_passes_when_reference_matches_exactly,
    test_run_integrity_check_raises_when_reference_wrong,
    test_run_campaign_never_reaches_phase_b_if_phase_a_fails,
    test_run_asset_year_targets_produces_exactly_two_rows,
    test_pullback_entry_receives_trigger_metadata,
    test_range_breakout_entries_no_t1_specific_logic,
    test_full_pipeline_end_to_end_on_synthetic_slice,
    test_results_to_frame_includes_trigger_and_entry_columns,
    test_ceiling_nivel1_solo_una_celda,
    test_ceiling_nivel2_un_activo_ambos_anios,
    test_ceiling_nivel3_los_tres_activos_ambos_anios,
    test_ceiling_no_selecciona_mejor_punto_post_hoc,
    test_run_blind_test_requires_frozen_candidate,
    test_run_blind_test_parses_candidate_string,
]


def main():
    print("scripts/trigger_entry_campaign_rama_b — validación estructural + real (CSV histórico)\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
