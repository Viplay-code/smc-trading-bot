"""
research/tests/test_gestion_espacio6_v3a_tp_campaign.py — Validación de
scripts/gestion_espacio6_v3a_tp_campaign.py (Espacio 6, Experimento 4:
V3-A + TP 2.5R).

Cuatro categorías de test:
  1. EQUIVALENCIA — la prueba central de este experimento: con tp_r
     inalcanzable, simulate_v3_tp reproduce trade-por-trade
     backtest.simulate_v3 bajo V3-A (mismo BE, mismo trailing, mismo
     timeout, mismos costos) — confirma ejecutablemente que la única
     diferencia real respecto de V3-A es el TP.
  2. MECANISMO — TP se activa en 2.5R, precedencia stop-gana-si-empatan,
     BE/trailing siguen funcionando igual que en V3-A cuando el TP no se
     alcanza, timeout respeta max_hold.
  3. CONTRATO — estructura de la campaña: Fase A, tres comparadores
     (V3-A/E1/Raw), gate_check/summarize_decision reutilizados.
  4. REAL — lectura de las 3 referencias ya committeadas.

Ejecutar:
    python -m research.tests.test_gestion_espacio6_v3a_tp_campaign  (o con pytest)
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
import scripts.gestion_espacio6_v3a_tp_campaign as camp


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def _mk_df(bars):
    idx = pd.date_range("2022-01-01", periods=len(bars), freq="1h", tz="UTC")
    o, h, l, c = zip(*bars)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=idx)


def _mk_entry(direction, entry, sl0, risk_pts, entry_idx=0):
    return {"entry_idx": entry_idx, "direction": direction, "entry": entry,
            "sl0": sl0, "risk_pts": risk_pts}


def _cfg(max_hold=20):
    return backtest.Config(max_hold=max_hold)


# --------------------------------------------------------------------------- #
# Equivalencia — la prueba central del experimento                          #
# --------------------------------------------------------------------------- #
def test_equivalencia_con_v3a_cuando_tp_es_inalcanzable():
    """Con tp_r gigante (nunca alcanzable dentro de max_hold), simulate_v3_tp
    debe producir EXACTAMENTE el mismo trade que backtest.simulate_v3 bajo
    V3-A, sobre varios caminos de precio distintos — prueba ejecutable de
    que la única diferencia real es el TP."""
    v3a = backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"]
    casos = [
        # (entry, bars)
        (_mk_entry("long", 100.0, 90.0, 10.0),
         [(100, 101, 99, 100), (105, 112, 108, 110), (105, 106, 95, 96)]),
        (_mk_entry("long", 100.0, 90.0, 10.0),
         [(100, 101, 99, 100), (130, 135, 132, 133), (128, 131, 120, 125), (123, 124, 105, 110)]),
        (_mk_entry("short", 100.0, 110.0, 10.0),
         [(100, 101, 99, 100), (95, 98, 85, 90), (88, 90, 80, 85)]),
        (_mk_entry("long", 100.0, 90.0, 10.0),
         [(100, 101, 99, 100)] + [(103, 105, 96, 102)] * 25),
    ]
    ok = True
    for entry, bars in casos:
        df = _mk_df(bars)
        cfg = _cfg(max_hold=len(bars) - 1)
        res_v3a = backtest.simulate_v3(df, dict(entry), v3a, cfg)
        res_tp = camp.simulate_v3_tp(df, dict(entry), v3a, cfg, tp_r=1e9)
        same = (res_v3a["reason"] == res_tp["reason"]
                and res_v3a["exit_time"] == res_tp["exit_time"]
                and res_v3a["pnl_r"] == res_tp["pnl_r"])
        ok = ok and same
        if not same:
            print(f"    mismatch: v3a={res_v3a} tp={res_tp}")
    return _p("simulate_v3_tp con tp_r inalcanzable reproduce EXACTO backtest.simulate_v3 "
              "(BE/trailing/timeout/costos idénticos) en 4 caminos de precio distintos", ok)


def test_no_modifica_simulate_v3():
    """Confirma por inspección de código que el módulo no reasigna
    backtest.simulate_v3 ni lo redefine — solo agrega una función nueva."""
    import inspect
    src = inspect.getsource(camp)
    ok = "backtest.simulate_v3 =" not in src and "def simulate_v3(" not in src
    return _p("El módulo NO modifica backtest.simulate_v3 — define simulate_v3_tp como "
              "función nueva y separada", ok)


# --------------------------------------------------------------------------- #
# Mecanismo — TP + BE + trailing conviviendo                                #
# --------------------------------------------------------------------------- #
def test_tp_se_activa_en_2_5r_exacto():
    entry = _mk_entry("long", 100.0, 90.0, 10.0)   # TP = 100 + 2.5*10 = 125
    bars = [
        (100, 101, 99, 100),
        (105, 112, 108, 110),    # fav +1.2R -> BE dispara
        (120, 126, 118, 124),    # high=126 >= 125 -> TP hit
    ]
    df = _mk_df(bars)
    res = camp.simulate_v3_tp(df, entry, backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], _cfg(max_hold=2))
    ok = res["reason"] == "tp" and res["exit_time"] == df.index[2]
    return _p(f"TP se activa exactamente en 2.5R (reason={res['reason']}, exit_time correcto)", ok)


def test_stop_gana_si_stop_y_tp_caen_en_la_misma_vela():
    """Precedencia conservadora: si low<=stop Y high>=tp en la misma vela,
    gana el stop (se testea primero, con break inmediato)."""
    entry = _mk_entry("long", 100.0, 90.0, 10.0)   # stop=90, TP=125
    bars = [
        (100, 101, 99, 100),
        (105, 112, 108, 110),     # BE dispara, stop->100
        (105, 130, 89, 128),      # low=89<=100(stop tras BE) Y high=128>=125(TP) misma vela
    ]
    df = _mk_df(bars)
    res = camp.simulate_v3_tp(df, entry, backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], _cfg(max_hold=2))
    ok = res["reason"] == "stop"
    return _p(f"Cuando stop y TP caen en la misma vela, gana el STOP (reason={res['reason']})", ok)


def test_be_y_trailing_funcionan_igual_que_v3a_cuando_no_hay_tp():
    """Con tp_r inalcanzable, un camino de precio que activa BE y luego
    trailing debe comportarse EXACTO a V3-A (ya cubierto por el test de
    equivalencia, pero acá se verifica explícitamente el mecanismo de
    trailing con un TP alcanzable pero no tocado en este camino)."""
    entry = _mk_entry("long", 100.0, 90.0, 10.0)   # TP=125, muy por encima del pico de este camino
    bars = [
        (100, 101, 99, 100),
        (105, 112, 108, 110),     # fav +1.2R -> BE
        (112, 118, 111, 116),     # fav +1.8R -> aun no act_lvl=2.0
        (116, 121, 114, 119),     # fav +2.1R -> trailing activa; trail_stop=100+(21-10)=111
        (118, 119, 108, 110),     # low=108 <= 111(trail_stop) -> stop-out por trailing
    ]
    df = _mk_df(bars)
    res = camp.simulate_v3_tp(df, entry, backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], _cfg(max_hold=4))
    ok = res["reason"] == "stop" and res["exit_time"] == df.index[4]
    return _p(f"BE+trailing funcionan igual que V3-A cuando el TP (125) nunca se alcanza "
              f"(reason={res['reason']}, cierre por trailing en vela 4)", ok)


def test_timeout_respeta_max_hold_20():
    entry = _mk_entry("long", 100.0, 90.0, 10.0)
    bars = [(100, 101, 99, 100)] + [(103, 105, 96, 102)] * 25
    df = _mk_df(bars)
    res = camp.simulate_v3_tp(df, entry, backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], _cfg(max_hold=20))
    ok = res["reason"] == "timeout" and res["exit_time"] == df.index[20]
    return _p(f"max_hold=20 respetado exactamente igual que V3-A/E1/E2/Raw (exit_time={res['exit_time']})", ok)


# --------------------------------------------------------------------------- #
# Contrato                                                                    #
# --------------------------------------------------------------------------- #
def test_candidates_single_value():
    ok = camp.CANDIDATES == ("V3A_mas_TP_2.5R",)
    return _p(f"CANDIDATES tiene una única celda ({camp.CANDIDATES})", ok)


def test_fixed_variables_match_contract():
    ok = (
        camp.ATR_MULT_ANCHOR == 1.5 and camp.ATR_PERIOD_ANCHOR == 14
        and camp.MAX_HOLD_ANCHOR == 20 and camp.TRIGGER_CANDIDATE == "T1_ema_cross"
        and camp.ENTRY_CANDIDATE == "C_market_close" and camp.SESSION_LABEL == "dcv1_activo_15h"
        and camp.BIAS_CANDIDATE == "A" and camp.TP_R == 2.5
        and camp.V3A_EXIT_CFG == {"be": 1.0, "activation": 2.0, "distance": 1.0}
    )
    return _p("Constantes de variables fijas, TP_R y V3A_EXIT_CFG coinciden con el contrato "
              "(BE/trailing IDÉNTICOS a V3-A)", ok)


def test_tp_r_coincide_con_e1():
    import scripts.gestion_espacio6_tp_fijo_campaign as e1_camp
    ok = camp.TP_R == e1_camp.TP_R == 2.5
    return _p("TP_R reutiliza literalmente el mismo valor que E1 (2.5R), no un valor nuevo", ok)


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


def test_no_hay_run_blind_test():
    ok = not hasattr(camp, "run_blind_test")
    return _p("El módulo NO define run_blind_test — 2024 no es alcanzable desde este script", ok)


def test_v3a_reference_lee_el_ancla_real():
    ref = camp._v3a_reference("BTCUSDT", 2022)
    ok = ref["pf"] == 0.681 and ref["n_entries"] == 119 and ref["n_trades"] == 115
    return _p(f"_v3a_reference lee la fila real publicada (BTCUSDT/2022, pf={ref['pf']})", ok)


def test_e1_y_raw_reference_leen_resultados_reales():
    e1 = camp._e1_reference("BTCUSDT", 2022)
    raw = camp._raw_reference("BTCUSDT", 2022)
    ok = (e1 is not None and e1["n_entries"] == 119 and e1["pf"] == 0.878
          and raw is not None and raw["n_entries"] == 119 and raw["pf"] == 0.846)
    return _p(f"_e1_reference/_raw_reference leen filas reales publicadas "
              f"(E1 pf={e1['pf'] if e1 is not None else None}, Raw pf={raw['pf'] if raw is not None else None})", ok)


def test_check_entries_vs_reference_detecta_match_y_mismatch():
    match = camp.check_entries_vs_reference("BTCUSDT", 2022, 119)
    mismatch = camp.check_entries_vs_reference("BTCUSDT", 2022, 999)
    ok = match["match_e1"] is True and match["match_raw"] is True and mismatch["match_e1"] is False
    return _p("check_entries_vs_reference detecta correctamente coincidencia/no-coincidencia "
              "de n_entries contra E1 y Raw", ok)


def test_run_campaign_nunca_llega_a_fase_b_si_fase_a_falla():
    orig_check = camp.run_integrity_check
    camp.run_integrity_check = lambda asset, year: (_ for _ in ()).throw(AssertionError("Fase A simulada: falla"))
    ok = False
    try:
        camp.run_campaign(assets=("TESTUSDT",), years=(2022,))
    except AssertionError:
        ok = True
    finally:
        camp.run_integrity_check = orig_check
    return _p("run_campaign() propaga la falla de Fase A sin invocar Fase B", ok)


# --------------------------------------------------------------------------- #
# Pipeline completo sobre datos sintéticos                                   #
# --------------------------------------------------------------------------- #
def make_synthetic_raw_1h(start="2021-10-01", n=8000, seed=7):
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
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx)


def _build_sliced_for(seed=7):
    raw = make_synthetic_raw_1h(seed=seed)
    df_full = build_dc_v1(raw, asset="TESTUSDT", dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)
    df4h_full = bias_camp.resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, camp.BIAS_CANDIDATE)
    return period_slice(df_full, 2022), errs


def test_reason_categorias_incluyen_tp():
    sliced, errs = _build_sliced_for()
    if sliced.empty:
        return _p("reasons puede incluir 'tp' (slice vacío)", False)

    orig_load = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    try:
        frame, cfg, entries = camp._entries_for_asset_year("TESTUSDT", 2022)
        trades = camp.run_config_v3a_tp(frame, entries, camp.V3A_EXIT_CFG, cfg, camp.TP_R)
    finally:
        trigger_camp.load_asset_year = orig_load

    reasons_present = set(trades["reason"].unique()) if not trades.empty else set()
    ok = (not errs) and reasons_present <= {"stop", "tp", "timeout"}
    m = backtest.metrics(trades, cfg)
    row = camp._row("TESTUSDT", 2022, entries, trades, m, None, None, None)
    df_out = camp.results_to_frame([row])
    ok = ok and {"reason_stop", "reason_tp", "reason_timeout"} <= set(df_out.columns)
    return _p(f"Razones de salida de V3-A+TP ⊆ {{stop, tp, timeout}} ({reasons_present}) — "
              f"a diferencia de E2/Raw, este mecanismo SÍ puede cerrar por 'tp'", ok)


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
        rows, entry_checks = camp.run_campaign(assets=("TESTUSDT",), years=(2022,))
        df = camp.results_to_frame(rows)
        ok = (
            not errs
            and len(rows) == 1
            and len(entry_checks) == 1
            and df.iloc[0]["mechanism"] == "V3A_mas_TP_2.5R"
            and df.iloc[0]["bias"] == "A"
            and df.iloc[0]["delta_pf_v3a"] is not None
        )
    except AssertionError as e:
        ok = False
        print(f"    (excepción inesperada: {e})")
    finally:
        camp._v3a_reference = orig_ref
        trigger_camp.load_asset_year = orig_load

    return _p("run_campaign() end-to-end (Fase A + Fase B) produce 1 fila con mechanism/bias "
              "correctos y deltas vs V3-A pobladas", ok)


ALL_TESTS = [
    test_equivalencia_con_v3a_cuando_tp_es_inalcanzable,
    test_no_modifica_simulate_v3,
    test_tp_se_activa_en_2_5r_exacto,
    test_stop_gana_si_stop_y_tp_caen_en_la_misma_vela,
    test_be_y_trailing_funcionan_igual_que_v3a_cuando_no_hay_tp,
    test_timeout_respeta_max_hold_20,
    test_candidates_single_value,
    test_fixed_variables_match_contract,
    test_tp_r_coincide_con_e1,
    test_no_risk_override_en_llamadas_a_config,
    test_gate_check_and_summarize_decision_son_los_mismos_objetos,
    test_no_hay_run_blind_test,
    test_v3a_reference_lee_el_ancla_real,
    test_e1_y_raw_reference_leen_resultados_reales,
    test_check_entries_vs_reference_detecta_match_y_mismatch,
    test_run_campaign_nunca_llega_a_fase_b_si_fase_a_falla,
    test_reason_categorias_incluyen_tp,
    test_full_pipeline_end_to_end_sobre_datos_sinteticos,
]


def main():
    print("scripts/gestion_espacio6_v3a_tp_campaign — validación de equivalencia + "
          "mecanismo + contrato + real, Espacio 6 Experimento 4 (V3-A + TP)\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
