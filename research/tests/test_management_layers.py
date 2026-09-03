"""
research/tests/test_management_layers.py — Fase 5 (segundo mecanismo de
Gestión, 2026-09-02): interfaz común de `MANAGEMENT_LAYERS`, resolución
por registro (sin if/elif), y disciplina de "sin fabricación" de
`TradeRecord`.

Ejecutar:
    python -m research.tests.test_management_layers  (o con pytest)
"""
from __future__ import annotations

import ast
import inspect
import sys

import pandas as pd

sys.path.insert(0, ".")
import backtest
import research
from research import runner
from research.schema import TradeRecord

_CANONICAL_GATES = {
    "pf_min": research.PF_MIN, "max_dd_min": research.MAX_DD_MIN,
    "exp_r_min": research.EXP_R_MIN, "freq_min": research.FREQ_MIN_PER_MONTH,
    "freq_max": research.FREQ_MAX_PER_MONTH,
}


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def _valid_contract(management_name: str = "V3-A") -> dict:
    return {
        "name": "mgmt_layers_check", "contract_version": "1", "assets": ["BTCUSDT"],
        "years": {"train": 2022}, "bias": {"name": "A_ema200_neutral", "params": {}},
        "trigger": {"name": "T1_ema_cross", "params": {}}, "entry": {"name": "C_market_close", "params": {}},
        "session": "dcv1_activo_15h", "management": {"name": management_name, "params": {}},
        "risk": 0.005, "cost_per_trade": 0.0009, "max_hold": 20, "atr_mult": 1.5,
        "gates": dict(_CANONICAL_GATES), "independent_variable": "management.name",
        "blind_authorized": False,
    }


# --------------------------------------------------------------------------- #
# Registro exacto y firma común                                              #
# --------------------------------------------------------------------------- #
def test_management_layers_contiene_exactamente_v3a_y_raw():
    ok = set(runner.MANAGEMENT_LAYERS.keys()) == {"V3-A", "Raw"}
    return _p(f"MANAGEMENT_LAYERS contiene EXACTAMENTE {{'V3-A', 'Raw'}} "
              f"(actual: {set(runner.MANAGEMENT_LAYERS.keys())})", ok)


def test_ambos_mecanismos_son_callable_con_la_interfaz_comun():
    """(frame, entries, cfg) -> DataFrame — sin cost_per_trade (decisión
    de Fase 5, ver docstring de research/runner.py)."""
    entry = {"entry_idx": 0, "direction": "long", "entry": 100.0, "sl0": 90.0, "risk_pts": 10.0}
    idx = pd.date_range("2022-01-01", periods=3, freq="1h", tz="UTC")
    frame = pd.DataFrame({"open": [100, 100, 100], "high": [101, 101, 101],
                           "low": [99, 95, 95], "close": [100, 96, 96]}, index=idx)
    cfg = backtest.Config(max_hold=2)
    ok = True
    for name, fn in runner.MANAGEMENT_LAYERS.items():
        sig = inspect.signature(fn)
        params_ok = len(sig.parameters) == 3
        result = fn(frame, [entry], cfg)
        result_ok = isinstance(result, pd.DataFrame)
        ok = ok and params_ok and result_ok
        if not (params_ok and result_ok):
            print(f"    {name}: params_ok={params_ok} result_ok={result_ok} sig={sig}")
    return _p("MANAGEMENT_LAYERS['V3-A']/['Raw'] aceptan exactamente 3 parámetros "
              "(frame, entries, cfg) y devuelven un DataFrame", ok)


def test_raw_resuelve_exit_configs_raw_correctamente():
    ok = (
        research.EXIT_CONFIGS["Raw"] == {"be": float("inf"), "activation": float("inf"), "distance": 0.0}
        and runner._MANAGEMENT_PARAMS["Raw"] == research.EXIT_CONFIGS["Raw"]
    )
    return _p(f"research.EXIT_CONFIGS['Raw'] == {{'be': inf, 'activation': inf, 'distance': 0.0}} "
              f"exacto, y runner._MANAGEMENT_PARAMS['Raw'] coincide", ok)


def test_v3a_y_raw_usan_el_mismo_motor_simulate_v3():
    """Verificación de identidad: ambas entradas de MANAGEMENT_LAYERS
    terminan invocando backtest.run_config, que a su vez llama
    research.simulate_v3 (mismo objeto, Fase 4) — ninguna define una
    función de simulación propia."""
    src_v3a = inspect.getsource(runner._make_run_config_management)
    ok = (
        "def simulate_v3" not in inspect.getsource(runner)
        and "backtest.run_config" in src_v3a
        and callable(research.simulate_v3)
    )
    return _p("Ni V3-A ni Raw definen una función de simulación propia — ambas delegan a "
              "backtest.run_config/research.simulate_v3 vía la misma fábrica", ok)


# --------------------------------------------------------------------------- #
# Sin selección manual (if/elif) por nombre de mecanismo                    #
# --------------------------------------------------------------------------- #
def test_runner_no_tiene_if_elif_por_nombre_de_management():
    """Inspección AST (no solo grep de texto): confirma que no existe
    ningún `if`/`elif` cuya condición compare `management`/`mgmt_name`
    contra un string literal ("V3-A", "Raw", etc.) en todo el archivo."""
    src = inspect.getsource(runner)
    tree = ast.parse(src)
    offending = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            src_segment = ast.get_source_segment(src, node) or ""
            if ("management" in src_segment.lower()) and ("==" in src_segment) and (
                '"V3-A"' in src_segment or "'V3-A'" in src_segment
                or '"Raw"' in src_segment or "'Raw'" in src_segment
            ):
                offending.append(src_segment)
    ok = not offending
    if offending:
        for seg in offending:
            print(f"    encontrado: {seg}")
    return _p("Ningún if/elif en research/runner.py compara el nombre de management contra "
              "'V3-A'/'Raw' literalmente — la resolución es siempre vía MANAGEMENT_LAYERS[...]", ok)


def test_management_layers_es_un_dict_resuelto_por_indexacion():
    """Confirma en código que run() indexa MANAGEMENT_LAYERS por nombre
    (`MANAGEMENT_LAYERS[management_name]`), no un despacho manual."""
    src = inspect.getsource(runner.run)
    ok = "MANAGEMENT_LAYERS[management_name]" in src
    return _p("research.runner.run() resuelve el mecanismo vía "
              "MANAGEMENT_LAYERS[management_name] — indexación de diccionario, no despacho manual", ok)


# --------------------------------------------------------------------------- #
# Rechazos                                                                    #
# --------------------------------------------------------------------------- #
def test_management_inexistente_rechaza():
    c = _valid_contract()
    c["management"] = {"name": "NoExiste", "params": {}}
    ok = False
    try:
        runner.validate_contract(c)
    except runner.ContractError:
        ok = True
    return _p("management.name inexistente en MANAGEMENT_LAYERS -> ContractError", ok)


def test_management_no_soportado_pero_futuro_rechaza():
    """E1/TP fijo/V3A+TP no están en MANAGEMENT_LAYERS todavía (fuera de
    alcance de Fase 5) — deben rechazar igual que un nombre inexistente."""
    c = _valid_contract()
    c["management"] = {"name": "E1_TP_fijo", "params": {}}
    ok = False
    try:
        runner.validate_contract(c)
    except runner.ContractError:
        ok = True
    return _p("management.name='E1_TP_fijo' (no implementado en esta fase) -> ContractError", ok)


def test_contrato_no_acepta_codigo_arbitrario_en_management():
    """El contrato solo declara management.name (string) + params (dict de
    datos) — nunca una función, código, ni un callable arbitrario."""
    c = _valid_contract()
    c["management"] = {"name": lambda frame, entries, cfg: None, "params": {}}
    ok = False
    try:
        runner.validate_contract(c)
    except runner.ContractError:
        ok = True
    except TypeError:
        ok = True  # tampoco es hashable de forma útil contra el dict -- de cualquier forma, rechazado
    return _p("management.name que NO es un string (ej. un callable) es rechazado, nunca "
              "ejecutado como código", ok)


# --------------------------------------------------------------------------- #
# Determinismo (por mecanismo)                                              #
# --------------------------------------------------------------------------- #
def test_mismo_contrato_raw_mismo_resultado():
    c = _valid_contract("Raw")
    r1 = runner.run(dict(c))
    r2 = runner.run(dict(c))
    ok = r1 == r2 and r1.contract_hash == r2.contract_hash
    return _p(f"Mismo contrato (management=Raw) ejecutado dos veces produce el mismo "
              f"ExperimentResult y el mismo contract_hash ({r1.contract_hash})", ok)


def test_v3a_y_raw_mismo_dataset_producen_resultados_distintos():
    """Chequeo de sanidad: no es que el registro resuelva siempre a la
    misma función por error — V3-A y Raw, sobre el MISMO dataset, deben
    producir métricas DIFERENTES (mecanismos distintos)."""
    r_v3a = runner.run(_valid_contract("V3-A"))
    r_raw = runner.run(_valid_contract("Raw"))
    ok = r_v3a.pf != r_raw.pf and r_v3a.n_entries == r_raw.n_entries  # mismas entradas, distinto PF
    return _p(f"V3-A (pf={r_v3a.pf}) y Raw (pf={r_raw.pf}) producen resultados distintos "
              f"sobre las mismas entradas ({r_v3a.n_entries}) — el registro no colapsa a un "
              f"solo mecanismo por error", ok)


# --------------------------------------------------------------------------- #
# TradeRecord — sin fabricación                                             #
# --------------------------------------------------------------------------- #
def test_trade_record_no_fabrica_campos_para_ningun_mecanismo():
    for mgmt in ("V3-A", "Raw"):
        _, trades = runner.run(_valid_contract(mgmt), include_trades=True)
        ok = len(trades) > 0 and all(
            tr.exit_price is None and tr.pnl_r is not None and tr.reason in ("stop", "timeout")
            for tr in trades
        )
        if not ok:
            return _p(f"TradeRecord de {mgmt}: exit_price=None (no fabricado), pnl_r/reason "
                      f"producidos directamente", False)
    return _p("TradeRecord de V3-A y Raw: exit_price=None (no producido, no fabricado), "
              "pnl_r/reason siempre producidos directamente por simulate_v3", True)


def test_include_trades_false_no_rompe_llamadores_existentes():
    """include_trades=False (default) debe devolver EXACTAMENTE lo mismo
    que antes de Fase 5 — un ExperimentResult solo, no una tupla."""
    result = runner.run(_valid_contract("V3-A"))
    ok = not isinstance(result, tuple) and hasattr(result, "pf")
    return _p("runner.run(experiment) sin include_trades sigue devolviendo un ExperimentResult "
              "solo (no una tupla) — compatibilidad con todo llamador de Fase 2-4 preservada", ok)


def test_metricas_no_cambian_por_introducir_trade_record():
    """El ExperimentResult debe ser IDÉNTICO llamando con o sin
    include_trades — TradeRecord es una vista adicional, no una fuente de
    cálculo distinta."""
    c = _valid_contract("Raw")
    r_solo = runner.run(dict(c))
    r_con_trades, _ = runner.run(dict(c), include_trades=True)
    ok = r_solo == r_con_trades
    return _p("ExperimentResult es idéntico con y sin include_trades=True — TradeRecord no "
              "altera las métricas ya calculadas", ok)


# --------------------------------------------------------------------------- #
# simulate_v3 / semántica de costos sin cambios                             #
# --------------------------------------------------------------------------- #
def test_simulate_v3_no_modificado_por_fase5():
    src = inspect.getsource(research.simulate.simulate_v3)
    ok = "def simulate_v3" in src and "import backtest" in src  # el import local sigue ahí, sin cambios
    return _p("research.simulate.simulate_v3 conserva su import local a backtest (sin "
              "modificaciones de Fase 5)", ok)


def test_semantica_de_costos_sin_cambios_para_raw():
    """El monkeypatch de backtest.COST_PER_TRADE (ahora en run(), capa de
    ejecución) debe seguir controlando el resultado, también para Raw."""
    c = _valid_contract("Raw")
    c["cost_per_trade"] = 0.0
    r_sin_costo = runner.run(dict(c))
    c["cost_per_trade"] = 0.0009
    r_con_costo = runner.run(dict(c))
    ok = r_sin_costo.total_r > r_con_costo.total_r
    return _p(f"cost_per_trade sigue controlando el resultado de Raw a través del runner "
              f"(total_r sin costo={r_sin_costo.total_r} > con costo={r_con_costo.total_r})", ok)


ALL_TESTS = [
    test_management_layers_contiene_exactamente_v3a_y_raw,
    test_ambos_mecanismos_son_callable_con_la_interfaz_comun,
    test_raw_resuelve_exit_configs_raw_correctamente,
    test_v3a_y_raw_usan_el_mismo_motor_simulate_v3,
    test_runner_no_tiene_if_elif_por_nombre_de_management,
    test_management_layers_es_un_dict_resuelto_por_indexacion,
    test_management_inexistente_rechaza,
    test_management_no_soportado_pero_futuro_rechaza,
    test_contrato_no_acepta_codigo_arbitrario_en_management,
    test_mismo_contrato_raw_mismo_resultado,
    test_v3a_y_raw_mismo_dataset_producen_resultados_distintos,
    test_trade_record_no_fabrica_campos_para_ningun_mecanismo,
    test_include_trades_false_no_rompe_llamadores_existentes,
    test_metricas_no_cambian_por_introducir_trade_record,
    test_simulate_v3_no_modificado_por_fase5,
    test_semantica_de_costos_sin_cambios_para_raw,
]


def main():
    print("research/tests/test_management_layers — Fase 5: interfaz común, registro, TradeRecord\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
