"""
research/tests/test_decision.py — Automatización experimental, Componente 5
(capa de Decisión, 2026-09-04): tests estructurales/de mecanismo sobre
`research.decision.summarize_decision`, con `ExperimentResult` construidos
directamente (sin `run()`, sin I/O) — cubren exactamente los 8 casos
obligatorios del diseño aprobado.

La equivalencia contra `scripts/bias_campaign.py::summarize_decision`
legacy sobre un dataset REAL ya publicado vive en
`research/tests/test_decision_equivalence.py`, separada de este archivo.

Ejecutar:
    python -m research.tests.test_decision  (o con pytest)
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")
from research.decision import summarize_decision, CandidateDecision
from research.schema import ExperimentResult


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def _result(asset, role, period, pf, gate_pass, trigger="T1_ema_cross", session="dcv1_activo_15h") -> ExperimentResult:
    """Constructor mínimo de ExperimentResult para tests estructurales —
    no proviene de run(), sin ninguna pretensión de ser un resultado
    científico real."""
    return ExperimentResult(
        experiment_name="test", asset=asset, period=period, period_role=role,
        bias="A_ema200_neutral", trigger=trigger, entry="C_market_close",
        session=session, management="V3-A",
        n_entries=10, n_trades=10, pf=pf, wr=50.0, exp_r=0.1,
        total_r=1.0, max_dd=-5.0, freq=8.0, gate_pass=gate_pass,
    )


# --------------------------------------------------------------------------- #
# 1. Candidato que pasa todos los años/roles requeridos                      #
# --------------------------------------------------------------------------- #
def test_candidato_pasa_todos_los_roles():
    results = [
        _result("BTCUSDT", "train", 2022, pf=1.8, gate_pass=True),
        _result("BTCUSDT", "validate", 2023, pf=1.6, gate_pass=True),
    ]
    out = summarize_decision(
        results, candidate_fields=("trigger",), required_roles=("train", "validate"),
        rank_by_role="validate",
    )
    ok = len(out) == 1 and out[0].survives_required_roles is True and out[0].rank_within_asset == 1
    return _p("Candidato con gate_pass=True en train y validate -> sobrevive, rank=1", ok)


# --------------------------------------------------------------------------- #
# 2. Candidato que falla un año/rol                                          #
# --------------------------------------------------------------------------- #
def test_candidato_falla_un_rol():
    results = [
        _result("BTCUSDT", "train", 2022, pf=1.8, gate_pass=True),
        _result("BTCUSDT", "validate", 2023, pf=0.9, gate_pass=False),
    ]
    out = summarize_decision(
        results, candidate_fields=("trigger",), required_roles=("train", "validate"),
        rank_by_role="validate",
    )
    ok = len(out) == 1 and out[0].survives_required_roles is False and out[0].rank_within_asset is None
    return _p("Candidato con gate_pass=False en validate -> NO sobrevive, sin rank", ok)


def test_candidato_falta_un_rol_no_se_descarta_en_silencio():
    """Un candidato al que le falta un rol requerido se reporta como
    'no sobrevive' — nunca se elimina silenciosamente del resultado."""
    results = [_result("BTCUSDT", "train", 2022, pf=1.8, gate_pass=True)]
    out = summarize_decision(
        results, candidate_fields=("trigger",), required_roles=("train", "validate"),
        rank_by_role="validate",
    )
    ok = (
        len(out) == 1
        and out[0].survives_required_roles is False
        and "validate" not in out[0].per_role
        and "train" in out[0].per_role
    )
    return _p("Candidato sin el rol 'validate' -> reportado como no-sobreviviente, "
              "presente en el resultado (no descartado en silencio)", ok)


# --------------------------------------------------------------------------- #
# 3. Múltiples candidatos                                                    #
# --------------------------------------------------------------------------- #
def test_multiples_candidatos():
    results = [
        _result("BTCUSDT", "train", 2022, pf=1.8, gate_pass=True, trigger="T1_ema_cross"),
        _result("BTCUSDT", "validate", 2023, pf=1.6, gate_pass=True, trigger="T1_ema_cross"),
        _result("BTCUSDT", "train", 2022, pf=1.2, gate_pass=False, trigger="A_sweep_bos"),
        _result("BTCUSDT", "validate", 2023, pf=1.1, gate_pass=False, trigger="A_sweep_bos"),
    ]
    out = summarize_decision(
        results, candidate_fields=("trigger",), required_roles=("train", "validate"),
        rank_by_role="validate",
    )
    ok = len(out) == 2
    survivors = [c for c in out if c.survives_required_roles]
    ok = ok and len(survivors) == 1 and survivors[0].candidate == ("T1_ema_cross",)
    return _p("2 candidatos (T1_ema_cross, A_sweep_bos) -> 2 decisiones, 1 sobreviviente", ok)


# --------------------------------------------------------------------------- #
# 4. Ranking determinista                                                    #
# --------------------------------------------------------------------------- #
def test_ranking_determinista_multiples_sobrevivientes():
    results = []
    for trig, pf_val in (("T1_ema_cross", 1.5), ("A_sweep_bos", 2.0), ("C_bos_only", 1.7)):
        results.append(_result("BTCUSDT", "train", 2022, pf=pf_val + 0.1, gate_pass=True, trigger=trig))
        results.append(_result("BTCUSDT", "validate", 2023, pf=pf_val, gate_pass=True, trigger=trig))

    out = summarize_decision(
        results, candidate_fields=("trigger",), required_roles=("train", "validate"),
        rank_by_role="validate",
    )
    ranked = sorted([c for c in out if c.survives_required_roles], key=lambda c: c.rank_within_asset)
    ok = [c.candidate for c in ranked] == [("A_sweep_bos",), ("C_bos_only",), ("T1_ema_cross",)]
    ok = ok and [c.rank_within_asset for c in ranked] == [1, 2, 3]
    return _p("3 sobrevivientes rankeados descendente por pf en 'validate' "
              "(2.0 > 1.7 > 1.5) -> orden y rank_within_asset correctos", ok)


# --------------------------------------------------------------------------- #
# 5. Años/roles distintos de 2022/2023                                       #
# --------------------------------------------------------------------------- #
def test_roles_distintos_de_2022_2023():
    """Confirma que la función no depende de ningún año/rol literal —
    funciona igual con 2019/2020/2021 y con roles no estándar."""
    results = [
        _result("ETHUSDT", "train", 2019, pf=1.9, gate_pass=True),
        _result("ETHUSDT", "validate", 2020, pf=1.7, gate_pass=True),
        _result("ETHUSDT", "blind", 2021, pf=1.5, gate_pass=True),
    ]
    out = summarize_decision(
        results, candidate_fields=("trigger",), required_roles=("train", "validate", "blind"),
        rank_by_role="blind",
    )
    ok = len(out) == 1 and out[0].survives_required_roles is True and out[0].rank_within_asset == 1
    return _p("Roles 'train'/'validate'/'blind' sobre años 2019/2020/2021 (no 2022/2023) "
              "-> funciona igual, sin ningún año hardcodeado", ok)


# --------------------------------------------------------------------------- #
# 6. Identidad de candidato configurable                                     #
# --------------------------------------------------------------------------- #
def test_identidad_candidato_configurable_por_session():
    """candidate_fields=('session',) — igual que gestion_campaign_session.py,
    donde 'candidate' significa 'ventana de sesión', no Trigger."""
    results = [
        _result("BTCUSDT", "train", 2022, pf=1.8, gate_pass=True, session="control_8h"),
        _result("BTCUSDT", "validate", 2023, pf=1.6, gate_pass=True, session="control_8h"),
        _result("BTCUSDT", "train", 2022, pf=0.9, gate_pass=False, session="sin_filtro_24h"),
        _result("BTCUSDT", "validate", 2023, pf=0.8, gate_pass=False, session="sin_filtro_24h"),
    ]
    out = summarize_decision(
        results, candidate_fields=("session",), required_roles=("train", "validate"),
        rank_by_role="validate",
    )
    ok = {c.candidate for c in out} == {("control_8h",), ("sin_filtro_24h",)}
    return _p("candidate_fields=('session',) identifica candidatos por ventana de sesión, "
              "no por Trigger — identidad de candidato es configurable", ok)


def test_identidad_candidato_multicampo():
    """candidate_fields=('session','management') — combina 2 dimensiones,
    igual que legacy agrupaba por (candidate, exit_config)."""
    results = [
        _result("BTCUSDT", "train", 2022, pf=1.8, gate_pass=True, session="dcv1_activo_15h"),
        _result("BTCUSDT", "validate", 2023, pf=1.6, gate_pass=True, session="dcv1_activo_15h"),
    ]
    out = summarize_decision(
        results, candidate_fields=("session", "management"), required_roles=("train", "validate"),
        rank_by_role="validate",
    )
    ok = len(out) == 1 and out[0].candidate == ("dcv1_activo_15h", "V3-A")
    return _p("candidate_fields=('session','management') combina 2 dimensiones en la "
              "identidad del candidato", ok)


# --------------------------------------------------------------------------- #
# 7. Colección vacía                                                         #
# --------------------------------------------------------------------------- #
def test_coleccion_vacia():
    out = summarize_decision(
        [], candidate_fields=("trigger",), required_roles=("train", "validate"),
        rank_by_role="validate",
    )
    ok = out == []
    return _p("summarize_decision([]) -> [] (sin excepción)", ok)


# --------------------------------------------------------------------------- #
# 8. Determinismo                                                             #
# --------------------------------------------------------------------------- #
def test_determinismo_mismo_input():
    results = [
        _result("BTCUSDT", "train", 2022, pf=1.8, gate_pass=True, trigger="T1_ema_cross"),
        _result("BTCUSDT", "validate", 2023, pf=1.6, gate_pass=True, trigger="T1_ema_cross"),
        _result("BTCUSDT", "train", 2022, pf=1.9, gate_pass=True, trigger="A_sweep_bos"),
        _result("BTCUSDT", "validate", 2023, pf=1.95, gate_pass=True, trigger="A_sweep_bos"),
    ]
    out1 = summarize_decision(
        list(results), candidate_fields=("trigger",), required_roles=("train", "validate"),
        rank_by_role="validate",
    )
    out2 = summarize_decision(
        list(results), candidate_fields=("trigger",), required_roles=("train", "validate"),
        rank_by_role="validate",
    )
    ok = out1 == out2
    return _p("Mismo input ejecutado dos veces produce exactamente la misma salida (determinismo)", ok)


def test_determinismo_independiente_del_orden_de_entrada():
    """El orden de agrupación no debe depender del orden en que llegan los
    ExperimentResult — solo del contenido."""
    results_a = [
        _result("BTCUSDT", "train", 2022, pf=1.8, gate_pass=True, trigger="T1_ema_cross"),
        _result("BTCUSDT", "validate", 2023, pf=1.6, gate_pass=True, trigger="T1_ema_cross"),
        _result("BTCUSDT", "train", 2022, pf=1.9, gate_pass=True, trigger="A_sweep_bos"),
        _result("BTCUSDT", "validate", 2023, pf=1.95, gate_pass=True, trigger="A_sweep_bos"),
    ]
    results_b = list(reversed(results_a))

    out_a = summarize_decision(
        results_a, candidate_fields=("trigger",), required_roles=("train", "validate"),
        rank_by_role="validate",
    )
    out_b = summarize_decision(
        results_b, candidate_fields=("trigger",), required_roles=("train", "validate"),
        rank_by_role="validate",
    )
    ok = out_a == out_b
    return _p("Mismo conjunto de ExperimentResult en orden distinto produce la misma "
              "salida (no depende del orden de entrada)", ok)


# --------------------------------------------------------------------------- #
# Hallazgos de la revisión final — required_roles vacío / rank_metric        #
# inválido, ambos ahora rechazados explícitamente en vez de fallar en       #
# silencio.                                                                  #
# --------------------------------------------------------------------------- #
def test_required_roles_vacio_rechaza():
    results = [_result("BTCUSDT", "train", 2022, pf=1.8, gate_pass=True)]
    ok = True
    try:
        summarize_decision(results, candidate_fields=("trigger",), required_roles=(),
                            rank_by_role="train")
        ok = False
    except ValueError:
        pass
    return _p("required_roles=() -> ValueError (evita que todo candidato "
              "'sobreviva' vacuamente)", ok)


def test_rank_metric_invalido_falla_explicitamente():
    """Un typo en rank_metric (ej. 'fp' en vez de 'pf') debe fallar
    ruidosamente, no producir un ranking silenciosamente vacío."""
    results = [
        _result("BTCUSDT", "train", 2022, pf=1.8, gate_pass=True),
        _result("BTCUSDT", "validate", 2023, pf=1.6, gate_pass=True),
    ]
    ok = True
    try:
        summarize_decision(results, candidate_fields=("trigger",),
                            required_roles=("train", "validate"),
                            rank_by_role="validate", rank_metric="fp")
        ok = False
    except ValueError:
        pass
    return _p("rank_metric='fp' (typo, no es un campo de ExperimentResult) -> ValueError, "
              "no un ranking vacío en silencio", ok)


ALL_TESTS = [
    test_candidato_pasa_todos_los_roles,
    test_candidato_falla_un_rol,
    test_candidato_falta_un_rol_no_se_descarta_en_silencio,
    test_multiples_candidatos,
    test_ranking_determinista_multiples_sobrevivientes,
    test_roles_distintos_de_2022_2023,
    test_identidad_candidato_configurable_por_session,
    test_identidad_candidato_multicampo,
    test_coleccion_vacia,
    test_determinismo_mismo_input,
    test_determinismo_independiente_del_orden_de_entrada,
    test_required_roles_vacio_rechaza,
    test_rank_metric_invalido_falla_explicitamente,
]


def main():
    print("research/tests/test_decision — Componente 5 (capa de Decisión)\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
