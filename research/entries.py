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
def _raw_events(frame: pd.DataFrame, trigger_name: str, cfg) -> list:
    """Genera los eventos crudos de Capa 2 para `trigger_name`. Solo
    T1_ema_cross consume kwargs derivados de `cfg` (atr_period/atr_mult) —
    los demás candidatos de TRIGGER_LAYERS usan sus propios defaults de
    estructura de velas/sweep/rango, sin depender de `cfg` en absoluto."""
    if trigger_name == "T1_ema_cross":
        return research.TRIGGER_LAYERS[trigger_name](
            frame, atr_period=cfg.atr_period, atr_mult=cfg.atr_mult,
        )
    if trigger_name in research.TRIGGER_LAYERS:
        return research.TRIGGER_LAYERS[trigger_name](frame)
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
def find_entries(frame: pd.DataFrame, cfg, trigger_name: str, entry_name: str) -> list[dict]:
    """Generalización de `backtest.find_entries`/`scripts.trigger_campaign.
    find_entries_for_trigger`, parametrizada por Trigger Y Entry (el
    precedente de `scripts/` solo parametrizaba Trigger). Para
    `trigger_name="T1_ema_cross"`, `entry_name="C_market_close"` sobre el
    mismo frame, produce EXACTAMENTE las mismas entradas que
    `backtest.find_entries` — ver `research/tests/test_entries_equivalence.py`.

    `entry_name` debe existir en `research.ENTRY_LAYERS`; si requiere campos
    de `event.meta` que `trigger_name` no produce (ver
    `ENTRY_META_REQUIREMENTS`), este llamador debería haber sido rechazado
    antes por `research.runner.validate_contract` — acá no se valida esa
    compatibilidad de nuevo (evitar la duplicación de esa regla en dos
    lugares); un `KeyError` dentro de `entry_fn(...)` en ese caso indica que
    algo llamó a esta función sin pasar por `validate_contract` primero.
    """
    raw_events = _raw_events(frame, trigger_name, cfg)
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
