"""research/expand.py — Automatización experimental, Componente 4
(expansión del universo experimental, 2026-09-04).

Cuello de botella identificado por auditoría de código (no por intuición,
ver diseño aprobado): el patrón `for year in (...): for asset in ASSETS:`
está presente en el 100% de los scripts de campaña de `scripts/`, sin
excepción — es la dimensión de duplicación más extendida del repositorio,
más que cualquier barrido de parámetros. `research.runner.run_many`
(Componente 3) ya puede ejecutar una lista de contratos, pero construir
esa lista sigue siendo enteramente manual.

`parameter_grid` (Componente 2) NO puede cubrir esta dimensión — no es
una cuestión de alcance, es un desajuste estructural: `assets` es una
`list[str]` y `years` es un `dict[str,int]`, ninguno de los dos es un
escalar JSON, y `_resolve_grid_path` de `research/runner.py` exige que
toda ruta de grid resuelva a un escalar. `expand_universe` es, por
diseño, un mecanismo SEPARADO de `parameter_grid` — no una generalización
de él.

`expand_universe(template) -> list[dict]` expande ÚNICAMENTE `assets` y
`years` en su producto cartesiano — ninguna otra responsabilidad. NO
genera ni modifica nombres (`name` se copia verbatim, igual que todo
campo distinto de `assets`/`years` — decisión revisada explícitamente:
`name` no participa en `compute_contract_hash`/`validate_contract`/
ninguna lógica de identidad, verificado en código antes de decidir esto,
así que modificarlo no es necesario). NO calcula ningún hash — cada
contrato generado obtiene su propio `contract_hash` naturalmente al
pasar por `run()`, porque `assets`/`years` (que sí difieren por celda)
ya bastan para que `compute_contract_hash` produzca valores distintos.
NO ejecuta `run()`, NO hace I/O — función pura (a diferencia de
`run_many`, que sí es un orquestador con efectos reales vía `run()`):
mismo `template` -> misma lista de salida, siempre, sin efectos
colaterales.

SEMÁNTICA DE `years` — celdas independientes, NO fases (Opción A del
diseño aprobado, verificada contra el código real de
`research/runner.py`: `validate_contract`/`run()` no contienen ninguna
lógica que secuencie o relacione una celda "train" con "validate"/
"blind" — cada llamada a `run()` es una ejecución aislada. La disciplina
train→validate→blind es hoy exclusivamente un guardrail MANUAL de los
scripts legacy, ej. `trigger_campaign.py::run_blind_test`, que exige un
`--candidate` ya congelado antes de aceptar correr el año ciego — nada
equivalente existe en `research/`). Por lo tanto: `expand_universe` NO
representa ni orquesta ninguna secuencia de fases. Si `template["years"]`
incluye el rol `"blind"`, se expande como cualquier otro rol, sin ningún
tratamiento especial — el único guardrail que sigue aplicando es
`blind_authorized`, ya validado por `validate_contract` contrato a
contrato, SIN reforzar ni tocar acá. Esto es una limitación conocida y
documentada, no resuelta en este componente (resolverla sería introducir
lógica de fases, explícitamente prohibido para este componente).

`MAX_UNIVERSE_CELLS` es una constante DELIBERADAMENTE separada de
`research.runner.MAX_GRID_CELLS` — no una reutilización. `MAX_GRID_CELLS`
protege contra un riesgo distinto (comparaciones múltiples/fishing de
parámetros no-identidad, calibrado contra el mayor grid real corrido en
el programa, 36 combinaciones). La expansión de `assets`/`years` no es un
barrido de candidatos científicos — es la cobertura del universo estándar
que `FRAMEWORK.md` ya exige evaluar, acotado naturalmente por el tamaño
real y pequeño del programa (`market_data.ASSETS` tiene 3 activos; hasta
3 roles por campaña). El riesgo real acá es un error de datos (un
`years` con decenas de entradas por accidente), no una campaña
científicamente injustificada — por eso el valor y el nombre son
distintos.

Import LOCAL A LA FUNCIÓN (no a nivel de módulo) evitado a propósito:
este módulo NO importa `research.runner` en absoluto — ni siquiera
localmente. `research/runner.py` hace `import research` a nivel de
módulo; si `research/expand.py` importara algo de `research.runner` Y
`research/__init__.py` expusiera `expand_universe`, se introduciría el
mismo tipo de riesgo de import circular ya identificado y evitado en
Fase 4/C2 (`research/simulate.py`). Por eso los errores acá son
`ValueError` simple, no `research.runner.ContractError` — este módulo es
deliberadamente autónomo, sin ninguna dependencia de la capa de
ejecución.
"""
from __future__ import annotations

import copy


MAX_UNIVERSE_CELLS = 12
"""Tope de cardinalidad (`len(assets) * len(years)`) para
`expand_universe`. Ver docstring del módulo para la justificación
completa de por qué es una constante separada de
`research.runner.MAX_GRID_CELLS` y por qué vale 12 (universo real actual:
3 activos x hasta 3 roles = 9, con un margen modesto de sanidad de
datos, no un límite anti-fishing)."""


def expand_universe(template: dict) -> list[dict]:
    """Expande `template["assets"]` x `template["years"]` en su producto
    cartesiano, produciendo un contrato completo e independiente por
    combinación — `len(assets) * len(years)` contratos en total.

    Orden determinista: `assets` en el orden LITERAL de la lista
    declarada (no se reordena); `years` recorrido ORDENADO
    ALFABÉTICAMENTE por nombre de rol (no por orden de inserción del
    dict) — mismo principio ya usado para las claves de
    `research.runner`'s `parameter_grid`.

    Cada contrato generado es una copia PROFUNDA e INDEPENDIENTE de
    `template` (nunca comparten ningún objeto anidado mutable entre sí
    ni con `template`), con SOLO `assets`=`[un_activo]` y
    `years`={rol: año} (una sola entrada) sobrescritos — todo lo demás,
    INCLUIDO `name`, se copia verbatim, sin ninguna transformación.
    `template` en sí NUNCA se modifica.

    No genera nombres, no calcula ningún hash, no ejecuta `run()`, no
    hace I/O, no interpreta `hypothesis`/`space`/`baseline`/
    `parameter_grid`/`gates` ni ninguna otra parte del contrato más allá
    de leer `assets`/`years` para expandirlos.

    Lanza `ValueError` (no `research.runner.ContractError` — ver
    docstring del módulo) si `assets`/`years` están ausentes o vacíos, o
    si la cardinalidad resultante supera `MAX_UNIVERSE_CELLS` — en
    cualquiera de los tres casos, ANTES de generar ningún contrato.
    """
    if "assets" not in template or not template["assets"]:
        raise ValueError(
            f"expand_universe requiere 'assets' no vacío en el template — "
            f"recibido: {template.get('assets')!r}."
        )
    if "years" not in template or not template["years"]:
        raise ValueError(
            f"expand_universe requiere 'years' no vacío en el template — "
            f"recibido: {template.get('years')!r}."
        )

    assets = template["assets"]
    years = template["years"]

    cardinality = len(assets) * len(years)
    if cardinality > MAX_UNIVERSE_CELLS:
        raise ValueError(
            f"expand_universe produce {cardinality} combinaciones "
            f"(len(assets)={len(assets)} x len(years)={len(years)}), supera "
            f"MAX_UNIVERSE_CELLS={MAX_UNIVERSE_CELLS} — reducí assets/years o "
            f"justificá explícitamente un tope mayor antes de declarar un "
            f"universo de este tamaño."
        )

    contracts: list[dict] = []
    for asset in assets:
        for role in sorted(years.keys()):
            contract = copy.deepcopy(template)
            contract["assets"] = [asset]
            contract["years"] = {role: years[role]}
            contracts.append(contract)
    return contracts
