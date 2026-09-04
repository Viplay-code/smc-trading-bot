"""
research/tests/test_contract_extension.py — Automatización experimental,
Componente 2 (ampliación del contrato experimental, 2026-09-04): tests de
los 4 campos opcionales nuevos (`hypothesis`, `space`, `baseline`,
`parameter_grid`) y de los 3 campos nuevos de `ExperimentResult`
(`dataset_version`, `pipeline_version`, `engine_version`).

Explícitamente NO prueba generación de combinaciones de `parameter_grid`
NI comparación de `baseline` — ninguna de las dos existe todavía (fuera de
alcance de este componente, ver diseño revisado y aprobado).

Ejecutar:
    python -m research.tests.test_contract_extension  (o con pytest)
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")
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
    """Mismo contrato mínimo que research/tests/test_runner_invariants.py
    ::_valid_contract — duplicado localmente por la misma convención de
    test standalone ya usada en todo research/tests/."""
    return {
        "name": "contract_extension_check", "contract_version": "1", "assets": ["BTCUSDT"],
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
# Regresión de contrato existente                                            #
# --------------------------------------------------------------------------- #
def test_contrato_sin_campos_nuevos_sigue_validando_y_ejecutando():
    """Un contrato que no declara ninguno de los 4 campos nuevos debe
    validar y ejecutar exactamente igual que antes de este componente —
    y los 3 campos nuevos de ExperimentResult deben quedar poblados
    automáticamente por el motor (no None, porque SÍ hay dataset real)."""
    c = _valid_contract()
    ok = True
    try:
        runner.validate_contract(c)
    except runner.ContractError as e:
        ok = False
        print(f"    {e}")
    try:
        result = runner.run(c)
        ok = ok and result.n_trades > 0
    except Exception as e:
        ok = False
        print(f"    excepción inesperada: {type(e).__name__}: {e}")
    return _p("Contrato sin hypothesis/space/baseline/parameter_grid valida y "
              "ejecuta de punta a punta sin cambios", ok)


# --------------------------------------------------------------------------- #
# hypothesis / space — metadata de trazabilidad, sin efecto en el Engine     #
# --------------------------------------------------------------------------- #
def test_hypothesis_valida_no_lanza():
    c = _valid_contract()
    c["hypothesis"] = "Si aislamos el trailing, PF mejora respecto a V3-A."
    ok = True
    try:
        runner.validate_contract(c)
    except runner.ContractError as e:
        ok = False
        print(f"    {e}")
    return _p("hypothesis (string no vacío) pasa validate_contract() sin excepción", ok)


def test_hypothesis_vacio_rechaza():
    c = _valid_contract()
    c["hypothesis"] = ""
    return _p("hypothesis='' -> ContractError", _expect_contract_error(c, "hypothesis vacío"))


def test_hypothesis_no_string_rechaza():
    c = _valid_contract()
    c["hypothesis"] = 123
    return _p("hypothesis no-string -> ContractError", _expect_contract_error(c, "hypothesis no-string"))


def test_space_valido_no_lanza():
    c = _valid_contract()
    c["space"] = "Espacio 6"
    ok = True
    try:
        runner.validate_contract(c)
    except runner.ContractError as e:
        ok = False
        print(f"    {e}")
    return _p("space (string no vacío) pasa validate_contract() sin excepción", ok)


def test_space_vacio_rechaza():
    c = _valid_contract()
    c["space"] = ""
    return _p("space='' -> ContractError", _expect_contract_error(c, "space vacío"))


def test_hypothesis_y_space_no_tienen_efecto_en_ejecucion():
    """Dos contratos idénticos salvo por hypothesis/space deben producir el
    MISMO resultado numérico (n_entries/n_trades/pf/...) — confirma que son
    metadata de trazabilidad pura, sin ningún efecto sobre el Engine."""
    c1 = _valid_contract()
    c2 = _valid_contract()
    c2["hypothesis"] = "Una hipótesis cualquiera, sin relación con el resultado."
    c2["space"] = "Espacio X"

    r1 = runner.run(c1)
    r2 = runner.run(c2)

    campos_numericos = ("n_entries", "n_trades", "pf", "wr", "exp_r", "total_r", "max_dd", "freq", "gate_pass")
    ok = all(getattr(r1, f) == getattr(r2, f) for f in campos_numericos)
    return _p("hypothesis/space no cambian ningún resultado numérico (n_entries, n_trades, "
              "pf, wr, exp_r, total_r, max_dd, freq, gate_pass idénticos)", ok)


# --------------------------------------------------------------------------- #
# contract_hash — identidad exacta, no funcional (decisión explícita)        #
# --------------------------------------------------------------------------- #
def test_contract_hash_cambia_con_hypothesis_y_space():
    """Decisión explícita del diseño: contract_hash es identidad EXACTA del
    contrato, no identidad FUNCIONAL de la ejecución — dos contratos
    funcionalmente idénticos con distinto hypothesis/space deben producir
    contract_hash DISTINTOS."""
    c1 = _valid_contract()
    c2 = _valid_contract()
    c2["hypothesis"] = "Una hipótesis cualquiera."
    c2["space"] = "Espacio X"

    h1 = research.compute_contract_hash(c1)
    h2 = research.compute_contract_hash(c2)
    ok = h1 != h2
    return _p(f"contract_hash cambia cuando se agrega hypothesis/space "
              f"(h1={h1}, h2={h2}) — identidad exacta, no funcional, por diseño", ok)


# --------------------------------------------------------------------------- #
# parameter_grid — validación de FORMA únicamente                            #
# --------------------------------------------------------------------------- #
def test_parameter_grid_valido_no_lanza():
    c = _valid_contract()
    c["parameter_grid"] = {"atr_mult": [1.2, 1.5, 1.8], "management.params.distance": [1.0]}
    # atr_mult=1.5 ya existe en el contrato base; management.params.distance
    # no existe en V3-A/params={} — usar un path que sí resuelva:
    c["management"]["params"] = {"be": 1.0, "activation": 2.0, "distance": 1.0}
    ok = True
    try:
        runner.validate_contract(c)
    except runner.ContractError as e:
        ok = False
        print(f"    {e}")
    return _p("parameter_grid con rutas resolubles/escalares/sin duplicados pasa "
              "validate_contract() sin excepción (sin generar ninguna combinación)", ok)


def test_parameter_grid_ruta_inexistente_rechaza():
    c = _valid_contract()
    c["parameter_grid"] = {"no_existe_este_campo": [1, 2]}
    return _p("parameter_grid con ruta inexistente -> ContractError",
              _expect_contract_error(c, "ruta inexistente"))


def test_parameter_grid_ruta_anidada_inexistente_rechaza():
    c = _valid_contract()
    c["parameter_grid"] = {"management.params.no_existe": [1.0, 2.0]}
    return _p("parameter_grid con ruta anidada que no resuelve contra el contrato base "
              "-> ContractError", _expect_contract_error(c, "ruta anidada inexistente"))


def test_parameter_grid_ruta_gates_rechaza():
    c = _valid_contract()
    c["parameter_grid"] = {"gates.pf_min": [1.0, 1.2]}
    return _p("parameter_grid apuntando a gates.* -> ContractError",
              _expect_contract_error(c, "ruta a gates"))


def test_parameter_grid_ruta_identidad_rechaza():
    c = _valid_contract()
    c["parameter_grid"] = {"name": ["a", "b"]}
    return _p("parameter_grid apuntando a un campo de identidad (name) -> ContractError",
              _expect_contract_error(c, "ruta de identidad"))


def test_parameter_grid_nombre_de_capa_rechaza():
    c = _valid_contract()
    c["parameter_grid"] = {"trigger.name": ["T1_ema_cross", "A_sweep_bos"]}
    return _p("parameter_grid apuntando a trigger.name -> ContractError "
              "(no se puede variar la identidad de una capa vía grid)",
              _expect_contract_error(c, "*.name prohibido"))


def test_parameter_grid_todos_los_name_prohibidos():
    ok = True
    for path in ("bias.name", "trigger.name", "entry.name", "management.name"):
        c = _valid_contract()
        c["parameter_grid"] = {path: ["x", "y"]}
        ok = ok and _expect_contract_error(c, f"{path} prohibido")
    return _p("bias.name/trigger.name/entry.name/management.name TODOS rechazados "
              "como ruta de parameter_grid", ok)


def test_parameter_grid_anidado_rechaza():
    c = _valid_contract()
    c["parameter_grid"] = {"atr_mult": {"nested": [1.0, 2.0]}}
    return _p("parameter_grid con un dict como valor (grid anidado) -> ContractError",
              _expect_contract_error(c, "grid anidado (dict como valor)"))


def test_parameter_grid_valor_lista_dentro_de_lista_rechaza():
    c = _valid_contract()
    c["parameter_grid"] = {"atr_mult": [1.0, [2.0, 3.0]]}
    return _p("parameter_grid con una lista dentro de la lista de valores -> ContractError",
              _expect_contract_error(c, "lista anidada dentro de valores"))


def test_parameter_grid_lista_vacia_rechaza():
    c = _valid_contract()
    c["parameter_grid"] = {"atr_mult": []}
    return _p("parameter_grid con lista vacía -> ContractError",
              _expect_contract_error(c, "lista vacía"))


def test_parameter_grid_duplicados_rechaza():
    c = _valid_contract()
    c["parameter_grid"] = {"atr_mult": [1.0, 1.5, 1.5]}
    return _p("parameter_grid con valores duplicados -> ContractError",
              _expect_contract_error(c, "duplicados"))


def test_parameter_grid_cardinalidad_excede_maximo_rechaza():
    c = _valid_contract()
    # 8 x 8 = 64 > MAX_GRID_CELLS (50) — producto determinista, sin ejecutar nada.
    vals_a = [round(1.0 + i * 0.01, 2) for i in range(8)]
    vals_b = [round(0.001 + i * 0.0001, 4) for i in range(8)]
    c["parameter_grid"] = {"atr_mult": vals_a, "cost_per_trade": vals_b}
    ok = 8 * 8 > runner.MAX_GRID_CELLS
    ok = ok and _expect_contract_error(c, "cardinalidad excede MAX_GRID_CELLS")
    return _p(f"parameter_grid con cardinalidad 64 > MAX_GRID_CELLS={runner.MAX_GRID_CELLS} "
              f"-> ContractError", ok)


def test_parameter_grid_cardinalidad_en_el_limite_no_lanza_por_ese_motivo():
    """Cardinalidad EXACTAMENTE en MAX_GRID_CELLS no debe rechazarse por
    cardinalidad (el límite es inclusivo: > MAX_GRID_CELLS rechaza, ==
    MAX_GRID_CELLS no)."""
    c = _valid_contract()
    n = runner.MAX_GRID_CELLS
    c["parameter_grid"] = {"atr_mult": [round(1.0 + i * 0.001, 4) for i in range(n)]}
    ok = True
    try:
        runner.validate_contract(c)
    except runner.ContractError as e:
        ok = False
        print(f"    {e}")
    return _p(f"parameter_grid con cardinalidad EXACTA {n} (== MAX_GRID_CELLS) no se "
              f"rechaza por cardinalidad", ok)


def test_parameter_grid_no_genera_ninguna_combinacion():
    """Confirmación explícita de alcance: declarar un parameter_grid válido
    NO cambia el resultado de run() respecto al mismo contrato sin grid —
    no se genera ninguna combinación, run() sigue ejecutando UNA sola
    celda (la del contrato base tal cual)."""
    c1 = _valid_contract()
    c2 = _valid_contract()
    c2["parameter_grid"] = {"cost_per_trade": [0.0009, 0.001, 0.0011]}

    r1 = runner.run(c1)
    r2 = runner.run(c2)
    campos_numericos = ("n_entries", "n_trades", "pf", "wr", "exp_r", "total_r", "max_dd", "freq")
    ok = all(getattr(r1, f) == getattr(r2, f) for f in campos_numericos)
    return _p("Declarar parameter_grid válido no genera ninguna combinación adicional — "
              "run() sigue ejecutando exactamente 1 celda, resultado idéntico al contrato sin grid", ok)


# --------------------------------------------------------------------------- #
# baseline — validación de FORMA únicamente                                  #
# --------------------------------------------------------------------------- #
def test_baseline_valido_no_lanza():
    c = _valid_contract()
    c["baseline"] = {
        "contract_hash": "0123456789abcdef", "experiment_name": "gestion_campaign_session_v3a",
        "asset": "BTCUSDT", "period": 2022,
    }
    ok = True
    try:
        runner.validate_contract(c)
    except runner.ContractError as e:
        ok = False
        print(f"    {e}")
    return _p("baseline con las 4 claves exactas, tipadas correctamente, pasa "
              "validate_contract() sin excepción (sin buscar ni comparar nada)", ok)


def test_baseline_claves_faltantes_rechaza():
    c = _valid_contract()
    c["baseline"] = {"contract_hash": "0123456789abcdef", "asset": "BTCUSDT"}
    return _p("baseline con claves faltantes -> ContractError",
              _expect_contract_error(c, "baseline claves faltantes"))


def test_baseline_clave_extra_rechaza():
    c = _valid_contract()
    c["baseline"] = {
        "contract_hash": "0123456789abcdef", "experiment_name": "x",
        "asset": "BTCUSDT", "period": 2022, "extra_no_declarada": True,
    }
    return _p("baseline con una clave extra no declarada -> ContractError",
              _expect_contract_error(c, "baseline clave extra"))


def test_baseline_contract_hash_formato_invalido_rechaza():
    c = _valid_contract()
    c["baseline"] = {
        "contract_hash": "no-es-un-hash-hex", "experiment_name": "x",
        "asset": "BTCUSDT", "period": 2022,
    }
    return _p("baseline.contract_hash con formato inválido (no hex de 16) -> ContractError",
              _expect_contract_error(c, "baseline.contract_hash inválido"))


def test_baseline_period_no_int_rechaza():
    c = _valid_contract()
    c["baseline"] = {
        "contract_hash": "0123456789abcdef", "experiment_name": "x",
        "asset": "BTCUSDT", "period": "2022",
    }
    return _p("baseline.period como string (no int) -> ContractError",
              _expect_contract_error(c, "baseline.period no-int"))


def test_baseline_no_es_dict_rechaza():
    c = _valid_contract()
    c["baseline"] = "gestion_campaign_session_results.csv"
    return _p("baseline como string (patrón legacy '_v3a_reference = ...') -> ContractError",
              _expect_contract_error(c, "baseline no es dict"))


# --------------------------------------------------------------------------- #
# ExperimentResult — propagación de dataset_version/pipeline_version/       #
# engine_version                                                             #
# --------------------------------------------------------------------------- #
def test_dataset_version_se_propaga():
    import versions
    result = runner.run(_valid_contract())
    ok = result.dataset_version == versions.DATASET_VERSION and result.dataset_version is not None
    return _p(f"ExperimentResult.dataset_version ({result.dataset_version!r}) coincide con "
              f"versions.DATASET_VERSION", ok)


def test_pipeline_version_se_propaga():
    import versions
    result = runner.run(_valid_contract())
    ok = result.pipeline_version == versions.PIPELINE_VERSION and result.pipeline_version is not None
    return _p(f"ExperimentResult.pipeline_version ({result.pipeline_version!r}) coincide con "
              f"versions.PIPELINE_VERSION", ok)


def test_engine_version_se_propaga():
    result = runner.run(_valid_contract())
    ok = result.engine_version == runner.ENGINE_VERSION and result.engine_version is not None
    return _p(f"ExperimentResult.engine_version ({result.engine_version!r}) coincide con "
              f"runner.ENGINE_VERSION", ok)


def test_campos_nuevos_de_experimentresult_no_rompen_igualdad_entre_corridas():
    """Mismo contrato ejecutado dos veces produce el mismo ExperimentResult
    completo (incluyendo los 3 campos nuevos) — determinismo preservado."""
    c = _valid_contract()
    r1 = runner.run(dict(c))
    r2 = runner.run(dict(c))
    ok = r1 == r2
    return _p("Mismo contrato ejecutado dos veces produce el mismo ExperimentResult "
              "completo, incluyendo dataset_version/pipeline_version/engine_version", ok)


ALL_TESTS = [
    test_contrato_sin_campos_nuevos_sigue_validando_y_ejecutando,
    test_hypothesis_valida_no_lanza,
    test_hypothesis_vacio_rechaza,
    test_hypothesis_no_string_rechaza,
    test_space_valido_no_lanza,
    test_space_vacio_rechaza,
    test_hypothesis_y_space_no_tienen_efecto_en_ejecucion,
    test_contract_hash_cambia_con_hypothesis_y_space,
    test_parameter_grid_valido_no_lanza,
    test_parameter_grid_ruta_inexistente_rechaza,
    test_parameter_grid_ruta_anidada_inexistente_rechaza,
    test_parameter_grid_ruta_gates_rechaza,
    test_parameter_grid_ruta_identidad_rechaza,
    test_parameter_grid_nombre_de_capa_rechaza,
    test_parameter_grid_todos_los_name_prohibidos,
    test_parameter_grid_anidado_rechaza,
    test_parameter_grid_valor_lista_dentro_de_lista_rechaza,
    test_parameter_grid_lista_vacia_rechaza,
    test_parameter_grid_duplicados_rechaza,
    test_parameter_grid_cardinalidad_excede_maximo_rechaza,
    test_parameter_grid_cardinalidad_en_el_limite_no_lanza_por_ese_motivo,
    test_parameter_grid_no_genera_ninguna_combinacion,
    test_baseline_valido_no_lanza,
    test_baseline_claves_faltantes_rechaza,
    test_baseline_clave_extra_rechaza,
    test_baseline_contract_hash_formato_invalido_rechaza,
    test_baseline_period_no_int_rechaza,
    test_baseline_no_es_dict_rechaza,
    test_dataset_version_se_propaga,
    test_pipeline_version_se_propaga,
    test_engine_version_se_propaga,
    test_campos_nuevos_de_experimentresult_no_rompen_igualdad_entre_corridas,
]


def main():
    print("research/tests/test_contract_extension — Componente 2 (ampliación del "
          "contrato experimental)\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
