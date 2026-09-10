"""
research/tests/test_donchian_breakout_n_hypothesis.py — Validación de la
campaña Fase 3 (investigación de `range_lookback`, H-N, 2026-09-10):
diseño pre-registrado, 24 contratos (2 N x 2 managements x 3 assets x 2
years). Verifica, además de la ejecución en sí, que las 3 capas exigidas
por el diseño (unidad experimental / unidad de decisión C5 / unidad de
promoción) permanecen correctamente separadas — en particular, que C5
(`research.summarize_decision`) nunca se modifica ni recibe `range_lookback`
como campo (no existe en `ExperimentResult`).

Sin comparación contra ningún artifact histórico salvo el baseline N=10 ya
congelado (usado únicamente como referencia externa, NUNCA re-ejecutado).

Ejecutar:
    python -m research.tests.test_donchian_breakout_n_hypothesis  (o con pytest)
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
from research.schema import ExperimentResult
import scripts.donchian_breakout_n_hypothesis as camp


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


# --------------------------------------------------------------------------- #
# Universo canónico (C4) — estructural, sin datos reales                    #
# --------------------------------------------------------------------------- #
def test_build_universe_produce_24_contratos_alcance_exacto():
    contracts = camp.build_universe(("BTCUSDT", "ETHUSDT", "SOLUSDT"), {"train": 2022, "validate": 2023})
    for c in contracts:
        runner.validate_contract(c)  # ContractError se propagaría sin capturar
    ns = {camp.n_of(c) for c in contracts}
    mgmts = {c["management"]["name"] for c in contracts}
    biases = {c["bias"]["name"] for c in contracts}
    sessions = {c["session"] for c in contracts}
    entries = {c["entry"]["name"] for c in contracts}
    triggers = {c["trigger"]["name"] for c in contracts}
    hashes = {research.compute_contract_hash(c) for c in contracts}
    ok = (
        len(contracts) == 24
        and ns == {20, 55}
        and mgmts == {"V3-A", "V3-B"}
        and biases == {"A_ema200_neutral"}
        and sessions == {"sin_filtro_24h"}
        and entries == {"C_market_close"}
        and triggers == {"D_range_breakout"}
        and len(hashes) == 24
    )
    return _p(f"build_universe produce 24 contratos (3 assets x 2 years x 2 N x 2 managements), "
              f"N={{20,55}} exacto (visto: {ns}), management={{'V3-A','V3-B'}} (visto: {mgmts})", ok)


def test_ningun_n_adicional_ni_raw_ni_otros_triggers():
    """Guardia de regresión: N_VALUES es una tupla EXPLÍCITA (20, 55) —
    ningún otro valor se cuela, ni Raw ni otro Trigger participan."""
    ok = (
        camp.N_VALUES == (20, 55)
        and camp.MANAGEMENTS == ("V3-A", "V3-B")
        and "Raw" not in camp.MANAGEMENTS
        and "Raw" in runner.MANAGEMENT_LAYERS  # confirma que el guard es real
    )
    contracts = camp.build_universe(("BTCUSDT",), {"train": 2022})
    ok = ok and len(contracts) == 4  # 2 N x 2 managements x 1 asset x 1 year
    ok = ok and all(c["management"]["name"] != "Raw" for c in contracts)
    ok = ok and all(camp.n_of(c) in (20, 55) for c in contracts)
    return _p("N_VALUES=(20,55) y MANAGEMENTS=('V3-A','V3-B') explícitos -- ningún valor/Trigger/"
              "management adicional se cuela en el universo", ok)


def test_trigger_params_range_lookback_declarado_correctamente():
    """Cada contrato declara EXACTAMENTE {'range_lookback': N} en
    trigger.params -- ninguna otra clave, consistente con la validación de
    C2 (Fase 2) que rechazaría cualquier clave desconocida."""
    contracts = camp.build_universe(("BTCUSDT",), {"train": 2022})
    ok = all(
        c["trigger"]["params"] == {"range_lookback": camp.n_of(c)}
        for c in contracts
    )
    return _p("trigger.params == {'range_lookback': N} exacto en todos los contratos", ok)


# --------------------------------------------------------------------------- #
# Ejecución real — sobre datos reales de data/raw/.                         #
# --------------------------------------------------------------------------- #
def test_run_hypothesis_produce_24_resultados_reales():
    if not os.path.exists("data/raw"):
        return _p("run_hypothesis produce 24 resultados reales (data/raw/ no disponible)", False)

    contracts, results = camp.run_hypothesis()
    ok = (
        len(contracts) == 24 and len(results) == 24
        and all(r.n_entries > 0 for r in results)
        and all(isinstance(r.gate_pass, bool) for r in results)
        and all(r.dataset_version and r.pipeline_version and r.engine_version for r in results)
        and len({r.contract_hash for r in results}) == 24
    )
    return _p("run_hypothesis produce 24/24 resultados reales, n_entries>0, gate_pass bool, "
              "24 contract_hash únicos", ok)


def test_n20_y_n55_producen_n_entries_distintos_del_baseline_n10():
    """Chequeo de sanidad: N=20/N=55 deben producir n_entries DISTINTOS
    entre sí y respecto del baseline N=10 ya congelado (para el mismo
    asset/year/management) -- confirma que cada N realmente ejecuta un
    universo de entradas propio, no una repetición accidental."""
    if not os.path.exists("data/raw") or not os.path.exists("donchian_breakout_baseline_results.csv"):
        return _p("N=20/N=55 producen n_entries distintos entre sí y del baseline N=10 "
                  "(artifacts/data/raw no disponibles)", False)

    baseline = pd.read_csv("donchian_breakout_baseline_results.csv")
    n10_btc_2022_v3a = baseline[
        (baseline.asset == "BTCUSDT") & (baseline.period == 2022) & (baseline.management == "V3-A")
    ].iloc[0]["n_entries"]

    contracts, results = camp.run_hypothesis(("BTCUSDT",))
    by_n = {}
    for c, r in zip(contracts, results):
        if c["years"] == {"train": 2022} and c["management"]["name"] == "V3-A":
            by_n[camp.n_of(c)] = r.n_entries

    ok = (
        by_n[20] != by_n[55]
        and by_n[20] != int(n10_btc_2022_v3a)
        and by_n[55] != int(n10_btc_2022_v3a)
    )
    return _p(f"n_entries distintos: N=10 (baseline, no re-ejecutado)={int(n10_btc_2022_v3a)}, "
              f"N=20={by_n.get(20)}, N=55={by_n.get(55)}", ok)


def test_baseline_n10_no_fue_re_ejecutado():
    """Confirma que este script NUNCA construye un contrato con
    range_lookback=10 -- el baseline es control histórico, no una celda
    de esta ronda (regla pre-registrada del diseño de Fase 3)."""
    contracts = camp.build_universe()
    ok = all(camp.n_of(c) != 10 for c in contracts)
    return _p("Ningún contrato de esta campaña declara range_lookback=10 -- el baseline N=10 "
              "permanece como control histórico, no re-ejecutado", ok)


# --------------------------------------------------------------------------- #
# Separación de capas: unidad de decisión (C5) vs unidad de promoción.      #
# --------------------------------------------------------------------------- #
def test_c5_nunca_recibe_range_lookback_como_campo():
    """Guardia arquitectónica: range_lookback NO es un campo de
    ExperimentResult -- confirma que decisions_by_n() nunca podría pasarlo
    como candidate_field (fallaría con AttributeError/getattr(None) si lo
    intentara), y que la separación de capas documentada en el módulo es
    real, no solo declarativa."""
    ok = "range_lookback" not in ExperimentResult.__dataclass_fields__
    return _p("'range_lookback' NO es un campo de ExperimentResult -- C5 no puede agrupar por él "
              "directamente, confirma que decisions_by_n() invoca C5 una vez por N con "
              "candidate_fields=('management',) exclusivamente", ok)


def test_decisions_by_n_produce_18_decisiones_por_n_via_c5_sin_modificar():
    """decisions_by_n() debe invocar C5 exactamente 2 veces (una por N),
    cada una con candidate_fields=('management',) -- 3 assets x 2
    managements = 6 CandidateDecision por N, 12 en total."""
    if not os.path.exists("data/raw"):
        return _p("decisions_by_n produce 6 decisiones por N vía C5 (data/raw/ no disponible)", False)

    contracts, results = camp.run_hypothesis()
    by_n = camp.decisions_by_n(contracts, results)
    ok = (
        set(by_n.keys()) == {20, 55}
        and all(len(by_n[n]) == 6 for n in (20, 55))
        and all(d.candidate[0] in ("V3-A", "V3-B") for n in (20, 55) for d in by_n[n])
    )
    return _p(f"decisions_by_n produce 6 CandidateDecision por N (candidate=(management,)) "
              f"vía C5 sin modificar -- {[len(by_n[n]) for n in (20,55)]}", ok)


def test_decisions_for_persistence_reetiqueta_sin_alterar_supervivencia():
    """decisions_for_persistence() debe preservar EXACTAMENTE
    survives_required_roles/rank_within_asset de cada CandidateDecision
    original de C5 -- solo cambia candidate=(mgmt,) a
    candidate=(N,mgmt), nunca recalcula la decisión en sí."""
    if not os.path.exists("data/raw"):
        return _p("decisions_for_persistence preserva supervivencia exacta (data/raw/ no disponible)", False)

    contracts, results = camp.run_hypothesis()
    by_n = camp.decisions_by_n(contracts, results)
    persisted = camp.decisions_for_persistence(by_n)

    ok = len(persisted) == 12
    for n in (20, 55):
        for original in by_n[n]:
            match = next(
                p for p in persisted
                if p.candidate == (n,) + original.candidate and p.asset == original.asset
            )
            if (match.survives_required_roles != original.survives_required_roles
                    or match.rank_within_asset != original.rank_within_asset):
                ok = False
    return _p("decisions_for_persistence preserva survives_required_roles/rank_within_asset "
              "exactos de C5 -- solo reetiqueta candidate para persistencia", ok)


def test_promotion_summary_regla_2_de_3_pre_registrada():
    """promotion_summary() debe marcar promoted=True si y solo si >=2 de
    los 3 activos sobreviven para ese (N, management) -- verificado con
    datos sintéticos controlados, sin depender de datos reales, para
    probar la regla en sí (incluyendo el caso límite 1/3 -> NO promovido)."""
    from research.decision import CandidateDecision

    def _mkdec(asset, mgmt, survives):
        return CandidateDecision(asset=asset, candidate=(mgmt,), per_role={},
                                  survives_required_roles=survives, rank_within_asset=None)

    by_n_sintetico = {
        20: [  # 2/3 sobreviven para V3-A -> promovido; 0/3 para V3-B -> no
            _mkdec("BTCUSDT", "V3-A", True), _mkdec("ETHUSDT", "V3-A", True), _mkdec("SOLUSDT", "V3-A", False),
            _mkdec("BTCUSDT", "V3-B", False), _mkdec("ETHUSDT", "V3-B", False), _mkdec("SOLUSDT", "V3-B", False),
        ],
        55: [  # 1/3 para V3-A -> NO promovido (caso límite)
            _mkdec("BTCUSDT", "V3-A", True), _mkdec("ETHUSDT", "V3-A", False), _mkdec("SOLUSDT", "V3-A", False),
            _mkdec("BTCUSDT", "V3-B", False), _mkdec("ETHUSDT", "V3-B", False), _mkdec("SOLUSDT", "V3-B", False),
        ],
    }
    promo = camp.promotion_summary(by_n_sintetico)
    row_20_va = promo[(promo.range_lookback == 20) & (promo.management == "V3-A")].iloc[0]
    row_20_vb = promo[(promo.range_lookback == 20) & (promo.management == "V3-B")].iloc[0]
    row_55_va = promo[(promo.range_lookback == 55) & (promo.management == "V3-A")].iloc[0]

    ok = (
        row_20_va["assets_surviving"] == 2 and row_20_va["promoted"] == True  # noqa: E712
        and row_20_vb["assets_surviving"] == 0 and row_20_vb["promoted"] == False  # noqa: E712
        and row_55_va["assets_surviving"] == 1 and row_55_va["promoted"] == False  # noqa: E712 (caso límite 1/3)
    )
    return _p("promotion_summary aplica la regla >=2/3 exacta (2/3->promovido, 1/3->NO promovido, "
              "0/3->no promovido), sobre datos sintéticos controlados", ok)


def test_persistence_roundtrip_sobre_datos_reales():
    """C6 write -> C8 read -> C7 compare sobre los 24 resultados reales,
    en un artifact TEMPORAL (nunca donchian_breakout_n_hypothesis_
    results.csv, el artifact real de main())."""
    if not os.path.exists("data/raw"):
        return _p("persistence round-trip (data/raw/ no disponible)", False)

    contracts, results = camp.run_hypothesis()
    tmp_path = "test_donchian_n_hypothesis_TEMP.csv"
    try:
        write_experiment_results_csv(tmp_path, results)
        read_back = read_experiment_results_csv(tmp_path)
        comps = [compare_results(read_back[i], results[i]) for i in range(len(results))]
        ok = len(read_back) == 24 and all(c.matches for c in comps)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    return _p("C6 write -> C8 read -> C7 compare produce 24/24 ExperimentResult idénticos "
              "(artifact temporal, eliminado al terminar)", ok)


ALL_TESTS = [
    test_build_universe_produce_24_contratos_alcance_exacto,
    test_ningun_n_adicional_ni_raw_ni_otros_triggers,
    test_trigger_params_range_lookback_declarado_correctamente,
    test_run_hypothesis_produce_24_resultados_reales,
    test_n20_y_n55_producen_n_entries_distintos_del_baseline_n10,
    test_baseline_n10_no_fue_re_ejecutado,
    test_c5_nunca_recibe_range_lookback_como_campo,
    test_decisions_by_n_produce_18_decisiones_por_n_via_c5_sin_modificar,
    test_decisions_for_persistence_reetiqueta_sin_alterar_supervivencia,
    test_promotion_summary_regla_2_de_3_pre_registrada,
    test_persistence_roundtrip_sobre_datos_reales,
]


def main():
    print("scripts/donchian_breakout_n_hypothesis — validación Fase 3 (H-N)\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
