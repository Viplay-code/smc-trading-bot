"""
research/tests/test_runner_equivalence.py — Fase 2 (MVP del runner) +
Fase 3 (endurecimiento, 2026-09-02): TEST CRÍTICO del programa.

Ejecuta el contrato equivalente a la celda V3-A/`dcv1_activo_15h` de
`scripts/gestion_campaign_session.py` vía `research.runner.run()`, y lo
compara CAMPO POR CAMPO contra la fila ya publicada en
`gestion_campaign_session_results.csv` — sin redondear, sin tolerancias.
Cualquier diferencia hace fallar el test con AssertionError describiendo
exactamente qué campo difiere.

Fase 3 amplía la cobertura de 2 a las 6/6 celdas completas de la
referencia (3 activos × 2022/2023) — el objetivo explícito de esta fase.

Ejecutar:
    python -m research.tests.test_runner_equivalence  (o con pytest)
"""
from __future__ import annotations

import sys

import pandas as pd

sys.path.insert(0, ".")
import research
from research import runner

_REF_PATH = "gestion_campaign_session_results.csv"
_REF_CANDIDATE = "dcv1_activo_15h"
_REF_EXIT_CONFIG = "V3-A (1R/2R/1R)"

_CANONICAL_GATES = {
    "pf_min": research.PF_MIN, "max_dd_min": research.MAX_DD_MIN,
    "exp_r_min": research.EXP_R_MIN, "freq_min": research.FREQ_MIN_PER_MONTH,
    "freq_max": research.FREQ_MAX_PER_MONTH,
}

# Campos comparados EXACTOS (sin redondeo) — mínimo pedido: n_entries,
# n_trades, pf, wr, exp_r, total_r, max_dd, freq.
_COMPARE_FIELDS = ("n_entries", "n_trades", "pf", "wr", "exp_r", "total_r", "max_dd", "freq")


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def _build_contract(asset: str, year: int, role: str) -> dict:
    return {
        "name": f"runner_equivalence_{asset}_{year}",
        "contract_version": "1",
        "assets": [asset],
        "years": {role: year},
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
        "independent_variable": "management.name",
        "blind_authorized": False,
    }


def _load_reference_row(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["candidate"] == _REF_CANDIDATE) & (df["exit_config"] == _REF_EXIT_CONFIG)]
    if match.empty:
        raise AssertionError(f"No se encontró fila de referencia para {asset}/{year} en {_REF_PATH}.")
    return match.iloc[0]


def _assert_equivalence_exacta(asset: str, year: int, role: str = "train") -> None:
    """Ejecuta el contrato vía el runner, compara campo por campo contra
    la referencia legacy YA PUBLICADA. AssertionError con el campo exacto
    que difiere ante cualquier discrepancia — SIN redondear, SIN
    tolerancias arbitrarias."""
    contract = _build_contract(asset, year, role)
    result = runner.run(contract)
    ref = _load_reference_row(asset, year)

    mismatches = []
    for field_name in _COMPARE_FIELDS:
        got = getattr(result, field_name)
        expected = ref[field_name]
        # Comparación exacta — float() normaliza numpy scalar vs. valor
        # nativo del CSV, NO introduce tolerancia (== estricto sobre el
        # valor numérico, no round()).
        if float(got) != float(expected):
            mismatches.append(f"{field_name}: runner={got!r} vs referencia legacy={expected!r}")

    if mismatches:
        raise AssertionError(
            f"Equivalencia runner vs legacy FALLÓ para {asset}/{year} "
            f"({_REF_CANDIDATE}/{_REF_EXIT_CONFIG}):\n  " + "\n  ".join(mismatches)
        )


_ALL_CELLS = (
    ("BTCUSDT", 2022), ("BTCUSDT", 2023),
    ("ETHUSDT", 2022), ("ETHUSDT", 2023),
    ("SOLUSDT", 2022), ("SOLUSDT", 2023),
)


def _make_equivalence_test(asset: str, year: int):
    def _test():
        ok = True
        try:
            _assert_equivalence_exacta(asset, year)
        except AssertionError as e:
            ok = False
            print(f"    {e}")
        return _p(f"research.runner.run() reproduce EXACTO (sin redondeo) la fila legacy "
                  f"{asset}/{year}/dcv1_activo_15h/V3-A: n_entries/n_trades/pf/wr/exp_r/"
                  f"total_r/max_dd/freq", ok)
    _test.__name__ = f"test_equivalencia_exacta_{asset.lower()}_{year}"
    return _test


# 6/6 celdas completas de gestion_campaign_session_results.csv (Fase 3) —
# una función de test por celda, generadas explícitamente (no un loop
# oculto dentro de un solo test) para que un fallo individual identifique
# la celda exacta en el reporte de pytest/consola.
test_equivalencia_exacta_btcusdt_2022 = _make_equivalence_test("BTCUSDT", 2022)
test_equivalencia_exacta_btcusdt_2023 = _make_equivalence_test("BTCUSDT", 2023)
test_equivalencia_exacta_ethusdt_2022 = _make_equivalence_test("ETHUSDT", 2022)
test_equivalencia_exacta_ethusdt_2023 = _make_equivalence_test("ETHUSDT", 2023)
test_equivalencia_exacta_solusdt_2022 = _make_equivalence_test("SOLUSDT", 2022)
test_equivalencia_exacta_solusdt_2023 = _make_equivalence_test("SOLUSDT", 2023)


def test_contract_hash_presente_y_es_string():
    contract = _build_contract("BTCUSDT", 2022, "train")
    result = runner.run(contract)
    ok = isinstance(result.contract_hash, str) and len(result.contract_hash) == 16
    return _p(f"ExperimentResult.contract_hash presente y con la forma esperada "
              f"({result.contract_hash})", ok)


ALL_TESTS = [
    test_equivalencia_exacta_btcusdt_2022,
    test_equivalencia_exacta_btcusdt_2023,
    test_equivalencia_exacta_ethusdt_2022,
    test_equivalencia_exacta_ethusdt_2023,
    test_equivalencia_exacta_solusdt_2022,
    test_equivalencia_exacta_solusdt_2023,
    test_contract_hash_presente_y_es_string,
]


def main():
    print("research/tests/test_runner_equivalence — TEST CRÍTICO de la Fase 2 del runner\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
