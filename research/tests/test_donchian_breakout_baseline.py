"""
research/tests/test_donchian_breakout_baseline.py — Validación del baseline
científico mínimo de Donchian Channel Breakout / Trend Following
(2026-09-10), primera estrategia nueva construida directamente sobre C1-C8
(sin predecesor legacy — ver docstring de
scripts/donchian_breakout_baseline.py).

Sin comparación contra ningún artifact histórico (no existe: es la primera
corrida de esta familia de estrategia) — la validación acá es estructural
(universo/contrato/alcance) y de consistencia interna (reproducibilidad,
persistencia round-trip), sobre datos reales de `data/raw/`.

Ejecutar:
    python -m research.tests.test_donchian_breakout_baseline  (o con pytest)
"""
from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, ".")
import research
from research import runner
from research.comparison import compare_results
from research.persistence import read_experiment_results_csv, write_experiment_results_csv
import scripts.donchian_breakout_baseline as camp


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


# --------------------------------------------------------------------------- #
# Universo canónico (C4) — estructural, sin datos reales                    #
# --------------------------------------------------------------------------- #
def test_build_universe_produce_12_contratos_alcance_exacto():
    contracts = camp.build_universe(("BTCUSDT", "ETHUSDT", "SOLUSDT"), {"train": 2022, "validate": 2023})
    for c in contracts:
        runner.validate_contract(c)  # ContractError se propagaría sin capturar
    biases = {c["bias"]["name"] for c in contracts}
    triggers = {c["trigger"]["name"] for c in contracts}
    entries = {c["entry"]["name"] for c in contracts}
    sessions = {c["session"] for c in contracts}
    mgmts = {c["management"]["name"] for c in contracts}
    trigger_params = {tuple(sorted(c["trigger"]["params"].items())) for c in contracts}
    hashes = {research.compute_contract_hash(c) for c in contracts}
    ok = (
        len(contracts) == 12
        and biases == {"A_ema200_neutral"}
        and triggers == {"D_range_breakout"}
        and entries == {"C_market_close"}
        and sessions == {"sin_filtro_24h"}
        and mgmts == {"V3-A", "V3-B"}
        and trigger_params == {()}  # trigger.params vacío en los 12 contratos
        and len(hashes) == 12
    )
    return _p(f"build_universe produce 12 contratos (3 assets x 2 years x 2 managements), "
              f"bias/trigger/entry/session fijos, trigger.params vacío, management={{'V3-A','V3-B'}} "
              f"(visto: {mgmts})", ok)


def test_trigger_params_vacio_no_promete_control_de_range_lookback():
    """Guardia de regresión conceptual: mientras research.entries no
    propague trigger.params genéricamente (restricción arquitectónica
    documentada, ver docstring del script), este baseline NO debe declarar
    ningún valor en trigger.params -- declarar uno sería aceptado por
    validate_contract pero ignorado en silencio por find_entries, creando
    una apariencia falsa de control experimental."""
    contracts = camp.build_universe(("BTCUSDT",), {"train": 2022})
    ok = all(c["trigger"]["params"] == {} for c in contracts)
    return _p("trigger.params == {} en todos los contratos (ningún range_lookback declarado "
              "falsamente como controlado)", ok)


def test_universo_no_incluye_raw_ni_otros_managements():
    contracts = camp.build_universe(("BTCUSDT",), {"train": 2022})
    ok = len(contracts) == 2 and all(c["management"]["name"] in ("V3-A", "V3-B") for c in contracts)
    ok = ok and "Raw" not in {c["management"]["name"] for c in contracts}
    return _p("universo restringido a V3-A/V3-B -- Raw excluido (mismo criterio ya establecido "
              "en el resto del programa)", ok)


# --------------------------------------------------------------------------- #
# Ejecución real — sobre datos reales de data/raw/.                         #
# --------------------------------------------------------------------------- #
def test_run_baseline_produce_12_resultados_reales():
    """No hay artifact histórico contra el cual comparar (primera corrida
    de esta familia) -- se verifica consistencia interna: 12 resultados,
    n_entries>0 (el Trigger genera eventos reales), gate_pass es siempre
    bool, contract_hash únicos, metadata de reproducibilidad presente."""
    if not os.path.exists("data/raw"):
        return _p("run_baseline produce 12 resultados reales (data/raw/ no disponible)", False)

    contracts, results = camp.run_baseline()
    ok = (
        len(contracts) == 12 and len(results) == 12
        and all(r.n_entries > 0 for r in results)
        and all(isinstance(r.gate_pass, bool) for r in results)
        and all(r.dataset_version and r.pipeline_version and r.engine_version for r in results)
        and len({r.contract_hash for r in results}) == 12
    )
    return _p(f"run_baseline produce 12/12 resultados reales, n_entries>0, gate_pass bool, "
              f"metadata de reproducibilidad presente, 12 contract_hash únicos", ok)


def test_reproducibilidad_misma_corrida_mismo_resultado():
    """Mismo criterio de determinismo ya exigido en todo el programa: dos
    corridas del mismo universo producen los mismos ExperimentResult
    (mismo contract_hash por posición, mismas métricas)."""
    if not os.path.exists("data/raw"):
        return _p("reproducibilidad (data/raw/ no disponible)", False)

    contracts1, results1 = camp.run_baseline(("BTCUSDT",))
    contracts2, results2 = camp.run_baseline(("BTCUSDT",))
    ok = (
        [r.contract_hash for r in results1] == [r.contract_hash for r in results2]
        and results1 == results2
    )
    return _p("misma corrida ejecutada dos veces produce los mismos ExperimentResult "
              "(mismo contract_hash por posición)", ok)


def test_persistence_roundtrip_sobre_datos_reales():
    """C6 write -> C8 read -> C7 compare_results sobre los 12 resultados
    reales, en un artifact TEMPORAL (nunca
    donchian_breakout_baseline_results.csv, el artifact real de main())."""
    if not os.path.exists("data/raw"):
        return _p("persistence round-trip (data/raw/ no disponible)", False)

    contracts, results = camp.run_baseline()
    tmp_path = "test_donchian_breakout_baseline_TEMP.csv"
    try:
        write_experiment_results_csv(tmp_path, results)
        read_back = read_experiment_results_csv(tmp_path)
        comps = [compare_results(read_back[i], results[i]) for i in range(len(results))]
        ok = len(read_back) == 12 and all(c.matches for c in comps)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    return _p("C6 write -> C8 read -> C7 compare produce 12/12 ExperimentResult idénticos "
              "(artifact temporal, eliminado al terminar)", ok)


ALL_TESTS = [
    test_build_universe_produce_12_contratos_alcance_exacto,
    test_trigger_params_vacio_no_promete_control_de_range_lookback,
    test_universo_no_incluye_raw_ni_otros_managements,
    test_run_baseline_produce_12_resultados_reales,
    test_reproducibilidad_misma_corrida_mismo_resultado,
    test_persistence_roundtrip_sobre_datos_reales,
]


def main():
    print("scripts/donchian_breakout_baseline — validación estructural + ejecución real\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
