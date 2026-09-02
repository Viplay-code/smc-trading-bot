"""
research/tests/test_runner_invariants.py — Fase 2 (MVP del runner,
2026-09-02): disciplina científica del runner (Parte 3 del diseño de
Fase 0) — qué debe RECHAZAR antes de tocar datos, y qué garantiza sobre
el motor de simulación.

Ejecutar:
    python -m research.tests.test_runner_invariants  (o con pytest)
"""
from __future__ import annotations

import copy
import inspect
import sys

sys.path.insert(0, ".")
import backtest
import research
from research import runner


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


_CANONICAL_GATES = {
    "pf_min": research.PF_MIN, "max_dd_min": research.MAX_DD_MIN,
    "exp_r_min": research.EXP_R_MIN, "freq_min": research.FREQ_MIN_PER_MONTH,
    "freq_max": research.FREQ_MAX_PER_MONTH,
}


def _valid_contract() -> dict:
    return {
        "name": "invariant_check", "contract_version": "1", "assets": ["BTCUSDT"],
        "years": {"train": 2022}, "bias": {"name": "A_ema200_neutral", "params": {}},
        "trigger": {"name": "T1_ema_cross", "params": {}},
        "entry": {"name": "C_market_close", "params": {}},
        "session": "dcv1_activo_15h", "management": {"name": "V3-A", "params": {}},
        "risk": 0.005, "cost_per_trade": 0.0009, "max_hold": 20, "atr_mult": 1.5,
        "gates": dict(_CANONICAL_GATES), "independent_variable": "management.name",
        "blind_authorized": False,
    }


def _expect_contract_error(contract: dict, label: str) -> bool:
    try:
        runner.validate_contract(contract)
        print(f"    {label}: NO lanzó ContractError (debería haberlo hecho)")
        return False
    except runner.ContractError:
        return True
    except Exception as e:
        print(f"    {label}: lanzó {type(e).__name__} en vez de ContractError: {e}")
        return False


# --------------------------------------------------------------------------- #
# Contrato válido -> no rechaza                                              #
# --------------------------------------------------------------------------- #
def test_contrato_valido_no_lanza():
    ok = True
    try:
        runner.validate_contract(_valid_contract())
    except runner.ContractError as e:
        ok = False
        print(f"    {e}")
    return _p("Un contrato válido y completo pasa validate_contract() sin excepción", ok)


def test_contrato_valido_ejecuta_completo():
    ok = True
    try:
        result = runner.run(_valid_contract())
        ok = result.n_trades > 0 and result.gate_pass is not None
    except Exception as e:
        ok = False
        print(f"    excepción inesperada: {type(e).__name__}: {e}")
    return _p("Un contrato válido se ejecuta de punta a punta y produce un ExperimentResult", ok)


# --------------------------------------------------------------------------- #
# Rechazos obligatorios                                                       #
# --------------------------------------------------------------------------- #
def test_sin_independent_variable_rechaza():
    c = _valid_contract()
    del c["independent_variable"]
    return _p("Contrato sin independent_variable -> ContractError", _expect_contract_error(c, "sin independent_variable"))


def test_independent_variable_vacio_rechaza():
    c = _valid_contract()
    c["independent_variable"] = ""
    return _p("Contrato con independent_variable='' -> ContractError", _expect_contract_error(c, "independent_variable vacío"))


def test_componente_inexistente_rechaza_bias():
    c = _valid_contract()
    c["bias"] = {"name": "Z_no_existe", "params": {}}
    return _p("Contrato con bias.name inexistente -> ContractError, antes de tocar datos",
              _expect_contract_error(c, "bias inexistente"))


def test_componente_no_soportado_en_mvp_rechaza_trigger():
    """A_sweep_bos SÍ existe en research.TRIGGER_LAYERS, pero NO está
    soportado por este MVP del runner (find_entries está hardcodeado a
    T1_ema_cross+C_market_close) — debe rechazar igual, con un mensaje
    distinto al de 'no existe en absoluto'."""
    c = _valid_contract()
    c["trigger"] = {"name": "A_sweep_bos", "params": {}}
    ok = _expect_contract_error(c, "trigger no soportado en MVP (pero existe en el registro)")
    ok = ok and "A_sweep_bos" in research.TRIGGER_LAYERS   # confirma que SÍ existe globalmente
    return _p("Contrato con trigger.name registrado globalmente pero fuera del alcance de "
              "este MVP -> ContractError igualmente (rechazo explícito, no silencioso)", ok)


def test_management_no_soportado_rechaza():
    c = _valid_contract()
    c["management"] = {"name": "Raw", "params": {}}
    return _p("Contrato con management.name='Raw' (no implementado en MANAGEMENT_LAYERS "
              "de este MVP) -> ContractError", _expect_contract_error(c, "management no soportado"))


def test_management_params_distintos_de_v3a_rechaza():
    c = _valid_contract()
    c["management"] = {"name": "V3-A", "params": {"be": 2.0, "activation": 3.0, "distance": 1.0}}
    return _p("Contrato con management.params distinto de V3-A -> ContractError "
              "(variante paramétrica fuera de alcance de este MVP)",
              _expect_contract_error(c, "management.params distinto"))


def test_gates_ausentes_rechaza():
    c = _valid_contract()
    del c["gates"]
    return _p("Contrato sin 'gates' -> ContractError", _expect_contract_error(c, "gates ausentes"))


def test_gates_distintos_de_canonicos_rechaza():
    """Un gate MÁS PERMISIVO (freq_min=4 en vez de 6, análogo a
    backtest.py::passes()) también debe rechazarse — el runner nunca
    acepta un gate distinto del oficial, ni siquiera uno 'razonable'."""
    c = _valid_contract()
    c["gates"] = {**_CANONICAL_GATES, "freq_min": 4}
    return _p("Contrato con gates que NO coinciden exacto con los canónicos "
              "(ej. freq_min=4 en vez de 6) -> ContractError", _expect_contract_error(c, "gates no canónicos"))


def test_blind_sin_autorizar_rechaza():
    c = _valid_contract()
    c["years"] = {"blind": 2024}
    c["blind_authorized"] = False
    return _p("Contrato con years={'blind': 2024} y blind_authorized=False -> ContractError",
              _expect_contract_error(c, "blind sin autorizar"))


def test_blind_autorizado_no_rechaza_por_ese_motivo():
    """blind_authorized=True SÍ debe pasar la validación de blind (no
    verifica que 2024 esté disponible en datos — eso es un error de
    ejecución posterior, no de contrato)."""
    c = _valid_contract()
    c["years"] = {"blind": 2024}
    c["blind_authorized"] = True
    ok = True
    try:
        runner.validate_contract(c)
    except runner.ContractError as e:
        ok = False
        print(f"    {e}")
    return _p("Contrato con years={'blind': 2024} y blind_authorized=True pasa la "
              "validación de contrato (el rechazo era específicamente por falta de autorización)", ok)


def test_multiples_activos_rechaza():
    c = _valid_contract()
    c["assets"] = ["BTCUSDT", "ETHUSDT"]
    return _p("Contrato con más de 1 activo -> ContractError (fuera de alcance de este MVP)",
              _expect_contract_error(c, "múltiples activos"))


def test_multiples_anios_rechaza():
    c = _valid_contract()
    c["years"] = {"train": 2022, "validate": 2023}
    return _p("Contrato con más de 1 (rol, año) -> ContractError (fuera de alcance de este MVP)",
              _expect_contract_error(c, "múltiples años"))


def test_falta_campo_obligatorio_rechaza():
    c = _valid_contract()
    del c["cost_per_trade"]
    return _p("Contrato sin 'cost_per_trade' -> ContractError", _expect_contract_error(c, "cost_per_trade ausente"))


def test_rechazo_es_antes_de_tocar_datos():
    """Un contrato inválido con un activo inexistente NO debe intentar
    cargar ningún dataset — debe fallar por ContractError (validación),
    nunca por FileNotFoundError (intento de carga)."""
    c = _valid_contract()
    c["bias"] = {"name": "Z_no_existe", "params": {}}
    c["assets"] = ["ACTIVO_QUE_NO_EXISTE"]
    try:
        runner.run(c)
        ok = False
    except runner.ContractError:
        ok = True
    except FileNotFoundError:
        ok = False
        print("    run() llegó a intentar cargar datos ANTES de rechazar el contrato inválido")
    return _p("run() con contrato inválido falla por ContractError, NUNCA llega a "
              "intentar cargar datos (FileNotFoundError)", ok)


# --------------------------------------------------------------------------- #
# Determinismo                                                                #
# --------------------------------------------------------------------------- #
def test_mismo_contrato_mismo_hash_y_mismo_resultado():
    c = _valid_contract()
    r1 = runner.run(copy.deepcopy(c))
    r2 = runner.run(copy.deepcopy(c))
    ok = r1 == r2 and r1.contract_hash == r2.contract_hash
    return _p(f"Mismo contrato ejecutado dos veces (con copias independientes) produce "
              f"el mismo contract_hash ({r1.contract_hash}) y el mismo ExperimentResult", ok)


def test_contratos_distintos_hash_distinto():
    c1 = _valid_contract()
    c2 = _valid_contract()
    c2["name"] = "otro_nombre"
    h1 = research.compute_contract_hash(c1)
    h2 = research.compute_contract_hash(c2)
    ok = h1 != h2
    return _p("Contratos con contenido distinto (aunque solo difiera 'name') producen "
              "contract_hash distinto", ok)


# --------------------------------------------------------------------------- #
# El runner no toca simulate_v3                                              #
# --------------------------------------------------------------------------- #
def test_runner_no_modifica_simulate_v3_en_codigo():
    src = inspect.getsource(runner)
    ok = "def simulate_v3" not in src and "backtest.simulate_v3 =" not in src
    return _p("research/runner.py NO redefine ni reasigna backtest.simulate_v3 — solo lo invoca", ok)


def test_cost_per_trade_se_restaura_tras_ejecucion():
    orig = backtest.COST_PER_TRADE
    runner.run(_valid_contract())
    ok = backtest.COST_PER_TRADE == orig
    return _p(f"backtest.COST_PER_TRADE queda restaurado a {orig} después de run() "
              f"(valor actual={backtest.COST_PER_TRADE})", ok)


def test_cost_per_trade_se_restaura_incluso_si_management_falla():
    """Fuerza una excepción dentro de MANAGEMENT_LAYERS['V3-A'] y confirma
    que el finally de _run_v3a restaura la constante de todas formas."""
    orig = backtest.COST_PER_TRADE
    broken = runner.MANAGEMENT_LAYERS
    original_fn = broken["V3-A"]

    def _boom(*args, **kwargs):
        raise RuntimeError("boom simulado")

    runner.MANAGEMENT_LAYERS["V3-A"] = _boom
    ok = False
    try:
        runner.run(_valid_contract())
    except RuntimeError:
        ok = backtest.COST_PER_TRADE == orig
    finally:
        runner.MANAGEMENT_LAYERS["V3-A"] = original_fn

    return _p(f"backtest.COST_PER_TRADE se restaura incluso si el mecanismo de Gestión "
              f"lanza una excepción (valor actual={backtest.COST_PER_TRADE})", ok)


# --------------------------------------------------------------------------- #
# Fase 3 — endurecimiento: sin dependencia research -> scripts, sin          #
# constantes científicas ocultas, año declarado se respeta exacto.          #
# --------------------------------------------------------------------------- #
def test_runner_no_importa_scripts():
    """Inspección de código (no solo de sys.modules, que podría dar falso
    positivo si algo más ya importó scripts.* antes) — confirma que el
    CÓDIGO FUENTE de research/runner.py no contiene ningún import de
    scripts/, ni siquiera dentro de una función."""
    src = inspect.getsource(runner)
    ok = "import scripts" not in src and "from scripts" not in src
    return _p("research/runner.py NO contiene ningún 'import scripts'/'from scripts' "
              "en su código fuente (dependencia research -> scripts eliminada, Fase 3)", ok)


def test_research_data_no_importa_scripts():
    """research/data.py (donde vive la carga real de datasets) tampoco
    debe importar scripts/ — si el runner delegara la dependencia
    prohibida un nivel más abajo, seguiría existiendo."""
    import research.data as data_mod
    src = inspect.getsource(data_mod)
    ok = "import scripts" not in src and "from scripts" not in src
    return _p("research/data.py TAMPOCO importa scripts/ — la dependencia no se "
              "movió un nivel más abajo, se eliminó de verdad", ok)


def test_config_recibe_exactamente_los_valores_del_contrato():
    """'Sin constantes científicas ocultas': espía backtest.Config para
    confirmar que atr_mult/atr_period/max_hold/risk/sessions que recibe
    son EXACTAMENTE los del contrato — no un default silencioso del
    runner que compense/reemplace un valor no declarado."""
    orig_config = backtest.Config
    captured = {}

    class _SpyConfig(orig_config):
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)
            super().__init__(*args, **kwargs)

    c = _valid_contract()
    c["atr_mult"] = 1.9   # valor deliberadamente distinto del default (1.5) para
    c["max_hold"] = 17    # confirmar que el runner NO usa el default de backtest.Config,
    c["risk"] = 0.0123    # usa lo declarado en el contrato.

    backtest.Config = _SpyConfig
    try:
        runner.run(c)
    finally:
        backtest.Config = orig_config

    ok = (
        captured.get("atr_mult") == 1.9
        and captured.get("max_hold") == 17
        and captured.get("risk") == 0.0123
        and captured.get("sessions") == runner.SESSION_WINDOWS["dcv1_activo_15h"]
    )
    return _p(f"backtest.Config recibe exactamente atr_mult/max_hold/risk/sessions "
              f"del contrato, sin sustituciones silenciosas (capturado: {captured})", ok)


def test_periodo_ejecutado_es_exactamente_el_declarado():
    """Ningún año no declarado puede entrar en la ejecución: el
    ExperimentResult.period debe ser EXACTO al año declarado en
    experiment['years'] — nunca otro."""
    c = _valid_contract()
    c["years"] = {"validate": 2023}
    result = runner.run(c)
    ok = result.period == 2023 and result.period_role == "validate"
    return _p(f"ExperimentResult.period ({result.period}) coincide exacto con el año "
              f"declarado en el contrato (2023), period_role ('{result.period_role}') "
              f"con el rol declarado ('validate')", ok)


def test_gates_canonicos_siguen_vigentes_tras_fase_3():
    """Re-confirmación explícita, tras el refactor de Fase 3, de que los
    gates que el runner exige siguen siendo los mismos 4 umbrales
    oficiales — no se relajaron ni cambiaron durante la eliminación de la
    dependencia research -> scripts."""
    ok = (
        research.PF_MIN == 1.50 and research.MAX_DD_MIN == -10.0
        and research.EXP_R_MIN == 0.0 and research.FREQ_MIN_PER_MONTH == 6
        and research.FREQ_MAX_PER_MONTH == 12
    )
    return _p("Gates canónicos (PF>=1.50/MaxDD>=-10%/ExpR>0/freq en [6,12]) sin cambios "
              "tras el refactor de Fase 3", ok)


ALL_TESTS = [
    test_contrato_valido_no_lanza,
    test_contrato_valido_ejecuta_completo,
    test_sin_independent_variable_rechaza,
    test_independent_variable_vacio_rechaza,
    test_componente_inexistente_rechaza_bias,
    test_componente_no_soportado_en_mvp_rechaza_trigger,
    test_management_no_soportado_rechaza,
    test_management_params_distintos_de_v3a_rechaza,
    test_gates_ausentes_rechaza,
    test_gates_distintos_de_canonicos_rechaza,
    test_blind_sin_autorizar_rechaza,
    test_blind_autorizado_no_rechaza_por_ese_motivo,
    test_multiples_activos_rechaza,
    test_multiples_anios_rechaza,
    test_falta_campo_obligatorio_rechaza,
    test_rechazo_es_antes_de_tocar_datos,
    test_mismo_contrato_mismo_hash_y_mismo_resultado,
    test_contratos_distintos_hash_distinto,
    test_runner_no_modifica_simulate_v3_en_codigo,
    test_cost_per_trade_se_restaura_tras_ejecucion,
    test_cost_per_trade_se_restaura_incluso_si_management_falla,
    test_runner_no_importa_scripts,
    test_research_data_no_importa_scripts,
    test_config_recibe_exactamente_los_valores_del_contrato,
    test_periodo_ejecutado_es_exactamente_el_declarado,
    test_gates_canonicos_siguen_vigentes_tras_fase_3,
]


def main():
    print("research/tests/test_runner_invariants — disciplina científica del runner (Fase 2)\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
