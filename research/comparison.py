"""research/comparison.py — Automatización experimental, Componente 7
(Comparison, 2026-09-05).

Compara dos `ExperimentResult` ya materializados, campo a campo, y
devuelve una estructura pequeña con el resultado — reemplaza la lógica
`_verify_against`/equivalente duplicada en 16/30 scripts de campaña
(auditoría previa a este componente). Responsabilidad EXCLUSIVAMENTE de
comparación pura en memoria — NO lee CSV, NO toca filesystem, NO importa
`pandas`, NO conoce `research.persistence`, NO resuelve `baseline`, NO
interpreta `_REF_PATH`, NO busca por `contract_hash` en ningún catálogo
(esa resolución — "Baseline resolution" — es una capacidad FUTURA,
deliberadamente NO construida acá). Ningún threshold científico, ninguna
métrica se recalcula ni se reinterpreta — solo se comparan valores ya
calculados por capas anteriores.

Auditoría de los 16 scripts (`_verify_against`/equivalente) que motiva
este diseño — ver también el informe de diseño aprobado antes de esta
implementación:
  - Igualdad EXACTA en los 16, sin excepción — cero scripts usan
    tolerancia numérica para esta comparación (los 2 hits de
    `abs(diff) > tolerancia` encontrados en `gestion_espacio6_raw_
    campaign.py`/`gestion_espacio6_costo_cero_diagnostico.py` verifican
    que un valor calculado coincide con una FÓRMULA teórica, un patrón
    estructuralmente distinto que no pertenece a esta familia).
  - 3/16 scripts (`bias_b_campaign.py`, `trigger_c_campaign.py`,
    `trigger_entry_campaign_rama_b.py`) usan una comparación NaN-consciente
    idéntica en los 3 (`pd.isna(actual) and pd.isna(expected) -> True`),
    motivada por un caso real documentado ("ETHUSDT/2023 es no-computable
    en la referencia de Espacio 3").
  - Todos recolectan TODOS los mismatches, nunca solo el primero.
  - Ningún script compara metadata de reproducibilidad (no existía
    cuando se escribieron) ni campos de identidad/dimensión (se asumen
    iguales por construcción — la fila de referencia ya se filtró por
    asset/año/candidato ANTES de comparar).

Frontera Comparison vs. Baseline resolution (futuro, NO construido acá):
    Comparison (este módulo):  ExperimentResult + ExperimentResult -> ComparisonResult   [PURO]
    Baseline resolution:       baseline locator -> Persistence/catálogo (lectura, no
                                construida) -> ExperimentResult

Este módulo es completamente independiente de `research.persistence` — no
lo importa, no lo necesita. `research.persistence` (C6) solo ESCRIBE
artifacts hoy; no existe ninguna capacidad de LECTURA/consulta de la que
Comparison pudiera depender, y no se construye acá.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, fields as dataclass_fields
from typing import Any, Sequence

from .schema import ExperimentResult

DEFAULT_COMPARISON_FIELDS: tuple[str, ...] = (
    "n_entries", "n_trades", "pf", "wr", "exp_r", "total_r", "max_dd", "freq", "gate_pass",
)
"""Conjunto de campos comparados cuando `fields` no se especifica —
exclusivamente campos de RESULTADO/MÉTRICA de `ExperimentResult` (ver
docstring del módulo). Deliberadamente EXCLUYE:
  - campos de identidad/dimensión (`experiment_name`/`asset`/`period`/
    `period_role`/`bias`/`trigger`/`entry`/`session`/`management`) — se
    asumen iguales por construcción, mismo supuesto implícito ya usado
    en los 16 scripts legacy (la referencia se busca filtrando por estos
    campos ANTES de comparar).
  - metadata de reproducibilidad (`contract_hash`/`dataset_version`/
    `pipeline_version`/`engine_version`) — dos resultados científicamente
    equivalentes pueden tener metadata de ejecución distinta sin que eso
    sea una divergencia real (mismo principio ya aplicado en C6/
    `research.decision`).
Ampliación declarada, no oculta, respecto al núcleo mínimo de los 16
scripts (`pf`/`wr`/`exp_r`/`max_dd`/`freq` + `n_entries`/`n_trades`):
se agregan `total_r`/`gate_pass`, nunca comparados explícitamente por
ningún script legacy pero legítimamente parte del resultado."""

_VALID_FIELDS: frozenset[str] = frozenset(f.name for f in dataclass_fields(ExperimentResult))


@dataclass(frozen=True)
class FieldDifference:
    """Una divergencia puntual en UN campo. `actual`/`reference` son los
    valores tal cual venían en cada `ExperimentResult` — nunca
    redondeados, truncados ni reinterpretados."""
    field: str
    actual: Any
    reference: Any


@dataclass(frozen=True)
class ComparisonResult:
    """Resultado de comparar dos `ExperimentResult`. `matches` es
    `True` si y solo si `differences` está vacío. `fields_compared`
    deja explícito qué se comparó realmente (el default, o el
    subconjunto pedido) — sin ambigüedad al inspeccionar el resultado
    fuera de contexto. `differences` contiene TODAS las divergencias
    encontradas, en el mismo orden que `fields_compared` — nunca solo
    la primera (mismo comportamiento universal de los 16 scripts
    legacy que este módulo reemplaza)."""
    matches: bool
    fields_compared: tuple[str, ...]
    differences: tuple[FieldDifference, ...]


def _is_nan(x: Any) -> bool:
    """`True` solo si `x` es un número de punto flotante NaN (incluye
    `numpy.float64('nan')`, que `math.isnan` acepta igual que un
    `float` nativo). Cualquier otro tipo (incluido `None`, `str`, `bool`,
    `int`) devuelve `False` sin lanzar — `math.isnan` solo acepta
    numéricos, así que el resto se captura explícitamente."""
    try:
        return math.isnan(x)
    except TypeError:
        return False


def _values_match(actual: Any, reference: Any) -> bool:
    """Igualdad EXACTA, NaN-consciente, con normalización de TIPO
    numérico (nunca de VALOR) — sin tolerancia, sin redondeo, sin
    truncamiento. Semántica, en orden de evaluación:
      1. `None` y `None` -> coincide (mismo estado: "muestra insuficiente"
         en ambos lados).
      2. Exactamente uno de los dos es `None` (el otro no) -> NO coincide
         — incluye explícitamente el caso `None` vs `NaN`: son estados
         DISTINTOS (`None` = todo el dict de métricas era `None`; `NaN` =
         una métrica puntual no computable con el resto del dict
         presente) y NO se conflacionan.
      3. Alguno de los dos es NaN -> coincide solo si AMBOS lo son (mismo
         criterio ya usado en 3/16 scripts legacy, caso real documentado).
      4. Intento de comparación numérica: `float(actual) == float(reference)`
         — normaliza `int`/`float`/`numpy.float64`/`bool` sin introducir
         ninguna tolerancia de valor (mismo precedente ya usado en este
         repositorio: `research/tests/test_runner_equivalence.py::
         _assert_equivalence_exacta`, "normaliza numpy scalar vs. valor
         nativo del CSV, NO introduce tolerancia").
      5. Si la conversión a `float` falla (ej. comparando strings como
         `asset`/`bias`), cae a igualdad directa (`==`).
    """
    if actual is None and reference is None:
        return True
    if actual is None or reference is None:
        return False

    a_nan, r_nan = _is_nan(actual), _is_nan(reference)
    if a_nan or r_nan:
        return a_nan and r_nan

    try:
        return float(actual) == float(reference)
    except (TypeError, ValueError):
        return actual == reference


def compare_results(
    actual: ExperimentResult,
    reference: ExperimentResult,
    fields: Sequence[str] | None = None,
) -> ComparisonResult:
    """Compara `actual` contra `reference`, campo a campo, sobre
    `fields` (o `DEFAULT_COMPARISON_FIELDS` si no se especifica).

    Pura: sin I/O, sin filesystem, sin `pandas`, determinista — mismos
    `actual`/`reference`/`fields` producen siempre el mismo
    `ComparisonResult`.

    Lanza `ValueError` si algún nombre en `fields` no es un campo real
    de `ExperimentResult` — ANTES de comparar nada (mismo principio ya
    aplicado a `rank_metric` en `research.decision.summarize_decision`,
    Componente 5): un typo en el nombre de campo debe fallar
    ruidosamente, no producir silenciosamente una comparación vacía o
    parcial.
    """
    fields_compared = DEFAULT_COMPARISON_FIELDS if fields is None else tuple(fields)

    invalid = [f for f in fields_compared if f not in _VALID_FIELDS]
    if invalid:
        raise ValueError(
            f"fields contiene nombres que no son campos de ExperimentResult: {invalid!r} "
            f"(campos válidos: {sorted(_VALID_FIELDS)})."
        )

    differences = []
    for field in fields_compared:
        a = getattr(actual, field)
        r = getattr(reference, field)
        if not _values_match(a, r):
            differences.append(FieldDifference(field=field, actual=a, reference=r))

    return ComparisonResult(
        matches=not differences, fields_compared=fields_compared,
        differences=tuple(differences),
    )
