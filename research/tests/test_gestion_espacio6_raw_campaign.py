"""
research/tests/test_gestion_espacio6_raw_campaign.py — Validación de
scripts/gestion_espacio6_raw_campaign.py (Espacio 6, Experimento 3: Raw).

Tres categorías de test:
  1. MECANISMO — pruebas directas sobre DataFrames sintéticos construidos a
     mano, llamando a backtest.simulate_v3 (SIN reimplementar) con
     exit_cfg={"be":inf,"activation":inf,"distance":0.0}: ni breakeven ni
     trailing se activan nunca (comparado directamente contra V3-A real,
     misma vela), el stop nunca se mueve de sl0, ausencia de TP incluso con
     movimiento extremo, timeout respeta max_hold, distance=0.0 es
     inalcanzable (no un parámetro).
  2. CONTRATO — estructura de la campaña: Fase A antes de Fase B,
     comparador V3-A + comparador E1, verificación de n_entries contra E1
     publicado, gate_check/summarize_decision reutilizados, sin categoría
     "tp".
  3. REAL — lectura de gestion_campaign_session_results.csv y
     gestion_espacio6_tp_fijo_campaign_results.csv (ya committeados, no
     requieren data/raw/) para las referencias de Fase A.

Ejecutar:
    python -m research.tests.test_gestion_espacio6_raw_campaign  (o con pytest)
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
import scripts.gestion_espacio6_raw_campaign as camp


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


# --------------------------------------------------------------------------- #
# Helpers — DataFrame OHLC sintético construido a mano                       #
# --------------------------------------------------------------------------- #
def _mk_df(bars: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    idx = pd.date_range("2022-01-01", periods=len(bars), freq="1h", tz="UTC")
    o, h, l, c = zip(*bars)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=idx)


def _mk_entry(direction: str, entry: float, sl0: float, risk_pts: float,
              entry_idx: int = 0) -> dict:
    return {"entry_idx": entry_idx, "direction": direction, "entry": entry,
            "sl0": sl0, "risk_pts": risk_pts}


def _cfg(max_hold: int = 20) -> "backtest.Config":
    return backtest.Config(max_hold=max_hold)


# --------------------------------------------------------------------------- #
# Mecanismo — reutiliza backtest.simulate_v3 SIN reimplementar              #
# --------------------------------------------------------------------------- #
def test_no_hay_funcion_simulate_propia_en_el_modulo():
    import inspect
    src = inspect.getsource(camp)
    ok = "def simulate_" not in src
    return _p("El módulo no reimplementa ninguna función simulate_* — "
              "reutiliza backtest.simulate_v3 sin modificar", ok)


def test_tratamiento_usa_backtest_simulate_v3_realmente():
    entry = _mk_entry("long", 100.0, 90.0, 10.0)
    df = _mk_df([(100, 101, 99, 100), (95, 96, 85, 90)])
    cfg = _cfg()

    call_count = {"n": 0}
    orig = backtest.simulate_v3

    def _counting(*args, **kwargs):
        call_count["n"] += 1
        return orig(*args, **kwargs)

    backtest.simulate_v3 = _counting
    try:
        trades = backtest.run_config(df, [entry], camp.EXIT_CFG_RAW, cfg)
    finally:
        backtest.simulate_v3 = orig

    ok = call_count["n"] == 1 and len(trades) == 1
    return _p(f"run_config con EXIT_CFG_RAW invoca backtest.simulate_v3 "
              f"({call_count['n']} llamada)", ok)


def test_breakeven_nunca_se_activa():
    """A diferencia de E2 (be=1.0), acá be=inf — ni siquiera un avance
    grande activa breakeven."""
    entry = _mk_entry("long", 100.0, 90.0, 10.0)
    df = _mk_df([
        (100, 101, 99, 100),
        (105, 130, 108, 125),    # fav +3.0R -> en V3-A/E2 ya dispara BE; acá NO
        (120, 122, 91, 95),      # retrocede hasta 91 (>90=sl0) -> sigue abierta si BE no actuó
    ])
    res = backtest.simulate_v3(df, entry, camp.EXIT_CFG_RAW, _cfg(max_hold=2))
    ok = res["reason"] == "timeout"   # nunca se acerca a stop=90, termina en timeout
    return _p(f"be=inf: breakeven nunca se activa pese a fav_r=3.0R (reason={res['reason']})", ok)


def test_trailing_nunca_se_activa():
    """Mismo camino de precio que el test análogo de E2: V3-A (con
    trailing) cierra antes por el ratchet; Raw (activation=inf, be=inf)
    no ratchea, no hace BE, y sigue abierta."""
    entry = _mk_entry("long", 100.0, 90.0, 10.0)
    bars = [
        (100, 101, 99, 100),
        (130, 135, 132, 133),     # fav +3.5R -> en V3-A dispara BE y trailing (trail_stop=125)
        (128, 131, 120, 125),     # low=120 -> V3-A (stop=125) cierra acá; Raw (stop=90) NO
        (123, 124, 105, 110),     # low=105 -> sigue > 90 -> Raw continúa
    ]
    df = _mk_df(bars)
    cfg = _cfg(max_hold=3)

    res_raw = backtest.simulate_v3(df, entry, camp.EXIT_CFG_RAW, cfg)
    res_v3a = backtest.simulate_v3(df, entry, backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], cfg)

    ok = (res_v3a["reason"] == "stop" and res_v3a["exit_time"] == df.index[2]
          and res_raw["reason"] == "timeout" and res_raw["exit_time"] == df.index[3])
    return _p(f"V3-A cierra en la vela 2 por trailing (reason={res_v3a['reason']}); "
              f"Raw (be=inf/activation=inf) sigue abierta y termina en timeout, vela 3 "
              f"(reason={res_raw['reason']}) — sin BE ni ratchet", ok)


def test_stop_nunca_se_mueve_de_sl0():
    """Verificación directa de la propiedad central del contrato: todo
    trade con reason=='stop' debe cerrar exactamente en entry['sl0'],
    sin importar cuánto haya avanzado el precio antes de revertir."""
    entry = _mk_entry("long", 100.0, 90.0, 10.0)
    bars = [
        (100, 101, 99, 100),
        (105, 150, 148, 145),   # fav +4.5R
        (140, 141, 89, 90),     # revierte y toca el stop original (90)
    ]
    df = _mk_df(bars)
    res = backtest.simulate_v3(df, entry, camp.EXIT_CFG_RAW, _cfg(max_hold=2))
    ok = res["reason"] == "stop" and res["exit_time"] == df.index[2]
    # pnl_r esperado: (90-100)/10 - costos = -1 - costos (stop en sl0 exacto, no en breakeven)
    expected_gross = (90.0 - 100.0) / 10.0
    ok = ok and res["pnl_r"] < expected_gross + 0.01 and res["pnl_r"] > expected_gross - 0.05
    return _p(f"El stop nunca se movió de sl0=90 pese a fav_r=4.5R — cierre en pérdida completa "
              f"(pnl_r={res['pnl_r']}, esperado≈{round(expected_gross,3)})", ok)


def test_sin_tp_pese_a_movimiento_extremo():
    entry = _mk_entry("long", 100.0, 90.0, 10.0)
    bars = [
        (100, 101, 99, 100),
        (150, 200, 148, 195),
        (196, 205, 190, 200),
    ]
    df = _mk_df(bars)
    res = backtest.simulate_v3(df, entry, camp.EXIT_CFG_RAW, _cfg(max_hold=2))
    ok = res["reason"] == "timeout" and res["pnl_r"] > 9.0
    return _p(f"Sin techo de ganancia: la operación llega a timeout con pnl_r={res['pnl_r']} "
              f"(>9R), sin que ningún nivel fijo la haya cerrado antes", ok)


def test_timeout_respeta_max_hold_20():
    entry = _mk_entry("long", 100.0, 90.0, 10.0)
    bars = [(100, 101, 99, 100)] + [(103, 105, 96, 102)] * 25
    df = _mk_df(bars)
    res = backtest.simulate_v3(df, entry, camp.EXIT_CFG_RAW, _cfg(max_hold=20))
    ok = res["reason"] == "timeout" and res["exit_time"] == df.index[20]
    return _p(f"max_hold=20 respetado exactamente igual que en V3-A/E1/E2 (exit_time={res['exit_time']})", ok)


def test_distance_es_inalcanzable_no_es_parametro():
    entry = _mk_entry("long", 100.0, 90.0, 10.0)
    bars = [
        (100, 101, 99, 100), (130, 135, 132, 133),
        (128, 131, 120, 125), (123, 124, 105, 110),
    ]
    df = _mk_df(bars)
    cfg = _cfg(max_hold=3)
    cfg_variant = {**camp.EXIT_CFG_RAW, "distance": 999.0}
    res_a = backtest.simulate_v3(df, entry, camp.EXIT_CFG_RAW, cfg)
    res_b = backtest.simulate_v3(df, entry, cfg_variant, cfg)
    ok = res_a == res_b
    return _p("distance=0.0 es estructuralmente inalcanzable (be=inf/activation=inf) — cambiar "
              "su valor no altera el resultado, confirmando que NO es un parámetro experimental", ok)


# --------------------------------------------------------------------------- #
# Contrato — estructura de la campaña                                        #
# --------------------------------------------------------------------------- #
def test_candidates_single_value():
    ok = camp.CANDIDATES == ("Raw",)
    return _p(f"CANDIDATES tiene una única celda ('Raw'), sin grid ({camp.CANDIDATES})", ok)


def test_fixed_variables_match_contract():
    ok = (
        camp.ATR_MULT_ANCHOR == 1.5 and camp.ATR_PERIOD_ANCHOR == 14
        and camp.MAX_HOLD_ANCHOR == 20 and camp.TRIGGER_CANDIDATE == "T1_ema_cross"
        and camp.ENTRY_CANDIDATE == "C_market_close" and camp.SESSION_LABEL == "dcv1_activo_15h"
        and camp.BIAS_CANDIDATE == "A"
        and camp.EXIT_CFG_RAW == {"be": float("inf"), "activation": float("inf"), "distance": 0.0}
    )
    return _p("Constantes de variables fijas y EXIT_CFG_RAW coinciden con el contrato", ok)


def test_no_risk_override_en_llamadas_a_config():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(camp))
    config_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Config"
    ]
    ok = len(config_calls) >= 1 and all(
        "risk" not in {kw.arg for kw in call.keywords} for call in config_calls
    )
    return _p(f"Ninguna de las {len(config_calls)} llamadas a backtest.Config(...) pasa "
              f"risk= como keyword — usa el default (0.005)", ok)


def test_gate_check_and_summarize_decision_son_los_mismos_objetos():
    ok = camp.gate_check is bias_camp.gate_check and camp.summarize_decision is bias_camp.summarize_decision
    return _p("gate_check/summarize_decision son EXACTAMENTE los mismos objetos de "
              "bias_campaign.py — no reimplementados", ok)


def test_v3a_reference_lee_el_ancla_real():
    ref = camp._v3a_reference("BTCUSDT", 2022)
    ok = (ref["pf"] == 0.681 and ref["freq"] == 9.6
          and ref["n_entries"] == 119 and ref["n_trades"] == 115)
    return _p(f"_v3a_reference lee la fila real publicada (BTCUSDT/2022, pf={ref['pf']})", ok)


def test_e1_reference_lee_los_resultados_reales():
    ref = camp._e1_reference("BTCUSDT", 2022)
    ok = ref is not None and ref["n_entries"] == 119 and ref["n_trades"] == 115 and ref["pf"] == 0.878
    return _p(f"_e1_reference lee la fila real publicada de E1 (BTCUSDT/2022, pf={ref['pf'] if ref is not None else None})", ok)


def test_check_entries_vs_e1_detecta_match_y_mismatch():
    match = camp.check_entries_vs_e1("BTCUSDT", 2022, 119)
    mismatch = camp.check_entries_vs_e1("BTCUSDT", 2022, 999)
    ok = match["match"] is True and mismatch["match"] is False
    return _p("check_entries_vs_e1 detecta correctamente coincidencia y no-coincidencia de n_entries", ok)


def test_verify_against_passa_en_match_exacto():
    m = {"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 8.0}
    ref = pd.Series({"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 8.0,
                      "n_entries": 100, "n_trades": 95})
    ok = True
    try:
        camp._verify_against("BTCUSDT", 2022, 100, 95, m, ref)
    except AssertionError:
        ok = False
    return _p("_verify_against no revienta cuando todos los campos coinciden exacto", ok)


def test_verify_against_revienta_en_mismatch():
    m = {"pf": 1.05, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 8.0}
    ref = pd.Series({"pf": 1.0, "wr": 30.0, "exp_r": 0.05, "max_dd": -5.0, "freq": 8.0,
                      "n_entries": 100, "n_trades": 95})
    ok = False
    try:
        camp._verify_against("BTCUSDT", 2022, 100, 95, m, ref)
    except AssertionError as e:
        ok = "pf:" in str(e) and "esperado=" in str(e) and "obtenido=1.05" in str(e)
    return _p("_verify_against identifica activo/año/campo/esperado/obtenido en el mensaje", ok)


def test_run_campaign_nunca_llega_a_fase_b_si_fase_a_falla():
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


def test_no_hay_run_blind_test_en_el_modulo():
    """Contrato explícito: Raw no define run_blind_test — 2024 no se
    ejecuta bajo ninguna circunstancia en esta campaña."""
    ok = not hasattr(camp, "run_blind_test")
    return _p("El módulo NO define run_blind_test — 2024 no es alcanzable desde este script", ok)


# --------------------------------------------------------------------------- #
# Pipeline completo sobre datos sintéticos                                   #
# --------------------------------------------------------------------------- #
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


def _build_sliced_for(seed=7):
    raw = make_synthetic_raw_1h(seed=seed)
    df_full = build_dc_v1(raw, asset="TESTUSDT", dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)
    df4h_full = bias_camp.resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, camp.BIAS_CANDIDATE)
    return period_slice(df_full, 2022), errs


def test_reason_categorias_son_solo_stop_timeout_sin_tp():
    sliced, errs = _build_sliced_for()
    if sliced.empty:
        return _p("reasons ⊆ {stop, timeout}, sin 'tp' (slice vacío)", False)

    orig_load = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        frame, cfg, entries = camp._entries_for_asset_year("TESTUSDT", 2022)
        trades = backtest.run_config(frame, entries, camp.EXIT_CFG_RAW, cfg)
    finally:
        trigger_camp.load_asset_year = orig_load

    reasons_present = set(trades["reason"].unique()) if not trades.empty else set()
    ok = (not errs) and reasons_present <= {"stop", "timeout"} and "tp" not in reasons_present
    m = backtest.metrics(trades, cfg)
    row = camp._row("TESTUSDT", 2022, entries, trades, m, None, None)
    df_out = camp.results_to_frame([row])
    ok = ok and {"reason_stop", "reason_timeout"} <= set(df_out.columns)
    ok = ok and "reason_tp" not in df_out.columns and "reason_be" not in df_out.columns
    return _p(f"Razones de salida de Raw ⊆ {{stop, timeout}} ({reasons_present}), "
              f"sin categoría 'tp'/'be' — coherente con que este mecanismo no tiene BE/trailing/TP", ok)


def test_full_pipeline_end_to_end_sobre_datos_sinteticos():
    sliced, errs = _build_sliced_for()
    if sliced.empty:
        return _p("pipeline completo corre end-to-end (slice vacío)", False)

    orig_load = trigger_camp.load_asset_year
    orig_ref = camp._v3a_reference
    trigger_camp.load_asset_year = lambda asset, year: sliced

    def _matching_ref(asset, year):
        frame, cfg, entries = camp._entries_for_asset_year(asset, year)
        trades_v3a = backtest.run_config(frame, entries, backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], cfg)
        m_v3a = backtest.metrics(trades_v3a, cfg)
        return pd.Series({**{k: m_v3a[k] for k in camp._CHECK_FIELDS},
                           "n_entries": len(entries), "n_trades": len(trades_v3a)})

    camp._v3a_reference = _matching_ref

    ok = True
    try:
        rows, entry_checks, integrity_rows = camp.run_campaign(assets=("TESTUSDT",), years=(2022,))
        df = camp.results_to_frame(rows)
        ok = (
            not errs
            and len(rows) == 1
            and len(entry_checks) == 1
            and len(integrity_rows) == 1
            and df.iloc[0]["mechanism"] == "Raw"
            and df.iloc[0]["bias"] == "A"
            and df.iloc[0]["trigger"] == "T1_ema_cross"
            and df.iloc[0]["entry"] == "C_market_close"
            and df.iloc[0]["delta_pf_v3a"] is not None
            and integrity_rows[0]["stop_mismatches"] == []
        )
    except AssertionError as e:
        ok = False
        print(f"    (excepción inesperada: {e})")
    finally:
        camp._v3a_reference = orig_ref
        trigger_camp.load_asset_year = orig_load

    return _p("run_campaign() end-to-end (Fase A + Fase B) produce 1 fila, con mechanism/bias/"
              "trigger/entry correctos, deltas vs V3-A pobladas, y sin mismatches de integridad "
              "(stop siempre en sl0)", ok)


ALL_TESTS = [
    test_no_hay_funcion_simulate_propia_en_el_modulo,
    test_tratamiento_usa_backtest_simulate_v3_realmente,
    test_breakeven_nunca_se_activa,
    test_trailing_nunca_se_activa,
    test_stop_nunca_se_mueve_de_sl0,
    test_sin_tp_pese_a_movimiento_extremo,
    test_timeout_respeta_max_hold_20,
    test_distance_es_inalcanzable_no_es_parametro,
    test_candidates_single_value,
    test_fixed_variables_match_contract,
    test_no_risk_override_en_llamadas_a_config,
    test_gate_check_and_summarize_decision_son_los_mismos_objetos,
    test_v3a_reference_lee_el_ancla_real,
    test_e1_reference_lee_los_resultados_reales,
    test_check_entries_vs_e1_detecta_match_y_mismatch,
    test_verify_against_passa_en_match_exacto,
    test_verify_against_revienta_en_mismatch,
    test_run_campaign_nunca_llega_a_fase_b_si_fase_a_falla,
    test_no_hay_run_blind_test_en_el_modulo,
    test_reason_categorias_son_solo_stop_timeout_sin_tp,
    test_full_pipeline_end_to_end_sobre_datos_sinteticos,
]


def main():
    print("scripts/gestion_espacio6_raw_campaign — validación de mecanismo + "
          "contrato + real, Espacio 6 Experimento 3 (Raw)\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
