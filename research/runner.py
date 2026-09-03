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
  - Gestión "V3-A" o "Raw" (Fase 5) — ambas vía `MANAGEMENT_LAYERS`,
    resuelto siempre por nombre desde el registro, NUNCA `if management
    == ...`/`elif` (verificado por test). Ambas delegan a
    `backtest.run_config` (orquestación) + `research.EXIT_CONFIGS`/
    `research.simulate_v3` (motor de simulación, ubicación CANÓNICA desde
    Fase 4/C2 — `research/simulate.py`) SIN MODIFICARLOS ni
    reimplementarlos — "Raw" NO es una función de simulación nueva, es
    `research.EXIT_CONFIGS["Raw"]` (`be`/`activation`=inf) sobre el MISMO
    `simulate_v3` (verificado por test de inspección de código y por
    identidad de objeto).
  - Gates: SOLO los canónicos de `research.gate_check` — el contrato debe
    declararlos explícitamente y deben coincidir EXACTO con los umbrales
    oficiales; el runner nunca acepta un gate distinto ("no modificar
    silenciosamente los gates", Parte 3 del diseño de Fase 0).

NO soportado todavía (fuera de alcance de esta fase, explícitamente):
  - Ningún mecanismo de Gestión más allá de V3-A/Raw (E1/TP fijo/V3A+TP
    quedan fuera — todos requieren una función de simulación propia,
    distinta de `simulate_v3`, no evaluada en esta fase), múltiples
    activos/años por corrida, orquestación train->validate->blind,
    selección de "ganador", optimización de parámetros, generación de
    hipótesis, cualquier interfaz autónoma.
  - Ningún campo `is_winner` ni lógica de interpretación científica en
    ningún punto de este módulo.

DEUDA TÉCNICA RESUELTA EN FASE 5 (2026-09-02): `MANAGEMENT_LAYERS`
ampliado a `{"V3-A": ..., "Raw": ...}`, ambos construidos por la MISMA
fábrica (`_make_run_config_management`), sin ningún `if`/`elif` de
selección manual — confirma en código que la interfaz común (`ManagementFn
= Callable[[frame, entries, cfg], DataFrame]`) ya alcanza para un segundo
mecanismo sin tocar el runner más que agregar una entrada al registro.
`research.EXIT_CONFIGS` ganó la entrada canónica `"Raw"` (`be`/
`activation`=inf, `distance`=0.0 — copiado exacto desde `scripts/
gestion_espacio6_raw_campaign.py::EXIT_CFG_RAW`, nunca antes registrado
centralmente). Decisión de interfaz: `cost_per_trade` SALIÓ de
`ManagementFn` (antes `_run_v3a(frame, entries, cfg, cost_per_trade)`) —
es un parámetro de la CAPA DE EJECUCIÓN (aplica igual sin importar qué
mecanismo corra), no una propiedad del mecanismo de Gestión en sí; el
parcheo de `backtest.COST_PER_TRADE` ahora vive UNA sola vez en `run()`,
alrededor de la llamada a `management_fn(...)`, evitando que cada
mecanismo nuevo deba repetir el mismo `try/finally`. `TradeRecord`
(declarado en Fase 1) ahora tiene consumidor real —
`run(experiment, include_trades=True)` devuelve `(ExperimentResult,
list[TradeRecord])`, construidos desde el MISMO `trades` DataFrame que ya
alimentó las métricas (nunca una fuente de cálculo distinta) — el
`include_trades=False` por defecto preserva 100% de compatibilidad con
todo llamador existente.

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
from typing import Callable

sys.path.insert(0, ".")

import pandas as pd

import backtest
import research
from research.schema import ExperimentResult, TradeRecord, compute_contract_hash


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


ManagementFn = Callable[[pd.DataFrame, list, "backtest.Config"], pd.DataFrame]
"""Interfaz común de un mecanismo de Gestión: (frame, entries, cfg) ->
DataFrame de trades. NO incluye `cost_per_trade` — decisión de diseño
explícita de Fase 5 (ver nota "COST_PER_TRADE: capa de ejecución, no de
Gestión" más abajo). Todo mecanismo que, como V3-A y Raw, reutilice
`backtest.run_config`/`research.simulate_v3` sin una función de
simulación propia encaja en esta interfaz vía `_make_run_config_management`
— un mecanismo que sí necesite una función de simulación distinta (fuera
de alcance de esta fase: E1/V3A+TP) implementaría esta misma interfaz con
su propio cuerpo, sin cambiarla."""


# Nombre de mecanismo (MANAGEMENT_LAYERS) -> clave en research.EXIT_CONFIGS.
# ÚNICA fuente de la relación management.name <-> exit_cfg — agregar un
# mecanismo nuevo que reutilice simulate_v3 sin función propia es agregar
# una entrada acá, nunca un `if`/`elif` en el runner.
_MANAGEMENT_EXIT_CONFIG_KEYS: dict[str, str] = {
    "V3-A": "V3-A (1R/2R/1R)",
    "Raw": "Raw",
}


def _make_run_config_management(exit_config_key: str) -> ManagementFn:
    """Fábrica: produce una función de Gestión que delega a
    `backtest.run_config`/`research.simulate_v3` SIN MODIFICARLOS ni
    reimplementarlos, usando exactamente `research.EXIT_CONFIGS
    [exit_config_key]` como `exit_cfg` — la interfaz común real para
    cualquier mecanismo que, como V3-A y Raw, no necesite una función de
    simulación propia. `exit_cfg` se resuelve UNA vez (al construir la
    función, no en cada llamada) para no repetir el lookup — es un dict
    inmutable en la práctica (nunca mutado en ningún punto del código
    auditado en Fase 4/5)."""
    exit_cfg = research.EXIT_CONFIGS[exit_config_key]

    def _run(frame, entries, cfg):
        return backtest.run_config(frame, entries, exit_cfg, cfg)

    return _run


MANAGEMENT_LAYERS: dict[str, ManagementFn] = {
    name: _make_run_config_management(key) for name, key in _MANAGEMENT_EXIT_CONFIG_KEYS.items()
}

# Parámetros canónicos por mecanismo (research.EXIT_CONFIGS) — si el
# contrato declara management.params, DEBE coincidir exacto con el de su
# management.name (no se acepta una variante paramétrica en este MVP; eso
# es "crear un mecanismo nuevo de Gestión", explícitamente fuera de
# alcance).
_MANAGEMENT_PARAMS: dict[str, dict] = {
    name: dict(research.EXIT_CONFIGS[key]) for name, key in _MANAGEMENT_EXIT_CONFIG_KEYS.items()
}


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
    expected_mgmt_params = _MANAGEMENT_PARAMS[mgmt_name]
    if mgmt_params and dict(mgmt_params) != expected_mgmt_params:
        raise ContractError(
            f"management.params debe coincidir exacto con {mgmt_name} ({expected_mgmt_params}) "
            f"o ausente — recibido: {mgmt_params!r}. Variantes paramétricas de Gestión están "
            f"fuera de alcance de este MVP (eso es 'crear un mecanismo nuevo de Gestión')."
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


def _build_trade_records(trades: pd.DataFrame, entries: list[dict], frame: pd.DataFrame,
                          mechanism: str) -> list[TradeRecord]:
    """Construye la representación canónica (research.TradeRecord) del
    MISMO `trades` DataFrame que ya alimentó `backtest.metrics(...)` —
    transformación pura, posterior, de solo lectura: no recalcula pnl_r,
    no vuelve a simular nada, no puede divergir de las métricas ya
    calculadas porque parte exactamente de los mismos datos.

    Mapeo campo por campo (documentado, ninguno fabricado):
      - entry_time/exit_time/direction/reason/pnl_r/duration_h: PRODUCIDOS
        DIRECTAMENTE por research.simulate_v3 (ver TradeRecord.from_raw).
      - exit_price: NO DISPONIBLE — ni V3-A ni Raw lo producen (ambos usan
        research.simulate_v3, que no lo incluye en su dict de retorno,
        verificado en Fase 4) — queda None, nunca fabricado.
      - entry_price: DERIVADO DETERMINÍSTICAMENTE — no lo produce
        simulate_v3, pero SÍ está disponible en `entries` (la lista que ya
        generó backtest.find_entries), emparejado por `entry_time` contra
        el índice del `frame` — mismo join, de solo lectura, ya usado en
        los diagnósticos de Espacio 6 (Raw/E2). Si un trade no tiene
        entrada emparejable (no debería ocurrir, entries y trades vienen
        de la misma corrida), queda None en vez de fallar.
      - mechanism: el nombre de management ya conocido por el llamador
        (no producido por simulate_v3, es contexto de la ejecución, no un
        dato fabricado).
    """
    entry_by_time = {frame.index[e["entry_idx"]]: e for e in entries}
    records = []
    for _, row in trades.iterrows():
        raw = row.to_dict()
        ent = entry_by_time.get(row["entry_time"])
        entry_price = ent["entry"] if ent is not None else None
        records.append(TradeRecord.from_raw(raw, mechanism=mechanism, entry_price=entry_price))
    return records


def run(experiment: dict, include_trades: bool = False):
    """Punto de entrada único del MVP. Flujo determinista y fijo:

        validate_contract
        -> resolver componentes (ya validados por nombre)
        -> cargar dataset (activo, año)
        -> aplicar Bias (ya resuelto por _load_dataset para 'A')
        -> generar entradas (backtest.find_entries, T1+C fijos)
        -> resolver Gestión (MANAGEMENT_LAYERS[...] — V3-A o Raw)
        -> ejecutar el mecanismo
        -> calcular métricas canónicas (backtest.metrics/compute_core_metrics)
        -> aplicar gate canónico (research.gate_check)
        -> construir ExperimentResult (+ TradeRecords si include_trades)
        -> return

    Sin ninguna decisión de "ganador", sin interpretación científica —
    eso es responsabilidad del Agente/Framework (ver diseño de Fase 0),
    no de este módulo. Sin selección manual por nombre de mecanismo
    (`if management == ...`) en ningún punto — la resolución es siempre
    vía `MANAGEMENT_LAYERS[management_name]`.

    `include_trades` (Fase 5, default False — NO rompe ningún llamador
    existente): si es True, devuelve `(ExperimentResult, list[TradeRecord])`
    en vez de solo `ExperimentResult`. Los TradeRecord se construyen desde
    el MISMO `trades` DataFrame que ya calculó las métricas — nunca una
    fuente de cálculo distinta (ver `_build_trade_records`).
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

    # Resolución de Gestión — SIEMPRE vía el registro, nunca if/elif por
    # nombre. COST_PER_TRADE se parchea acá (capa de EJECUCIÓN, no de
    # Gestión — decisión de diseño de Fase 5, ver ManagementFn arriba):
    # es un parámetro del contrato que aplica IGUAL sin importar qué
    # mecanismo se ejecute, no una propiedad de "cuál mecanismo" —
    # centralizarlo acá evita que cada mecanismo nuevo (V3-A, Raw, y
    # cualquiera futuro que reutilice simulate_v3) tenga que repetir el
    # mismo try/finally de parcheo.
    management_fn = MANAGEMENT_LAYERS[management_name]
    orig_cost = backtest.COST_PER_TRADE
    backtest.COST_PER_TRADE = experiment["cost_per_trade"]
    try:
        trades = management_fn(frame, entries, cfg)
    finally:
        backtest.COST_PER_TRADE = orig_cost

    m = backtest.metrics(trades, cfg)
    gate_pass = research.gate_check(m)

    result = ExperimentResult.from_metrics(
        experiment_name=experiment["name"], asset=asset, period=period_year,
        period_role=period_role, bias=bias_name, trigger=trigger_name, entry=entry_name,
        session=session_name, management=management_name,
        n_entries=len(entries), n_trades=len(trades), metrics=m,
        gate_pass=gate_pass, contract_hash=contract_hash,
    )
    if not include_trades:
        return result
    trade_records = _build_trade_records(trades, entries, frame, management_name)
    return result, trade_records
