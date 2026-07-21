"""
research/tests/test_layers.py — Suite de paridad Tarea 5 (plan de unificación
del motor de señales). Ejecutar:  python -m research.tests.test_layers
(o con pytest). Sigue el patrón de dc_v1/tests/test_dc_v1.py.

Verifica que los 3 candidatos baseline ya portados (bias_A_ema200_neutral,
trigger_A_sweep_bos, entry_A_pullback_50) reproducen exactamente el
comportamiento del motor legacy (bot.py/backtest.py), y que el contrato de
la Tarea 1 (tipos de retorno, inmutabilidad, registros) se cumple. No
modifica bot.py/backtest.py ni los conecta con research — solo valida.

Import de bot.py: dispara `logging.basicConfig(FileHandler("smc_bot.log"))`
como efecto secundario del módulo. Se limpia una vez, a nivel de módulo,
justo después del import — ninguna de las funciones que se usan acá
(detect_liquidity_sweep, detect_bos, htf_bias) escribe al log por sí misma.
"""
from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import pandas as pd

import bot
import backtest
from research.layers import (
    BIAS_LAYERS,
    TRIGGER_LAYERS,
    ENTRY_LAYERS,
    TriggerEvent,
    EntrySignal,
    bias_A_ema200_neutral,
    trigger_A_sweep_bos,
    entry_A_pullback_50,
)

Path("smc_bot.log").unlink(missing_ok=True)


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


# --------------------------------------------------------------------------- #
# Datos sintéticos (semilla fija, mismos parámetros ya usados y verificados   #
# manualmente en las Tareas 2-4).                                             #
# --------------------------------------------------------------------------- #
def make_synthetic_4h(n=260, seed=11):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=n, freq="4h", tz="UTC")
    ret = rng.normal(0, 0.01, n)
    close = 20000 * np.exp(np.cumsum(ret))
    return pd.DataFrame({
        "open": close, "high": close * 1.001, "low": close * 0.999, "close": close,
        "volume": rng.uniform(10, 100, n),
    }, index=idx)


def make_synthetic_1h(n=3000, seed=42):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=n, freq="1h", tz="UTC")
    ret = rng.normal(0, 0.006, n)
    close = 20000 * np.exp(np.cumsum(ret))
    open_ = np.empty(n)
    open_[0] = close[0]
    open_[1:] = close[:-1]
    spread = np.abs(rng.normal(0, 0.003, n)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    return pd.DataFrame({
        "open": open_, "high": high, "low": low, "close": close,
        "volume": rng.uniform(10, 100, n),
    }, index=idx)


# --------------------------------------------------------------------------- #
# Registro y contrato (ajustes pedidos: registros poblados + tipos)           #
# --------------------------------------------------------------------------- #
def test_registries_populated():
    ok = (
        BIAS_LAYERS.get("A_ema200_neutral") is bias_A_ema200_neutral
        and TRIGGER_LAYERS.get("A_sweep_bos") is trigger_A_sweep_bos
        and ENTRY_LAYERS.get("A_pullback_50") is entry_A_pullback_50
    )
    return _p("los 3 candidatos baseline están registrados en BIAS/TRIGGER/ENTRY_LAYERS", ok)


def test_contract_return_types():
    df4h = make_synthetic_4h()
    df1h = make_synthetic_1h(n=500)

    bias = bias_A_ema200_neutral(df4h)
    events = trigger_A_sweep_bos(df1h)
    ok_bias = isinstance(bias, pd.Series)
    ok_trigger = isinstance(events, list) and all(isinstance(e, TriggerEvent) for e in events)

    ok_entry = True
    if events:
        signal = entry_A_pullback_50(df1h, events[0])
        ok_entry = isinstance(signal, EntrySignal) and isinstance(signal.price, float)

    ok = ok_bias and ok_trigger and ok_entry
    return _p("BiasFn->Series, TriggerFn->list[TriggerEvent], EntryFn->EntrySignal", ok)


def test_trigger_event_immutable():
    ev = TriggerEvent(entry_idx=0, direction="long", meta={})
    try:
        ev.entry_idx = 1
        ok = False
    except FrozenInstanceError:
        ok = True
    return _p("TriggerEvent es frozen (rechaza mutación)", ok)


def test_entry_signal_immutable():
    sig = EntrySignal(price=1.0)
    try:
        sig.price = 2.0
        ok = False
    except FrozenInstanceError:
        ok = True
    return _p("EntrySignal es frozen (rechaza mutación)", ok)


# --------------------------------------------------------------------------- #
# Paridad Capa 1 — bias_A_ema200_neutral vs backtest.py/bot.py real           #
# --------------------------------------------------------------------------- #
def test_bias_matches_legacy():
    df4h = make_synthetic_4h()
    new_bias = bias_A_ema200_neutral(df4h)

    cfg_bt = backtest.Config()
    feats = backtest.build_features(df4h.copy(), df4h, cfg_bt)
    legacy_bias = feats["bias"].reindex(df4h.index).map(
        {"long": 1, "short": -1, "neutral": 0}
    ).astype("int8")

    rows_match = (new_bias == legacy_bias).all()

    cfg_bot = bot.Config()
    last_str = bot.htf_bias(df4h, cfg_bot)
    last_map = {"long": 1, "short": -1, "neutral": 0}
    last_matches = last_map[last_str] == int(new_bias.iloc[-1])

    ok = bool(rows_match) and last_matches
    return _p("bias_A_ema200_neutral == backtest.py fila a fila y == bot.py en el último valor", ok)


# --------------------------------------------------------------------------- #
# Paridad Capa 2 — trigger_A_sweep_bos vs bot.py real, sin máquina de estados #
# --------------------------------------------------------------------------- #
def test_trigger_matches_legacy():
    df1h = make_synthetic_1h()
    cfg = bot.Config()

    legacy = []
    for i in range(cfg.swing_lookback, len(df1h)):
        sweep = bot.detect_liquidity_sweep(df1h.iloc[:i + 1], cfg)
        if sweep is None:
            continue
        bos = bot.detect_bos(df1h, i, sweep["type"], cfg)
        if bos is None:
            continue
        legacy.append((bos["bos_idx"], sweep["type"], sweep["sweep_level"], bos["bos_level"]))

    new_events = trigger_A_sweep_bos(df1h)
    new = [(e.entry_idx, e.direction, e.meta["sweep_level"], e.meta["bos_level"]) for e in new_events]

    ok = legacy == new and len(legacy) > 0  # exigir >0 para que la prueba no sea trivialmente vacía
    return _p(f"trigger_A_sweep_bos == detección real de bot.py, evento a evento ({len(legacy)} eventos)", ok)


# --------------------------------------------------------------------------- #
# Paridad Capa 3 — entry_A_pullback_50.                                       #
#                                                                              #
# LIMITACIÓN CONOCIDA (documentada, no automatizada vía exec de bot.py):      #
# la fórmula de entrada vive inline en bot.py::run_bot ([bot.py:340-351]),    #
# mezclada con SL/TP/sizing — no existe como función aislada e importable.    #
# La Tarea 4 validó la equivalencia inicial ejecutando el bloque REAL de      #
# bot.py vía exec (ver commit ec861a8). Para este test committeado, de vida  #
# larga, se prefiere una transcripción documentada de esa misma fórmula en   #
# vez de depender de extracción de código fuente (frágil ante reformateos    #
# de bot.py). Si esa sección de bot.py cambia, esta referencia debe          #
# actualizarse a mano — no hay sincronización automática.                    #
#                                                                              #
# RESOLUCIÓN PREVISTA (Tarea 6): cuando bot.py se migre a consumir            #
# research.layers, la fórmula de entrada deja de vivir inline en run_bot —   #
# en ese momento _reference_entry_formula debe eliminarse y este test debe   #
# comparar directamente contra la implementación compartida (la única que    #
# quedará, ya no habrá una "copia" separada que mantener sincronizada).       #
# --------------------------------------------------------------------------- #
def _reference_entry_formula(direction, sweep_lvl, bos_lvl, pullback_pct):
    """Transcripción documentada de bot.py:340-351 (solo la parte de `entry`)."""
    if direction == "long":
        rng = bos_lvl - sweep_lvl
        return bos_lvl - rng * pullback_pct
    else:
        rng = sweep_lvl - bos_lvl
        return bos_lvl + rng * pullback_pct


def test_entry_matches_reference_formula():
    df1h = make_synthetic_1h()
    events = trigger_A_sweep_bos(df1h)
    assert events, "se necesitan eventos reales para esta prueba"

    price_ok = True
    direction_key_ok = True
    for ev in events:
        sweep_lvl = ev.meta["swing_low"] if ev.direction == "long" else ev.meta["swing_high"]
        expected = _reference_entry_formula(ev.direction, sweep_lvl, ev.meta["bos_level"], 0.50)
        got = entry_A_pullback_50(df1h, ev).price
        if got != expected:
            price_ok = False

        if ev.direction == "long" and "swing_low" not in ev.meta:
            direction_key_ok = False
        if ev.direction == "short" and "swing_high" not in ev.meta:
            direction_key_ok = False

    ok = price_ok and direction_key_ok
    return _p(f"entry_A_pullback_50 == fórmula de referencia + dirección->clave correcta ({len(events)} eventos)", ok)


ALL_TESTS = [
    test_registries_populated,
    test_contract_return_types,
    test_trigger_event_immutable,
    test_entry_signal_immutable,
    test_bias_matches_legacy,
    test_trigger_matches_legacy,
    test_entry_matches_reference_formula,
]


def main():
    print("research/layers — suite de paridad (Tarea 5)\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
