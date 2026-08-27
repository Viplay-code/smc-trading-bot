"""
research/tests/test_gestion_espacio6_experimento2_be_solo_campaign.py —
Validación de scripts/gestion_espacio6_experimento2_be_solo_campaign.py
(Espacio 6, Experimento 2: BE_solo_1.0R).

Tres categorías de test:
  1. MECANISMO — pruebas directas sobre DataFrames sintéticos construidos a
     mano, llamando a backtest.simulate_v3 (SIN reimplementar) con
     exit_cfg={"be":1.0,"activation":inf,"distance":0.0}: breakeven se
     activa en 1.0R, ausencia de trailing pese a superar el umbral de
     activación de V3-A (comparado directamente contra V3-A real, misma
     vela), ausencia de TP incluso con movimiento extremo, timeout
     respeta max_hold, distance=0.0 es inalcanzable (no un parámetro),
     mfe_r es de solo lectura y no altera la simulación.
  2. CONTRATO — estructura de la campaña: Fase A antes de Fase B,
     comparador único, gate_check/summarize_decision reutilizados,
     columnas delta_*/mfe secundarias, sin categoría "tp".
  3. REAL — lectura de gestion_campaign_session_results.csv (ya
     committeado, no requiere data/raw/) para la referencia de Fase A.

Ejecutar:
    python -m research.tests.test_gestion_espacio6_experimento2_be_solo_campaign  (o con pytest)
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
import scripts.gestion_espacio6_experimento2_be_solo_campaign as camp


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
    """Confirma por inspección de código que el módulo NO define ninguna
    función simulate_* propia — la ablación se logra parametrizando
    simulate_v3, no reimplementándolo."""
    import inspect
    src = inspect.getsource(camp)
    ok = "def simulate_" not in src
    return _p("El módulo no reimplementa ninguna función simulate_* — "
              "reutiliza backtest.simulate_v3 sin modificar", ok)


def test_tratamiento_usa_backtest_simulate_v3_realmente():
    """Monkeypatch de backtest.simulate_v3 con un contador — confirma que
    run_asset_year_target (Fase B) efectivamente invoca la MISMA función
    que usa V3-A, vía backtest.run_config."""
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
        trades = backtest.run_config(df, [entry], camp.EXIT_CFG_BE_SOLO, cfg)
    finally:
        backtest.simulate_v3 = orig

    ok = call_count["n"] == 1 and len(trades) == 1
    return _p(f"run_config con EXIT_CFG_BE_SOLO invoca backtest.simulate_v3 "
              f"({call_count['n']} llamada)", ok)


def test_breakeven_se_activa_en_1r_exacto():
    entry = _mk_entry("long", 100.0, 90.0, 10.0)   # be dispara a fav_r>=1.0 (precio>=110)
    df = _mk_df([
        (100, 101, 99, 100),     # vela 0
        (105, 112, 108, 110),    # vela 1: fav +1.2R -> dispara BE, stop pasa a 100
        (105, 106, 95, 96),      # vela 2: retrocede a 95 (>90, <100) -> si BE activo, cierra en 100
    ])
    res = backtest.simulate_v3(df, entry, camp.EXIT_CFG_BE_SOLO, _cfg())
    ok = res["reason"] == "stop" and abs(res["pnl_r"]) < 0.1   # cierre ~breakeven, no en sl0=90
    return _p(f"Breakeven se activa en 1.0R y mueve el stop a entry (pnl_r≈0, {res['pnl_r']})", ok)


def test_ausencia_de_trailing_comparado_directamente_con_v3a():
    """Mismo camino de precio: V3-A (con trailing) cierra antes por el
    ratchet; BE_solo_1.0R (activation=inf) no ratchea y sigue abierta —
    demuestra que activation=inf impide activar el trailing."""
    entry = _mk_entry("long", 100.0, 90.0, 10.0)
    bars = [
        (100, 101, 99, 100),      # vela 0
        (130, 135, 132, 133),     # vela 1: fav +3.5R -> BE dispara (stop=100);
                                   #   en V3-A también activa trailing (act_lvl=2.0)
                                   #   -> trail_stop = 100+(35-1.0*10) = 125
        (128, 131, 120, 125),     # vela 2: low=120 -> V3-A (stop=125) cierra acá;
                                   #   BE_solo (stop=100) NO cierra, sigue abierta
        (123, 124, 105, 110),     # vela 3: low=105, sigue > 100 -> BE_solo continúa
    ]
    df = _mk_df(bars)
    cfg = _cfg(max_hold=3)

    res_be_solo = backtest.simulate_v3(df, entry, camp.EXIT_CFG_BE_SOLO, cfg)
    res_v3a = backtest.simulate_v3(df, entry, backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], cfg)

    ok = (res_v3a["reason"] == "stop" and res_v3a["exit_time"] == df.index[2]
          and res_be_solo["reason"] == "timeout" and res_be_solo["exit_time"] == df.index[3])
    return _p(f"V3-A cierra en la vela 2 por trailing (reason={res_v3a['reason']}); "
              f"BE_solo_1.0R (activation=inf) sigue abierta y termina en timeout, vela 3 "
              f"(reason={res_be_solo['reason']}) — sin ratchet", ok)


def test_sin_tp_pese_a_movimiento_extremo():
    """Sin importar cuán favorable sea el movimiento, BE_solo_1.0R nunca
    cierra por alcanzar un R objetivo — solo por stop o timeout."""
    entry = _mk_entry("long", 100.0, 90.0, 10.0)
    bars = [
        (100, 101, 99, 100),
        (150, 200, 148, 195),    # fav +10R
        (196, 205, 190, 200),    # sigue favorable, +10.5R, nunca toca stop=100
    ]
    df = _mk_df(bars)
    res = backtest.simulate_v3(df, entry, camp.EXIT_CFG_BE_SOLO, _cfg(max_hold=2))
    ok = res["reason"] == "timeout" and res["pnl_r"] > 9.0   # muy por encima de cualquier TP fijo
    return _p(f"Sin techo de ganancia: la operación llega a timeout con pnl_r={res['pnl_r']} "
              f"(>9R), sin que ningún nivel fijo la haya cerrado antes", ok)


def test_timeout_respeta_max_hold_20():
    entry = _mk_entry("long", 100.0, 90.0, 10.0)   # be dispara recién a high>=110
    # Velas planas por debajo del umbral de breakeven (high<110) y por
    # encima del stop inicial (low>90) — ni BE ni stop se activan, para
    # que la operación llegue genuinamente a timeout.
    bars = [(100, 101, 99, 100)] + [(103, 105, 96, 102)] * 25
    df = _mk_df(bars)
    res = backtest.simulate_v3(df, entry, camp.EXIT_CFG_BE_SOLO, _cfg(max_hold=20))
    ok = res["reason"] == "timeout" and res["exit_time"] == df.index[20]
    return _p(f"max_hold=20 respetado exactamente igual que en V3-A/E1 (exit_time={res['exit_time']})", ok)


def test_distance_es_inalcanzable_no_es_parametro():
    """Con activation=inf, distance nunca se lee — variar su valor no
    debe cambiar el resultado en absoluto, en ningún escenario (incluida
    la ausencia de trailing del test anterior)."""
    entry = _mk_entry("long", 100.0, 90.0, 10.0)
    bars = [
        (100, 101, 99, 100), (130, 135, 132, 133),
        (128, 131, 120, 125), (123, 124, 105, 110),
    ]
    df = _mk_df(bars)
    cfg = _cfg(max_hold=3)
    cfg_variant = {**camp.EXIT_CFG_BE_SOLO, "distance": 999.0}
    res_a = backtest.simulate_v3(df, entry, camp.EXIT_CFG_BE_SOLO, cfg)
    res_b = backtest.simulate_v3(df, entry, cfg_variant, cfg)
    ok = res_a == res_b
    return _p("distance=0.0 es estructuralmente inalcanzable (activation=inf) — cambiar su "
              "valor no altera el resultado, confirmando que NO es un parámetro experimental", ok)


def test_mfe_r_no_altera_la_simulacion():
    """Calcular mfe_r (antes o después, o directamente no calcularlo) no
    debe cambiar en absoluto los trades producidos por run_config."""
    entries = [_mk_entry("long", 100.0, 90.0, 10.0, entry_idx=0),
               _mk_entry("short", 100.0, 110.0, 10.0, entry_idx=2)]
    bars = [
        (100, 101, 99, 100), (95, 96, 85, 90),
        (100, 101, 99, 100), (105, 112, 95, 108),
    ]
    df = _mk_df(bars)
    cfg = _cfg()

    trades_sin_mfe = backtest.run_config(df, [dict(e) for e in entries], camp.EXIT_CFG_BE_SOLO, cfg)
    trades_con_mfe = backtest.run_config(df, [dict(e) for e in entries], camp.EXIT_CFG_BE_SOLO, cfg)
    _ = camp.compute_mfe_r_for_trades(df, entries, trades_con_mfe, cfg)   # se calcula DESPUÉS

    ok = trades_sin_mfe.equals(trades_con_mfe)
    return _p("Calcular mfe_r (posterior, de solo lectura) no altera los trades producidos "
              "por run_config/simulate_v3", ok)


def test_mfe_r_no_muta_entradas_ni_df():
    entries = [_mk_entry("long", 100.0, 90.0, 10.0, entry_idx=0)]
    bars = [(100, 101, 99, 100), (95, 96, 85, 90)]
    df = _mk_df(bars)
    df_copy = df.copy()
    cfg = _cfg()
    import copy
    entries_original = copy.deepcopy(entries)

    trades = backtest.run_config(df, [dict(e) for e in entries], camp.EXIT_CFG_BE_SOLO, cfg)
    camp.compute_mfe_r_for_trades(df, entries, trades, cfg)

    ok = entries == entries_original and df.equals(df_copy)
    return _p("compute_mfe_r_for_trades no muta ni las entradas ni el DataFrame de precios", ok)


def test_mfe_r_es_correcto_sobre_ventana_de_max_hold():
    entry = _mk_entry("long", 100.0, 90.0, 10.0, entry_idx=0)
    bars = [(100, 101, 99, 100), (105, 118, 102, 110), (108, 112, 90.5, 95)]
    df = _mk_df(bars)
    cfg = _cfg(max_hold=2)
    # MFE esperado: max(high) en velas 1-2 = 118 -> (118-100)/10 = 1.8R
    mfe = camp._mfe_r_for_entry(df, entry, cfg)
    ok = mfe == 1.8
    return _p(f"mfe_r calculado correctamente sobre la ventana de max_hold (mfe_r={mfe}, esperado 1.8)", ok)


# --------------------------------------------------------------------------- #
# Contrato — estructura de la campaña                                        #
# --------------------------------------------------------------------------- #
def test_candidates_single_value():
    ok = camp.CANDIDATES == ("BE_solo_1.0R",)
    return _p(f"CANDIDATES tiene una única celda ('BE_solo_1.0R'), sin grid ({camp.CANDIDATES})", ok)


def test_fixed_variables_match_contract():
    ok = (
        camp.ATR_MULT_ANCHOR == 1.5 and camp.ATR_PERIOD_ANCHOR == 14
        and camp.MAX_HOLD_ANCHOR == 20 and camp.TRIGGER_CANDIDATE == "T1_ema_cross"
        and camp.ENTRY_CANDIDATE == "C_market_close" and camp.SESSION_LABEL == "dcv1_activo_15h"
        and camp.BIAS_CANDIDATE == "A" and camp.BE_LVL == 1.0
        and camp.EXIT_CFG_BE_SOLO == {"be": 1.0, "activation": float("inf"), "distance": 0.0}
    )
    return _p("Constantes de variables fijas y EXIT_CFG_BE_SOLO coinciden con el contrato", ok)


def test_be_lvl_coincide_con_ancla_v3a():
    ok = camp.BE_LVL == backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"]["be"]
    return _p("BE_LVL reutiliza literalmente el mismo valor que usa V3-A (be=1.0R), no un valor nuevo", ok)


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


def test_run_integrity_check_pasa_cuando_la_referencia_coincide():
    sliced, errs = _build_sliced_for()
    if sliced.empty:
        return _p("run_integrity_check pasa con referencia exacta (slice vacío)", False)

    orig_load = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        frame, cfg, entries = camp._entries_for_asset_year("TESTUSDT", 2022)
        trades_v3a = backtest.run_config(frame, entries, backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], cfg)
        m_v3a = backtest.metrics(trades_v3a, cfg)
    finally:
        trigger_camp.load_asset_year = orig_load

    ref_row = pd.Series({**{k: m_v3a[k] for k in camp._CHECK_FIELDS},
                          "n_entries": len(entries), "n_trades": len(trades_v3a)})
    orig_ref = camp._v3a_reference
    camp._v3a_reference = lambda asset, year: ref_row
    trigger_camp.load_asset_year = lambda asset, year: sliced
    ok = True
    try:
        camp.run_integrity_check("TESTUSDT", 2022)
    except AssertionError as e:
        ok = False
        print(f"    (excepción inesperada: {e})")
    finally:
        camp._v3a_reference = orig_ref
        trigger_camp.load_asset_year = orig_load

    return _p("run_integrity_check pasa (sin excepción) cuando la referencia V3-A coincide exacto",
              ok and not errs)


def test_run_integrity_check_revienta_con_referencia_incorrecta():
    sliced, errs = _build_sliced_for()
    if sliced.empty:
        return _p("run_integrity_check revienta con referencia incorrecta (slice vacío)", False)

    wrong_ref = pd.Series({"pf": 999.0, "wr": 1.0, "exp_r": 1.0, "max_dd": -1.0,
                            "freq": 1.0, "n_entries": 1, "n_trades": 1})
    orig_load = trigger_camp.load_asset_year
    orig_ref = camp._v3a_reference
    trigger_camp.load_asset_year = lambda asset, year: sliced
    camp._v3a_reference = lambda asset, year: wrong_ref
    ok = False
    try:
        camp.run_integrity_check("TESTUSDT", 2022)
    except AssertionError:
        ok = not errs
    finally:
        camp._v3a_reference = orig_ref
        trigger_camp.load_asset_year = orig_load

    return _p("run_integrity_check revienta con AssertionError si la referencia V3-A NO coincide", ok)


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


def test_reason_categorias_son_solo_stop_timeout_sin_tp():
    sliced, errs = _build_sliced_for()
    if sliced.empty:
        return _p("reasons ⊆ {stop, timeout}, sin 'tp' (slice vacío)", False)

    orig_load = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        frame, cfg, entries = camp._entries_for_asset_year("TESTUSDT", 2022)
        trades = backtest.run_config(frame, entries, camp.EXIT_CFG_BE_SOLO, cfg)
    finally:
        trigger_camp.load_asset_year = orig_load

    reasons_present = set(trades["reason"].unique()) if not trades.empty else set()
    ok = (not errs) and reasons_present <= {"stop", "timeout"} and "tp" not in reasons_present
    m = backtest.metrics(trades, cfg)
    mfe_rs = camp.compute_mfe_r_for_trades(frame, entries, trades, cfg)
    row = camp._row("TESTUSDT", 2022, entries, trades, m, None, mfe_rs)
    df_out = camp.results_to_frame([row])
    ok = ok and {"reason_stop", "reason_timeout"} <= set(df_out.columns)
    ok = ok and "reason_tp" not in df_out.columns
    return _p(f"Razones de salida de BE_solo_1.0R ⊆ {{stop, timeout}} ({reasons_present}), "
              f"sin categoría 'tp' — coherente con que este mecanismo no tiene TP", ok)


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
        rows = camp.run_campaign(assets=("TESTUSDT",), years=(2022,))
        df = camp.results_to_frame(rows)
        ok = (
            not errs
            and len(rows) == 1
            and df.iloc[0]["mechanism"] == "BE_solo_1.0R"
            and df.iloc[0]["bias"] == "A"
            and df.iloc[0]["trigger"] == "T1_ema_cross"
            and df.iloc[0]["entry"] == "C_market_close"
            and df.iloc[0]["delta_pf"] is not None
            and "mean_mfe_r_winners" in df.columns
            and "gap_avg_win_mfe" in df.columns
        )
    except AssertionError as e:
        ok = False
        print(f"    (excepción inesperada: {e})")
    finally:
        camp._v3a_reference = orig_ref
        trigger_camp.load_asset_year = orig_load

    return _p("run_campaign() end-to-end (Fase A + Fase B) produce 1 fila, con mechanism/bias/"
              "trigger/entry correctos, deltas y diagnóstico mfe poblados", ok)


def test_run_blind_test_exige_candidato_congelado():
    ok = True
    try:
        camp.run_blind_test(candidate=None)
        ok = False
    except ValueError:
        pass
    try:
        camp.run_blind_test(candidate="otro_mecanismo")
        ok = False
    except ValueError:
        pass
    return _p("run_blind_test exige --candidate en CANDIDATES antes de tocar data/raw/", ok)


ALL_TESTS = [
    test_no_hay_funcion_simulate_propia_en_el_modulo,
    test_tratamiento_usa_backtest_simulate_v3_realmente,
    test_breakeven_se_activa_en_1r_exacto,
    test_ausencia_de_trailing_comparado_directamente_con_v3a,
    test_sin_tp_pese_a_movimiento_extremo,
    test_timeout_respeta_max_hold_20,
    test_distance_es_inalcanzable_no_es_parametro,
    test_mfe_r_no_altera_la_simulacion,
    test_mfe_r_no_muta_entradas_ni_df,
    test_mfe_r_es_correcto_sobre_ventana_de_max_hold,
    test_candidates_single_value,
    test_fixed_variables_match_contract,
    test_be_lvl_coincide_con_ancla_v3a,
    test_no_risk_override_en_llamadas_a_config,
    test_gate_check_and_summarize_decision_son_los_mismos_objetos,
    test_v3a_reference_lee_el_ancla_real,
    test_verify_against_passa_en_match_exacto,
    test_verify_against_revienta_en_mismatch,
    test_run_integrity_check_pasa_cuando_la_referencia_coincide,
    test_run_integrity_check_revienta_con_referencia_incorrecta,
    test_run_campaign_nunca_llega_a_fase_b_si_fase_a_falla,
    test_reason_categorias_son_solo_stop_timeout_sin_tp,
    test_full_pipeline_end_to_end_sobre_datos_sinteticos,
    test_run_blind_test_exige_candidato_congelado,
]


def main():
    print("scripts/gestion_espacio6_experimento2_be_solo_campaign — validación de mecanismo + "
          "contrato + real, Espacio 6 Experimento 2\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
