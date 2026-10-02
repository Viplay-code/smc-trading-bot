"""Expansión declarativa y pura de especificaciones experimentales.

El módulo traduce una :class:`ExperimentSpec` a contratos concretos que
``research.runner.run_many`` puede ejecutar. No carga datos, no ejecuta el
motor, no calcula métricas, no aplica gates ni selecciona candidatos.

``years`` usa ``{period_role: year}`` en vez de una lista de años: el contrato
del runner exige conservar el rol ``train``/``validate``/``blind`` de cada
celda. Las dimensiones escalares admitidas son exactamente las que el runner
consume hoy: ``atr_mult``, ``atr_period``, ``max_hold``, ``risk`` y
``cost_per_trade``.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Mapping, Sequence

from .expand import expand_universe
from .metrics import EXP_R_MIN, FREQ_MAX_PER_MONTH, FREQ_MIN_PER_MONTH, MAX_DD_MIN, PF_MIN


class ExperimentSpecError(ValueError):
    """La especificación no puede producir contratos válidos y ejecutables."""


_SCALAR_PARAMETERS = (
    "atr_mult",
    "atr_period",
    "max_hold",
    "risk",
    "cost_per_trade",
)
@dataclass(frozen=True)
class ExperimentSpec:
    """Declaración de un espacio experimental compatible con el runner.

    Los valores de cada dimensión cualitativa conservan su orden literal.
    ``years`` es el único mapa: ``expand_universe`` ordena sus roles
    alfabéticamente, como ya hace para los universos de campañas existentes.
    ``parameters`` declara las cinco dimensiones escalares admitidas, usando
    listas de un valor para los anclajes que no se deseen barrer: el expansor
    no introduce defaults científicos propios.
    """

    name: str
    assets: Sequence[str]
    years: Mapping[str, int]
    bias: Sequence[str]
    triggers: Sequence[str]
    entries: Sequence[str]
    managements: Sequence[str]
    sessions: Sequence[str]
    parameters: Mapping[str, list]
    independent_variable: str
    contract_version: str = "1"
    blind_authorized: bool = False


def _canonical_gates() -> dict:
    """Valores declarativos requeridos por el contrato, sin evaluar gates."""
    return {
        "pf_min": PF_MIN,
        "max_dd_min": MAX_DD_MIN,
        "exp_r_min": EXP_R_MIN,
        "freq_min": FREQ_MIN_PER_MONTH,
        "freq_max": FREQ_MAX_PER_MONTH,
    }


def _require_nonempty_sequence(value, field_name: str) -> None:
    if not isinstance(value, (list, tuple)) or not value:
        raise ExperimentSpecError(
            f"ExperimentSpec.{field_name} debe ser una lista o tupla no vacía; recibido: {value!r}."
        )


def _require_unique_sequence(value, field_name: str) -> None:
    for index, item in enumerate(value):
        if any(item == earlier for earlier in value[:index]):
            raise ExperimentSpecError(
                f"ExperimentSpec.{field_name} no admite valores duplicados: {item!r}."
            )


def _validate_spec(spec: ExperimentSpec) -> None:
    if not isinstance(spec, ExperimentSpec):
        raise ExperimentSpecError(
            f"expand_experiment_spec requiere ExperimentSpec; recibido: {type(spec).__name__}."
        )
    if not isinstance(spec.name, str) or not spec.name:
        raise ExperimentSpecError("ExperimentSpec.name debe ser un string no vacío.")
    if not isinstance(spec.independent_variable, str) or not spec.independent_variable:
        raise ExperimentSpecError("ExperimentSpec.independent_variable debe ser un string no vacío.")
    if not isinstance(spec.contract_version, str) or not spec.contract_version:
        raise ExperimentSpecError("ExperimentSpec.contract_version debe ser un string no vacío.")
    if not isinstance(spec.blind_authorized, bool):
        raise ExperimentSpecError("ExperimentSpec.blind_authorized debe ser bool.")

    for field_name in (
        "assets", "bias", "triggers", "entries", "managements", "sessions",
    ):
        values = getattr(spec, field_name)
        _require_nonempty_sequence(values, field_name)
        _require_unique_sequence(values, field_name)

    if not isinstance(spec.years, Mapping) or not spec.years:
        raise ExperimentSpecError(
            "ExperimentSpec.years debe ser un mapa no vacío {rol: año}; una lista de años "
            "no puede preservar el period_role requerido por research.runner."
        )
    if not isinstance(spec.parameters, Mapping):
        raise ExperimentSpecError("ExperimentSpec.parameters debe ser un mapa de parámetros a listas.")
    missing_parameters = [name for name in _SCALAR_PARAMETERS if name not in spec.parameters]
    if missing_parameters:
        raise ExperimentSpecError(
            f"ExperimentSpec.parameters debe declarar los parámetros escalares {missing_parameters}. "
            "Usá una lista de un valor para un anclaje fijo."
        )
    for name in spec.parameters:
        if name not in _SCALAR_PARAMETERS:
            raise ExperimentSpecError(
                f"ExperimentSpec.parameters no admite {name!r}; admitidos: {_SCALAR_PARAMETERS}."
            )
    for name in _SCALAR_PARAMETERS:
        values = spec.parameters[name]
        if not isinstance(values, list) or not values:
            raise ExperimentSpecError(
                f"ExperimentSpec.parameters[{name!r}] debe ser una lista no vacía."
            )


def _base_contract(spec: ExperimentSpec, *, bias: str, trigger: str, entry: str,
                   management: str, session: str, scalar_values: dict) -> dict:
    return {
        "name": spec.name,
        "contract_version": spec.contract_version,
        "assets": list(spec.assets),
        "years": dict(spec.years),
        "bias": {"name": bias, "params": {}},
        "trigger": {"name": trigger, "params": {}},
        "entry": {"name": entry, "params": {}},
        "session": session,
        "management": {"name": management, "params": {}},
        **scalar_values,
        "gates": _canonical_gates(),
        "independent_variable": spec.independent_variable,
        "blind_authorized": spec.blind_authorized,
    }


def _validate_parameter_grid(spec: ExperimentSpec) -> None:
    """Reutiliza la validación de grid existente antes de expandir valores."""
    if not spec.parameters:
        return

    # Import local: research.runner importa research; mantenerlo fuera del
    # import de módulo evita introducir un ciclo al exponer esta API pública.
    from . import runner

    scalar_values = {name: spec.parameters[name][0] for name in _SCALAR_PARAMETERS}
    prototype = _base_contract(
        spec,
        bias=spec.bias[0], trigger=spec.triggers[0], entry=spec.entries[0],
        management=spec.managements[0], session=spec.sessions[0], scalar_values=scalar_values,
    )
    grid = {name: spec.parameters[name] for name in _SCALAR_PARAMETERS}
    prototype["parameter_grid"] = grid
    try:
        runner._validate_parameter_grid(grid, prototype)
    except runner.ContractError as exc:
        raise ExperimentSpecError(f"ExperimentSpec.parameters inválido: {exc}") from exc


def expand_experiment_spec(spec: ExperimentSpec) -> list[dict]:
    """Valida y expande ``spec`` en contratos concretos y válidos.

    El orden es estable: bias, trigger, entry, management, session,
    parámetros en el orden fijo de ``_SCALAR_PARAMETERS`` y, dentro de cada
    template, assets y roles de years según ``expand_universe``. Los contratos
    no contienen ``parameter_grid``: cada uno lleva ya los valores escalares
    concretos que ejecuta el runner.
    """
    _validate_spec(spec)
    _validate_parameter_grid(spec)

    scalar_dimensions = [spec.parameters[name] for name in _SCALAR_PARAMETERS]
    contracts: list[dict] = []

    # Import local por la misma razón que en _validate_parameter_grid.
    from . import runner

    for bias, trigger, entry, management, session in product(
        spec.bias, spec.triggers, spec.entries, spec.managements, spec.sessions,
    ):
        for values in product(*scalar_dimensions):
            scalar_values = dict(zip(_SCALAR_PARAMETERS, values))
            template = _base_contract(
                spec, bias=bias, trigger=trigger, entry=entry,
                management=management, session=session, scalar_values=scalar_values,
            )
            try:
                expanded_universe = expand_universe(template)
            except ValueError as exc:
                raise ExperimentSpecError(f"ExperimentSpec no respeta el límite de universo: {exc}") from exc
            for contract in expanded_universe:
                try:
                    runner.validate_contract(contract)
                except runner.ContractError as exc:
                    raise ExperimentSpecError(
                        f"ExperimentSpec produjo un contrato inválido: {exc}"
                    ) from exc
                contracts.append(contract)
    return contracts
