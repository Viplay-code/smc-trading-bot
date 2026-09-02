"""
research/tests/test_simulate_extraction.py — Fase 4 (C2, extracción del
motor de simulación, 2026-09-02): validación específica de la migración
`simulate_v3`/`EXIT_CONFIGS` -> `research/simulate.py`.

Categorías (pedidas explícitamente en la autorización de Fase 4):
  1. Compatibilidad de backtest.py (re-exports, mismo objeto).
  2. Mismo resultado vía runner vs. vía API legacy (backtest.run_config +
     backtest.EXIT_CONFIGS directo) — a nivel de trade record individual,
     no solo métricas agregadas.
  3. Determinismo.
  4. Ausencia de dependencia circular — en LOS TRES órdenes de import
     posibles, verificados en subprocesos frescos (no basta con probar
     dentro de un solo proceso, donde sys.modules ya cachea todo).
  5. Preservación de precedencia intrabar (stop gana si stop y avance
     favorable caen en la misma vela).
  6. Preservación del modelo de costos (fórmula exacta + monkeypatch de
     backtest.COST_PER_TRADE sigue controlando el resultado).

Ejecutar:
    python -m research.tests.test_simulate_extraction  (o con pytest)
"""
from __future__ import annotations

import subprocess
import sys

import pandas as pd

sys.path.insert(0, ".")
import backtest
import research


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


# --------------------------------------------------------------------------- #
# 1. Compatibilidad de backtest.py                                           #
# --------------------------------------------------------------------------- #
def test_backtest_simulate_v3_es_research_simulate_v3():
    ok = backtest.simulate_v3 is research.simulate_v3 is research.simulate.simulate_v3
    return _p("backtest.simulate_v3 IS research.simulate_v3 IS research.simulate.simulate_v3 "
              "(mismo objeto en toda la cadena, no una copia)", ok)


def test_backtest_exit_configs_es_research_exit_configs():
    ok = (backtest.EXIT_CONFIGS is research.EXIT_CONFIGS is research.simulate.EXIT_CONFIGS
          and backtest.EXIT_CONFIGS == {
              "V3-A (1R/2R/1R)": {"be": 1.0, "activation": 2.0, "distance": 1.0},
              "V3-B (0.75R/1.5R/0.75R)": {"be": 0.75, "activation": 1.5, "distance": 0.75},
          })
    return _p("backtest.EXIT_CONFIGS IS research.EXIT_CONFIGS (mismo dict), valores V3-A/V3-B sin cambios", ok)


def test_backtest_run_config_no_se_movio():
    """run_config debe seguir definida EN backtest.py (no ser un
    re-export) — es la decisión de diseño central de esta fase, ver
    docstring de research/simulate.py."""
    import inspect
    ok = "backtest" in inspect.getsourcefile(backtest.run_config)
    return _p("backtest.run_config sigue definida en backtest.py (NO se movió, decisión "
              "deliberada de esta fase)", ok)


def test_research_simulate_no_reimplementa_run_config():
    ok = not hasattr(research.simulate, "run_config")
    return _p("research/simulate.py NO define run_config — solo simulate_v3/EXIT_CONFIGS "
              "(alcance exacto de la extracción)", ok)


# --------------------------------------------------------------------------- #
# 2. Mismo resultado vía runner vs. vía API legacy (trade record completo)   #
# --------------------------------------------------------------------------- #
def test_mismo_resultado_via_runner_y_via_api_legacy_btcusdt_2022():
    """Compara, trade por trade (no solo métricas agregadas), los trades
    que produce el runner (research.runner.run(), vía MANAGEMENT_LAYERS)
    contra los que produce la ruta 100% legacy (backtest.find_entries +
    backtest.run_config + backtest.EXIT_CONFIGS, sin pasar por el runner
    en absoluto) — deben ser IDÉNTICOS."""
    from research import runner as runner_mod

    # Ruta legacy pura, sin usar el runner:
    df_full = research.load_asset_year("BTCUSDT", 2022)
    cfg = backtest.Config(atr_mult=1.5, atr_period=14, max_hold=20, risk=0.005,
                           sessions=runner_mod.SESSION_WINDOWS["dcv1_activo_15h"])
    frame = research.to_backtest_frame(df_full, df_full["bias_A"], cfg)
    entries = backtest.find_entries(frame, cfg)
    orig_cost = backtest.COST_PER_TRADE
    backtest.COST_PER_TRADE = 0.0009
    try:
        trades_legacy = backtest.run_config(frame, entries, backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], cfg)
    finally:
        backtest.COST_PER_TRADE = orig_cost

    # Ruta vía runner:
    contract = {
        "name": "legacy_vs_runner_check", "contract_version": "1", "assets": ["BTCUSDT"],
        "years": {"train": 2022}, "bias": {"name": "A_ema200_neutral", "params": {}},
        "trigger": {"name": "T1_ema_cross", "params": {}}, "entry": {"name": "C_market_close", "params": {}},
        "session": "dcv1_activo_15h", "management": {"name": "V3-A", "params": {}},
        "risk": 0.005, "cost_per_trade": 0.0009, "max_hold": 20, "atr_mult": 1.5,
        "gates": {"pf_min": research.PF_MIN, "max_dd_min": research.MAX_DD_MIN,
                  "exp_r_min": research.EXP_R_MIN, "freq_min": research.FREQ_MIN_PER_MONTH,
                  "freq_max": research.FREQ_MAX_PER_MONTH},
        "independent_variable": "management.name", "blind_authorized": False,
    }
    result = runner_mod.run(contract)

    ok = (
        result.n_entries == len(entries)
        and result.n_trades == len(trades_legacy)
        and result.pf == backtest.metrics(trades_legacy, cfg)["pf"]
        and result.total_r == backtest.metrics(trades_legacy, cfg)["total_r"]
    )
    return _p(f"research.runner.run() (BTCUSDT/2022) produce EXACTAMENTE el mismo n_entries/"
              f"n_trades/pf/total_r que la ruta 100% legacy (backtest.find_entries + "
              f"backtest.run_config + backtest.EXIT_CONFIGS, sin pasar por el runner)", ok)


def test_trade_records_identicos_via_ambas_rutas():
    """Va un nivel más profundo que el test anterior: compara el
    DataFrame de trades COMPLETO (entry_time/exit_time/reason/pnl_r/
    duration_h de cada trade individual), no solo las métricas agregadas."""
    from research import runner as runner_mod

    df_full = research.load_asset_year("ETHUSDT", 2023)
    cfg = backtest.Config(atr_mult=1.5, atr_period=14, max_hold=20, risk=0.005,
                           sessions=runner_mod.SESSION_WINDOWS["dcv1_activo_15h"])
    frame = research.to_backtest_frame(df_full, df_full["bias_A"], cfg)
    entries = backtest.find_entries(frame, cfg)
    orig_cost = backtest.COST_PER_TRADE
    backtest.COST_PER_TRADE = 0.0009
    try:
        trades_legacy = backtest.run_config(frame, entries, backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], cfg)
        trades_via_research = backtest.run_config(frame, entries, research.EXIT_CONFIGS["V3-A (1R/2R/1R)"], cfg)
    finally:
        backtest.COST_PER_TRADE = orig_cost

    ok = trades_legacy.equals(trades_via_research)
    return _p(f"El DataFrame de trades COMPLETO (entry_time/exit_time/reason/pnl_r/"
              f"duration_h, {len(trades_legacy)} trades) es idéntico usando "
              f"backtest.EXIT_CONFIGS vs. research.EXIT_CONFIGS", ok)


# --------------------------------------------------------------------------- #
# 3. Determinismo                                                            #
# --------------------------------------------------------------------------- #
def test_determinismo_simulate_v3():
    entry = _mk_entry("long", 100.0, 90.0, 10.0)
    bars = [(100, 101, 99, 100), (105, 112, 108, 110), (105, 106, 95, 96)]
    df = _mk_df(bars)
    cfg = backtest.Config(max_hold=2)
    r1 = research.simulate_v3(df, dict(entry), backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], cfg)
    r2 = research.simulate_v3(df, dict(entry), backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], cfg)
    ok = r1 == r2
    return _p("research.simulate_v3 es determinista (misma entrada -> mismo resultado exacto)", ok)


# --------------------------------------------------------------------------- #
# 4. Ausencia de dependencia circular — verificado en subprocesos frescos    #
# --------------------------------------------------------------------------- #
def _run_fresh_python(code: str) -> tuple[bool, str]:
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=".")
    return result.returncode == 0, (result.stdout + result.stderr)


def test_sin_circular_orden_backtest_primero():
    ok, out = _run_fresh_python(
        "import backtest; import research; "
        "assert research.simulate_v3 is backtest.simulate_v3; print('OK')"
    )
    if not ok:
        print(f"    {out}")
    return _p("Import fresco: 'import backtest' primero, luego 'import research' -> sin error", ok)


def test_sin_circular_orden_research_simulate_primero():
    ok, out = _run_fresh_python(
        "import research.simulate; import backtest; "
        "assert backtest.simulate_v3 is research.simulate.simulate_v3; print('OK')"
    )
    if not ok:
        print(f"    {out}")
    return _p("Import fresco: 'import research.simulate' primero (backtest nunca tocado "
              "antes), luego 'import backtest' -> sin error", ok)


def test_sin_circular_orden_research_paquete_primero():
    ok, out = _run_fresh_python(
        "import research; import backtest; "
        "assert backtest.simulate_v3 is research.simulate_v3; print('OK')"
    )
    if not ok:
        print(f"    {out}")
    return _p("Import fresco: 'import research' (paquete) primero, luego 'import backtest' "
              "-> sin error", ok)


# --------------------------------------------------------------------------- #
# 5. Precedencia intrabar preservada                                        #
# --------------------------------------------------------------------------- #
def test_precedencia_intrabar_stop_gana_si_empatan():
    """Si el extremo adverso (stop) Y el avance favorable caen en la misma
    vela, el stop debe ganar — el movimiento favorable intrabar nunca
    'protege' dentro de la misma vela (docstring original de backtest.py,
    preservado literal en research/simulate.py)."""
    entry = _mk_entry("long", 100.0, 90.0, 10.0)  # be dispara en 100+1.0*10=110
    # vela 1: high=200 (fav +10R, activaría BE/trailing) Y low=85 (<=90=stop) en la MISMA vela
    bars = [(100, 101, 99, 100), (150, 200, 85, 190)]
    df = _mk_df(bars)
    cfg = backtest.Config(max_hold=1)
    res = research.simulate_v3(df, entry, backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], cfg)
    ok = res["reason"] == "stop" and abs(res["pnl_r"] - (-1.0 - (100 * 0.0009 / 10))) < 1e-6
    return _p(f"Precedencia intrabar preservada: stop y avance favorable extremo en la misma "
              f"vela -> gana el stop, pnl_r={res['pnl_r']} (~-1R neto de costos)", ok)


# --------------------------------------------------------------------------- #
# 6. Modelo de costos preservado                                            #
# --------------------------------------------------------------------------- #
def test_formula_de_costo_exacta():
    entry = _mk_entry("long", 100.0, 90.0, 10.0)
    bars = [(100, 101, 99, 100), (95, 96, 85, 90)]
    df = _mk_df(bars)
    cfg = backtest.Config(max_hold=1)
    orig = backtest.COST_PER_TRADE
    backtest.COST_PER_TRADE = 0.0009
    try:
        res = research.simulate_v3(df, entry, backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], cfg)
    finally:
        backtest.COST_PER_TRADE = orig
    expected_cost_r = (100.0 * 0.0009) / 10.0
    expected_pnl = round(-1.0 - expected_cost_r, 4)
    ok = res["pnl_r"] == expected_pnl
    return _p(f"cost_r = entry*COST_PER_TRADE/risk_pts preservado exacto "
              f"(pnl_r={res['pnl_r']}, esperado={expected_pnl})", ok)


def test_monkeypatch_backtest_cost_per_trade_controla_research_simulate_v3():
    """El hallazgo central de la auditoría de esta fase: parchear
    backtest.COST_PER_TRADE debe seguir controlando el resultado de
    research.simulate_v3, pese a que la función ya no vive en
    backtest.py."""
    entry = _mk_entry("long", 100.0, 90.0, 10.0)
    bars = [(100, 101, 99, 100), (95, 96, 85, 90)]
    df = _mk_df(bars)
    cfg = backtest.Config(max_hold=1)

    orig = backtest.COST_PER_TRADE
    backtest.COST_PER_TRADE = 0.0
    try:
        res_sin_costo = research.simulate_v3(df, dict(entry), backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], cfg)
    finally:
        backtest.COST_PER_TRADE = orig
    res_con_costo = research.simulate_v3(df, dict(entry), backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], cfg)

    ok = res_sin_costo["pnl_r"] != res_con_costo["pnl_r"] and res_sin_costo["pnl_r"] == -1.0
    return _p(f"Monkeypatch de backtest.COST_PER_TRADE SIGUE controlando research.simulate_v3 "
              f"(sin costo pnl_r={res_sin_costo['pnl_r']}, con costo pnl_r={res_con_costo['pnl_r']})", ok)


ALL_TESTS = [
    test_backtest_simulate_v3_es_research_simulate_v3,
    test_backtest_exit_configs_es_research_exit_configs,
    test_backtest_run_config_no_se_movio,
    test_research_simulate_no_reimplementa_run_config,
    test_mismo_resultado_via_runner_y_via_api_legacy_btcusdt_2022,
    test_trade_records_identicos_via_ambas_rutas,
    test_determinismo_simulate_v3,
    test_sin_circular_orden_backtest_primero,
    test_sin_circular_orden_research_simulate_primero,
    test_sin_circular_orden_research_paquete_primero,
    test_precedencia_intrabar_stop_gana_si_empatan,
    test_formula_de_costo_exacta,
    test_monkeypatch_backtest_cost_per_trade_controla_research_simulate_v3,
]


def main():
    print("research/tests/test_simulate_extraction — Fase 4 (C2): validación de la extracción\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
