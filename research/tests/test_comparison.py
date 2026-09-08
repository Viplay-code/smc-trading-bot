"""
research/tests/test_comparison.py — Automatización experimental,
Componente 7 (Comparison, 2026-09-05).

Cubre los 12 grupos de tests especificados en el diseño aprobado:
resultados idénticos, una diferencia, múltiples diferencias, n_entries/
n_trades, None, NaN, normalización de tipo numérico sin tolerancia,
default vs fields explícito, campo inválido, metadata excluida por
defecto, determinismo y orden, pureza (sin I/O ni pandas).

Explícitamente NO prueba lectura de CSV, resolución de baseline, ni
tolerancia numérica — ninguna de las tres existe en este componente
(fuera de alcance, sin evidencia legacy que la justifique).

Ejecutar:
    python -m research.tests.test_comparison  (o con pytest)
"""
from __future__ import annotations

import math
import sys

sys.path.insert(0, ".")
from research.comparison import (
    compare_results, ComparisonResult, FieldDifference, DEFAULT_COMPARISON_FIELDS,
)
from research.schema import ExperimentResult


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def _result(**overrides) -> ExperimentResult:
    kwargs = dict(
        experiment_name="test_comparison", asset="BTCUSDT", period=2022, period_role="train",
        bias="A_ema200_neutral", trigger="T1_ema_cross", entry="C_market_close",
        session="dcv1_activo_15h", management="V3-A",
        n_entries=10, n_trades=10, pf=1.5, wr=50.0, exp_r=0.1,
        total_r=1.0, max_dd=-5.0, freq=8.0, gate_pass=True,
        contract_hash="0123456789abcdef", dataset_version="market-data-v1",
        pipeline_version="dc-v1", engine_version="research-engine-1",
    )
    kwargs.update(overrides)
    return ExperimentResult(**kwargs)


# --------------------------------------------------------------------------- #
# 1. Resultados idénticos                                                    #
# --------------------------------------------------------------------------- #
def test_resultados_identicos():
    a, b = _result(), _result()
    result = compare_results(a, b)
    ok = (
        result.matches is True
        and result.differences == ()
        and result.fields_compared == DEFAULT_COMPARISON_FIELDS
    )
    return _p("Dos ExperimentResult idénticos -> matches=True, sin diferencias", ok)


# --------------------------------------------------------------------------- #
# 2. Una diferencia                                                          #
# --------------------------------------------------------------------------- #
def test_una_diferencia():
    a = _result(pf=1.5)
    b = _result(pf=1.8)
    result = compare_results(a, b)
    ok = (
        result.matches is False
        and len(result.differences) == 1
        and result.differences[0] == FieldDifference(field="pf", actual=1.5, reference=1.8)
    )
    return _p("Un solo campo (pf) divergente -> matches=False, 1 FieldDifference exacta", ok)


# --------------------------------------------------------------------------- #
# 3. Múltiples diferencias                                                   #
# --------------------------------------------------------------------------- #
def test_multiples_diferencias_todas_recolectadas():
    a = _result(pf=1.5, wr=50.0, max_dd=-5.0)
    b = _result(pf=1.8, wr=55.0, max_dd=-7.0)
    result = compare_results(a, b)
    campos_divergentes = {d.field for d in result.differences}
    ok = (
        result.matches is False
        and len(result.differences) == 3
        and campos_divergentes == {"pf", "wr", "max_dd"}
    )
    return _p("3 campos divergentes -> TODOS recolectados, no solo el primero "
              "(mismo comportamiento universal de los 16 scripts legacy)", ok)


# --------------------------------------------------------------------------- #
# 4. n_entries/n_trades                                                      #
# --------------------------------------------------------------------------- #
def test_n_entries_n_trades_incluidos_por_defecto():
    a = _result(n_entries=100, n_trades=95)
    b = _result(n_entries=100, n_trades=90)
    result = compare_results(a, b)
    ok = (
        result.matches is False
        and len(result.differences) == 1
        and result.differences[0].field == "n_trades"
    )
    return _p("n_entries/n_trades forman parte del conjunto por defecto y se comparan "
              "igual que las métricas (n_entries coincide, n_trades diverge)", ok)


# --------------------------------------------------------------------------- #
# 5. None                                                                    #
# --------------------------------------------------------------------------- #
def test_none_vs_none_coincide():
    a = _result(pf=None, wr=None, exp_r=None, total_r=None, max_dd=None, freq=None, gate_pass=None)
    b = _result(pf=None, wr=None, exp_r=None, total_r=None, max_dd=None, freq=None, gate_pass=None)
    result = compare_results(a, b)
    ok = result.matches is True
    return _p("None vs None (muestra insuficiente en ambos lados) -> coincide", ok)


def test_none_vs_valor_real_diverge():
    a = _result(pf=None)
    b = _result(pf=1.5)
    result = compare_results(a, b)
    ok = result.matches is False and result.differences[0].field == "pf"
    return _p("None vs valor real -> diverge", ok)


def test_none_vs_nan_diverge():
    """None y NaN son estados DISTINTOS -- no se conflacionan."""
    a = _result(pf=None)
    b = _result(pf=float("nan"))
    result = compare_results(a, b)
    ok = result.matches is False and result.differences[0].field == "pf"
    return _p("None vs NaN -> diverge (estados distintos, no conflacionados)", ok)


# --------------------------------------------------------------------------- #
# 6. NaN                                                                     #
# --------------------------------------------------------------------------- #
def test_nan_vs_nan_coincide():
    a = _result(pf=float("nan"))
    b = _result(pf=float("nan"))
    result = compare_results(a, b)
    ok = result.matches is True
    return _p("NaN vs NaN -> coincide (comparación NaN-consciente, caso real de "
              "'ETHUSDT/2023 no-computable' en 3/16 scripts legacy)", ok)


def test_nan_vs_valor_real_diverge():
    a = _result(pf=float("nan"))
    b = _result(pf=1.5)
    result = compare_results(a, b)
    ok = result.matches is False and result.differences[0].field == "pf"
    return _p("NaN vs valor real -> diverge", ok)


# --------------------------------------------------------------------------- #
# 7. Normalización de tipo numérico, SIN tolerancia                          #
# --------------------------------------------------------------------------- #
def test_normalizacion_tipo_numerico_sin_tolerancia():
    """int vs float, y un 'numpy-scalar-like' (objeto float pero de otra
    instancia), deben coincidir SIN introducir ninguna tolerancia de
    valor -- mismo precedente ya usado en test_runner_equivalence.py."""
    a = _result(n_entries=100)
    b = _result(n_entries=100.0)  # mismo valor, distinto tipo (int vs float)
    result = compare_results(a, b)
    ok = result.matches is True
    return _p("100 (int) vs 100.0 (float) -> coincide (normalización de tipo, no de valor)", ok)


def test_normalizacion_tipo_numerico_no_oculta_diferencia_real():
    a = _result(pf=1.500001)
    b = _result(pf=1.5)
    result = compare_results(a, b)
    ok = result.matches is False and result.differences[0].field == "pf"
    return _p("1.500001 vs 1.5 -> diverge (la normalización de tipo NO introduce "
              "tolerancia de valor, ni siquiera mínima)", ok)


def test_bool_gate_pass_se_compara_exacto():
    a = _result(gate_pass=True)
    b = _result(gate_pass=False)
    result = compare_results(a, b)
    ok = result.matches is False and result.differences[0].field == "gate_pass"
    return _p("gate_pass=True vs False -> diverge", ok)


# --------------------------------------------------------------------------- #
# 8. Default vs fields explícito                                             #
# --------------------------------------------------------------------------- #
def test_fields_default_usa_las_9_metricas_de_resultado():
    a, b = _result(), _result()
    result = compare_results(a, b)
    ok = result.fields_compared == (
        "n_entries", "n_trades", "pf", "wr", "exp_r", "total_r", "max_dd", "freq", "gate_pass",
    )
    return _p("fields=None usa exactamente el conjunto por defecto de 9 campos de resultado", ok)


def test_fields_explicito_restringe_la_comparacion():
    a = _result(pf=1.5, wr=99.0)  # wr diverge pero no se pide comparar
    b = _result(pf=1.5, wr=1.0)
    result = compare_results(a, b, fields=("pf",))
    ok = result.matches is True and result.fields_compared == ("pf",)
    return _p("fields=('pf',) explícito ignora divergencias en campos no solicitados (wr)", ok)


def test_fields_explicito_replica_subconjunto_legacy():
    """Replica el subconjunto exacto de campos que compara la mayoría de
    los 16 scripts legacy (pf/wr/exp_r/max_dd/freq)."""
    a = _result(pf=1.5, wr=50.0, exp_r=0.1, max_dd=-5.0, freq=8.0)
    b = _result(pf=1.5, wr=50.0, exp_r=0.1, max_dd=-5.0, freq=8.0)
    result = compare_results(a, b, fields=("pf", "wr", "exp_r", "max_dd", "freq"))
    ok = result.matches is True and len(result.fields_compared) == 5
    return _p("fields=('pf','wr','exp_r','max_dd','freq') replica el núcleo de comparación "
              "usado por la mayoría de los scripts legacy", ok)


# --------------------------------------------------------------------------- #
# 9. Campo inválido                                                          #
# --------------------------------------------------------------------------- #
def test_campo_invalido_falla_explicitamente():
    a, b = _result(), _result()
    ok = True
    try:
        compare_results(a, b, fields=("pf", "no_existe_este_campo"))
        ok = False
    except ValueError:
        pass
    return _p("fields con un nombre que no existe en ExperimentResult -> ValueError, "
              "antes de comparar nada", ok)


def test_avg_win_avg_loss_no_son_campos_validos():
    """Confirma la limitación documentada: avg_win/avg_loss (comparados
    por integration_campaign_be.py) no existen en ExperimentResult."""
    a, b = _result(), _result()
    ok = True
    try:
        compare_results(a, b, fields=("avg_win",))
        ok = False
    except ValueError:
        pass
    return _p("fields=('avg_win',) -> ValueError (avg_win no existe en ExperimentResult, "
              "limitación documentada respecto a integration_campaign_be.py)", ok)


# --------------------------------------------------------------------------- #
# 10. Metadata excluida por defecto                                          #
# --------------------------------------------------------------------------- #
def test_metadata_no_se_compara_por_defecto():
    a = _result(contract_hash="aaaaaaaaaaaaaaaa", dataset_version="v1",
                pipeline_version="p1", engine_version="e1")
    b = _result(contract_hash="bbbbbbbbbbbbbbbb", dataset_version="v2",
                pipeline_version="p2", engine_version="e2")
    result = compare_results(a, b)
    ok = result.matches is True  # metadata distinta, pero fuera del default -> no afecta
    return _p("contract_hash/dataset_version/pipeline_version/engine_version distintos "
              "NO afectan matches con fields=None (excluidos del default)", ok)


def test_identidad_no_se_compara_por_defecto():
    a = _result(asset="BTCUSDT", trigger="T1_ema_cross")
    b = _result(asset="ETHUSDT", trigger="A_sweep_bos")
    result = compare_results(a, b)
    ok = result.matches is True  # identidad distinta, pero fuera del default
    return _p("asset/trigger distintos NO afectan matches con fields=None "
              "(campos de identidad excluidos del default)", ok)


# --------------------------------------------------------------------------- #
# 11. Determinismo y orden                                                   #
# --------------------------------------------------------------------------- #
def test_determinismo():
    a = _result(pf=1.5, wr=50.0)
    b = _result(pf=1.8, wr=55.0)
    r1 = compare_results(a, b)
    r2 = compare_results(a, b)
    ok = r1 == r2
    return _p("Mismo (actual, reference, fields) produce siempre el mismo ComparisonResult", ok)


def test_orden_de_differences_seguido_orden_de_fields():
    a = _result(freq=1.0, pf=1.0, n_entries=1)
    b = _result(freq=2.0, pf=2.0, n_entries=2)
    result = compare_results(a, b, fields=("freq", "pf", "n_entries"))
    ok = [d.field for d in result.differences] == ["freq", "pf", "n_entries"]
    return _p("El orden de differences sigue el orden de fields_compared, no un orden "
              "arbitrario", ok)


# --------------------------------------------------------------------------- #
# 12. Pureza — sin I/O, sin pandas                                           #
# --------------------------------------------------------------------------- #
def test_compare_results_no_hace_io():
    import builtins
    calls = []
    orig_open = builtins.open

    def _spy(*args, **kwargs):
        calls.append(args)
        return orig_open(*args, **kwargs)

    builtins.open = _spy
    try:
        a, b = _result(pf=1.5), _result(pf=1.8)
        compare_results(a, b)
        ok = len(calls) == 0
    finally:
        builtins.open = orig_open
    return _p("compare_results no invoca open() -- comparación pura, sin filesystem", ok)


def test_modulo_no_importa_pandas():
    import research.comparison as comparison_mod
    src_globals = vars(comparison_mod)
    ok = "pd" not in src_globals and "pandas" not in src_globals
    return _p("research/comparison.py no importa pandas en su espacio de nombres", ok)


ALL_TESTS = [
    test_resultados_identicos,
    test_una_diferencia,
    test_multiples_diferencias_todas_recolectadas,
    test_n_entries_n_trades_incluidos_por_defecto,
    test_none_vs_none_coincide,
    test_none_vs_valor_real_diverge,
    test_none_vs_nan_diverge,
    test_nan_vs_nan_coincide,
    test_nan_vs_valor_real_diverge,
    test_normalizacion_tipo_numerico_sin_tolerancia,
    test_normalizacion_tipo_numerico_no_oculta_diferencia_real,
    test_bool_gate_pass_se_compara_exacto,
    test_fields_default_usa_las_9_metricas_de_resultado,
    test_fields_explicito_restringe_la_comparacion,
    test_fields_explicito_replica_subconjunto_legacy,
    test_campo_invalido_falla_explicitamente,
    test_avg_win_avg_loss_no_son_campos_validos,
    test_metadata_no_se_compara_por_defecto,
    test_identidad_no_se_compara_por_defecto,
    test_determinismo,
    test_orden_de_differences_seguido_orden_de_fields,
    test_compare_results_no_hace_io,
    test_modulo_no_importa_pandas,
]


def main():
    print("research/tests/test_comparison — Componente 7 (Comparison)\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
