"""research/runner.py — Fase 2 (MVP controlado, 2026-09-02): primera
versión funcional de `research.runner`, sobre la infraestructura
consolidada en Fase 1 (`research.gate_check`, `research.ExperimentResult`,
`research.compute_contract_hash`).

OBJETIVO DE ESTA FASE (alcance autorizado, no ampliar sin autorización
explícita nueva): demostrar que la orquestación duplicada de una campaña
legacy (`scripts/gestion_campaign_session.py`, celda V3-A/`dcv1_activo_15h`)
puede reemplazarse por un runner determinista, SIN cambiar el
comportamiento científico ni el motor de simulación. Ver el test de
equivalencia exacta en
`research/tests/test_runner_equivalence.py`.

Soportado en este MVP, y SOLO esto:
  - 1 activo, 1 (año, rol) por llamada a `run()` — sin barrido, sin
    orquestación train/validate/blind (`years` del contrato se preserva
    como dict de rol->año para no romper la API futura, pero debe traer
    EXACTAMENTE una entrada en esta fase).
  - Bias "A_ema200_neutral", Trigger "T1_ema_cross", Entry "C_market_close"
    — la única combinación que `backtest.find_entries` ya implementa sin
    adaptador nuevo (ver nota de deuda técnica más abajo).
  - Gestión "V3-A" únicamente, vía `MANAGEMENT_LAYERS["V3-A"]` — delega a
    `backtest.run_config` (orquestación) + `research.simulate_v3`/
    `research.EXIT_CONFIGS` (motor de simulación, ubicación CANÓNICA
    desde Fase 4/C2 — `research/simulate.py`) SIN MODIFICARLOS ni
    reimplementarlos (verificado por test de inspección de código).
  - Gates: SOLO los canónicos de `research.gate_check` — el contrato debe
    declararlos explícitamente y deben coincidir EXACTO con los umbrales
    oficiales; el runner nunca acepta un gate distinto ("no modificar
    silenciosamente los gates", Parte 3 del diseño de Fase 0).

NO soportado todavía (fuera de alcance de esta fase, explícitamente):
  - Múltiples mecanismos de Gestión, múltiples activos/años por corrida,
    orquestación train->validate->blind, selección de "ganador",
    optimización de parámetros, generación de hipótesis, cualquier
    interfaz autónoma.
  - Ningún campo `is_winner` ni lógica de interpretación científica en
    ningún punto de este módulo.

DEUDA TÉCNICA RESUELTA EN FASE 3 (2026-09-02): la dependencia
`research -> scripts` identificada en Fase 2 (`_load_dataset` importaba
`scripts.trigger_campaign.load_asset_year`) fue eliminada — la carga de
datos ahora usa `research.data.load_asset_year`
(`research/data.py`, expuesta desde `research/__init__.py`), una
implementación NUEVA y AISLADA (no una copia de la de `scripts/`),
verificada equivalente por test
(`research/tests/test_data_equivalence.py`) contra
`scripts.trigger_campaign.load_asset_year` — no se asume la
equivalencia, se demuestra. `research/runner.py` ya NO importa ningún
módulo bajo `scripts/` (verificado por test de inspección de código).

DEUDA TÉCNICA RESUELTA EN FASE 4/C2 (2026-09-02): `simulate_v3`/
`EXIT_CONFIGS` (el motor de simulación en sí) MOVIDOS a
`research/simulate.py` — ubicación canónica, sin cambiar una línea de su
lógica (equivalencia exacta demostrada contra las 6/6 celdas de
`gestion_campaign_session_results.csv`, ver `research/tests/
test_runner_equivalence.py` y `research/tests/test_simulate_extraction.py`).
`backtest.run_config` NO se movió (permanece en `backtest.py`, ver
docstring de `research/simulate.py` para el motivo exacto: resuelve
`simulate_v3` como nombre libre en su propio módulo, y moverla rompería
los tests que monkeypatchean `backtest.simulate_v3`). `backtest.
COST_PER_TRADE` tampoco se movió, por el mismo tipo de razón (preservar
los monkeypatches ya committeados) — `research.simulate_v3` lo sigue
leyendo desde `backtest.py` vía un import LOCAL A LA FUNCIÓN (no a nivel
de módulo, para evitar una dependencia circular real, verificada por
trazado manual antes de implementar esta fase).

DEUDA TÉCNICA QUE PERMANECE (fuera de alcance de Fase 4, NO resuelta acá):
  - `backtest.find_entries` está hardcodeado a T1_ema_cross+C_market_close
    — no se generalizó (explícitamente fuera de alcance). El runner
    valida el nombre de Trigger/Entry declarado en el contrato contra esa
    combinación fija y rechaza cualquier otra, en vez de silenciosamente
    ignorar el contrato.
  - `research/runner.py` sigue importando `backtest` (para `Config`,
    `find_entries`, `run_config`, `metrics`) — solo la dependencia
    `research -> scripts` se eliminó (Fase 3); `research -> backtest.py`
    permanece, deliberadamente, porque `backtest.py` no es `scripts/` (es
    el motor compartido, en migración progresiva hacia `research/`, no
    una campaña legacy) y porque `find_entries`/`run_config` no se
    tocaron en esta fase (fuera de alcance explícito).
  - El costo (`backtest.COST_PER_TRADE`) sigue siendo una constante global
    de módulo, no un parámetro de función — el runner la parchea
    TEMPORALMENTE (mismo patrón ya usado y testeado en el diagnóstico de
    costo=0 de Espacio 6), restaurada siempre en `finally`.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

import backtest
import research
from research.schema import ExperimentResult, compute_contract_hash


class ContractError(ValueError):
    """Contrato experimental inválido o fuera del alcance soportado por
    esta fase del runner — nunca se ejecuta nada ante este error."""


# --------------------------------------------------------------------------- #
# Registros del MVP — deliberadamente de una sola entrada cada uno.          #
# Ampliar estos registros es exactamente el trabajo de las fases             #
# siguientes, no de esta.                                                    #
# --------------------------------------------------------------------------- #
_MVP_SUPPORTED_BIAS = {"A_ema200_neutral"}
_MVP_SUPPORTED_TRIGGER = {"T1_ema_cross"}
_MVP_SUPPORTED_ENTRY = {"C_market_close"}

SESSION_WINDOWS = {
    "control_8h": [(7, 11), (13, 17)],
    "dcv1_activo_15h": [(7, 22)],
    "sin_filtro_24h": [(0, 24)],
}


def _run_v3a(frame, entries: list[dict], cfg: "backtest.Config", cost_per_trade: float):
    """Delega a `backtest.run_config` (orquestación 'una posición a la
    vez', SIN modificar — permanece en backtest.py, ver research/
    simulate.py::__doc__ sobre por qué) + `research.EXIT_CONFIGS` (la
    ubicación CANÓNICA de la config V3-A desde Fase 4/C2 — `backtest.
    EXIT_CONFIGS` es el mismo objeto re-exportado, pero acá se referencia
    la fuente canónica explícitamente). `backtest.COST_PER_TRADE` se
    parchea temporalmente (try/finally, restaurado siempre) porque
    `research.simulate_v3` lo sigue leyendo desde `backtest.py` (única
    fuente autoritativa, deliberadamente no movida — ver research/
    simulate.py) como constante de módulo, no como parámetro."""
    orig_cost = backtest.COST_PER_TRADE
    backtest.COST_PER_TRADE = cost_per_trade
    try:
        return backtest.run_config(frame, entries, research.EXIT_CONFIGS["V3-A (1R/2R/1R)"], cfg)
    finally:
        backtest.COST_PER_TRADE = orig_cost


MANAGEMENT_LAYERS = {
    "V3-A": _run_v3a,
}

# Parámetros de research.EXIT_CONFIGS["V3-A (1R/2R/1R)"] (ubicación
# canónica, Fase 4/C2) — si el contrato declara management.params, DEBE
# coincidir exacto con esto (no se acepta una variante paramétrica en
# este MVP; eso es "crear un mecanismo nuevo de Gestión", explícitamente
# fuera de alcance).
_V3A_PARAMS = dict(research.EXIT_CONFIGS["V3-A (1R/2R/1R)"])


# --------------------------------------------------------------------------- #
# 1. Validación del contrato                                                  #
# --------------------------------------------------------------------------- #
def validate_contract(experiment: dict) -> None:
    """Valida ÚNICAMENTE lo necesario para este MVP — no es un validador
    de esquema general. Lanza ContractError con un mensaje específico ante
    cualquier incumplimiento; nunca corrige ni completa un contrato
    incompleto en silencio."""
    required_top_level = (
        "name", "assets", "years", "bias", "trigger", "entry", "session",
        "management", "risk", "cost_per_trade", "max_hold", "atr_mult",
        "gates", "independent_variable",
    )
    missing = [k for k in required_top_level if k not in experiment]
    if missing:
        raise ContractError(f"Contrato incompleto — faltan campos obligatorios: {missing}")

    if not isinstance(experiment.get("independent_variable"), str) or not experiment["independent_variable"]:
        raise ContractError(
            "independent_variable debe declararse explícitamente (string no vacío) — "
            "no se ejecuta ningún contrato sin declarar qué variable está bajo prueba."
        )

    assets = experiment["assets"]
    if not isinstance(assets, list) or len(assets) != 1:
        raise ContractError(
            f"Este MVP (Fase 2) soporta exactamente 1 activo por contrato — "
            f"recibido: {assets!r}. Múltiples activos por corrida quedan para una fase posterior."
        )

    years = experiment["years"]
    if not isinstance(years, dict) or len(years) != 1:
        raise ContractError(
            f"Este MVP (Fase 2) soporta exactamente 1 (rol, año) por contrato — "
            f"recibido: {years!r}. Orquestación train/validate/blind queda para una fase posterior."
        )
    (period_role, period_year), = years.items()
    if period_role not in ("train", "validate", "blind"):
        raise ContractError(f"period_role desconocido: {period_role!r} (esperado 'train'/'validate'/'blind')")
    if period_role == "blind" and not experiment.get("blind_authorized", False):
        raise ContractError(
            f"years declara rol 'blind' (año {period_year}) pero blind_authorized no es True — "
            f"2024/ciego no se ejecuta sin autorización explícita en el propio contrato."
        )

    gates = experiment["gates"]
    expected_gates = {
        "pf_min": research.PF_MIN, "max_dd_min": research.MAX_DD_MIN,
        "exp_r_min": research.EXP_R_MIN, "freq_min": research.FREQ_MIN_PER_MONTH,
        "freq_max": research.FREQ_MAX_PER_MONTH,
    }
    if not isinstance(gates, dict) or gates != expected_gates:
        raise ContractError(
            f"gates debe declararse EXACTO igual a los umbrales canónicos de "
            f"research.gate_check ({expected_gates}) — recibido: {gates!r}. El runner nunca "
            f"acepta un gate distinto del oficial ni lo completa/ajusta en silencio."
        )

    if experiment["bias"].get("name") not in _MVP_SUPPORTED_BIAS:
        raise ContractError(
            f"bias.name={experiment['bias'].get('name')!r} no soportado en este MVP "
            f"(solo {_MVP_SUPPORTED_BIAS})."
        )
    if experiment["bias"].get("name") not in research.BIAS_LAYERS:
        raise ContractError(f"bias.name={experiment['bias'].get('name')!r} no existe en research.BIAS_LAYERS.")

    if experiment["trigger"].get("name") not in _MVP_SUPPORTED_TRIGGER:
        raise ContractError(
            f"trigger.name={experiment['trigger'].get('name')!r} no soportado en este MVP "
            f"(solo {_MVP_SUPPORTED_TRIGGER} — backtest.find_entries está hardcodeado a esta "
            f"combinación, ver nota de deuda técnica en el docstring del módulo)."
        )
    if experiment["trigger"].get("name") not in research.TRIGGER_LAYERS:
        raise ContractError(f"trigger.name={experiment['trigger'].get('name')!r} no existe en research.TRIGGER_LAYERS.")

    if experiment["entry"].get("name") not in _MVP_SUPPORTED_ENTRY:
        raise ContractError(
            f"entry.name={experiment['entry'].get('name')!r} no soportado en este MVP "
            f"(solo {_MVP_SUPPORTED_ENTRY})."
        )
    if experiment["entry"].get("name") not in research.ENTRY_LAYERS:
        raise ContractError(f"entry.name={experiment['entry'].get('name')!r} no existe en research.ENTRY_LAYERS.")

    if experiment["session"] not in SESSION_WINDOWS:
        raise ContractError(f"session={experiment['session']!r} no reconocida (esperado una de {list(SESSION_WINDOWS)}).")

    mgmt_name = experiment["management"].get("name")
    if mgmt_name not in MANAGEMENT_LAYERS:
        raise ContractError(
            f"management.name={mgmt_name!r} no soportado en este MVP "
            f"(solo {list(MANAGEMENT_LAYERS)} — crear un mecanismo nuevo está fuera de alcance de esta fase)."
        )
    mgmt_params = experiment["management"].get("params")
    if mgmt_params and dict(mgmt_params) != _V3A_PARAMS:
        raise ContractError(
            f"management.params debe coincidir exacto con V3-A ({_V3A_PARAMS}) o ausente — "
            f"recibido: {mgmt_params!r}. Variantes paramétricas de Gestión están fuera de "
            f"alcance de este MVP (eso es 'crear un mecanismo nuevo de Gestión')."
        )


# --------------------------------------------------------------------------- #
# 2-9. Orquestación                                                           #
# --------------------------------------------------------------------------- #
def _load_dataset(asset: str, year: int):
    """Reutiliza research.data.load_asset_year (pipeline market_data ->
    dc_v1 -> periods, más aplicación de Bias 'A' ya resuelta) SIN
    reimplementar la construcción del dataset y SIN importar scripts/
    (Fase 3, ver docstring del módulo)."""
    return research.load_asset_year(asset, year)


def run(experiment: dict) -> ExperimentResult:
    """Punto de entrada único del MVP. Flujo determinista y fijo:

        validate_contract
        -> resolver componentes (ya validados por nombre)
        -> cargar dataset (activo, año)
        -> aplicar Bias (ya resuelto por _load_dataset para 'A')
        -> generar entradas (backtest.find_entries, T1+C fijos)
        -> ejecutar Gestión (MANAGEMENT_LAYERS[...], V3-A únicamente)
        -> calcular métricas canónicas (backtest.metrics/compute_core_metrics)
        -> aplicar gate canónico (research.gate_check)
        -> construir ExperimentResult
        -> return

    Sin ninguna decisión de "ganador", sin interpretación científica —
    eso es responsabilidad del Agente/Framework (ver diseño de Fase 0),
    no de este módulo.
    """
    validate_contract(experiment)
    contract_hash = compute_contract_hash(experiment)

    asset = experiment["assets"][0]
    (period_role, period_year), = experiment["years"].items()
    bias_name = experiment["bias"]["name"]
    trigger_name = experiment["trigger"]["name"]
    entry_name = experiment["entry"]["name"]
    session_name = experiment["session"]
    management_name = experiment["management"]["name"]

    df_full = _load_dataset(asset, period_year)

    cfg = backtest.Config(
        atr_mult=experiment["atr_mult"],
        atr_period=experiment.get("atr_period", 14),
        max_hold=experiment["max_hold"],
        risk=experiment["risk"],
        sessions=SESSION_WINDOWS[session_name],
    )

    # Bias ya resuelto por _load_dataset para el candidato "A" — MVP no
    # soporta otro Bias (validate_contract ya lo garantiza).
    frame = research.to_backtest_frame(df_full, df_full["bias_A"], cfg)

    # Trigger+Entry: backtest.find_entries está hardcodeado a
    # T1_ema_cross+C_market_close — exactamente lo que este MVP soporta
    # (validate_contract ya lo garantiza, sin adaptador nuevo necesario).
    entries = backtest.find_entries(frame, cfg)

    management_fn = MANAGEMENT_LAYERS[management_name]
    trades = management_fn(frame, entries, cfg, experiment["cost_per_trade"])

    m = backtest.metrics(trades, cfg)
    gate_pass = research.gate_check(m)

    return ExperimentResult.from_metrics(
        experiment_name=experiment["name"], asset=asset, period=period_year,
        period_role=period_role, bias=bias_name, trigger=trigger_name, entry=entry_name,
        session=session_name, management=management_name,
        n_entries=len(entries), n_trades=len(trades), metrics=m,
        gate_pass=gate_pass, contract_hash=contract_hash,
    )
