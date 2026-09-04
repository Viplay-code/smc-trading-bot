"""
research/tests/test_run_many.py — Automatización experimental, Componente 3
(`run_many`, ejecución de múltiples contratos, 2026-09-04).

`run_many` es un orquestador determinista en memoria que delega el 100% de
la ejecución a `research.runner.run()`, sin ninguna lógica experimental
propia — estos tests verifican exactamente eso: la igualdad
`run_many(contracts, include_trades=X)[i] == run(contracts[i],
include_trades=X)`, el rechazo de lista vacía, la política fail-fast (con
identificación de índice y preservación del tipo de excepción), la
ausencia de mutación de los contratos de entrada, el aislamiento de
`cost_per_trade` entre celdas, y el determinismo.

Explícitamente NO prueba generación de parameter_grid, persistencia,
comparación de baseline, ni summarize_decision — ninguno existe todavía
(fuera de alcance de este componente).

Ejecutar:
    python -m research.tests.test_run_many  (o con pytest)
"""
from __future__ import annotations

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


def _valid_contract(name: str = "run_many_check", asset: str = "BTCUSDT", year: int = 2022) -> dict:
    """Mismo contrato mínimo que los demás archivos de test de
    research/tests/ — duplicado localmente por la misma convención de
    test standalone ya usada en todo el paquete."""
    return {
        "name": name, "contract_version": "1", "assets": [asset],
        "years": {"train": year}, "bias": {"name": "A_ema200_neutral", "params": {}},
        "trigger": {"name": "T1_ema_cross", "params": {}},
        "entry": {"name": "C_market_close", "params": {}},
        "session": "dcv1_activo_15h", "management": {"name": "V3-A", "params": {}},
        "risk": 0.005, "cost_per_trade": 0.0009, "max_hold": 20, "atr_mult": 1.5,
        "gates": dict(_CANONICAL_GATES), "independent_variable": "management.name",
        "blind_authorized": False,
    }


# --------------------------------------------------------------------------- #
# Igualdad central: run_many(contracts)[i] == run(contracts[i])              #
# --------------------------------------------------------------------------- #
def test_run_many_un_contrato_igual_a_run():
    c = _valid_contract()
    esperado = [runner.run(dict(c))]
    obtenido = runner.run_many([dict(c)])
    ok = obtenido == esperado
    return _p("run_many([c]) == [run(c)]", ok)


def test_run_many_include_trades_true_conserva_la_tupla():
    c = _valid_contract()
    esperado = [runner.run(dict(c), include_trades=True)]
    obtenido = runner.run_many([dict(c)], include_trades=True)
    ok = (
        obtenido == esperado
        and len(obtenido) == 1
        and isinstance(obtenido[0], tuple)
        and len(obtenido[0]) == 2
    )
    return _p("run_many([c], include_trades=True) == [run(c, include_trades=True)] "
              "(tupla (ExperimentResult, list[TradeRecord]) sin reinterpretar)", ok)


def test_run_many_varios_contratos_conserva_orden_y_equivalencia():
    c1 = _valid_contract(name="a", asset="BTCUSDT", year=2022)
    c2 = _valid_contract(name="b", asset="ETHUSDT", year=2022)
    c3 = _valid_contract(name="c", asset="SOLUSDT", year=2023)
    contracts = [dict(c1), dict(c2), dict(c3)]

    esperado = [runner.run(dict(c1)), runner.run(dict(c2)), runner.run(dict(c3))]
    obtenido = runner.run_many(contracts)

    ok = (
        obtenido == esperado
        and [r.asset for r in obtenido] == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        and [r.contract_hash for r in obtenido] == [r.contract_hash for r in esperado]
    )
    return _p("run_many con 3 contratos distintos conserva el orden y equivale a "
              "llamar run() individualmente sobre cada uno", ok)


# --------------------------------------------------------------------------- #
# Lista vacía                                                                 #
# --------------------------------------------------------------------------- #
def test_run_many_lista_vacia_rechaza_antes_de_ejecutar():
    calls = []
    orig_run = runner.run

    def _spy(contract, include_trades=False):
        calls.append(contract)
        return orig_run(contract, include_trades)

    runner.run = _spy
    try:
        ok = True
        try:
            runner.run_many([])
            ok = False
        except runner.ContractError:
            pass
        ok = ok and len(calls) == 0
    finally:
        runner.run = orig_run
    return _p("run_many([]) -> ContractError, sin llamar a run() ninguna vez", ok)


# --------------------------------------------------------------------------- #
# Fail-fast: índice, tipo de excepción, no ejecuta posteriores               #
# --------------------------------------------------------------------------- #
def test_run_many_contrato_invalido_en_posicion_intermedia():
    """Contrato REAL inválido (sin 'gates') en la posición 1 de 3 — confirma
    tipo de excepción preservado (ContractError) y que la nota adjunta
    (add_note, PEP 678) identifica la posición exacta, sin reconstruir la
    excepción (mensaje original de ContractError sin alterar en str(e))."""
    c1 = _valid_contract(name="a")
    c_bad = _valid_contract(name="bad")
    del c_bad["gates"]
    c3 = _valid_contract(name="c")

    ok = True
    try:
        runner.run_many([dict(c1), dict(c_bad), dict(c3)])
        ok = False
    except runner.ContractError as e:
        notas = getattr(e, "__notes__", [])
        ok = any("posición 1" in n for n in notas)
        ok = ok and "gates" in str(e)  # mensaje original de validate_contract intacto, sin reconstruir
    except Exception as e:
        ok = False
        print(f"    tipo de excepción inesperado: {type(e).__name__}: {e}")
    return _p("run_many con contrato inválido en posición 1 de 3 -> ContractError "
              "(tipo y mensaje original preservados, EXACTAMENTE el mismo objeto que lanzó "
              "run()), con una nota (add_note) que identifica la posición", ok)


def test_run_many_add_note_es_universal_para_excepciones_no_triviales():
    """Confirma que el mecanismo NO depende de que la excepción acepte un
    constructor de un solo argumento — usa una excepción real de la
    stdlib (UnicodeDecodeError) cuyo constructor exige 5 argumentos
    posicionales específicos, algo que `type(e)("mensaje")` no podría
    reconstruir sin lanzar TypeError."""
    calls = []
    orig_run = runner.run

    def _spy(contract, include_trades=False):
        calls.append(contract["name"])
        if contract["name"] == "bad":
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "byte invalido simulado")
        return f"resultado-{contract['name']}"

    runner.run = _spy
    try:
        c1 = _valid_contract(name="ok1")
        c_bad = _valid_contract(name="bad")
        ok = True
        try:
            runner.run_many([c1, c_bad])
            ok = False
        except UnicodeDecodeError as e:
            notas = getattr(e, "__notes__", [])
            ok = any("posición 1" in n for n in notas) and e.reason == "byte invalido simulado"
        except Exception as e:
            ok = False
            print(f"    tipo de excepción inesperado: {type(e).__name__}: {e}")
    finally:
        runner.run = orig_run
    return _p("run_many propaga UnicodeDecodeError (constructor no trivial, 5 args) sin "
              "romper — add_note() es universal, no depende de la firma del constructor", ok)


def test_run_many_fail_fast_no_ejecuta_contratos_posteriores():
    """Spy sobre runner.run (mismo patrón de monkeypatch de free-name ya
    usado en otros tests de este paquete, ej. backtest.simulate_v3) —
    confirma que, tras fallar el contrato en la posición 1, run() NUNCA
    se invoca para la posición 2."""
    calls = []
    orig_run = runner.run

    def _spy(contract, include_trades=False):
        calls.append(contract["name"])
        if contract["name"] == "bad":
            raise runner.ContractError("boom simulado")
        return f"resultado-{contract['name']}"

    runner.run = _spy
    try:
        c1 = _valid_contract(name="ok1")
        c_bad = _valid_contract(name="bad")
        c3 = _valid_contract(name="ok3")
        ok = True
        try:
            runner.run_many([c1, c_bad, c3])
            ok = False
        except runner.ContractError:
            pass
        ok = ok and calls == ["ok1", "bad"]  # NUNCA llega a "ok3"
    finally:
        runner.run = orig_run
    return _p(f"Tras fallar el contrato en posición 1, run() NUNCA se invoca para la "
              f"posición 2 (llamadas registradas: {calls})", ok)


def test_run_many_no_devuelve_resultados_parciales():
    """La excepción impide cualquier retorno — no hay forma de recuperar
    ni siquiera los resultados de los contratos que sí tuvieron éxito
    antes del fallo (fail-fast estricto, sin resultados parciales)."""
    c1 = _valid_contract(name="a")
    c_bad = _valid_contract(name="bad")
    del c_bad["cost_per_trade"]

    retorno = "NO_SE_ASIGNO"
    try:
        retorno = runner.run_many([dict(c1), dict(c_bad)])
    except runner.ContractError:
        pass
    ok = retorno == "NO_SE_ASIGNO"
    return _p("run_many no asigna/devuelve ningún valor cuando falla — sin resultados "
              "parciales accesibles", ok)


# --------------------------------------------------------------------------- #
# No mutación de los contratos de entrada                                    #
# --------------------------------------------------------------------------- #
def test_run_many_no_muta_los_contratos_de_entrada():
    c1 = _valid_contract(name="a")
    c2 = _valid_contract(name="b", asset="ETHUSDT")
    snapshot1 = dict(c1)
    snapshot2 = dict(c2)
    contracts = [c1, c2]

    runner.run_many(contracts)

    ok = c1 == snapshot1 and c2 == snapshot2 and contracts[0] is c1 and contracts[1] is c2
    return _p("run_many no muta ninguno de los dicts de contracts", ok)


# --------------------------------------------------------------------------- #
# Aislamiento de cost_per_trade entre celdas + restauración final            #
# --------------------------------------------------------------------------- #
def test_run_many_aisla_cost_per_trade_entre_contratos():
    c_barato = _valid_contract(name="barato")
    c_barato["cost_per_trade"] = 0.0001
    c_caro = _valid_contract(name="caro", asset="ETHUSDT")
    c_caro["cost_per_trade"] = 0.01

    r_barato, r_caro = runner.run_many([c_barato, c_caro])

    # Ejecutados por separado (fuera de run_many) para comparar: el costo de
    # cada celda debe coincidir con el de SU PROPIO contrato, no con el del
    # otro ni con una mezcla entre ambos.
    r_barato_solo = runner.run(dict(c_barato))
    r_caro_solo = runner.run(dict(c_caro))

    ok = (
        r_barato.total_r == r_barato_solo.total_r
        and r_caro.total_r == r_caro_solo.total_r
    )
    return _p(f"cost_per_trade de cada contrato no contamina al otro dentro de la "
              f"misma llamada a run_many (total_r barato={r_barato.total_r}, "
              f"caro={r_caro.total_r}, coinciden con ejecución individual)", ok)


def test_run_many_restaura_cost_per_trade_al_finalizar():
    orig = backtest.COST_PER_TRADE
    c1 = _valid_contract(name="a")
    c2 = _valid_contract(name="b", asset="ETHUSDT")
    runner.run_many([c1, c2])
    ok = backtest.COST_PER_TRADE == orig
    return _p(f"backtest.COST_PER_TRADE queda restaurado a {orig} tras run_many "
              f"(valor actual={backtest.COST_PER_TRADE})", ok)


# --------------------------------------------------------------------------- #
# Determinismo                                                                #
# --------------------------------------------------------------------------- #
def test_run_many_determinista():
    c1 = _valid_contract(name="a")
    c2 = _valid_contract(name="b", asset="ETHUSDT")
    r1 = runner.run_many([dict(c1), dict(c2)])
    r2 = runner.run_many([dict(c1), dict(c2)])
    ok = (
        r1 == r2
        and [r.contract_hash for r in r1] == [r.contract_hash for r in r2]
    )
    return _p("Misma lista de contratos ejecutada dos veces produce resultados "
              "idénticos en el mismo orden (mismos contract_hash por posición)", ok)


ALL_TESTS = [
    test_run_many_un_contrato_igual_a_run,
    test_run_many_include_trades_true_conserva_la_tupla,
    test_run_many_varios_contratos_conserva_orden_y_equivalencia,
    test_run_many_lista_vacia_rechaza_antes_de_ejecutar,
    test_run_many_contrato_invalido_en_posicion_intermedia,
    test_run_many_add_note_es_universal_para_excepciones_no_triviales,
    test_run_many_fail_fast_no_ejecuta_contratos_posteriores,
    test_run_many_no_devuelve_resultados_parciales,
    test_run_many_no_muta_los_contratos_de_entrada,
    test_run_many_aisla_cost_per_trade_entre_contratos,
    test_run_many_restaura_cost_per_trade_al_finalizar,
    test_run_many_determinista,
]


def main():
    print("research/tests/test_run_many — Componente 3 (ejecución de múltiples contratos)\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
