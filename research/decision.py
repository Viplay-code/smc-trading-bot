"""research/decision.py — Automatización experimental, Componente 5
(capa de Decisión, 2026-09-04).

Extrae la capacidad reusable de `scripts/bias_campaign.py::summarize_decision`
(única implementación real del programa, reutilizada por alias en 25/30
scripts de campaña) a `research/`, generalizándola: elimina los hardcodes
de año (`IN_SAMPLE_YEAR=2022`/`VALIDATION_YEAR=2023`) y la noción implícita
de `"candidate"` (que significa una cosa distinta en cada script — nombre
de Trigger, ventana de sesión, etiqueta compuesta de parámetros de
Gestión...), y opera directamente sobre `list[ExperimentResult]` (el
formato de salida ya producido por `research.runner.run_many`), no sobre
un `DataFrame` con columnas específicas de un script.

Capa de decisión PURA — sin I/O, sin lectura/escritura de CSV, sin
ejecución de experimentos, sin conocimiento de ningún script concreto, sin
ningún año hardcodeado, sin ninguna noción fija de qué constituye "un
candidato". NO reimplementa ningún gate ni métrica — consume directamente
`ExperimentResult.gate_pass` (ya calculado por `research.gate_check` dentro
de `run()`) y el campo numérico que el llamador elija para rankear (por
defecto `"pf"`, igual que legacy). Ningún umbral científico (PF/DD/
expectancy/frecuencia) se toca ni se reimplementa acá.

Semántica preservada de `summarize_decision` legacy:
  - Un candidato "sobrevive" si TODOS los roles requeridos están presentes
    Y su `gate_pass` es `True` — un rol faltante no se descarta en
    silencio, se reporta como "no sobrevive" explícitamente (igual que
    legacy: "combinaciones a las que les falta alguno de los dos años se
    reportan como no evaluables, no se descartan en silencio").
  - El ranking es SIEMPRE dentro de cada `asset` — nunca compara ni
    promedia entre activos (invariante explícita de legacy, preservada sin
    excepción, no configurable).
  - Los sobrevivientes se rankean de forma descendente por el campo
    numérico elegido (`rank_metric`, default `"pf"`) del resultado en el
    rol de ranking (`rank_by_role`) — igual que legacy rankeaba por
    `pf_2023` (el año de validación).
  - Los candidatos que no sobreviven se reportan igual (con
    `rank_within_asset=None`), nunca se eliminan del resultado.

Generalización deliberada respecto a legacy (documentada, no oculta — ver
`research/tests/test_decision_equivalence.py` para el análisis completo de
diferencias): legacy identificaba los dos años requeridos por su valor
LITERAL (2022/2023, columna `year` de un DataFrame ad-hoc); acá se usa
`ExperimentResult.period_role` (`"train"`/`"validate"`/`"blind"`, ya un
campo del esquema canónico) en vez del año calendario — necesario para no
hardcodear ningún año concreto (instrucción explícita de este componente).
Sobre el mismo dataset real ya publicado, con el mapeo directo
año→rol (2022→"train", 2023→"validate"), el comportamiento es
IDÉNTICO — verificado por test de equivalencia exacta, no asumido.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .schema import ExperimentResult


@dataclass(frozen=True)
class CandidateDecision:
    """Decisión para UN candidato dentro de UN activo.

    `candidate`: tupla de valores (en el orden de `candidate_fields` pasado
    a `summarize_decision`) que identifica a este candidato — ej.
    `("T1_ema_cross",)` si `candidate_fields=("trigger",)`.

    `per_role`: TODOS los roles observados para este candidato en `results`
    (no solo los requeridos) — informativo, nunca fabricado: un rol
    ausente de `results` para este candidato simplemente no aparece acá,
    no se rellena con `None` ni con ningún valor centinela.

    `survives_required_roles`: `True` solo si CADA rol de `required_roles`
    está presente en `per_role` Y su `ExperimentResult.gate_pass` es
    `True`.

    `rank_within_asset`: entero 1-indexado entre los sobrevivientes DEL
    MISMO `asset`, ordenado descendente por `rank_metric` en
    `rank_by_role`; `None` si no sobrevive, o si sobrevive pero no tiene
    un resultado válido en `rank_by_role` para ese `rank_metric`.
    """
    asset: str
    candidate: tuple
    per_role: dict[str, ExperimentResult]
    survives_required_roles: bool
    rank_within_asset: int | None


def summarize_decision(
    results: Sequence[ExperimentResult],
    *,
    candidate_fields: Sequence[str],
    required_roles: Sequence[str],
    rank_by_role: str,
    rank_metric: str = "pf",
) -> list[CandidateDecision]:
    """Agrupa `results` por `(asset, *candidate_fields)`, evalúa
    supervivencia sobre `required_roles`, y rankea los sobrevivientes
    dentro de cada `asset` por `rank_metric` (descendente) en
    `rank_by_role`. Determinista: mismo `results` (en cualquier orden de
    entrada) produce siempre la misma lista de salida, en el mismo orden.

    Orden de salida: por `asset` (ascendente), y dentro de cada activo,
    sobrevivientes primero (ordenados por `rank_within_asset` ascendente),
    luego no-sobrevivientes (ordenados por `candidate` ascendente como
    desempate determinista) — mismo orden que produce el
    `.sort_values(["asset","survives_both_years","rank_within_asset"],
    ascending=[True, False, True])` de la versión legacy.

    `results` vacío -> `[]`, sin excepción.

    Si dos resultados en `results` comparten el mismo `(asset,
    candidate_fields, period_role)`, el ÚLTIMO de la lista de entrada
    prevalece para ese rol (comportamiento simple y documentado, no una
    validación de duplicados — la generación de duplicados reales
    correspondería a un error de quien construye `results`, fuera del
    alcance de esta función pura).

    `required_roles` no puede ser vacío: `all(... for role in ())` es
    verdadero vacuamente, lo que marcaría a TODO candidato como
    sobreviviente sin haber evaluado ningún gate — mismo principio de
    "no-op silencioso prohibido" ya aplicado en el resto de `research/`
    (ej. `parameter_grid`/`assets`/`years` vacíos).

    `rank_metric` debe ser un campo real de `ExperimentResult` — un typo
    en el nombre (ej. `"fp"` en vez de `"pf"`) produciría, sin esta
    validación, un `getattr(..., default=None)` silencioso: NINGÚN
    candidato entraría al ranking y `rank_within_asset` quedaría `None`
    para todos, indistinguible de "nadie sobrevivió" — se valida acá para
    que un nombre de campo inválido falle ruidosamente, distinto del caso
    legítimo de que el VALOR de ese campo sea `None` para un candidato en
    particular (ej. `pf=None` por muestra insuficiente), que sigue
    tratándose como "sin valor rankeable para ESE candidato", no como
    error.
    """
    candidate_fields = tuple(candidate_fields)
    required_roles = tuple(required_roles)

    if not required_roles:
        raise ValueError(
            "required_roles no puede estar vacío — sin ningún rol requerido, "
            "todo candidato 'sobreviviría' vacuamente sin haber evaluado ningún gate."
        )
    if rank_metric not in ExperimentResult.__dataclass_fields__:
        raise ValueError(
            f"rank_metric={rank_metric!r} no es un campo de ExperimentResult "
            f"(campos válidos: {sorted(ExperimentResult.__dataclass_fields__)})."
        )

    # (asset, candidate_tuple) -> {role: ExperimentResult}, preservando el
    # primer orden de aparición para no depender de ningún orden de hash.
    groups: dict[tuple, dict[str, ExperimentResult]] = {}
    order: list[tuple] = []
    for r in results:
        candidate_tuple = tuple(getattr(r, f) for f in candidate_fields)
        key = (r.asset, candidate_tuple)
        if key not in groups:
            groups[key] = {}
            order.append(key)
        groups[key][r.period_role] = r

    by_asset: dict[str, list[tuple]] = {}
    for key in order:
        asset, candidate_tuple = key
        per_role = groups[key]
        survives = all(
            role in per_role and bool(per_role[role].gate_pass)
            for role in required_roles
        )
        by_asset.setdefault(asset, []).append((candidate_tuple, per_role, survives))

    out: list[CandidateDecision] = []
    for asset in sorted(by_asset.keys()):
        entries = by_asset[asset]

        rankable = [
            (candidate_tuple, per_role)
            for candidate_tuple, per_role, survives in entries
            if survives
            and rank_by_role in per_role
            and getattr(per_role[rank_by_role], rank_metric, None) is not None
        ]
        rankable.sort(
            key=lambda e: (-getattr(e[1][rank_by_role], rank_metric), e[0])
        )
        rank_map = {cand: i + 1 for i, (cand, _) in enumerate(rankable)}

        def _sort_key(entry, _rank_map=rank_map):
            candidate_tuple, _per_role, survives = entry
            rank = _rank_map.get(candidate_tuple)
            return (0 if survives else 1, rank if rank is not None else 0, candidate_tuple)

        for candidate_tuple, per_role, survives in sorted(entries, key=_sort_key):
            out.append(CandidateDecision(
                asset=asset, candidate=candidate_tuple, per_role=dict(per_role),
                survives_required_roles=survives,
                rank_within_asset=rank_map.get(candidate_tuple),
            ))
    return out
