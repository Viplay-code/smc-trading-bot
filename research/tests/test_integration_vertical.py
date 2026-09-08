"""
research/tests/test_integration_vertical.py — Integración vertical
controlada de C1–C8 (2026-09-05), autorizada como actividad de
adopción, NO como un componente nuevo (NO es C9).

Ejecuta REALMENTE, contra datos reales de `data/raw/` (no sintéticos),
la cadena completa:

    Contract -> validate_contract -> expand_universe -> run_many
    -> summarize_decision -> write_experiment_results_csv/write_decision_csv
    -> read_experiment_results_csv -> compare_results

usando EXCLUSIVAMENTE las APIs públicas de C1–C8 tal como existen —
sin ningún adaptador, sin ninguna abstracción nueva, sin modificar
ningún archivo de `research/*.py`.

Ancla (misma combinación ya usada como referencia de equivalencia en
C1/C5/C6, y en la integración vertical previa a C7):
`V3-A / T1_ema_cross / C_market_close / A_ema200_neutral /
dcv1_activo_15h`, 3 activos (BTCUSDT/ETHUSDT/SOLUSDT) x 2 años
(2022=train, 2023=validate) — 6 celdas, 1 candidato
(`candidate_fields=()`).

Objetivo: demostrar COMPOSICIÓN vertical real, no volver a probar cada
componente por separado (eso ya lo hacen sus propias suites — 39
tests en `test_persistence.py`, 23 en `test_comparison.py`, 13+3 en
`test_decision*.py`, 12 en `test_run_many.py`, 19 en
`test_expand_universe.py`, etc.). Este archivo asume que cada
componente ya está probado individualmente y verifica únicamente que
se componen correctamente sobre datos reales.

Los artifacts canónicos (`research_engine_v3a_t1_results.csv`/
`research_engine_v3a_t1_decision.csv`) se escriben en la raíz del
repositorio — misma convención ya usada por los ~25 CSV legacy
existentes (`<nombre>_results.csv`/`<nombre>_decision.csv`) — y se
regeneran en cada corrida de este test (escritura determinista: una
corrida futura produce contenido byte-idéntico al ya committeado,
verificable por `git diff` sin cambios).

Requiere `data/raw/` poblado para BTCUSDT/ETHUSDT/SOLUSDT 2022/2023
(confirmado presente en este entorno). Si no lo estuviera, este test
fallaría con un error real de datos faltantes — no se sustituye por
datos sintéticos, por diseño de esta integración.

Ejecutar:
    python -m research.tests.test_integration_vertical  (o con pytest)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, ".")
import research
from research import runner
from research.expand import expand_universe
from research.decision import summarize_decision
from research.persistence import (
    write_experiment_results_csv, write_decision_csv, read_experiment_results_csv,
)
from research.comparison import compare_results

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS_PATH = os.path.join(_REPO_ROOT, "research_engine_v3a_t1_results.csv")
DECISION_PATH = os.path.join(_REPO_ROOT, "research_engine_v3a_t1_decision.csv")

_CANONICAL_GATES = {
    "pf_min": research.PF_MIN, "max_dd_min": research.MAX_DD_MIN,
    "exp_r_min": research.EXP_R_MIN, "freq_min": research.FREQ_MIN_PER_MONTH,
    "freq_max": research.FREQ_MAX_PER_MONTH,
}

TEMPLATE = {
    "name": "integration_vertical_c1_c8_v3a_t1",
    "contract_version": "1",
    "assets": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "years": {"train": 2022, "validate": 2023},
    "bias": {"name": "A_ema200_neutral", "params": {}},
    "trigger": {"name": "T1_ema_cross", "params": {}},
    "entry": {"name": "C_market_close", "params": {}},
    "session": "dcv1_activo_15h",
    "management": {"name": "V3-A", "params": {}},
    "risk": 0.005,
    "cost_per_trade": 0.0009,
    "max_hold": 20,
    "atr_mult": 1.5,
    "gates": dict(_CANONICAL_GATES),
    "independent_variable": "asset",
    "blind_authorized": False,
}


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def _run_full_chain():
    """Ejecuta realmente los pasos 2-9 de la integración autorizada.
    Devuelve todos los objetos intermedios para que cada aserción del
    test pueda inspeccionar la etapa exacta que le corresponde -- sin
    volver a ejecutar nada."""
    # Paso 2-3: Contract -> expand_universe -> validate_contract.
    contracts = expand_universe(TEMPLATE)
    for c in contracts:
        runner.validate_contract(c)  # ContractError se propagaría sin capturar

    # Paso 4: run_many sobre las 6 celdas reales.
    results = runner.run_many(contracts)

    # Paso 5: summarize_decision.
    decisions = summarize_decision(
        results, candidate_fields=(), required_roles=("train", "validate"),
        rank_by_role="validate",
    )

    # Paso 6: Persistencia -- artifacts canónicos reales, vía C6.
    write_experiment_results_csv(RESULTS_PATH, results)
    write_decision_csv(DECISION_PATH, decisions, candidate_fields=())

    # Paso 7: Read-back del artifact REALMENTE escrito, vía C8.
    read_back = read_experiment_results_csv(RESULTS_PATH)

    return contracts, results, decisions, read_back


# --------------------------------------------------------------------------- #
# Composición vertical -- un único test grande, deliberadamente: el objetivo #
# es demostrar la CADENA, no repetir la cobertura unitaria ya existente.     #
# --------------------------------------------------------------------------- #
def test_integracion_vertical_c1_c8_sobre_datos_reales():
    contracts, results, decisions, read_back = _run_full_chain()
    ok = True

    # --- Contract válido + expansión exacta a 6 contratos --- #
    ok = ok and _p("expand_universe produce exactamente 6 contratos (3 activos x 2 roles)",
                    len(contracts) == 6)
    ok = ok and _p("Cada contrato generado pasó validate_contract sin excepción "
                    "(ya verificado arriba -- si hubiera fallado, ContractError habría abortado)",
                    True)

    # --- 6 resultados reales --- #
    ok = ok and _p("run_many produjo 6 ExperimentResult reales", len(results) == 6)
    ok = ok and _p("Los 6 resultados tienen n_trades > 0 (datos reales, no vacíos)",
                    all(r.n_trades > 0 for r in results))
    ok = ok and _p("Los 6 resultados provienen de datos reales (dataset_version/"
                    "pipeline_version/engine_version presentes)",
                    all(r.dataset_version and r.pipeline_version and r.engine_version for r in results))

    # --- Decisión producida --- #
    ok = ok and _p("summarize_decision produjo 3 CandidateDecision (1 por activo)",
                    len(decisions) == 3)
    ok = ok and _p("Los 3 activos están representados en la decisión",
                    {d.asset for d in decisions} == {"BTCUSDT", "ETHUSDT", "SOLUSDT"})

    # --- Artifacts escritos --- #
    ok = ok and _p(f"Artifact results.csv existe en {RESULTS_PATH}", os.path.exists(RESULTS_PATH))
    ok = ok and _p(f"Artifact decision.csv existe en {DECISION_PATH}", os.path.exists(DECISION_PATH))
    with open(RESULTS_PATH, encoding="utf-8") as f:
        results_lines = f.read().splitlines()
    with open(DECISION_PATH, encoding="utf-8") as f:
        decision_lines = f.read().splitlines()
    ok = ok and _p("results.csv tiene 7 líneas (1 header + 6 filas)", len(results_lines) == 7)
    ok = ok and _p("decision.csv tiene 4 líneas (1 header + 3 filas)", len(decision_lines) == 4)
    ok = ok and _p("Header de results.csv son las 22 columnas canónicas de EXPERIMENT_RESULT_COLUMNS",
                    results_lines[0] == ",".join(research.EXPERIMENT_RESULT_COLUMNS))
    ok = ok and _p("Header de decision.csv es asset,survives_required_roles,rank_within_asset "
                    "(candidate_fields=())", decision_lines[0] == "asset,survives_required_roles,rank_within_asset")

    # --- Read-back --- #
    ok = ok and _p("read_experiment_results_csv (C8) leyó 6 ExperimentResult del artifact "
                    "REALMENTE escrito por write_experiment_results_csv (C6)", len(read_back) == 6)

    # --- Caso 1: equivalencia write/read (Comparison sobre las 6 celdas) --- #
    comparaciones_equivalentes = [compare_results(read_back[i], results[i]) for i in range(6)]
    ok = ok and _p("compare_results(leído[i], original[i]) -> matches=True para las 6 celdas "
                    "(round-trip C6->C8 verificado por C7, no por igualdad de dataclass a mano)",
                    all(c.matches for c in comparaciones_equivalentes))

    # --- Caso 2: divergencia real entre 2 celdas reales distintas --- #
    btc_train = next(r for r in results if r.asset == "BTCUSDT" and r.period_role == "train")
    btc_validate = next(r for r in results if r.asset == "BTCUSDT" and r.period_role == "validate")
    comparacion_divergente = compare_results(btc_train, btc_validate)
    ok = ok and _p("compare_results(BTCUSDT/train, BTCUSDT/validate) -> matches=False "
                    "(celdas reales genuinamente distintas, sin fabricar la diferencia)",
                    comparacion_divergente.matches is False and len(comparacion_divergente.differences) > 0)

    # --- contract_hash: preservado y consistente --- #
    hashes_originales = [r.contract_hash for r in results]
    hashes_leidos = [r.contract_hash for r in read_back]
    ok = ok and _p("contract_hash preservado exacto entre original y read-back (las 6 celdas)",
                    hashes_originales == hashes_leidos)
    ok = ok and _p("Los 6 contract_hash son únicos (una celda = un contrato = un hash distinto)",
                    len(set(hashes_originales)) == 6)
    ok = ok and _p("Ningún contract_hash es None (metadata de reproducibilidad presente)",
                    all(h is not None for h in hashes_originales))

    return _p("INTEGRACIÓN VERTICAL C1-C8 completa, sobre datos reales, sin regresiones", ok)


ALL_TESTS = [
    test_integracion_vertical_c1_c8_sobre_datos_reales,
]


def main():
    print("research/tests/test_integration_vertical — Integración vertical C1-C8 "
          "(adopción controlada, NO es C9)\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
