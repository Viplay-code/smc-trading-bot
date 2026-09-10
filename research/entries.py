"""research/entries.py — Automatización experimental, Componente 1
(generalización de Trigger/Entry, 2026-09-03).

OBJETIVO (alcance autorizado para este componente, ver auditoría previa):
eliminar la dependencia estructural de `research/runner.py` respecto a
`T1_ema_cross`/`C_market_close` — la "deuda técnica que permanece" documentada
en el módulo docstring de `research/runner.py` desde Fase 4 ("backtest.
find_entries está hardcodeado a T1_ema_cross+C_market_close — no se
generalizó, explícitamente fuera de alcance [de esa fase]").

PATRÓN: EXTRAER -> PRESERVAR -> VALIDAR (mismo usado en Fases 3/4 sobre
`research/data.py`/`research/simulate.py`) — no una reescritura libre.

Precedente ya existente y probado en el repo:
`scripts/trigger_campaign.py::find_entries_for_trigger` YA es una versión
parametrizada de `backtest.py::find_entries` — dispatch de Capa 2 por nombre
de Trigger en vez de tener "T1_ema_cross" fijo adentro, con equivalencia
exacta ya demostrada contra `backtest.find_entries` (`research/tests/
test_trigger_campaign.py::test_find_entries_for_trigger_t1_matches_
backtest_find_entries`). Esta función ES esa misma lógica, escrita de nuevo
y aislada acá (NO se modifica `scripts/trigger_campaign.py` — mismo criterio
de no tocar un script legacy en uso, aunque acá no exista una advertencia
explícita de "no tocar" como la de `bias_campaign.py::apply_bias`; se trata
igual por disciplina), con UNA generalización adicional respecto a ese
precedente: allá Entry quedaba fijo en "C_market_close" ("única combinación
válida sin escribir código nuevo", según su propio docstring); acá Entry
también se resuelve por nombre desde `research.ENTRY_LAYERS` — necesario
porque el objetivo explícito de este componente es eliminar la dependencia
de AMBOS nombres, no solo de Trigger.

Filtro de bias/sesión/riesgo degenerado: EXACTO al de `backtest.find_entries`
y al de `find_entries_for_trigger` — no se cambia ninguna fórmula, ningún
orden de evaluación, ningún criterio de descarte. Ver
`research/tests/test_entries_equivalence.py` para la prueba de equivalencia
BEFORE/AFTER exacta (sin tolerancias) contra `backtest.find_entries` sobre
T1_ema_cross+C_market_close, la única combinación que el runner soportaba
antes de este componente.

Compatibilidad estructural Entry<->Trigger (no una regla nueva, documenta lo
que ya está escrito en `research/layers.py`): `entry_A_pullback_50` requiere
`event.meta["bos_level"]` + `swing_low`/`swing_high` — SOLO `trigger_A_sweep_
bos` los produce (`trigger_T1_ema_cross`/`trigger_D_range_breakout`/
`trigger_C_bos_only` producen `meta={}`, ver sus docstrings en
`research/layers.py`). `ENTRY_META_REQUIREMENTS` hace explícita esa
restricción para que `research/runner.py::validate_contract` pueda
rechazarla ANTES de tocar datos (ContractError), en vez de fallar más tarde
con un `KeyError` opaco dentro de `entry_fn(...)`.

PROPAGACIÓN GENÉRICA DE `trigger.params` (Automatización Experimental,
2026-09-10 — extensión autorizada tras la auditoría de readiness de
Donchian, alcance ESTRICTAMENTE limitado a esta capacidad): hasta esta
extensión, `_raw_events` invocaba cualquier Trigger no-T1 sin argumentos
(`TRIGGER_LAYERS[trigger_name](frame)`) — cualquier valor declarado en
`experiment["trigger"]["params"]` era aceptado por `validate_contract`
(que no lo validaba) pero IGNORADO EN SILENCIO. `find_entries`/
`_raw_events` ahora aceptan un `trigger_params: dict` opcional (default
`None` -> `{}`, backward-compatible con todo llamador existente) y lo
propagan como `**trigger_params` a cualquier Trigger que NO sea
`T1_ema_cross` — T1 sigue derivando `atr_period`/`atr_mult` EXCLUSIVAMENTE
de `cfg` (ver docstring de `_raw_events`), sin cambio de ruta. Con
`trigger_params={}` (el valor de TODO contrato ya committeado, incluido el
baseline Donchian N=10 recién congelado), el comportamiento es IDÉNTICO al
de antes de esta extensión — verificado por test de regresión exacto contra
ese artifact. La validación de que las claves de `trigger.params` son
parámetros reales del Trigger declarado (rechazo con `ContractError` de
cualquier clave desconocida, ANTES de tocar datos) vive en
`research.runner.validate_contract`, no acá — mismo patrón ya usado para
`ENTRY_META_REQUIREMENTS` un párrafo arriba: la regla de compatibilidad se
valida una sola vez, en C2, nunca duplicada en la capa de ejecución.
"""
from __future__ import annotations

import pandas as pd

import research


# --------------------------------------------------------------------------- #
# Compatibilidad Entry <-> Trigger — deriva de los docstrings ya vigentes en  #
# research/layers.py (no una regla inventada acá). Un Entry ausente de este   #
# dict no exige ningún Trigger en particular (compatible con cualquiera).    #
# --------------------------------------------------------------------------- #
ENTRY_META_REQUIREMENTS: dict[str, set[str]] = {
    "A_pullback_50": {"A_sweep_bos"},
}


# --------------------------------------------------------------------------- #
# Capa 2 — dispatch de Trigger. Réplica exacta de                            #
# scripts/trigger_campaign.py::_raw_events, extendida a los 2 candidatos de  #
# Trigger que ese script no necesitaba dispatchar (D_range_breakout,         #
# C_bos_only) — ninguno de los dos usa kwargs dependientes de cfg (ver sus   #
# firmas en research/layers.py), mismo criterio ya aplicado ahí a           #
# A_sweep_bos.                                                               #
# --------------------------------------------------------------------------- #
def _raw_events(frame: pd.DataFrame, trigger_name: str, cfg, trigger_params: dict | None = None) -> list:
    """Genera los eventos crudos de Capa 2 para `trigger_name`. `T1_ema_cross`
    sigue consumiendo EXCLUSIVAMENTE los kwargs derivados de `cfg`
    (atr_period/atr_mult) — ruta especial sin cambios (Automatización
    Experimental, propagación de `trigger.params`, 2026-09-10): T1 ya tiene
    una vía canónica para controlar esos dos parámetros (los campos
    `atr_mult`/`atr_period` del propio contrato, vía `cfg`), así que
    `trigger_params` NUNCA se le pasa, ni siquiera si está vacío — evita
    dos rutas distintas para controlar el mismo parámetro. Cualquier OTRO
    candidato de `TRIGGER_LAYERS` recibe `trigger_params` como kwargs
    (`**trigger_params`) — con `trigger_params={}` (el default, y el valor
    de TODO contrato ya committeado hasta esta extensión), el comportamiento
    es IDÉNTICO al de antes de este cambio (`TRIGGER_LAYERS[trigger_name]
    (frame)`), verificado por test de regresión."""
    trigger_params = trigger_params or {}
    if trigger_name == "T1_ema_cross":
        return research.TRIGGER_LAYERS[trigger_name](
            frame, atr_period=cfg.atr_period, atr_mult=cfg.atr_mult,
        )
    if trigger_name in research.TRIGGER_LAYERS:
        return research.TRIGGER_LAYERS[trigger_name](frame, **trigger_params)
    raise ValueError(
        f"trigger de Capa 2 desconocido: {trigger_name!r} "
        f"(esperado uno de {list(research.TRIGGER_LAYERS)})"
    )


# --------------------------------------------------------------------------- #
# Adaptador genérico — reemplaza backtest.find_entries (T1_ema_cross +       #
# C_market_close hardcodeados) por una versión parametrizada por nombre en   #
# AMBAS capas. Filtro de bias/sesión/riesgo degenerado EXACTO al original —  #
# no se reordena, no se relaja, no se agrega ningún chequeo nuevo.          #
# --------------------------------------------------------------------------- #
def find_entries(
    frame: pd.DataFrame, cfg, trigger_name: str, entry_name: str,
    trigger_params: dict | None = None,
) -> list[dict]:
    """Generalización de `backtest.find_entries`/`scripts.trigger_campaign.
    find_entries_for_trigger`, parametrizada por Trigger Y Entry (el
    precedente de `scripts/` solo parametrizaba Trigger). Para
    `trigger_name="T1_ema_cross"`, `entry_name="C_market_close"` sobre el
    mismo frame, produce EXACTAMENTE las mismas entradas que
    `backtest.find_entries` — ver `research/tests/test_entries_equivalence.py`.

    `trigger_params` (Automatización Experimental, propagación genérica,
    2026-09-10): kwargs adicionales pasados al Trigger vía `_raw_events`
    (ver su docstring para la ruta especial de T1_ema_cross, que nunca los
    recibe). Default `None` -> `{}`, backward-compatible con todo llamador
    existente que no pase este argumento (posicional o no) — con
    `trigger_params={}`/omitido, el comportamiento es IDÉNTICO al de antes
    de esta extensión. Las claves de `trigger_params` deben ser parámetros
    reales del Trigger declarado — esa validación vive en
    `research.runner.validate_contract` (ANTES de tocar datos), no acá,
    mismo criterio ya aplicado a la compatibilidad Entry<->Trigger un
    párrafo más abajo.

    `entry_name` debe existir en `research.ENTRY_LAYERS`; si requiere campos
    de `event.meta` que `trigger_name` no produce (ver
    `ENTRY_META_REQUIREMENTS`), este llamador debería haber sido rechazado
    antes por `research.runner.validate_contract` — acá no se valida esa
    compatibilidad de nuevo (evitar la duplicación de esa regla en dos
    lugares); un `KeyError` dentro de `entry_fn(...)` en ese caso indica que
    algo llamó a esta función sin pasar por `validate_contract` primero.
    """
    raw_events = _raw_events(frame, trigger_name, cfg, trigger_params)
    entry_fn = research.ENTRY_LAYERS[entry_name]

    entries: list[dict] = []
    for ev in raw_events:
        row = frame.iloc[ev.entry_idx]
        if not row["in_session"] or row["bias"] != ev.direction:
            continue

        entry = entry_fn(frame, ev).price
        atr = row["atr"]
        if ev.direction == "long":
            sl = min(row["low"], entry - cfg.atr_mult * atr)
        else:
            sl = max(row["high"], entry + cfg.atr_mult * atr)
        risk_pts = abs(entry - sl)
        if risk_pts < 1e-9:
            continue

        entries.append({
            "entry_idx": ev.entry_idx, "direction": ev.direction,
            "entry": entry, "sl0": sl, "risk_pts": risk_pts,
        })
    return entries
