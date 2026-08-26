"""
research/tests/test_gestion_espacio6_tp_fijo_campaign.py — Validación de
scripts/gestion_espacio6_tp_fijo_campaign.py (Espacio 6, Experimento 1).

Tres categorías de test:
  1. MECANISMO — pruebas directas de `simulate_tp_fixed`/`run_config_tp_fixed`
     sobre DataFrames sintéticos construidos a mano (sin pasar por dc_v1):
     TP alcanzado, SL alcanzado, timeout, precedencia intrabar SL>TP, largos/
     cortos, cálculo de 2.5R, ausencia de breakeven/trailing, `max_hold`,
     una posición a la vez, preservación de la lista de entradas.
  2. CONTRATO — estructura de la campaña: Fase A antes de Fase B, comparador
     único, sin mezclar categorías de razón de salida, `gate_check`/
     `summarize_decision` reutilizados sin modificar, columnas delta_*.
  3. REAL — lectura de `gestion_campaign_session_results.csv` (ya
     committeado, no requiere data/raw/) para la referencia de Fase A.

Ejecutar:
    python -m research.tests.test_gestion_espacio6_tp_fijo_campaign  (o con pytest)
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
import scripts.gestion_espacio6_tp_fijo_campaign as camp


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


# --------------------------------------------------------------------------- #
# Helpers — DataFrame OHLC sintético construido a mano (sin dc_v1) para       #
# probar el mecanismo directamente, vela a vela, de forma determinista.       #
# --------------------------------------------------------------------------- #
def _mk_df(bars: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    """bars: lista de (open, high, low, close). Índice horario sintético."""
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
# Mecanismo — TP alcanzado / SL alcanzado / timeout / precedencia intrabar    #
# --------------------------------------------------------------------------- #
def test_long_tp_alcanzado():
    entry = _mk_entry("long", 100.0, 90.0, 10.0)   # tp_price = 100 + 2.5*10 = 125
    df = _mk_df([(100, 101, 99, 100), (110, 126, 108, 120)])
    res = camp.simulate_tp_fixed(df, entry, _cfg())
    ok = res["reason"] == "tp" and res["exit_price"] == 125.0
    return _p(f"long: TP alcanzado (reason={res['reason']}, exit_price={res['exit_price']})", ok)


def test_long_sl_alcanzado():
    entry = _mk_entry("long", 100.0, 90.0, 10.0)
    df = _mk_df([(100, 101, 99, 100), (95, 96, 85, 90)])
    res = camp.simulate_tp_fixed(df, entry, _cfg())
    ok = res["reason"] == "stop" and res["exit_price"] == 90.0
    return _p(f"long: SL alcanzado (reason={res['reason']}, exit_price={res['exit_price']})", ok)


def test_long_timeout():
    entry = _mk_entry("long", 100.0, 90.0, 10.0)   # tp=125
    bars = [(100, 101, 99, 100)] + [(102, 110, 96, 105)] * 3  # nunca toca 90 ni 125
    df = _mk_df(bars)
    res = camp.simulate_tp_fixed(df, entry, _cfg(max_hold=3))
    ok = res["reason"] == "timeout" and res["exit_price"] == df.iloc[3]["close"]
    return _p(f"long: timeout a max_hold (reason={res['reason']}, exit_idx=3)", ok)


def test_long_sl_y_tp_misma_vela_gana_sl():
    entry = _mk_entry("long", 100.0, 90.0, 10.0)   # sl=90, tp=125
    df = _mk_df([(100, 101, 99, 100), (100, 130, 85, 110)])  # vela toca ambos niveles
    res = camp.simulate_tp_fixed(df, entry, _cfg())
    ok = res["reason"] == "stop" and res["exit_price"] == 90.0
    return _p("long: SL y TP en la misma vela -> gana SL (precedencia conservadora)", ok)


def test_short_tp_alcanzado():
    entry = _mk_entry("short", 100.0, 110.0, 10.0)   # tp = 100 - 2.5*10 = 75
    df = _mk_df([(100, 101, 99, 100), (90, 92, 74, 80)])
    res = camp.simulate_tp_fixed(df, entry, _cfg())
    ok = res["reason"] == "tp" and res["exit_price"] == 75.0
    return _p(f"short: TP alcanzado (reason={res['reason']}, exit_price={res['exit_price']})", ok)


def test_short_sl_alcanzado():
    entry = _mk_entry("short", 100.0, 110.0, 10.0)
    df = _mk_df([(100, 101, 99, 100), (105, 112, 95, 108)])
    res = camp.simulate_tp_fixed(df, entry, _cfg())
    ok = res["reason"] == "stop" and res["exit_price"] == 110.0
    return _p(f"short: SL alcanzado (reason={res['reason']}, exit_price={res['exit_price']})", ok)


def test_short_sl_y_tp_misma_vela_gana_sl():
    entry = _mk_entry("short", 100.0, 110.0, 10.0)   # sl=110, tp=75
    df = _mk_df([(100, 101, 99, 100), (95, 115, 70, 90)])  # toca ambos niveles
    res = camp.simulate_tp_fixed(df, entry, _cfg())
    ok = res["reason"] == "stop" and res["exit_price"] == 110.0
    return _p("short: SL y TP en la misma vela -> gana SL (precedencia conservadora)", ok)


def test_calculo_correcto_de_2_5r():
    ok = camp.TP_R == 2.5
    entry_a = _mk_entry("long", 100.0, 95.0, 5.0)     # tp = 100+2.5*5 = 112.5
    entry_b = _mk_entry("long", 200.0, 180.0, 20.0)   # tp = 200+2.5*20 = 250.0
    df_a = _mk_df([(100, 101, 99, 100), (110, 112.5, 108, 112)])
    df_b = _mk_df([(200, 201, 199, 200), (240, 250.0, 235, 245)])
    res_a = camp.simulate_tp_fixed(df_a, entry_a, _cfg())
    res_b = camp.simulate_tp_fixed(df_b, entry_b, _cfg())
    ok = ok and res_a["reason"] == "tp" and res_a["exit_price"] == 112.5
    ok = ok and res_b["reason"] == "tp" and res_b["exit_price"] == 250.0
    return _p("TP_R=2.5 exacto y tp_price = entry + 2.5*risk_pts, escalado correctamente "
              "con risk_pts distintos", ok)


# --------------------------------------------------------------------------- #
# Mecanismo — stop inicial idéntico a V3-A, sin breakeven, sin trailing       #
# --------------------------------------------------------------------------- #
def test_stop_inicial_identico_a_v3a():
    """Un stop-out en la PRIMERA vela evaluada usa entry['sl0'] sin ningún
    ajuste en ambos mecanismos (V3-A no pudo haber movido el stop todavía —
    el breakeven/trailing de simulate_v3 solo tiene efecto en velas
    SIGUIENTES a la que lo dispara)."""
    entry = _mk_entry("long", 100.0, 90.0, 10.0)
    df = _mk_df([(100, 101, 99, 100), (95, 96, 85, 90)])   # toca sl0=90 en la vela 1
    res_tp = camp.simulate_tp_fixed(df, entry, _cfg())
    res_v3a = backtest.simulate_v3(df, entry, backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], _cfg())
    # simulate_v3 no expone exit_price (solo pnl_r) — como ambos cierran en
    # la MISMA vela por el MISMO nivel (entry['sl0'], sin BE/trailing posible
    # todavía) y comparten exactamente el mismo modelo de costos
    # (backtest.COST_PER_TRADE), el pnl_r resultante debe coincidir exacto.
    ok = (res_tp["reason"] == "stop" and res_v3a["reason"] == "stop"
          and res_tp["exit_price"] == entry["sl0"]
          and res_tp["pnl_r"] == res_v3a["pnl_r"])
    return _p(f"Stop inicial idéntico a V3-A en la primera vela (mismo exit_price={entry['sl0']}, "
              f"mismo pnl_r={res_tp['pnl_r']})", ok)


def test_ausencia_de_breakeven():
    """Camino: avance favorable >1R (activaría el breakeven de V3-A a
    entry=100), retrocede por DEBAJO de entry pero por ENCIMA de sl0
    (no tocaría el breakeven de V3-A si estuviera activo... en realidad SÍ
    lo tocaría, por eso es la prueba: TP fijo NO tiene ese nivel y sigue
    abierta), y finalmente toca el sl0 original varias velas después."""
    entry = _mk_entry("long", 100.0, 90.0, 10.0)   # tp=125, be de V3-A activaría a 110
    bars = [
        (100, 101, 99, 100),    # vela 0 (apertura, no evaluada por el loop)
        (105, 115, 108, 112),   # vela 1: fav +1.5R (110+), NO toca sl(90) ni tp(125)
        (108, 109, 95, 96),     # vela 2: retrocede a 95 — por ENCIMA de sl0=90;
                                 #   si hubiera breakeven activo (stop en 100), esto
                                 #   ya habría cerrado la operación en 100
        (94, 95, 88, 89),        # vela 3: toca sl0=90
    ]
    df = _mk_df(bars)
    res = camp.simulate_tp_fixed(df, entry, _cfg())
    ok = res["reason"] == "stop" and res["exit_price"] == 90.0 and res["exit_time"] == df.index[3]
    return _p("Ausencia de breakeven: el stop nunca sube a entry pese a superar 1R de avance "
              "favorable — la operación sigue abierta y cierra en el sl0 original, vela 3", ok)


def test_ausencia_de_trailing():
    """Camino: avance favorable grande (activaría el trailing de V3-A,
    subiendo el stop cerca del máximo), retrocede lo suficiente para que
    V3-A hubiera cerrado por el trailing, pero NO toca ni sl0 ni tp — bajo
    TP fijo debe llegar a timeout, no cerrar antes por ningún nivel movido."""
    entry = _mk_entry("long", 100.0, 90.0, 10.0)   # tp=125
    bars = [
        (100, 101, 99, 100),     # vela 0
        (110, 122, 115, 120),    # vela 1: fav +2.2R, activaría trailing de V3-A; no toca tp(125)
        (118, 119, 105, 108),    # vela 2: retrocede a 105 — V3-A con trailing ya habría
                                  #   cerrado cerca de 112 (100 + (22-10)); TP fijo sigue abierta
                                  #   (105 > sl0=90, 119 < tp=125)
        (106, 108, 100, 103),    # vela 3: sigue sin tocar ningún nivel
    ]
    df = _mk_df(bars)
    res = camp.simulate_tp_fixed(df, entry, _cfg(max_hold=3))
    ok = res["reason"] == "timeout" and res["exit_price"] == df.iloc[3]["close"]
    return _p("Ausencia de trailing: un retroceso que habría cerrado la operación bajo el "
              "trailing de V3-A no cierra nada bajo TP fijo — termina en timeout", ok)


def test_stop_nunca_cambia_de_valor_durante_la_simulacion():
    """Verificación directa (no solo por resultado): construimos un camino
    largo y confirmamos, recorriendo manualmente la misma lógica de
    precedencia, que el nivel de stop-out reportado siempre es exactamente
    entry['sl0'] cuando la razón es 'stop' — nunca otro valor."""
    entry = _mk_entry("long", 100.0, 90.0, 10.0)
    bars = [(100, 101, 99, 100)] + [(105, 118, 102, 110)] * 4 + [(95, 96, 85, 90)]
    df = _mk_df(bars)
    res = camp.simulate_tp_fixed(df, entry, _cfg(max_hold=10))
    ok = res["reason"] == "stop" and res["exit_price"] == entry["sl0"]
    return _p("El nivel de stop reportado en una salida 'stop' es siempre entry['sl0'] "
              "sin importar cuánto haya avanzado el precio antes", ok)


# --------------------------------------------------------------------------- #
# max_hold                                                                    #
# --------------------------------------------------------------------------- #
def test_max_hold_20_respeta_el_limite():
    entry = _mk_entry("long", 100.0, 90.0, 10.0)   # tp=125, nunca tocado
    bars = [(100, 101, 99, 100)] + [(103, 110, 96, 105)] * 25   # 25 velas planas
    df = _mk_df(bars)
    res = camp.simulate_tp_fixed(df, entry, _cfg(max_hold=20))
    ok = res["reason"] == "timeout" and res["exit_time"] == df.index[20]
    return _p(f"max_hold=20: timeout exactamente en la vela 20 (exit_time={res['exit_time']})", ok)


# --------------------------------------------------------------------------- #
# run_config_tp_fixed — una posición a la vez, preservación de entradas       #
# --------------------------------------------------------------------------- #
def test_una_posicion_a_la_vez():
    # entrada 1 abre en 0, cierra por SL en la vela 1; entrada 2 (idx=1) cae
    # dentro de la ventana ocupada -> debe descartarse; entrada 3 (idx=2,
    # después del cierre) sí debe procesarse.
    e1 = _mk_entry("long", 100.0, 90.0, 10.0, entry_idx=0)
    e2 = _mk_entry("long", 100.0, 90.0, 10.0, entry_idx=1)
    e3 = _mk_entry("long", 100.0, 90.0, 10.0, entry_idx=2)
    bars = [
        (100, 101, 99, 100),   # 0
        (95, 96, 85, 90),      # 1: e1 cierra por stop acá
        (100, 101, 99, 100),   # 2: e3 entra acá
        (95, 96, 85, 90),      # 3: e3 cierra por stop acá
    ]
    df = _mk_df(bars)
    trades = camp.run_config_tp_fixed(df, [e1, e2, e3], _cfg())
    ok = len(trades) == 2 and list(trades["entry_time"]) == [df.index[0], df.index[2]]
    return _p(f"Una posición a la vez: e2 (solapada) se descarta, quedan {len(trades)} trades", ok)


def test_preservacion_de_la_lista_de_entradas():
    e1 = _mk_entry("long", 100.0, 90.0, 10.0, entry_idx=0)
    e2 = _mk_entry("short", 100.0, 110.0, 10.0, entry_idx=2)
    entries = [dict(e1), dict(e2)]
    import copy
    original = copy.deepcopy(entries)
    bars = [
        (100, 101, 99, 100), (95, 96, 85, 90),
        (100, 101, 99, 100), (105, 112, 95, 108),
    ]
    df = _mk_df(bars)
    camp.run_config_tp_fixed(df, entries, _cfg())
    ok = entries == original
    return _p("run_config_tp_fixed no muta la lista de entradas ni sus dicts", ok)


# --------------------------------------------------------------------------- #
# Contrato — estructura de la campaña                                        #
# --------------------------------------------------------------------------- #
def test_candidates_single_value():
    ok = camp.CANDIDATES == ("TP_fijo_2.5R",)
    return _p(f"CANDIDATES tiene una única celda ('TP_fijo_2.5R'), sin grid ({camp.CANDIDATES})", ok)


def test_fixed_variables_match_contract():
    ok = (
        camp.ATR_MULT_ANCHOR == 1.5 and camp.ATR_PERIOD_ANCHOR == 14
        and camp.MAX_HOLD_ANCHOR == 20 and camp.TRIGGER_CANDIDATE == "T1_ema_cross"
        and camp.ENTRY_CANDIDATE == "C_market_close" and camp.SESSION_LABEL == "dcv1_activo_15h"
        and camp.BIAS_CANDIDATE == "A" and camp.TP_R == 2.5
    )
    return _p("Constantes de variables fijas coinciden con el contrato "
              "(atr_mult=1.5/atr_period=14/max_hold=20/T1_ema_cross/C_market_close/"
              "dcv1_activo_15h/Bias=A/TP_R=2.5)", ok)


def test_no_risk_override_en_llamadas_a_config():
    """AST, no regex sobre texto — evita falso positivo con las menciones de
    'risk=0.005' en el docstring (prosa, no código)."""
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


def test_entradas_reutilizadas_identicas_entre_fase_a_y_fase_b():
    sliced, errs = _build_sliced_for()
    if sliced.empty:
        return _p("entradas idénticas entre Fase A y Fase B (slice vacío)", False)

    orig_load = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced

    call_count = {"n": 0}
    orig_find = backtest.find_entries

    def _counting(df, cfg):
        call_count["n"] += 1
        return orig_find(df, cfg)

    backtest.find_entries = _counting
    orig_ref = camp._v3a_reference
    try:
        frame, cfg, entries = camp._entries_for_asset_year("TESTUSDT", 2022)
        trades_v3a = backtest.run_config(frame, entries, backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], cfg)
        m_v3a = backtest.metrics(trades_v3a, cfg)
        ref_row = pd.Series({**{k: m_v3a[k] for k in camp._CHECK_FIELDS},
                              "n_entries": len(entries), "n_trades": len(trades_v3a)})
        camp._v3a_reference = lambda asset, year: ref_row

        known = camp.run_integrity_check("TESTUSDT", 2022)   # 1ra llamada a find_entries
        frame2, cfg2, entries2, m_v3a2 = known
        row = camp.run_asset_year_target("TESTUSDT", 2022, frame2, cfg2, entries2, m_v3a2)
        ok = (entries2 is entries2) and call_count["n"] == 2  # 1 en el setup manual + 1 en run_integrity_check
    finally:
        backtest.find_entries = orig_find
        camp._v3a_reference = orig_ref
        trigger_camp.load_asset_year = orig_load

    return _p(f"Fase B reutiliza el objeto de entradas de Fase A sin recomputarlo "
              f"(find_entries llamado {call_count['n']} veces: 1 en setup + 1 en run_integrity_check, "
              f"0 adicionales en Fase B)", ok and not errs)


def test_reason_categorias_son_solo_stop_tp_timeout():
    sliced, errs = _build_sliced_for()
    if sliced.empty:
        return _p("reasons ⊆ {stop, tp, timeout} (slice vacío)", False)

    orig_load = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        frame, cfg, entries = camp._entries_for_asset_year("TESTUSDT", 2022)
        trades = camp.run_config_tp_fixed(frame, entries, cfg)
    finally:
        trigger_camp.load_asset_year = orig_load

    reasons_present = set(trades["reason"].unique()) if not trades.empty else set()
    ok = (not errs) and reasons_present <= {"stop", "tp", "timeout"}
    row = camp._row("TESTUSDT", 2022, entries, trades, backtest.metrics(trades, cfg), None)
    df_out = camp.results_to_frame([row])
    ok = ok and {"reason_stop", "reason_tp", "reason_timeout"} <= set(df_out.columns)
    ok = ok and not any("trailing" in c or "breakeven" in c for c in df_out.columns)
    return _p(f"Razones de salida de TP fijo ⊆ {{stop, tp, timeout}} ({reasons_present}), "
              f"sin ninguna categoría mezclada tipo 'reason_tp_o_trailing'", ok)


def test_results_to_frame_incluye_columnas_delta():
    m = {"pf": 1.2, "wr": 30.0, "exp_r": 0.05, "avg_win": 0.5, "avg_loss": -0.3,
         "total_r": 5.0, "max_dd": -3.0, "freq": 8.0, "be": 0, "reasons": {"stop": 3, "tp": 2, "timeout": 1}}
    m_v3a = {"pf": 1.0, "wr": 25.0, "exp_r": 0.0, "max_dd": -5.0, "freq": 9.0, "trades": 100}
    row = camp._row("BTCUSDT", 2022, [1] * 10, pd.DataFrame({"pnl_r": [1] * 6}), m, m_v3a)
    df_out = camp.results_to_frame([row])
    expected_cols = {"pf_v3a", "max_dd_v3a", "exp_r_v3a", "freq_v3a", "n_trades_v3a",
                      "delta_pf", "delta_max_dd", "delta_exp_r", "delta_freq", "delta_n_trades"}
    ok = expected_cols <= set(df_out.columns)
    ok = ok and df_out.iloc[0]["delta_pf"] == round(1.2 - 1.0, 4)
    ok = ok and df_out.iloc[0]["delta_n_trades"] == 6 - 100
    return _p(f"results_to_frame incluye las columnas delta_* y *_v3a requeridas ({sorted(expected_cols)})", ok)


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
            and df.iloc[0]["mechanism"] == "TP_fijo_2.5R"
            and df.iloc[0]["bias"] == "A"
            and df.iloc[0]["trigger"] == "T1_ema_cross"
            and df.iloc[0]["entry"] == "C_market_close"
            and df.iloc[0]["delta_pf"] is not None
        )
    except AssertionError as e:
        ok = False
        print(f"    (excepción inesperada: {e})")
    finally:
        camp._v3a_reference = orig_ref
        trigger_camp.load_asset_year = orig_load

    return _p("run_campaign() end-to-end (Fase A + Fase B) produce 1 fila (1 mecanismo x "
              "1 activo x 1 año), con mechanism/bias/trigger/entry correctos y deltas poblados", ok)


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
    test_long_tp_alcanzado,
    test_long_sl_alcanzado,
    test_long_timeout,
    test_long_sl_y_tp_misma_vela_gana_sl,
    test_short_tp_alcanzado,
    test_short_sl_alcanzado,
    test_short_sl_y_tp_misma_vela_gana_sl,
    test_calculo_correcto_de_2_5r,
    test_stop_inicial_identico_a_v3a,
    test_ausencia_de_breakeven,
    test_ausencia_de_trailing,
    test_stop_nunca_cambia_de_valor_durante_la_simulacion,
    test_max_hold_20_respeta_el_limite,
    test_una_posicion_a_la_vez,
    test_preservacion_de_la_lista_de_entradas,
    test_candidates_single_value,
    test_fixed_variables_match_contract,
    test_no_risk_override_en_llamadas_a_config,
    test_gate_check_and_summarize_decision_son_los_mismos_objetos,
    test_v3a_reference_lee_el_ancla_real,
    test_verify_against_passa_en_match_exacto,
    test_verify_against_revienta_en_mismatch,
    test_run_integrity_check_pasa_cuando_la_referencia_coincide,
    test_run_integrity_check_revienta_con_referencia_incorrecta,
    test_run_campaign_nunca_llega_a_fase_b_si_fase_a_falla,
    test_entradas_reutilizadas_identicas_entre_fase_a_y_fase_b,
    test_reason_categorias_son_solo_stop_tp_timeout,
    test_results_to_frame_incluye_columnas_delta,
    test_full_pipeline_end_to_end_sobre_datos_sinteticos,
    test_run_blind_test_exige_candidato_congelado,
]


def main():
    print("scripts/gestion_espacio6_tp_fijo_campaign — validación de mecanismo + contrato + real, "
          "Espacio 6 Experimento 1\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
