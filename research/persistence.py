"""research/persistence.py — Automatización experimental, Componente 6
(Persistence / Artifacts, 2026-09-04).

Convierte `list[ExperimentResult]` (salida de `research.runner.run`/
`run_many`) y `list[CandidateDecision]` (salida de
`research.decision.summarize_decision`) en artifacts CSV canónicos,
reproducibles y trazables. Responsabilidad EXCLUSIVAMENTE de
representación — NO ejecuta experimentos, NO calcula métricas, NO aplica
gates, NO toma decisiones, NO compara contra baseline. Ningún threshold
científico, ningún año hardcodeado, ningún nombre de campaña vive acá.

Dos responsabilidades separadas, sin mezclar (diseño aprobado):
  - Transformación PURA: `to_experiment_rows`/`to_decision_rows` (dict por
    fila, sin I/O, sin filesystem, deterministas) y `render_experiment_csv`/
    `render_decision_csv` (texto CSV completo en memoria, también puras).
  - Writer delgado: `write_experiment_results_csv`/`write_decision_csv`
    (I/O — abren el archivo y escriben el texto ya renderizado, sin
    ninguna lógica de transformación propia).

ESQUEMA CANÓNICO — `results` (de `ExperimentResult`): SIN transformación
con pérdida. Cada uno de los 22 campos de `ExperimentResult` (identidad:
`experiment_name`; dimensiones: `asset`/`period`/`period_role`/`bias`/
`trigger`/`entry`/`session`/`management`; volumen: `n_entries`/`n_trades`;
métricas: `pf`/`wr`/`exp_r`/`total_r`/`max_dd`/`freq`; gate:
`gate_pass`; metadata de reproducibilidad: `contract_hash`/
`dataset_version`/`pipeline_version`/`engine_version`) se persiste tal
cual, en el orden de declaración del propio dataclass —
`dataclasses.fields(ExperimentResult)` es la ÚNICA fuente del orden de
columnas, nunca una lista paralela que pudiera desincronizarse si
`schema.py` gana un campo nuevo. Nada se descarta, nada se fabrica.

ESQUEMA CANÓNICO — `decision` (de `CandidateDecision`): decisión de
diseño explícita, DISTINTA de la de los CSV legacy (`*_decision.csv`,
ej. `gestion_campaign_session_decision.csv`, columnas `pf_2022`/
`pf_2023`/`gate_2022`/`gate_2023`) — legacy aplana los años/roles
requeridos en columnas fijas, lo cual re-introduciría exactamente el
hardcodeo de roles que Componente 5 eliminó deliberadamente
(`required_roles` es abierto, configurable por el llamador; un esquema
"wide" necesitaría enumerar roles por adelantado). En su lugar:
`per_role: dict[str, ExperimentResult]` NO se aplana acá — cada
`ExperimentResult` dentro de `per_role` es, en sí mismo, una fila
canónica de `results` (mismo esquema de arriba) — la trazabilidad
completa por rol vive en el artifact `results`, reutilizando el mismo
esquema sin duplicar ninguna columna ni ningún dato. El artifact
`decision` contiene, por candidato, SOLO lo que `CandidateDecision`
agrega por encima de `results`: `asset`, las columnas de identidad del
candidato (`candidate_fields`, el mismo parámetro que ya recibe
`research.decision.summarize_decision` — `CandidateDecision.candidate`
es una tupla SIN nombres, así que `candidate_fields` es indispensable
para etiquetar las columnas), `survives_required_roles`,
`rank_within_asset`. Deliberadamente SIN `period_role`, sin métricas, y
sin metadata de reproducibilidad (`experiment_name`/`contract_hash`/
`dataset_version`/`pipeline_version`/`engine_version`) — justificación
precisa, no solo "por conveniencia": un `CandidateDecision` abarca, por
diseño (C5), MÚLTIPLES roles simultáneamente (`per_role` es un dict de
varios `ExperimentResult`) — no existe UN `period_role` para toda la
fila, ni UNA métrica, ni UN `contract_hash` que representen al
candidato completo, cada rol tiene el suyo propio (potencialmente
distinto). Poner cualquiera de esos campos en `decision` obligaría a
fabricar un valor (¿cuál de los N roles gana la columna?) o a mentir
por omisión (mostrar solo uno como si fuera "el" valor) — ambas
prohibidas por el principio de "sin fabricación" ya vigente en todo el
proyecto. Esa información SÍ existe, íntegra, en `results` — vinculable
por `(asset, candidate_fields..., period_role)` DENTRO de la colección
coherente de una misma ejecución (ver "Trazabilidad" más abajo para el
alcance preciso de ese join — no es una clave global).

Diferencia respecto al formato legacy (documentada, no oculta):
  - Qué cambia: 1 archivo `decision.csv` con columnas por-año fijas
    (`pf_2022`, `gate_2023`, ...) -> 2 archivos (`results`+`decision`)
    donde `decision` no fija ningún año/rol y `results` ya trae toda la
    métrica por celda.
  - Por qué: `required_roles` de C5 es abierto — un esquema wide de
    `decision` no puede representarlo sin volver a hardcodear roles.
  - Qué se conserva: exactamente la misma información (supervivencia,
    ranking, métrica por rol) — recuperable por join, no perdida.
  - Qué deja de persistirse EN EL MISMO ARCHIVO: las métricas por rol
    embebidas en la fila de decisión (ahora viven en `results`, no en
    `decision` — ninguna métrica se pierde, cambia dónde vive).
  - Por qué es arquitectónicamente superior: no fija el vocabulario de
    roles en el esquema del artifact, igual que C5 no lo fija en el
    código; escala a cualquier `required_roles` sin cambiar el esquema.

CSV, no JSON: única decisión consistente con la evidencia real (26/30
scripts escriben CSV, cero JSON de persistencia real en todo el
repositorio) — JSON queda explícitamente fuera de alcance de este
componente, no introducido "porque es técnicamente posible".

Determinismo — PROPIEDAD GARANTIZADA, precisa (verificada, no asumida):
"mismos inputs EN EL MISMO ORDEN -> mismo output byte-a-byte". Columnas
deterministas (ver arriba); orden de FILAS = orden LITERAL de la lista
de entrada, SIN reordenar nunca (transparente — este módulo no impone
ningún criterio de orden propio, ni siquiera para "canonizar" una
colección); `None` -> celda vacía (nunca la cadena `"None"`); floats vía
`str()` de Python, SIN redondeo ni reformateo (incluye `"inf"` para
`pf=float('inf')`, sin normalizar); sin dependencia de `pandas` en el
núcleo; `newline=""` + UTF-8; header siempre presente; colección vacía
-> CSV válido con solo header, NO es un error.

Distinción importante, verificada explícitamente (no se asume "misma
colección lógica en cualquier orden -> mismo output" — ESO NO es
cierto para `results`):
  - Artifact `results`: el orden de filas es el de `list[ExperimentResult]`
    tal como llega — si dos llamadas construyen la MISMA colección
    lógica pero en distinto orden (ej. `run_many` con `contracts` en
    otro orden), el CSV resultante difiere byte a byte. Esto es
    DELIBERADO, no un defecto: `persistence.py` no debe imponer un
    orden propio sobre lo que `run_many` (C3) ya decidió preservar tal
    cual — hacerlo sería la misma clase de "reinterpretación" que C3
    explícitamente prohíbe (`run_many` no reinterpreta el resultado de
    `run()`; por el mismo principio, `persistence` no reinterpreta el
    orden de `run_many`). Introducir un sort global acá alteraría, sin
    justificación nueva, una invariante ya establecida y testeada en C3
    — no se hace.
  - Artifact `decision`: en la práctica, SÍ es insensible al orden de
    entrada de los `ExperimentResult` originales — pero esa propiedad
    la aporta `research.decision.summarize_decision` (C5), que YA
    normaliza su orden de salida independientemente del orden de
    entrada (verificado en C5:
    `test_determinismo_independiente_del_orden_de_entrada`) — no es
    algo que `persistence.py` calcule ni deba reclamar como propio; acá
    solo se preserva, sin alterar, el orden que `summarize_decision` ya
    entregó.

Trazabilidad `CandidateDecision -> ExperimentResult` — alcance preciso,
verificado (no asumido): `(asset, candidate_fields..., period_role)`
identifica sin ambigüedad a un `ExperimentResult` dentro de un
`per_role` de UN `CandidateDecision` — pero NO es una clave GLOBALMENTE
única a través de un artifact `results` arbitrario. Verificado
explícitamente: dos contratos DISTINTOS (`contract_hash` distinto,
`management` distinto) pueden compartir el mismo `(asset, trigger,
period_role)` si provienen de campañas/ejecuciones diferentes
concatenadas en el mismo artifact — el join por `candidate_fields` es
CONTEXTUAL a la colección coherente de UNA ejecución de
`summarize_decision` (donde el propio llamador ya eligió
`candidate_fields` lo bastante fino para discriminar sus candidatos,
mismo principio ya documentado en C5), no una clave universal. La
identidad GLOBALMENTE única de qué contrato produjo un `ExperimentResult`
sigue siendo `contract_hash` (columna ya presente en `results`, sin
cambios) — quien necesite un join robusto entre colecciones arbitrarias
debe usar `contract_hash`, no `(asset, candidate_fields, period_role)`.

`experiment_name` — verificado, sin cambiar su semántica: es una
etiqueta a nivel de CONTRATO (`experiment["name"]`), sin validación de
contenido ni de unicidad en `validate_contract` (confirmado en C2).
Además, `expand_universe` (C4) deliberadamente NO la varía entre
celdas — todas las celdas de una campaña generada vía `expand_universe`
comparten el MISMO `experiment_name`. Por lo tanto `experiment_name` NO
identifica una celda ni una ejecución específica, y deliberadamente NO
participa en ninguna clave de trazabilidad de este módulo.
"""
from __future__ import annotations

import csv
import io
from dataclasses import fields as dataclass_fields
from typing import Sequence

from .decision import CandidateDecision
from .schema import ExperimentResult

EXPERIMENT_RESULT_COLUMNS: tuple[str, ...] = tuple(f.name for f in dataclass_fields(ExperimentResult))
"""Orden canónico de columnas del artifact `results` — derivado de
`dataclasses.fields(ExperimentResult)`, nunca una lista paralela."""

_DECISION_FIXED_COLUMNS: tuple[str, ...] = ("survives_required_roles", "rank_within_asset")


def _decision_columns(candidate_fields: Sequence[str]) -> tuple[str, ...]:
    """Orden canónico de columnas del artifact `decision` para un
    `candidate_fields` dado: `asset`, luego cada campo de
    `candidate_fields` (en el orden dado), luego los 2 campos fijos de
    `CandidateDecision` que no son ni asset ni candidate."""
    return ("asset",) + tuple(candidate_fields) + _DECISION_FIXED_COLUMNS


# --------------------------------------------------------------------------- #
# Transformación PURA — sin I/O, sin filesystem.                            #
# --------------------------------------------------------------------------- #
def to_experiment_rows(results: Sequence[ExperimentResult]) -> list[dict]:
    """`list[ExperimentResult]` -> `list[dict]`, un dict por resultado,
    con EXACTAMENTE las claves de `EXPERIMENT_RESULT_COLUMNS` (mismo
    orden) — sin fabricar ni descartar ningún campo. Pura: no toca disco,
    no depende de ningún estado externo, determinista."""
    return [{col: getattr(r, col) for col in EXPERIMENT_RESULT_COLUMNS} for r in results]


def to_decision_rows(
    decisions: Sequence[CandidateDecision], *, candidate_fields: Sequence[str],
) -> list[dict]:
    """`list[CandidateDecision]` -> `list[dict]`, un dict por candidato,
    con las columnas de `_decision_columns(candidate_fields)`. `candidate_fields`
    debe ser EXACTAMENTE el mismo que se usó al llamar
    `research.decision.summarize_decision(...)` — `CandidateDecision.candidate`
    es una tupla posicional sin nombres, así que este parámetro es lo único
    que permite etiquetar sus columnas correctamente; no se infiere ni se
    adivina. Lanza `ValueError` si algún `candidate` no tiene exactamente
    `len(candidate_fields)` elementos (detecta un `candidate_fields`
    incorrecto ANTES de producir un CSV con columnas mal alineadas).

    Deliberadamente NO incluye ninguna métrica ni metadata de
    reproducibilidad — ver docstring del módulo. Pura: sin I/O."""
    candidate_fields = tuple(candidate_fields)
    rows = []
    for d in decisions:
        if len(d.candidate) != len(candidate_fields):
            raise ValueError(
                f"CandidateDecision.candidate={d.candidate!r} tiene "
                f"{len(d.candidate)} elementos, pero candidate_fields="
                f"{candidate_fields!r} declara {len(candidate_fields)} — "
                f"no coinciden, no se puede etiquetar la fila."
            )
        row = {"asset": d.asset}
        row.update(dict(zip(candidate_fields, d.candidate)))
        row["survives_required_roles"] = d.survives_required_roles
        row["rank_within_asset"] = d.rank_within_asset
        rows.append(row)
    return rows


def _render_csv(rows: list[dict], columns: Sequence[str]) -> str:
    """`list[dict]` + orden de columnas -> texto CSV completo, en
    memoria. Pura: no toca disco. `None` -> celda vacía; cualquier otro
    valor -> `str(valor)`, sin redondeo ni reformateo de floats. Header
    siempre presente, incluso con `rows` vacío."""
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow("" if row[c] is None else str(row[c]) for c in columns)
    return buf.getvalue()


def render_experiment_csv(results: Sequence[ExperimentResult]) -> str:
    """`list[ExperimentResult]` -> texto CSV completo del artifact
    `results`, en memoria. Pura."""
    return _render_csv(to_experiment_rows(results), EXPERIMENT_RESULT_COLUMNS)


def render_decision_csv(
    decisions: Sequence[CandidateDecision], *, candidate_fields: Sequence[str],
) -> str:
    """`list[CandidateDecision]` -> texto CSV completo del artifact
    `decision`, en memoria. Pura."""
    columns = _decision_columns(candidate_fields)
    return _render_csv(to_decision_rows(decisions, candidate_fields=candidate_fields), columns)


# --------------------------------------------------------------------------- #
# Writer — capa delgada de I/O. Sin ninguna lógica de transformación propia. #
# --------------------------------------------------------------------------- #
def write_experiment_results_csv(path: str, results: Sequence[ExperimentResult]) -> None:
    """Escribe el artifact `results` en `path`. Delgado: renderiza vía
    `render_experiment_csv` y escribe el texto tal cual — ninguna
    transformación ocurre acá."""
    text = render_experiment_csv(results)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def write_decision_csv(
    path: str, decisions: Sequence[CandidateDecision], *, candidate_fields: Sequence[str],
) -> None:
    """Escribe el artifact `decision` en `path`. Delgado: renderiza vía
    `render_decision_csv` y escribe el texto tal cual."""
    text = render_decision_csv(decisions, candidate_fields=candidate_fields)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
