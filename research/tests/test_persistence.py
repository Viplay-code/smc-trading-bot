"""
research/tests/test_persistence.py — Automatización experimental,
Componente 6 (Persistence / Artifacts, 2026-09-04).

Cubre los 13 casos obligatorios del diseño aprobado: serialización de
ExperimentResult (individual y múltiple), colección vacía, metadata,
serialización de CandidateDecision (múltiples roles, roles adicionales),
determinismo, orden de columnas, escritura, lectura/verificación,
valores nulos, y separación transformación/I-O.

Explícitamente NO prueba decision/gates/métricas (ya cubiertos en C5),
ni baseline/comparison/parameter_grid/reporting (fuera de alcance de C6).

Además (Componente 8, Persistence Read, 2026-09-05): round-trip de
`read_experiment_results_csv` — round-trip simple/múltiple, header-only,
None, NaN, bool, inf, strings, columna canónica faltante, columna extra
tolerada, archivo inexistente, archivo vacío, fila malformada, y
composición write->read end-to-end. Explícitamente NO prueba lectura de
`decision.csv`/`CandidateDecision` (diferido, ver diseño aprobado de C8),
ni Baseline Resolution/Legacy Adapter (fuera de alcance).

Ejecutar:
    python -m research.tests.test_persistence  (o con pytest)
"""
from __future__ import annotations

import csv
import io
import math
import os
import sys
import tempfile

sys.path.insert(0, ".")
from research.decision import CandidateDecision
from research.persistence import (
    EXPERIMENT_RESULT_COLUMNS,
    to_experiment_rows,
    to_decision_rows,
    render_experiment_csv,
    render_decision_csv,
    write_experiment_results_csv,
    write_decision_csv,
    read_experiment_results_csv,
)
from research.schema import ExperimentResult


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def _result(asset="BTCUSDT", role="train", period=2022, pf=1.8, gate_pass=True,
            trigger="T1_ema_cross", session="dcv1_activo_15h", management="V3-A",
            **overrides) -> ExperimentResult:
    kwargs = dict(
        experiment_name="test_persistence", asset=asset, period=period, period_role=role,
        bias="A_ema200_neutral", trigger=trigger, entry="C_market_close",
        session=session, management=management,
        n_entries=10, n_trades=10, pf=pf, wr=50.0, exp_r=0.1,
        total_r=1.0, max_dd=-5.0, freq=8.0, gate_pass=gate_pass,
        contract_hash="0123456789abcdef", dataset_version="market-data-v1",
        pipeline_version="dc-v1", engine_version="research-engine-1",
    )
    kwargs.update(overrides)
    return ExperimentResult(**kwargs)


def _read_csv_rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


# --------------------------------------------------------------------------- #
# 1. Serialización de un ExperimentResult                                    #
# --------------------------------------------------------------------------- #
def test_serializacion_un_resultado():
    r = _result()
    rows = to_experiment_rows([r])
    ok = (
        len(rows) == 1
        and rows[0]["asset"] == "BTCUSDT"
        and rows[0]["pf"] == 1.8
        and rows[0]["contract_hash"] == "0123456789abcdef"
        and set(rows[0].keys()) == set(EXPERIMENT_RESULT_COLUMNS)
    )
    return _p("to_experiment_rows([r]) produce 1 fila con todas las columnas canónicas", ok)


# --------------------------------------------------------------------------- #
# 2. Serialización de múltiples resultados                                   #
# --------------------------------------------------------------------------- #
def test_serializacion_multiples_resultados():
    results = [_result(asset="BTCUSDT"), _result(asset="ETHUSDT"), _result(asset="SOLUSDT")]
    rows = to_experiment_rows(results)
    ok = len(rows) == 3 and [r["asset"] for r in rows] == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    return _p("to_experiment_rows conserva el orden y produce 1 fila por resultado", ok)


# --------------------------------------------------------------------------- #
# 3. Colección vacía                                                         #
# --------------------------------------------------------------------------- #
def test_coleccion_vacia_experiment_rows():
    ok = to_experiment_rows([]) == []
    return _p("to_experiment_rows([]) -> []", ok)


def test_coleccion_vacia_decision_rows():
    ok = to_decision_rows([], candidate_fields=("trigger",)) == []
    return _p("to_decision_rows([], ...) -> []", ok)


def test_coleccion_vacia_produce_csv_valido_con_solo_header():
    text = render_experiment_csv([])
    rows = _read_csv_rows(text)
    ok = rows == [] and text.strip("\n").split("\n")[0] == ",".join(EXPERIMENT_RESULT_COLUMNS)
    return _p("render_experiment_csv([]) produce un CSV válido con solo header, no un error", ok)


# --------------------------------------------------------------------------- #
# 4. Serialización de metadata                                               #
# --------------------------------------------------------------------------- #
def test_metadata_de_reproducibilidad_preservada():
    r = _result(contract_hash="fedcba9876543210", dataset_version="ds-v2",
                pipeline_version="pipe-v3", engine_version="engine-v4")
    row = to_experiment_rows([r])[0]
    ok = (
        row["contract_hash"] == "fedcba9876543210"
        and row["dataset_version"] == "ds-v2"
        and row["pipeline_version"] == "pipe-v3"
        and row["engine_version"] == "engine-v4"
        and row["experiment_name"] == "test_persistence"
        and row["period"] == 2022 and row["period_role"] == "train"
    )
    return _p("contract_hash/dataset_version/pipeline_version/engine_version/"
              "experiment_name/period/period_role se preservan exactos", ok)


def test_metadata_ausente_no_se_fabrica():
    """Un ExperimentResult sin metadata de reproducibilidad (campos
    opcionales en None) no debe fabricar ningún valor."""
    r = _result(contract_hash=None, dataset_version=None, pipeline_version=None,
                engine_version=None, gate_pass=None)
    row = to_experiment_rows([r])[0]
    ok = (
        row["contract_hash"] is None and row["dataset_version"] is None
        and row["pipeline_version"] is None and row["engine_version"] is None
        and row["gate_pass"] is None
    )
    return _p("Metadata ausente (None) se preserva como None -- nunca fabricada", ok)


# --------------------------------------------------------------------------- #
# 5-7. CandidateDecision: serialización, múltiples roles, roles adicionales #
# --------------------------------------------------------------------------- #
def test_serializacion_candidate_decision():
    d = CandidateDecision(
        asset="BTCUSDT", candidate=("T1_ema_cross",),
        per_role={"train": _result(role="train"), "validate": _result(role="validate")},
        survives_required_roles=True, rank_within_asset=1,
    )
    rows = to_decision_rows([d], candidate_fields=("trigger",))
    ok = (
        len(rows) == 1
        and rows[0]["asset"] == "BTCUSDT" and rows[0]["trigger"] == "T1_ema_cross"
        and rows[0]["survives_required_roles"] is True
        and rows[0]["rank_within_asset"] == 1
        and set(rows[0].keys()) == {"asset", "trigger", "survives_required_roles", "rank_within_asset"}
    )
    return _p("to_decision_rows produce 1 fila con asset/candidate_fields/survives/rank -- "
              "sin ninguna métrica embebida", ok)


def test_multiples_roles_no_se_flatten_en_decision():
    """per_role con 2 roles NO produce columnas pf_train/pf_validate en el
    artifact decision -- esa información vive en el artifact results."""
    d = CandidateDecision(
        asset="BTCUSDT", candidate=("T1_ema_cross",),
        per_role={"train": _result(role="train", pf=1.5), "validate": _result(role="validate", pf=1.9)},
        survives_required_roles=True, rank_within_asset=1,
    )
    row = to_decision_rows([d], candidate_fields=("trigger",))[0]
    ok = "pf_train" not in row and "pf_validate" not in row and "pf" not in row
    return _p("La fila de decision NO contiene columnas pf_train/pf_validate/pf -- "
              "el flatten por rol está deliberadamente excluido", ok)


def test_roles_adicionales_no_afectan_la_fila_de_decision():
    """Un candidato con un rol extra (ej. 'blind', no requerido) no
    produce ninguna columna nueva en decision -- decision resume, no
    replica per_role."""
    d1 = CandidateDecision(
        asset="BTCUSDT", candidate=("T1_ema_cross",),
        per_role={"train": _result(role="train"), "validate": _result(role="validate")},
        survives_required_roles=True, rank_within_asset=1,
    )
    d2 = CandidateDecision(
        asset="BTCUSDT", candidate=("A_sweep_bos",),
        per_role={"train": _result(role="train"), "validate": _result(role="validate"),
                  "blind": _result(role="blind")},
        survives_required_roles=True, rank_within_asset=2,
    )
    rows = to_decision_rows([d1, d2], candidate_fields=("trigger",))
    ok = set(rows[0].keys()) == set(rows[1].keys())  # mismas columnas pese a distinto n° de roles
    return _p("Roles adicionales (ej. 'blind') en per_role no cambian el esquema de columnas "
              "de la fila de decision", ok)


def test_per_role_completo_vive_en_results_no_en_decision():
    """La trazabilidad por rol NO se pierde -- vive en el artifact
    results, reconstruible desde CandidateDecision.per_role.values()."""
    d = CandidateDecision(
        asset="BTCUSDT", candidate=("T1_ema_cross",),
        per_role={"train": _result(role="train", pf=1.5), "validate": _result(role="validate", pf=1.9)},
        survives_required_roles=True, rank_within_asset=1,
    )
    results_rows = to_experiment_rows(list(d.per_role.values()))
    ok = (
        len(results_rows) == 2
        and {r["period_role"] for r in results_rows} == {"train", "validate"}
        and {r["pf"] for r in results_rows} == {1.5, 1.9}
    )
    return _p("CandidateDecision.per_role.values() se serializa vía el MISMO esquema de "
              "results, preservando pf por rol sin duplicar código", ok)


def test_candidate_fields_desalineado_falla_explicitamente():
    d = CandidateDecision(
        asset="BTCUSDT", candidate=("T1_ema_cross", "dcv1_activo_15h"),
        per_role={"train": _result()}, survives_required_roles=False, rank_within_asset=None,
    )
    ok = True
    try:
        to_decision_rows([d], candidate_fields=("trigger",))  # solo 1 campo, candidate tiene 2
        ok = False
    except ValueError:
        pass
    return _p("candidate_fields con longitud distinta a CandidateDecision.candidate -> "
              "ValueError explícito, no una fila mal alineada", ok)


# --------------------------------------------------------------------------- #
# 8-9. Determinismo y orden de columnas                                      #
# --------------------------------------------------------------------------- #
def test_determinismo_render():
    results = [_result(asset="BTCUSDT"), _result(asset="ETHUSDT")]
    text1 = render_experiment_csv(results)
    text2 = render_experiment_csv(results)
    ok = text1 == text2
    return _p("render_experiment_csv produce texto BYTE-IDÉNTICO en 2 corridas con el "
              "mismo input", ok)


def test_orden_de_columnas_fijo_y_derivado_del_dataclass():
    import dataclasses
    expected = tuple(f.name for f in dataclasses.fields(ExperimentResult))
    ok = EXPERIMENT_RESULT_COLUMNS == expected
    text = render_experiment_csv([_result()])
    header = text.split("\n")[0]
    ok = ok and header == ",".join(expected)
    return _p("EXPERIMENT_RESULT_COLUMNS coincide exacto con dataclasses.fields(ExperimentResult) "
              "y el header del CSV usa ese mismo orden", ok)


def test_orden_de_columnas_decision():
    d = CandidateDecision(asset="BTCUSDT", candidate=("T1_ema_cross", "dcv1_activo_15h"),
                           per_role={}, survives_required_roles=False, rank_within_asset=None)
    text = render_decision_csv([d], candidate_fields=("trigger", "session"))
    header = text.split("\n")[0]
    ok = header == "asset,trigger,session,survives_required_roles,rank_within_asset"
    return _p("El header del artifact decision es asset,<candidate_fields...>,"
              "survives_required_roles,rank_within_asset, en ese orden", ok)


# --------------------------------------------------------------------------- #
# 10-11. Escritura y lectura/verificación                                    #
# --------------------------------------------------------------------------- #
def test_escritura_y_lectura_resultados():
    results = [_result(asset="BTCUSDT"), _result(asset="ETHUSDT", pf=2.1)]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "results.csv")
        write_experiment_results_csv(path, results)
        ok = os.path.exists(path)
        with open(path, "r", encoding="utf-8", newline="") as f:
            content = f.read()
        rows = _read_csv_rows(content)
        ok = ok and len(rows) == 2 and rows[0]["asset"] == "BTCUSDT" and rows[1]["pf"] == "2.1"
        ok = ok and content == render_experiment_csv(results)
    return _p("write_experiment_results_csv escribe un archivo leíble cuyo contenido es "
              "idéntico al render en memoria", ok)


def test_escritura_y_lectura_decision():
    d = CandidateDecision(asset="BTCUSDT", candidate=("T1_ema_cross",),
                           per_role={"train": _result()}, survives_required_roles=False,
                           rank_within_asset=None)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "decision.csv")
        write_decision_csv(path, [d], candidate_fields=("trigger",))
        with open(path, "r", encoding="utf-8", newline="") as f:
            content = f.read()
        rows = _read_csv_rows(content)
        ok = len(rows) == 1 and rows[0]["trigger"] == "T1_ema_cross" and rows[0]["survives_required_roles"] == "False"
    return _p("write_decision_csv escribe un archivo leíble con las columnas y valores esperados", ok)


# --------------------------------------------------------------------------- #
# 12. Valores nulos                                                          #
# --------------------------------------------------------------------------- #
def test_valores_none_se_representan_como_celda_vacia():
    r = _result(gate_pass=None, contract_hash=None)
    text = render_experiment_csv([r])
    rows = _read_csv_rows(text)
    ok = rows[0]["gate_pass"] == "" and rows[0]["contract_hash"] == ""
    return _p("None se representa como celda vacía en el CSV, no como la cadena 'None'", ok)


def test_rank_within_asset_none_se_representa_como_celda_vacia():
    d = CandidateDecision(asset="BTCUSDT", candidate=("T1_ema_cross",), per_role={},
                           survives_required_roles=False, rank_within_asset=None)
    text = render_decision_csv([d], candidate_fields=("trigger",))
    rows = _read_csv_rows(text)
    ok = rows[0]["rank_within_asset"] == ""
    return _p("rank_within_asset=None se representa como celda vacía en el artifact decision", ok)


def test_float_inf_no_se_normaliza():
    """pf=inf (gross_loss=0) no debe truncarse ni reformatearse."""
    r = _result(pf=float("inf"))
    text = render_experiment_csv([r])
    rows = _read_csv_rows(text)
    ok = rows[0]["pf"] == "inf"
    return _p("pf=float('inf') se serializa como 'inf' (str() de Python), sin normalizar", ok)


# --------------------------------------------------------------------------- #
# 13. Separación transformación/I-O                                          #
# --------------------------------------------------------------------------- #
def test_to_experiment_rows_no_hace_io():
    """to_experiment_rows/render_experiment_csv no tocan filesystem --
    verificado interceptando builtins.open."""
    import builtins
    calls = []
    orig_open = builtins.open

    def _spy(*args, **kwargs):
        calls.append(args)
        return orig_open(*args, **kwargs)

    builtins.open = _spy
    try:
        results = [_result(asset="BTCUSDT"), _result(asset="ETHUSDT")]
        to_experiment_rows(results)
        render_experiment_csv(results)
        ok = len(calls) == 0
    finally:
        builtins.open = orig_open
    return _p("to_experiment_rows/render_experiment_csv no invocan open() -- "
              "transformación pura, sin filesystem", ok)


def test_write_es_la_unica_funcion_que_toca_disco():
    """write_experiment_results_csv SÍ toca disco (comportamiento
    esperado del writer) -- confirma la separación: solo las funciones
    write_* hacen I/O, el resto son puras."""
    import builtins
    calls = []
    orig_open = builtins.open

    def _spy(*args, **kwargs):
        calls.append(args[0] if args else kwargs.get("file"))
        return orig_open(*args, **kwargs)

    builtins.open = _spy
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "r.csv")
            write_experiment_results_csv(path, [_result()])
            ok = any(str(c) == path for c in calls)
    finally:
        builtins.open = orig_open
    return _p("write_experiment_results_csv es la única función que invoca open() -- "
              "delgada, sin lógica de transformación propia", ok)


# --------------------------------------------------------------------------- #
# Hallazgos de la revisión final — alcance preciso de determinismo y de la    #
# trazabilidad (asset, candidate_fields, period_role).                       #
# --------------------------------------------------------------------------- #
def test_results_es_sensible_al_orden_de_entrada():
    """Propiedad DECLARADA: 'mismos inputs EN EL MISMO ORDEN -> mismo
    output'. Esta NO es la propiedad más fuerte 'misma colección lógica,
    cualquier orden -> mismo output' — se verifica explícitamente que
    esa propiedad más fuerte NO se cumple para 'results' (deliberado, ver
    docstring del módulo: persistence.py no impone un orden propio sobre
    lo que run_many/C3 ya decidió preservar)."""
    a, b = _result(asset="BTCUSDT"), _result(asset="ETHUSDT")
    text_ab = render_experiment_csv([a, b])
    text_ba = render_experiment_csv([b, a])
    ok = text_ab != text_ba
    return _p("render_experiment_csv([a,b]) != render_experiment_csv([b,a]) -- 'results' "
              "es sensible al orden de entrada, NO se canoniza (deliberado)", ok)


def test_decision_es_insensible_al_orden_solo_por_normalizacion_upstream():
    """La insensibilidad al orden del artifact decision proviene de
    research.decision.summarize_decision (C5), NO de persistence.py --
    se verifica pasando los MISMOS ExperimentResult en 2 órdenes de
    entrada distintos A TRAVÉS de summarize_decision, confirmando que
    el CSV resultante es idéntico."""
    from research.decision import summarize_decision
    results_order1 = [
        _result(asset="BTCUSDT", role="train"), _result(asset="BTCUSDT", role="validate"),
        _result(asset="ETHUSDT", role="train"), _result(asset="ETHUSDT", role="validate"),
    ]
    results_order2 = list(reversed(results_order1))
    d1 = summarize_decision(results_order1, candidate_fields=("trigger",),
                             required_roles=("train", "validate"), rank_by_role="validate")
    d2 = summarize_decision(results_order2, candidate_fields=("trigger",),
                             required_roles=("train", "validate"), rank_by_role="validate")
    text1 = render_decision_csv(d1, candidate_fields=("trigger",))
    text2 = render_decision_csv(d2, candidate_fields=("trigger",))
    ok = text1 == text2
    return _p("render_decision_csv es insensible al orden de los ExperimentResult "
              "originales -- propiedad heredada de summarize_decision (C5), no calculada "
              "por persistence.py", ok)


def test_asset_candidate_fields_role_no_es_clave_globalmente_unica():
    """(asset, candidate_fields, period_role) NO identifica de forma
    única un ExperimentResult a través de un artifact results arbitrario
    -- 2 contratos DISTINTOS (management/contract_hash distintos) pueden
    compartir esa clave si provienen de campañas concatenadas. La
    identidad global sigue siendo contract_hash, ya presente en la fila."""
    r_a = _result(asset="BTCUSDT", role="train", trigger="T1_ema_cross",
                  management="V3-A", contract_hash="hash-campania-A")
    r_b = _result(asset="BTCUSDT", role="train", trigger="T1_ema_cross",
                  management="Raw", contract_hash="hash-campania-B")
    rows = to_experiment_rows([r_a, r_b])
    matches = [row for row in rows if row["asset"] == "BTCUSDT"
               and row["trigger"] == "T1_ema_cross" and row["period_role"] == "train"]
    ok = (
        len(matches) == 2  # la clave (asset, trigger, role) NO discrimina -- ambos matchean
        and matches[0]["contract_hash"] != matches[1]["contract_hash"]  # contract_hash sí lo hace
    )
    return _p("(asset, trigger, period_role) matchea 2 filas de contratos DISTINTOS "
              "(management/contract_hash distintos) -- no es una clave global; "
              "contract_hash sigue discriminándolas correctamente", ok)


# --------------------------------------------------------------------------- #
# Componente 8 (Persistence Read, 2026-09-05) — deserialización simétrica    #
# del artifact `results`. Mismo precedente que los tests de escritura de C6: #
# tempfile.TemporaryDirectory(), sin fixtures nuevos.                        #
# --------------------------------------------------------------------------- #
def test_read_round_trip_una_fila():
    r = _result(asset="BTCUSDT")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "r.csv")
        write_experiment_results_csv(path, [r])
        leidos = read_experiment_results_csv(path)
    ok = leidos == [r]
    return _p("read_experiment_results_csv(write_experiment_results_csv([r])) == [r] "
              "(round-trip de 1 fila)", ok)


def test_read_round_trip_multiples_filas_orden_preservado():
    resultados = [_result(asset="BTCUSDT"), _result(asset="ETHUSDT"), _result(asset="SOLUSDT")]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "r.csv")
        write_experiment_results_csv(path, resultados)
        leidos = read_experiment_results_csv(path)
    ok = leidos == resultados and [r.asset for r in leidos] == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    return _p("Round-trip de 3 filas conserva el orden exacto de escritura", ok)


def test_read_header_only_produce_lista_vacia():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "r.csv")
        write_experiment_results_csv(path, [])
        leidos = read_experiment_results_csv(path)
    ok = leidos == []
    return _p("read_experiment_results_csv sobre un CSV de solo header -> [] "
              "(NO es un error, simétrico del diseño de C6)", ok)


def test_read_campos_none_se_preservan():
    r = _result(gate_pass=None, contract_hash=None, dataset_version=None,
                pipeline_version=None, engine_version=None, pf=None, wr=None,
                exp_r=None, total_r=None, max_dd=None, freq=None)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "r.csv")
        write_experiment_results_csv(path, [r])
        leido = read_experiment_results_csv(path)[0]
    ok = (
        leido.gate_pass is None and leido.contract_hash is None
        and leido.dataset_version is None and leido.pipeline_version is None
        and leido.engine_version is None and leido.pf is None and leido.wr is None
        and leido.exp_r is None and leido.total_r is None and leido.max_dd is None
        and leido.freq is None
    )
    return _p("Todos los campos opcionales en None se preservan como None tras el "
              "round-trip (celda vacía -> None, no la cadena 'None')", ok)


def test_read_nan_round_trip():
    """NaN round-trip correcto, verificado con math.isnan -- NO con ==
    (NaN nunca es igual a sí mismo, propiedad matemática, no un defecto)."""
    r = _result(pf=float("nan"))
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "r.csv")
        write_experiment_results_csv(path, [r])
        leido = read_experiment_results_csv(path)[0]
    ok = isinstance(leido.pf, float) and math.isnan(leido.pf)
    return _p("pf=float('nan') round-trip correcto, verificado con math.isnan "
              "(no con ==, que siempre es False para NaN)", ok)


def test_read_bool_true_false_none():
    r_true = _result(asset="BTCUSDT", gate_pass=True)
    r_false = _result(asset="ETHUSDT", gate_pass=False)
    r_none = _result(asset="SOLUSDT", gate_pass=None)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "r.csv")
        write_experiment_results_csv(path, [r_true, r_false, r_none])
        leidos = read_experiment_results_csv(path)
    ok = (
        leidos[0].gate_pass is True
        and leidos[1].gate_pass is False  # NO bool("False") == True (gotcha evitado)
        and leidos[2].gate_pass is None
    )
    return _p("gate_pass True/False/None round-trip exacto -- 'False' se lee como "
              "False, no como True (bool(str) gotcha explícitamente evitado)", ok)


def test_read_inf_round_trip():
    r = _result(pf=float("inf"))
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "r.csv")
        write_experiment_results_csv(path, [r])
        leido = read_experiment_results_csv(path)[0]
    ok = leido.pf == float("inf")
    return _p("pf=float('inf') round-trip exacto", ok)


def test_read_strings_se_preservan_literalmente():
    r = _result(asset="BTCUSDT", trigger="T1_ema_cross", session="dcv1_activo_15h",
                management="V3-A", bias="A_ema200_neutral", entry="C_market_close")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "r.csv")
        write_experiment_results_csv(path, [r])
        leido = read_experiment_results_csv(path)[0]
    ok = (
        leido.asset == "BTCUSDT" and leido.trigger == "T1_ema_cross"
        and leido.session == "dcv1_activo_15h" and leido.management == "V3-A"
        and leido.bias == "A_ema200_neutral" and leido.entry == "C_market_close"
    )
    return _p("Campos string (asset/trigger/session/management/bias/entry) se "
              "preservan literalmente tras el round-trip", ok)


def test_read_columna_canonica_faltante_rechaza():
    r = _result()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "r.csv")
        write_experiment_results_csv(path, [r])
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # Elimina la columna 'pf' del header (primera ocurrencia exacta).
        content = content.replace("pf,wr", "wr", 1)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        ok = True
        try:
            read_experiment_results_csv(path)
            ok = False
        except ValueError as e:
            ok = "pf" in str(e)
    return _p("CSV sin la columna canónica 'pf' -> ValueError nombrando la columna faltante", ok)


def test_read_columna_extra_se_tolera():
    r = _result()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "r.csv")
        write_experiment_results_csv(path, [r])
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        lines[0] += ",columna_desconocida"
        for i in range(1, len(lines)):
            lines[i] += ",valor_extra"
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("\n".join(lines) + "\n")
        leidos = read_experiment_results_csv(path)
    ok = len(leidos) == 1 and leidos[0] == r
    return _p("CSV con una columna adicional desconocida -> tolerada, ignorada, "
              "lectura correcta del resto", ok)


def test_read_archivo_inexistente():
    ok = True
    try:
        read_experiment_results_csv("este/archivo/no/existe/en/absoluto.csv")
        ok = False
    except FileNotFoundError:
        pass
    return _p("read_experiment_results_csv sobre una ruta inexistente -> FileNotFoundError "
              "(propagada natural de open(), sin envolver)", ok)


def test_read_archivo_vacio():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "vacio.csv")
        with open(path, "w", encoding="utf-8") as f:
            pass  # 0 bytes
        ok = True
        try:
            read_experiment_results_csv(path)
            ok = False
        except ValueError:
            pass
    return _p("read_experiment_results_csv sobre un archivo de 0 bytes -> ValueError explícito", ok)


def test_read_fila_malformada_error_descriptivo():
    r = _result()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "r.csv")
        write_experiment_results_csv(path, [r])
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace(f",{r.pf},", ",no_es_un_numero,", 1)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        ok = True
        try:
            read_experiment_results_csv(path)
            ok = False
        except ValueError as e:
            msg = str(e)
            ok = "pf" in msg and "no_es_un_numero" in msg and "fila 0" in msg
    return _p("Fila con pf='no_es_un_numero' -> ValueError identificando fila, campo "
              "y valor crudo (sin fallo opaco)", ok)


def test_write_read_composicion_end_to_end():
    resultados = [_result(asset="BTCUSDT", pf=1.5), _result(asset="ETHUSDT", pf=None, gate_pass=None)]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "r.csv")
        write_experiment_results_csv(path, resultados)
        leidos = read_experiment_results_csv(path)
    ok = leidos == resultados
    return _p("write_experiment_results_csv -> read_experiment_results_csv compuestos "
              "end-to-end reproducen la colección original exacta", ok)


ALL_TESTS = [
    test_serializacion_un_resultado,
    test_serializacion_multiples_resultados,
    test_coleccion_vacia_experiment_rows,
    test_coleccion_vacia_decision_rows,
    test_coleccion_vacia_produce_csv_valido_con_solo_header,
    test_metadata_de_reproducibilidad_preservada,
    test_metadata_ausente_no_se_fabrica,
    test_serializacion_candidate_decision,
    test_multiples_roles_no_se_flatten_en_decision,
    test_roles_adicionales_no_afectan_la_fila_de_decision,
    test_per_role_completo_vive_en_results_no_en_decision,
    test_candidate_fields_desalineado_falla_explicitamente,
    test_determinismo_render,
    test_orden_de_columnas_fijo_y_derivado_del_dataclass,
    test_orden_de_columnas_decision,
    test_escritura_y_lectura_resultados,
    test_escritura_y_lectura_decision,
    test_valores_none_se_representan_como_celda_vacia,
    test_rank_within_asset_none_se_representa_como_celda_vacia,
    test_float_inf_no_se_normaliza,
    test_to_experiment_rows_no_hace_io,
    test_write_es_la_unica_funcion_que_toca_disco,
    test_results_es_sensible_al_orden_de_entrada,
    test_decision_es_insensible_al_orden_solo_por_normalizacion_upstream,
    test_asset_candidate_fields_role_no_es_clave_globalmente_unica,
    test_read_round_trip_una_fila,
    test_read_round_trip_multiples_filas_orden_preservado,
    test_read_header_only_produce_lista_vacia,
    test_read_campos_none_se_preservan,
    test_read_nan_round_trip,
    test_read_bool_true_false_none,
    test_read_inf_round_trip,
    test_read_strings_se_preservan_literalmente,
    test_read_columna_canonica_faltante_rechaza,
    test_read_columna_extra_se_tolera,
    test_read_archivo_inexistente,
    test_read_archivo_vacio,
    test_read_fila_malformada_error_descriptivo,
    test_write_read_composicion_end_to_end,
]


def main():
    print("research/tests/test_persistence — Componente 6 (Persistence / Artifacts)\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
