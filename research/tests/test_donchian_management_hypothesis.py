"""
research/tests/test_donchian_management_hypothesis.py — Fase 4 (H-M,
2026-09-11): validación de la campaña conforme al Protocol v2 FINAL.

DOS NIVELES, DELIBERADAMENTE SEPARADOS:

  ALL_TESTS (nivel PREPARACIÓN, el que corre por defecto): NO ejecuta
  ninguna de las 6 celdas DCH-EXIT. Verifica construcción de contratos,
  separación control/tratamiento, provenance, C5, promoción, diagnósticos
  y artifacts sobre datos SINTÉTICOS controlados o sobre el artifact
  congelado (solo lectura). Es lo único autorizado antes de la ejecución
  de la campaña.

  POST_EXECUTION_TESTS (nivel POST-CAMPAÑA): requiere las 6 ejecuciones
  reales. NO se invoca desde `main()` — solo con `--post`, y únicamente
  tras autorización explícita para ejecutar la campaña.

Esta separación es en sí misma una garantía auditable de que la
preparación no puede disparar la campaña por accidente.

Ejecutar (preparación):
    python -m research.tests.test_donchian_management_hypothesis
Ejecutar (post-campaña, requiere autorización previa):
    python -m research.tests.test_donchian_management_hypothesis --post
"""
from __future__ import annotations

import inspect
import os
import sys

import pandas as pd

sys.path.insert(0, ".")
import research
from research import runner
from research.decision import CandidateDecision
from research.schema import ExperimentResult
import scripts.donchian_breakout_management_hypothesis as camp


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def _mk_result(asset, period, role, management, gate_pass, pf=1.0, n_entries=100, n_trades=50):
    return ExperimentResult(
        experiment_name="x", asset=asset, period=period, period_role=role,
        bias="A_ema200_neutral", trigger="D_range_breakout", entry="C_market_close",
        session="sin_filtro_24h", management=management, n_entries=n_entries,
        n_trades=n_trades, pf=pf, wr=30.0, exp_r=0.05, total_r=1.0, max_dd=-3.0,
        freq=8.0, gate_pass=gate_pass, contract_hash=f"h_{asset}_{period}_{management}",
        dataset_version="market-data-v1", pipeline_version="dc-v1",
        engine_version="research-engine-1",
    )


# --------------------------------------------------------------------------- #
# 1. Construcción de los 6 contratos DCH-EXIT (estructural, sin ejecutar)   #
# --------------------------------------------------------------------------- #
def test_build_treatment_universe_produce_6_contratos_exactos():
    contracts = camp.build_treatment_universe(("BTCUSDT", "ETHUSDT", "SOLUSDT"),
                                               {"train": 2022, "validate": 2023})
    for c in contracts:
        runner.validate_contract(c)   # ContractError se propagaría sin capturar
    mgmts = {c["management"]["name"] for c in contracts}
    params = {tuple(sorted(c["management"]["params"].items())) for c in contracts}
    assets = {c["assets"][0] for c in contracts}
    roles = {list(c["years"].keys())[0] for c in contracts}
    years = {list(c["years"].values())[0] for c in contracts}
    hashes = {research.compute_contract_hash(c) for c in contracts}
    ok = (
        len(contracts) == 6
        and mgmts == {"DCH-EXIT"}
        and params == {(("exit_lookback", 5),)}
        and assets == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}
        and roles == {"train", "validate"} and years == {2022, 2023}
        and len(hashes) == 6
    )
    return _p(f"build_treatment_universe: 6 contratos válidos, management={mgmts}, "
              f"params={{'exit_lookback': 5}}, 3 assets x 2 years, 6 contract_hash únicos", ok)


def test_variables_congeladas_en_los_6_contratos():
    contracts = camp.build_treatment_universe()
    ok = all(
        c["bias"]["name"] == "A_ema200_neutral"
        and c["trigger"]["name"] == "D_range_breakout"
        and c["trigger"]["params"] == {}          # default range_lookback=10
        and c["entry"]["name"] == "C_market_close"
        and c["session"] == "sin_filtro_24h"
        and c["atr_mult"] == 1.5 and c.get("atr_period", 14) == 14
        and c["risk"] == 0.005 and c["cost_per_trade"] == 0.0009
        and c["max_hold"] == 20
        and c["gates"] == camp._CANONICAL_GATES
        and c["blind_authorized"] is False
        for c in contracts
    )
    return _p("Las 12 variables congeladas son idénticas al baseline en los 6 contratos "
              "(Bias/Trigger+params/Entry/Session/ATR/risk/cost/max_hold/gates/blind)", ok)


def test_exit_lookback_no_puede_desviarse_de_5():
    """Doble barrera pre-registrada: (a) el contrato declara exactamente
    {'exit_lookback': 5}; (b) aun si se declarase otro valor,
    validate_contract lo rechaza con ContractError tipado."""
    contracts = camp.build_treatment_universe(("BTCUSDT",), {"train": 2022})
    declara_5 = all(c["management"]["params"] == {"exit_lookback": 5} for c in contracts)
    c_bad = dict(contracts[0])
    c_bad["management"] = {"name": "DCH-EXIT", "params": {"exit_lookback": 7}}
    rechaza = False
    try:
        runner.validate_contract(c_bad)
    except runner.ContractError:
        rechaza = True
    except KeyError:
        rechaza = False
    return _p("exit_lookback congelado en 5: el contrato lo declara así y un valor distinto "
              "(7) -> ContractError tipado", declara_5 and rechaza)


def test_no_hay_seleccion_secuencial_en_run_treatment():
    """Auditoría de código: `run_treatment` debe validar TODOS los
    contratos y ejecutarlos en UNA sola llamada a run_many — sin ninguna
    rama condicional sobre resultados, y sin mirar train para decidir
    validate."""
    import ast, textwrap
    tree = ast.parse(textwrap.dedent(inspect.getsource(camp.run_treatment)))
    fn = tree.body[0]
    # Inspección del CÓDIGO, no del texto: el docstring menciona
    # deliberadamente "run_many" y "train" al documentar la propiedad, así
    # que un grep textual daría un falso positivo (misma lección ya
    # aplicada en test_simulate_donchian).
    body = [n for n in fn.body if not (isinstance(n, ast.Expr)
                                        and isinstance(n.value, ast.Constant)
                                        and isinstance(n.value.value, str))]
    calls = [n for n in ast.walk(ast.Module(body=body, type_ignores=[]))
             if isinstance(n, ast.Call)]
    run_many_calls = [c for c in calls
                      if isinstance(c.func, ast.Attribute) and c.func.attr == "run_many"]
    # Ninguna rama condicional en el cuerpo ejecutable (la única
    # estructura de control admisible es el for de validación).
    ifs = [n for n in ast.walk(ast.Module(body=body, type_ignores=[]))
           if isinstance(n, ast.If)]
    names = {n.attr for n in ast.walk(ast.Module(body=body, type_ignores=[]))
             if isinstance(n, ast.Attribute)}
    ok = (
        len(run_many_calls) == 1                      # UNA sola ejecución, todos los contratos
        and not ifs                                    # sin ninguna rama condicional
        and "gate_pass" not in names                   # no consulta resultados
        and "validate_contract" in names               # valida TODOS antes de ejecutar
    )
    return _p("run_treatment ejecuta los 6 contratos en UNA sola llamada a run_many, sin "
              "ninguna rama condicional sobre resultados (sin selección secuencial)", ok)


# --------------------------------------------------------------------------- #
# 2. Controles congelados: rehidratación, NO re-ejecución                   #
# --------------------------------------------------------------------------- #
def test_controles_se_rehidratan_del_artifact_congelado():
    if not os.path.exists(camp.BASELINE_RESULTS_PATH):
        return _p("rehidratación de los 12 controles (artifact congelado no disponible)", False)
    controls = camp.load_frozen_controls()
    frozen_csv = pd.read_csv(camp.BASELINE_RESULTS_PATH)
    hashes_obj = sorted(r.contract_hash for r in controls)
    hashes_csv = sorted(frozen_csv["contract_hash"].tolist())
    ok = (
        len(controls) == 12
        and {r.management for r in controls} == {"V3-A", "V3-B"}
        and hashes_obj == hashes_csv          # contract_hash ORIGINAL preservado
        and all(isinstance(r, ExperimentResult) for r in controls)
    )
    return _p("Los 12 controles se rehidratan como ExperimentResult vía C8 conservando su "
              "contract_hash ORIGINAL del artifact congelado", ok)


def test_load_frozen_controls_es_solo_lectura():
    """La rehidratación no puede modificar el artifact congelado."""
    if not os.path.exists(camp.BASELINE_RESULTS_PATH):
        return _p("load_frozen_controls es solo lectura (artifact no disponible)", False)
    before = open(camp.BASELINE_RESULTS_PATH, "rb").read()
    camp.load_frozen_controls()
    after = open(camp.BASELINE_RESULTS_PATH, "rb").read()
    ok = before == after
    return _p("load_frozen_controls NO modifica el artifact congelado (byte a byte idéntico "
              "antes y después)", ok)


def test_el_tratamiento_no_reconstruye_contratos_de_control():
    """Separación control/tratamiento: el universo de tratamiento NO
    contiene ningún contrato V3-A/V3-B — los controles jamás se
    re-ejecutan como campaña."""
    contracts = camp.build_treatment_universe()
    ok = all(c["management"]["name"] == "DCH-EXIT" for c in contracts) and len(contracts) == 6
    src = inspect.getsource(camp.run_treatment)
    ok = ok and "build_treatment_universe" in src and "V3-A" not in src and "V3-B" not in src
    return _p("run_treatment solo construye/ejecuta contratos DCH-EXIT — ningún control se "
              "re-ejecuta como campaña", ok)


def test_rederivacion_diagnostica_aborta_ante_discrepancia():
    """La verificación de identidad de la seccion 4.b debe ABORTAR (no
    advertir) ante cualquier discrepancia. Se verifica en el código que
    lanza RuntimeError y que compara contract_hash + las 9 métricas
    core."""
    src = inspect.getsource(camp.rederive_control_diagnostics)
    ok = (
        "raise RuntimeError" in src and "ABORT" in src
        and "contract_hash" in src and "CORE_METRICS" in src
        and camp.CORE_METRICS == ("n_entries", "n_trades", "pf", "wr", "exp_r",
                                   "total_r", "max_dd", "freq", "gate_pass")
    )
    return _p("rederive_control_diagnostics ABORTA con RuntimeError ante cualquier "
              "discrepancia de contract_hash o de las 9 métricas core", ok)


# --------------------------------------------------------------------------- #
# 3. C5 y promoción sobre las 18 (datos sintéticos controlados)             #
# --------------------------------------------------------------------------- #
def test_c5_exige_18_observaciones_y_agrupa_por_management():
    """C5 se invoca UNA sola vez sobre las 18; `management` es campo real
    de ExperimentResult, así que agrupa directamente sin reetiquetar."""
    obs = []
    for asset in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        for mgmt in ("V3-A", "V3-B", "DCH-EXIT"):
            for period, role in ((2022, "train"), (2023, "validate")):
                obs.append(_mk_result(asset, period, role, mgmt, gate_pass=False))
    decisions = camp.decide(obs)
    ok = (
        len(decisions) == 9
        and {d.candidate[0] for d in decisions} == {"V3-A", "V3-B", "DCH-EXIT"}
        and all(len(d.candidate) == 1 for d in decisions)
    )
    rechaza_17 = False
    try:
        camp.decide(obs[:17])
    except ValueError:
        rechaza_17 = True
    return _p("C5 sobre 18 observaciones -> 9 decisiones (3 assets x 3 management); "
              "un conteo distinto de 18 se rechaza", ok and rechaza_17)


def test_c5_exige_gate_pass_en_ambos_roles():
    """Un management que pasa solo train (o solo validate) NO sobrevive."""
    obs = []
    for asset in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        for mgmt in ("V3-A", "V3-B", "DCH-EXIT"):
            for period, role in ((2022, "train"), (2023, "validate")):
                # DCH-EXIT pasa SOLO validate; el resto nunca.
                gp = (mgmt == "DCH-EXIT" and role == "validate")
                obs.append(_mk_result(asset, period, role, mgmt, gate_pass=gp))
    decisions = camp.decide(obs)
    ok = all(d.survives_required_roles is False for d in decisions)
    return _p("gate_pass solo en validate (sin train) NO produce supervivencia C5 en ningún "
              "candidato", ok)


def test_promocion_regla_2_de_3_identica_para_los_3_managements():
    """La regla >=2/3 se aplica IDÉNTICAMENTE a control y tratamiento.
    Casos: DCH-EXIT 2/3 -> promovido; V3-A 1/3 -> NO (caso límite);
    V3-B 3/3 -> promovido."""
    def _d(asset, mgmt, survives):
        return CandidateDecision(asset=asset, candidate=(mgmt,), per_role={},
                                  survives_required_roles=survives, rank_within_asset=None)
    decisions = [
        _d("BTCUSDT", "DCH-EXIT", True), _d("ETHUSDT", "DCH-EXIT", True), _d("SOLUSDT", "DCH-EXIT", False),
        _d("BTCUSDT", "V3-A", True), _d("ETHUSDT", "V3-A", False), _d("SOLUSDT", "V3-A", False),
        _d("BTCUSDT", "V3-B", True), _d("ETHUSDT", "V3-B", True), _d("SOLUSDT", "V3-B", True),
    ]
    promo = camp.promotion_summary(decisions)
    r = {row["management"]: row for _, row in promo.iterrows()}
    ok = (
        r["DCH-EXIT"]["assets_surviving"] == 2 and r["DCH-EXIT"]["promoted"] == True   # noqa: E712
        and r["V3-A"]["assets_surviving"] == 1 and r["V3-A"]["promoted"] == False      # noqa: E712
        and r["V3-B"]["assets_surviving"] == 3 and r["V3-B"]["promoted"] == True       # noqa: E712
        and len(promo) == 3
    )
    return _p("Promoción >=2/3 aplicada idénticamente a los 3 managements (2/3->sí, "
              "1/3->no, 3/3->sí)", ok)


def test_promocion_no_toca_gates_ni_c5():
    """Auditoría de código: promotion_summary solo lee
    survives_required_roles; nunca gate_pass, pf, freq ni ningún umbral."""
    src = inspect.getsource(camp.promotion_summary)
    ok = ("survives_required_roles" in src
          and "gate_pass" not in src and "pf" not in src
          and "freq" not in src and "PF_MIN" not in src)
    return _p("promotion_summary solo cuenta decisiones de C5 — nunca accede a gates ni "
              "métricas individuales", ok)


# --------------------------------------------------------------------------- #
# 4. Comparison artifact + provenance                                        #
# --------------------------------------------------------------------------- #
def test_comparison_tiene_18_filas_con_provenance_y_metricas_verbatim():
    controls = [_mk_result(a, p, role, m, gate_pass=False, pf=1.23)
                for a in ("BTCUSDT", "ETHUSDT", "SOLUSDT")
                for m in ("V3-A", "V3-B")
                for p, role in ((2022, "train"), (2023, "validate"))]
    treatment = [_mk_result(a, p, role, "DCH-EXIT", gate_pass=False, pf=4.56)
                 for a in ("BTCUSDT", "ETHUSDT", "SOLUSDT")
                 for p, role in ((2022, "train"), (2023, "validate"))]
    rows = camp.build_comparison_rows(controls, treatment)
    sources = {r["source"] for r in rows}
    ok = (
        len(rows) == 18
        and sources == {"phase1_baseline_frozen", "phase4_new"}
        and sum(1 for r in rows if r["source"] == "phase1_baseline_frozen") == 12
        and sum(1 for r in rows if r["source"] == "phase4_new") == 6
        and all(r["source_artifact"] == camp.BASELINE_RESULTS_PATH
                for r in rows if r["source"] == "phase1_baseline_frozen")
        # métricas COPIADAS VERBATIM del objeto de origen, no recalculadas
        and all(r["pf"] == 1.23 for r in rows if r["source"] == "phase1_baseline_frozen")
        and all(r["pf"] == 4.56 for r in rows if r["source"] == "phase4_new")
        and all(set(camp.CORE_METRICS).issubset(r.keys()) for r in rows)
    )
    return _p("comparison: 18 filas, 12 control (source=phase1_baseline_frozen) + 6 "
              "tratamiento, con source_artifact/contract_hash y métricas verbatim", ok)


def test_join_asset_management_resuelve_provenance_de_cada_decision():
    """Solución externa mínima de trazabilidad (Protocol v2 seccion 19):
    decision.csv ⋈ comparison.csv por (asset, management) debe devolver
    EXACTAMENTE las 2 observaciones (train+validate) que alimentaron cada
    decisión."""
    controls = [_mk_result(a, p, role, m, gate_pass=False)
                for a in ("BTCUSDT", "ETHUSDT", "SOLUSDT")
                for m in ("V3-A", "V3-B")
                for p, role in ((2022, "train"), (2023, "validate"))]
    treatment = [_mk_result(a, p, role, "DCH-EXIT", gate_pass=False)
                 for a in ("BTCUSDT", "ETHUSDT", "SOLUSDT")
                 for p, role in ((2022, "train"), (2023, "validate"))]
    comp = pd.DataFrame(camp.build_comparison_rows(controls, treatment))
    decisions = camp.decide(controls + treatment)

    ok = len(decisions) == 9
    for d in decisions:
        sub = comp[(comp.asset == d.asset) & (comp.management == d.candidate[0])]
        if len(sub) != 2 or set(sub["period_role"]) != {"train", "validate"}:
            ok = False
    return _p("El join (asset, management) entre decision y comparison resuelve exactamente "
              "2 observaciones (train+validate) por decisión", ok)


def test_artifacts_no_sobrescriben_baseline_ni_fase3():
    """Los 4 paths de Fase 4 deben ser distintos de todo artifact
    congelado."""
    protegidos = {
        "donchian_breakout_baseline_results.csv", "donchian_breakout_baseline_decision.csv",
        "donchian_breakout_n_hypothesis_results.csv", "donchian_breakout_n_hypothesis_decision.csv",
    }
    nuevos = {camp.RESULTS_PATH, camp.COMPARISON_PATH, camp.DECISION_PATH, camp.DIAGNOSTICS_PATH}
    ok = not (nuevos & protegidos) and len(nuevos) == 4
    return _p(f"Los 4 artifacts de Fase 4 no colisionan con ningún artifact congelado "
              f"({sorted(nuevos)})", ok)


# --------------------------------------------------------------------------- #
# 5. Diagnósticos: aislamiento y no-gate                                     #
# --------------------------------------------------------------------------- #
def test_mfe_mae_se_calculan_sin_reglas_de_salida():
    """MFE/MAE recorren la MISMA ventana max_hold con la MISMA fórmula de
    excursión que simulate_v3, pero SIN stop/BE/trailing/canal/timeout.
    Frame sintético: long en i0=0, entry=100, risk_pts=10, max_hold=3.
    highs 105/120/110 -> MFE = 20 pts = 2.0R; lows 95/90/99 -> MAE = 10
    pts = 1.0R. Un stop en el camino NO debe truncar la medición."""
    idx = pd.date_range("2022-01-01", periods=5, freq="1h", tz="UTC")
    frame = pd.DataFrame({
        "open": [100.0] * 5, "high": [100.0, 105.0, 120.0, 110.0, 100.0],
        "low": [100.0, 95.0, 90.0, 99.0, 100.0], "close": [100.0] * 5,
    }, index=idx)
    entry = {"entry_idx": 0, "direction": "long", "entry": 100.0,
             "sl0": 99.0, "risk_pts": 10.0}

    class _Cfg:
        max_hold = 3
    mfe_r, mae_r = camp._mfe_mae_r_for_entry(frame, entry, _Cfg())
    ok = mfe_r == 2.0 and mae_r == 1.0
    return _p(f"MFE/MAE medidos sobre la ventana completa de max_hold sin aplicar ninguna "
              f"regla de salida (MFE_R={mfe_r}, MAE_R={mae_r}; el stop en 99 no trunca)", ok)


def test_diagnosticos_verifican_el_universo_antes_de_medir():
    """compute_diagnostics DEBE abortar si el frame re-derivado no
    reproduce n_entries — garantía de que N2 mide sobre el MISMO universo
    que ejecutó el runner (Protocol v2 seccion 11)."""
    src = inspect.getsource(camp.compute_diagnostics)
    ok = ("len(entries) != result.n_entries" in src and "RuntimeError" in src
          and "ABORT" in src)
    return _p("compute_diagnostics aborta si len(entries) != ExperimentResult.n_entries "
              "(verificación de universo obligatoria)", ok)


def test_diagnosticos_no_entran_en_c5_ni_en_promocion():
    """Auditoría de código: ni decide() ni promotion_summary() leen
    ninguna magnitud diagnóstica."""
    src_decide = inspect.getsource(camp.decide)
    src_promo = inspect.getsource(camp.promotion_summary)
    prohibidas = ("mfe", "mae", "capture", "avg_win", "avg_loss", "duration")
    ok = all(p not in src_decide.lower() and p not in src_promo.lower() for p in prohibidas)
    return _p("Ninguna métrica diagnóstica (MFE/MAE/capture/avg_win/avg_loss/duration) "
              "aparece en decide() ni en promotion_summary()", ok)


def test_diagnosticos_se_aplican_igual_a_control_y_tratamiento():
    """El mismo `compute_diagnostics` se usa para ambos orígenes; la
    única diferencia es la etiqueta `origin`."""
    src = inspect.getsource(camp.main)
    ok = (src.count("compute_diagnostics") == 2
          and 'origin="diagnostic_re_derivation"' in src
          and 'origin="phase4_execution"' in src)
    return _p("compute_diagnostics se aplica con la MISMA función a controles y tratamiento, "
              "distinguidos solo por la etiqueta origin", ok)


# --------------------------------------------------------------------------- #
# POST-CAMPAÑA — requiere las 6 ejecuciones. NO se corre en preparación.    #
# --------------------------------------------------------------------------- #
def test_post_run_treatment_produce_6_resultados_reales():
    contracts, results, trades = camp.run_treatment()
    ok = (len(contracts) == 6 and len(results) == 6 and len(trades) == 6
          and all(r.management == "DCH-EXIT" for r in results)
          and len({r.contract_hash for r in results}) == 6
          and all(r.n_entries > 0 for r in results))
    return _p("run_treatment produce 6/6 resultados reales DCH-EXIT con contract_hash únicos", ok)


def test_post_donchian_exit_aparece_en_los_trades():
    _c, _r, trades = camp.run_treatment()
    reasons = {t.reason for cell in trades for t in cell}
    ok = "donchian_exit" in reasons
    return _p(f"El mecanismo DCH-EXIT produce salidas reales por canal (reasons observados: "
              f"{sorted(reasons)})", ok)


def test_post_18_observaciones_alimentan_c5():
    controls = camp.load_frozen_controls()
    _c, results, _t = camp.run_treatment()
    decisions = camp.decide(list(controls) + list(results))
    ok = len(decisions) == 9 and {d.candidate[0] for d in decisions} == set(camp.ALL_MANAGEMENTS)
    return _p("Las 18 observaciones (12 congeladas + 6 nuevas) alimentan C5 -> 9 decisiones", ok)


ALL_TESTS = [
    test_build_treatment_universe_produce_6_contratos_exactos,
    test_variables_congeladas_en_los_6_contratos,
    test_exit_lookback_no_puede_desviarse_de_5,
    test_no_hay_seleccion_secuencial_en_run_treatment,
    test_controles_se_rehidratan_del_artifact_congelado,
    test_load_frozen_controls_es_solo_lectura,
    test_el_tratamiento_no_reconstruye_contratos_de_control,
    test_rederivacion_diagnostica_aborta_ante_discrepancia,
    test_c5_exige_18_observaciones_y_agrupa_por_management,
    test_c5_exige_gate_pass_en_ambos_roles,
    test_promocion_regla_2_de_3_identica_para_los_3_managements,
    test_promocion_no_toca_gates_ni_c5,
    test_comparison_tiene_18_filas_con_provenance_y_metricas_verbatim,
    test_join_asset_management_resuelve_provenance_de_cada_decision,
    test_artifacts_no_sobrescriben_baseline_ni_fase3,
    test_mfe_mae_se_calculan_sin_reglas_de_salida,
    test_diagnosticos_verifican_el_universo_antes_de_medir,
    test_diagnosticos_no_entran_en_c5_ni_en_promocion,
    test_diagnosticos_se_aplican_igual_a_control_y_tratamiento,
]

POST_EXECUTION_TESTS = [
    test_post_run_treatment_produce_6_resultados_reales,
    test_post_donchian_exit_aparece_en_los_trades,
    test_post_18_observaciones_alimentan_c5,
]


def main():
    post = "--post" in sys.argv
    if post:
        print("scripts/donchian_breakout_management_hypothesis — POST-CAMPAÑA "
              "(ejecuta las 6 celdas)\n")
        tests = ALL_TESTS + POST_EXECUTION_TESTS
    else:
        print("scripts/donchian_breakout_management_hypothesis — PREPARACIÓN "
              "(NO ejecuta las 6 celdas)\n")
        tests = ALL_TESTS
    results = [t() for t in tests]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
