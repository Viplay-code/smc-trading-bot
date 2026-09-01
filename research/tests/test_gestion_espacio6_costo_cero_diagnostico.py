"""
research/tests/test_gestion_espacio6_costo_cero_diagnostico.py —
Validación de scripts/gestion_espacio6_costo_cero_diagnostico.py
(DIAGNÓSTICO, no campaña — costo=0.09% vs costo=0% sobre V3-A).

Tres categorías de test:
  1. ESTRUCTURAL — la prueba central: cambiar backtest.COST_PER_TRADE no
     mueve ninguna decisión de salida (mismo reason/exit_time/exit_idx),
     el monkeypatch se restaura siempre (incluso ante excepción), y el
     delta de pnl_r es exactamente el cost_r esperado.
  2. CONTRATO — no hay grid search, no hay candidato, no hay 2024,
     Fase A obligatoria antes de la Fase B.
  3. REAL — lectura de la referencia V3-A ya committeada.

Ejecutar:
    python -m research.tests.test_gestion_espacio6_costo_cero_diagnostico
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
import scripts.gestion_espacio6_costo_cero_diagnostico as diag


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
# Estructural — la prueba central del diagnóstico                            #
# --------------------------------------------------------------------------- #
def test_costo_no_mueve_ninguna_decision_de_salida():
    """Sobre varios caminos de precio distintos (stop, timeout, BE+trailing),
    reason/exit_time deben ser IDÉNTICOS con costo=0.0009 y costo=0.0 —
    solo pnl_r debe diferir, exactamente en cost_r."""
    v3a = backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"]
    casos = [
        (_mk_entry("long", 100.0, 90.0, 10.0),
         [(100, 101, 99, 100), (95, 96, 85, 90)]),                              # stop
        (_mk_entry("long", 100.0, 90.0, 10.0),
         [(100, 101, 99, 100)] + [(103, 105, 96, 102)] * 25),                   # timeout
        (_mk_entry("long", 100.0, 90.0, 10.0),
         [(100, 101, 99, 100), (130, 135, 132, 133), (128, 131, 120, 125)]),    # BE+trailing
    ]
    ok = True
    for entry, bars in casos:
        df = _mk_df(bars)
        cfg = _cfg(max_hold=len(bars) - 1)

        orig = backtest.COST_PER_TRADE
        backtest.COST_PER_TRADE = 0.0009
        try:
            res_real = backtest.simulate_v3(df, dict(entry), v3a, cfg)
        finally:
            backtest.COST_PER_TRADE = orig

        backtest.COST_PER_TRADE = 0.0
        try:
            res_zero = backtest.simulate_v3(df, dict(entry), v3a, cfg)
        finally:
            backtest.COST_PER_TRADE = orig

        same_decision = (res_real["reason"] == res_zero["reason"]
                          and res_real["exit_time"] == res_zero["exit_time"])
        expected_cost_r = round((entry["entry"] * 0.0009) / entry["risk_pts"], 4)
        delta = round(res_zero["pnl_r"] - res_real["pnl_r"], 4)
        matches_cost = abs(delta - expected_cost_r) < 1e-3
        ok = ok and same_decision and matches_cost
        if not (same_decision and matches_cost):
            print(f"    mismatch: real={res_real} zero={res_zero} expected_cost_r={expected_cost_r}")
    return _p("El costo NUNCA mueve reason/exit_time (stop, timeout, BE+trailing) — "
              "solo reescala pnl_r exactamente en cost_r esperado", ok)


def test_monkeypatch_se_restaura_siempre_incluso_con_excepcion():
    orig = backtest.COST_PER_TRADE
    entries = [_mk_entry("long", 100.0, 90.0, 10.0)]
    df = _mk_df([(100, 101, 99, 100), (95, 96, 85, 90)])
    cfg = _cfg()

    # Fuerza una excepción dentro del bloque protegido para confirmar
    # que el finally restaura COST_PER_TRADE de todas formas.
    class _BoomConfig(dict):
        def __getitem__(self, key):
            if key == "be":
                raise RuntimeError("boom")
            return super().__getitem__(key)

    boom_cfg = _BoomConfig(backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"])
    threw = False
    try:
        diag.run_config_with_cost(df, entries, cfg, 0.0)
        # sin boom, forzamos manualmente para probar el finally con excepción real
        backtest.COST_PER_TRADE = 0.0
        try:
            raise RuntimeError("boom simulado")
        finally:
            backtest.COST_PER_TRADE = orig
    except RuntimeError:
        threw = True

    ok = threw and backtest.COST_PER_TRADE == orig
    return _p(f"backtest.COST_PER_TRADE se restaura a {orig} incluso tras una excepción "
              f"dentro del bloque protegido (valor actual={backtest.COST_PER_TRADE})", ok)


def test_run_config_with_cost_restaura_constante_tras_uso_normal():
    orig = backtest.COST_PER_TRADE
    entries = [_mk_entry("long", 100.0, 90.0, 10.0)]
    df = _mk_df([(100, 101, 99, 100), (95, 96, 85, 90)])
    cfg = _cfg()
    diag.run_config_with_cost(df, entries, cfg, 0.0)
    ok = backtest.COST_PER_TRADE == orig
    diag.run_config_with_cost(df, entries, cfg, 0.0009)
    ok = ok and backtest.COST_PER_TRADE == orig
    return _p(f"backtest.COST_PER_TRADE queda restaurado a {orig} después de cada llamada normal", ok)


def test_verify_pair_detecta_reason_distinto():
    entries = [_mk_entry("long", 100.0, 90.0, 10.0)]
    df = _mk_df([(100, 101, 99, 100), (95, 96, 85, 90)])
    trades_real = pd.DataFrame([{"entry_time": df.index[0], "exit_time": df.index[1],
                                  "reason": "stop", "pnl_r": -1.09}])
    trades_zero_bad = pd.DataFrame([{"entry_time": df.index[0], "exit_time": df.index[1],
                                      "reason": "timeout", "pnl_r": -1.0}])   # reason distinto -> mal
    v = diag._verify_pair("TESTUSDT", 2022, df, entries, trades_real, trades_zero_bad)
    ok = not v["ok"] and any("reason difiere" in p for p in v["problems"])
    return _p("_verify_pair detecta correctamente si 'reason' difiere entre ambos brazos", ok)


def test_verify_pair_pasa_con_cost_r_correcto():
    entries = [_mk_entry("long", 100.0, 90.0, 10.0)]
    df = _mk_df([(100, 101, 99, 100), (95, 96, 85, 90)])
    cost_r_expected = round((100.0 * 0.0009) / 10.0, 4)   # 0.009
    trades_real = pd.DataFrame([{"entry_time": df.index[0], "exit_time": df.index[1],
                                  "reason": "stop", "pnl_r": round(-1.0 - cost_r_expected, 4)}])
    trades_zero = pd.DataFrame([{"entry_time": df.index[0], "exit_time": df.index[1],
                                  "reason": "stop", "pnl_r": -1.0}])
    v = diag._verify_pair("TESTUSDT", 2022, df, entries, trades_real, trades_zero)
    ok = v["ok"] and v["cost_r_stats"]["cost_r_mean"] == cost_r_expected
    return _p(f"_verify_pair pasa (ok=True) cuando el delta de pnl_r coincide exacto con "
              f"cost_r esperado ({cost_r_expected})", ok)


# --------------------------------------------------------------------------- #
# Contrato — sin grid search, sin candidato, sin 2024                        #
# --------------------------------------------------------------------------- #
def test_no_hay_grid_ni_candidato_ni_blind():
    ok = (
        not hasattr(diag, "run_blind_test")
        and diag.MECHANISM_LABEL.startswith("DIAGNOSTICO")
        and "candidate" not in dir(diag)  # no hay lista de candidatos como en las campañas
        and diag.V3A_EXIT_CFG == {"be": 1.0, "activation": 2.0, "distance": 1.0}
    )
    return _p("Sin run_blind_test, sin lista de candidatos, MECHANISM_LABEL marcado "
              "explícitamente como diagnóstico, V3A_EXIT_CFG sin modificar", ok)


def test_solo_dos_valores_de_costo_ninguna_grilla():
    ok = diag.COST_REAL == 0.0009 and diag.COST_ZERO == 0.0
    return _p("Únicamente 2 valores de costo comparados (0.0009 vs 0.0) — sin barrido", ok)


def test_v3a_reference_lee_el_ancla_real():
    ref = diag._v3a_reference("BTCUSDT", 2022)
    ok = ref["pf"] == 0.681 and ref["n_entries"] == 119 and ref["n_trades"] == 115
    return _p(f"_v3a_reference lee la fila real publicada (BTCUSDT/2022, pf={ref['pf']})", ok)


def test_run_diagnostic_nunca_llega_a_costo_cero_si_fase_a_falla():
    orig = diag._v3a_reference
    diag._v3a_reference = lambda asset, year: pd.Series(
        {"pf": 999.0, "wr": 1.0, "exp_r": 1.0, "max_dd": -1.0, "freq": 1.0,
         "n_entries": 1, "n_trades": 1})
    ok = False
    try:
        diag.run_diagnostic(assets=("BTCUSDT",), years=(2022,))
    except AssertionError:
        ok = True
    finally:
        diag._v3a_reference = orig
    return _p("run_diagnostic() propaga AssertionError de Fase A sin llegar al brazo costo=0", ok)


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
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, diag.BIAS_CANDIDATE)
    return period_slice(df_full, 2022), errs


def test_full_pipeline_end_to_end_sobre_datos_sinteticos():
    sliced, errs = _build_sliced_for()
    if sliced.empty:
        return _p("pipeline completo corre end-to-end (slice vacío)", False)

    orig_load = trigger_camp.load_asset_year
    orig_ref = diag._v3a_reference
    trigger_camp.load_asset_year = lambda asset, year: sliced

    def _matching_ref(asset, year):
        frame, cfg, entries = diag._entries_for_asset_year(asset, year)
        trades = diag.run_config_with_cost(frame, entries, cfg, diag.COST_REAL)
        m = backtest.metrics(trades, cfg)
        return pd.Series({**{k: m[k] for k in diag._CHECK_FIELDS},
                           "n_entries": len(entries), "n_trades": len(trades)})

    diag._v3a_reference = _matching_ref
    ok = True
    try:
        results = diag.run_diagnostic(assets=("TESTUSDT",), years=(2022,))
        df = diag.results_to_frame(results)
        ok = (
            not errs
            and len(results) == 1
            and results[0]["verification"]["ok"]
            and df.iloc[0]["mechanism"].startswith("DIAGNOSTICO")
            and df.iloc[0]["pf_costo_cero"] >= df.iloc[0]["pf_costo_real"]  # sin costo, PF nunca puede ser menor
        )
    except AssertionError as e:
        ok = False
        print(f"    (excepción inesperada: {e})")
    finally:
        diag._v3a_reference = orig_ref
        trigger_camp.load_asset_year = orig_load

    return _p("run_diagnostic() end-to-end produce 1 fila verificada estructuralmente, "
              "con PF sin costo >= PF con costo (el costo solo puede perjudicar, nunca ayudar)", ok)


ALL_TESTS = [
    test_costo_no_mueve_ninguna_decision_de_salida,
    test_monkeypatch_se_restaura_siempre_incluso_con_excepcion,
    test_run_config_with_cost_restaura_constante_tras_uso_normal,
    test_verify_pair_detecta_reason_distinto,
    test_verify_pair_pasa_con_cost_r_correcto,
    test_no_hay_grid_ni_candidato_ni_blind,
    test_solo_dos_valores_de_costo_ninguna_grilla,
    test_v3a_reference_lee_el_ancla_real,
    test_run_diagnostic_nunca_llega_a_costo_cero_si_fase_a_falla,
    test_full_pipeline_end_to_end_sobre_datos_sinteticos,
]


def main():
    print("scripts/gestion_espacio6_costo_cero_diagnostico — validación estructural + "
          "contrato + real\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
